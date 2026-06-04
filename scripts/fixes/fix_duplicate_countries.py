#!/usr/bin/env python3
"""Detect and collapse near-duplicate country variants across the metadata stack.

The country filter dropdown in the search UI sometimes shows the same country
multiple times. The dropdown is built from a Qdrant facet over the
``map_country`` payload, which aggregates by exact string match. Tiny surface
differences (trailing whitespace, casing, NBSP, trailing punctuation) therefore
create separate buckets and look like duplicates in the UI.

This script:

  1. Scans every place ``map_country`` lives:
       PostgreSQL:
         - docs_<source>.map_country                       (text column)
         - docs_<source>.src_doc_raw_metadata->>'Country'  (JSONB string)
       Qdrant:
         - documents_<source>.map_country  (payload string)
         - chunks_<source>.map_country     (payload string)
  2. Tokenises each value on ``'; '`` to match the production splitter in
     ``ui/backend/utils/facet_helpers.py``.
  3. Groups tokens by a canonical key:
         NFC-normalise, collapse internal whitespace, strip, casefold,
         strip trailing ``.,;``. Diacritics are preserved on purpose so
         legitimately distinct values (e.g. ``Türkiye`` vs ``Turkiye``)
         are not silently merged.
  4. For each cluster with >= ``--min-group-size`` distinct surface forms,
     picks a winning form (most PG docs win; non-ASCII tie-break preserves
     diacritics; final tie-break alphabetical).
  5. Rewrites each variant to the winner everywhere it appears, also
     collapsing repeated tokens within a single value. Idempotent.

In addition to the auto-discovered trivial variants, the script applies a
small ``SYNONYM_RENAMES`` table of explicit semantic renames that were
agreed upon for this dataset (e.g. ``Tanzania`` ->
``United Republic of Tanzania``, bare ``Congo`` -> ``Republic of the Congo``).
These cannot be inferred from canonical-key normalisation and have to be
listed by hand — see the table near the top of this module. New entries
should be added only with explicit user approval. Pass ``--skip-synonyms``
to apply only the auto-detected trivial-variant cleanup.

For one-off single-pair renames where the canonical choice is dataset-
agnostic and reviewable on its own (e.g. ``Syria`` ->
``Syrian Arab Republic``), prefer the dedicated single-script pattern in
``fix_syria_country_name.py``.

Defaults to dry-run — nothing is written without ``--apply``.

Usage:
    # Dry-run (default — no writes):
    python scripts/fixes/fix_duplicate_countries.py --data-source wfp

    # Apply for real:
    python scripts/fixes/fix_duplicate_countries.py --data-source wfp --apply

    # Be more conservative — only touch clusters with 3+ variants:
    python scripts/fixes/fix_duplicate_countries.py --data-source wfp \\
        --min-group-size 3

    # Trivial-variant cleanup only, skip the explicit synonym table:
    python scripts/fixes/fix_duplicate_countries.py --data-source wfp \\
        --skip-synonyms
"""

import argparse
import json
import logging
import os
import re
import sys
import time
import unicodedata
from collections import Counter
from typing import Any, Dict, List, Mapping, Optional, Tuple

from dotenv import load_dotenv
from qdrant_client import QdrantClient

# Defensive logging setup — matches fix_duplicate_summaries.py.
#
# pipeline.db and its transitive imports can initialise the root logger
# during import. If that happens before our basicConfig() runs, ours
# becomes a no-op and every log line in this script gets silently dropped
# (manifests as "no terminal output, exit 0" on environments where the
# import order differs from our dev machine — e.g. the prod VM).
#
# We defend by wiping any pre-existing root handlers, forcing
# basicConfig, and routing to stdout + a log file so the report is never
# lost regardless of how stderr is being captured.
_LOG_DIR = os.path.join(os.path.dirname(__file__), "../../logs")
os.makedirs(_LOG_DIR, exist_ok=True)
_LOG_FILE = os.path.join(_LOG_DIR, "duplicate_country_fix.log")

for _handler in logging.root.handlers[:]:
    logging.root.removeHandler(_handler)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(_LOG_FILE), logging.StreamHandler(sys.stdout)],
    force=True,
)
logger = logging.getLogger(__name__)

SEPARATOR = "; "
MAX_PER_CLUSTER_LOG = 8
MAX_ROW_PREVIEW = 5

# Explicit semantic synonym renames — each pair is a deliberate human
# decision about which surface form is canonical for this dataset.
# Unlike the auto-discovered trivial variants (whitespace, casing), these
# cannot be inferred by canonical_key normalisation and must be listed
# by hand. New entries should only be added with explicit user approval
# — see fix_syria_country_name.py for the dedicated single-pair pattern.
# Disable with ``--skip-synonyms`` to apply only the auto-detected
# trivial-variant cleanup.
SYNONYM_RENAMES: Dict[str, str] = {
    "Tanzania": "United Republic of Tanzania",
    "Kyrgyzstan": "Kyrgyz Republic",
    # Per-dataset disambiguation: bare "Congo" refers to the Republic of
    # the Congo (Brazzaville), not the DRC.
    "Congo": "Republic of the Congo",
    # Missing "the" — refers to the DRC (Kinshasa).
    "Democratic Republic of Congo": "Democratic Republic of the Congo",
    # Typo fixes confirmed against the source data:
    "Burkina": "Burkina Faso",
    "Nicarague": "Nicaragua",
    # 'Zambabwe' appears in a row alongside 'Zambia', so the typo refers
    # to Zimbabwe (the other country), not a duplicate of Zambia.
    "Zambabwe": "Zimbabwe",
}


# ---------------------------------------------------------------------------
# Pure helpers — easy to unit-test, no I/O.
# ---------------------------------------------------------------------------


def canonical_key(token: str) -> str:
    """Return the equivalence-class key for a country token.

    Two surface forms with the same canonical key are treated as the same
    country for clustering purposes. NFC-normalises, collapses internal
    whitespace, strips, removes trailing ``.,;``, then casefolds. Diacritics
    are preserved — see module docstring.
    """
    if not isinstance(token, str):
        return ""
    normalised = unicodedata.normalize("NFC", token)
    collapsed = re.sub(r"\s+", " ", normalised).strip()
    trimmed = collapsed.strip(".,;")
    return trimmed.casefold()


def tokenize_country_value(value: Any) -> List[str]:
    """Split a country field value into individual tokens.

    Mirrors ``_accumulate_raw_value`` in ui/backend/utils/facet_helpers.py:

    - Multi-value strings (``'; '`` separator present) split into parts
      and each part is ``.strip()``-ed — same as production.
    - Single-value strings are returned **verbatim, unstripped**. Production
      bucketizes single values as-is, so ``"Bolivia "`` and ``"Bolivia"``
      are two distinct dropdown entries and must remain distinct tokens
      here so the clustering logic can detect them.
    - Lists are returned with each element ``.strip()``-ed (Qdrant list
      payloads — uncommon, but supported).
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not isinstance(value, str):
        return []
    if SEPARATOR in value:
        return [p.strip() for p in value.split(SEPARATOR) if p.strip()]
    return [value] if value else []


def _pick_winner(variants: List[str], counts: Mapping[str, int]) -> str:
    """Choose the canonical surface form from a cluster of variants.

    Highest doc count wins. Tie-break: prefer a form containing any
    non-ASCII character (so ``Türkiye`` beats ``Turkiye`` at equal count);
    final tie-break alphabetical.
    """

    def sort_key(form: str) -> Tuple[int, int, str]:
        has_non_ascii = any(ord(c) > 127 for c in form)
        return (-counts.get(form, 0), 0 if has_non_ascii else 1, form)

    return sorted(variants, key=sort_key)[0]


def build_rewrite_map(
    token_counts: Mapping[str, int], min_group_size: int = 2
) -> Dict[str, str]:
    """Cluster ``token_counts`` keys by canonical key and emit rewrites.

    Returns ``{variant: winner}`` for every cluster with ``>= min_group_size``
    distinct surface forms. The winner itself is never included as an
    identity entry — callers can treat absence as "leave unchanged".

    Only auto-discovered trivial variants are returned. Semantic synonym
    renames (where the two surface forms have different canonical keys)
    live in ``SYNONYM_RENAMES`` and are merged via ``merge_with_synonyms``.
    """
    groups: Dict[str, List[str]] = {}
    for token in token_counts:
        groups.setdefault(canonical_key(token), []).append(token)

    rewrite: Dict[str, str] = {}
    for variants in groups.values():
        if len(variants) < min_group_size:
            continue
        winner = _pick_winner(variants, token_counts)
        for form in variants:
            if form != winner:
                rewrite[form] = winner
    return rewrite


def _resolve_chains(rewrite: Dict[str, str]) -> Dict[str, str]:
    """Flatten chains ``X -> Y -> Z`` into ``X -> Z``. Raises on cycles.

    Keeps the rewrite map a strict source-to-final mapping so the apply
    step can do a single dictionary lookup per token without re-walking.
    """
    resolved: Dict[str, str] = {}
    for src in rewrite:
        target = src
        path: List[str] = []
        while target in rewrite:
            if target in path:
                raise ValueError(f"Rewrite cycle: {' -> '.join(path + [target])}")
            path.append(target)
            target = rewrite[target]
        resolved[src] = target
    return resolved


def merge_with_synonyms(
    auto: Mapping[str, str],
    synonyms: Mapping[str, str],
) -> Dict[str, str]:
    """Combine auto-discovered rewrites with explicit synonym renames.

    Synonyms take precedence for the same source token. Chains created by
    the merge (auto says ``X -> Y``, synonyms say ``Y -> Z``) are flattened
    so each source maps directly to its final form.
    """
    merged: Dict[str, str] = dict(auto)
    for old, new in synonyms.items():
        merged[old] = new
    return _resolve_chains(merged)


def _apply_rewrite_to_tokens(
    tokens: List[str], rewrite: Mapping[str, str]
) -> List[str]:
    """Apply rewrite map and dedupe, preserving first-seen order."""
    seen: set = set()
    out: List[str] = []
    for tok in tokens:
        new = rewrite.get(tok, tok)
        if new not in seen:
            seen.add(new)
            out.append(new)
    return out


def rewrite_country_value(value: Any, rewrite: Mapping[str, str]) -> Any:
    """Rewrite a country field value and collapse intra-value duplicates.

    Accepts a ``'; '``-joined string or a list of strings. Returns the
    same object (identity-preserving) when nothing needs changing, so
    callers can cheaply detect "no-op" with ``new is value``.
    """
    if isinstance(value, str):
        if not value:
            return value
        tokens = tokenize_country_value(value)
        rewritten = _apply_rewrite_to_tokens(tokens, rewrite)
        new = SEPARATOR.join(rewritten)
        return new if new != value else value
    if isinstance(value, list):
        string_items = [item for item in value if isinstance(item, str)]
        if len(string_items) != len(value):
            # Mixed list with non-strings — leave alone; this script only
            # owns the string case.
            return value
        rewritten = _apply_rewrite_to_tokens([s.strip() for s in string_items], rewrite)
        return rewritten if rewritten != value else value
    return value


def needs_rewrite(value: Any, rewrite: Mapping[str, str]) -> bool:
    return value is not None and rewrite_country_value(value, rewrite) != value


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------


def _pg_scan_tokens(conn, table: str) -> Counter:
    """Return ``Counter`` of token -> # PG docs containing that token.

    Sources: the ``map_country`` column and the ``Country`` JSONB key.
    Each doc contributes a token at most once per source (set-per-row).
    """
    counts: Counter = Counter()
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT map_country, src_doc_raw_metadata->>'Country' " f"FROM {table}"
        )
        for col_val, jsonb_val in cur.fetchall():
            for raw in (col_val, jsonb_val):
                for tok in set(tokenize_country_value(raw)):
                    counts[tok] += 1
    return counts


def _update_pg_column(
    conn,
    table: str,
    rewrite: Mapping[str, str],
    apply: bool,
) -> int:
    """Rewrite ``{table}.map_country`` in place. Returns rows changed."""
    changes: List[Tuple[str, str, str]] = []
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT doc_id, map_country FROM {table} "
            f"WHERE map_country IS NOT NULL AND map_country <> ''"
        )
        for doc_id, val in cur.fetchall():
            new = rewrite_country_value(val, rewrite)
            if new != val:
                changes.append((doc_id, val, new))

    _log_pg_changes(f"{table}.map_country", changes)

    if apply and changes:
        with conn.cursor() as cur:
            for doc_id, old, new in changes:
                cur.execute(
                    f"UPDATE {table} SET map_country = %s "
                    f"WHERE doc_id = %s AND map_country = %s",
                    (new, doc_id, old),
                )
                if cur.rowcount != 1:
                    raise RuntimeError(
                        f"Expected to update exactly 1 row for "
                        f"doc_id={doc_id}, got {cur.rowcount}"
                    )
    return len(changes)


def _update_pg_jsonb(
    conn,
    table: str,
    rewrite: Mapping[str, str],
    apply: bool,
) -> int:
    """Rewrite ``{table}.src_doc_raw_metadata->>'Country'`` in place."""
    changes: List[Tuple[str, str, str]] = []
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT doc_id, src_doc_raw_metadata->>'Country' "
            f"FROM {table} "
            f"WHERE src_doc_raw_metadata->>'Country' IS NOT NULL "
            f"AND src_doc_raw_metadata->>'Country' <> ''"
        )
        for doc_id, val in cur.fetchall():
            new = rewrite_country_value(val, rewrite)
            if new != val:
                changes.append((doc_id, val, new))

    _log_pg_changes(f"{table}.raw_metadata.Country", changes)

    if apply and changes:
        with conn.cursor() as cur:
            for doc_id, old, new in changes:
                cur.execute(
                    f"UPDATE {table} "
                    f"SET src_doc_raw_metadata = jsonb_set("
                    f"  src_doc_raw_metadata, '{{Country}}', %s::jsonb) "
                    f"WHERE doc_id = %s "
                    f"AND src_doc_raw_metadata->>'Country' = %s",
                    (json.dumps(new), doc_id, old),
                )
                if cur.rowcount != 1:
                    raise RuntimeError(
                        f"Expected 1 jsonb row for doc_id={doc_id}, "
                        f"got {cur.rowcount}"
                    )
    return len(changes)


def _log_pg_changes(label: str, changes: List[Tuple[str, str, str]]) -> None:
    logger.info("[PG] %s: %d rows need rewrite", label, len(changes))
    for doc_id, old, new in changes[:MAX_ROW_PREVIEW]:
        logger.info("  doc=%s  %r -> %r", doc_id, old, new)
    if len(changes) > MAX_ROW_PREVIEW:
        logger.info("  ...and %d more (omitted)", len(changes) - MAX_ROW_PREVIEW)


def fix_postgres(
    conn,
    data_source: str,
    rewrite: Mapping[str, str],
    apply: bool,
) -> Dict[str, int]:
    table = f"docs_{data_source}"
    stats = {
        "map_country_rows": _update_pg_column(conn, table, rewrite, apply),
        "raw_metadata_rows": _update_pg_jsonb(conn, table, rewrite, apply),
    }
    if apply:
        conn.commit()
    return stats


# ---------------------------------------------------------------------------
# Qdrant
# ---------------------------------------------------------------------------


def _scroll_country_points(
    client: QdrantClient, collection: str, batch: int = 200
) -> List[Tuple[Any, Any]]:
    """Yield (point_id, payload_value) for every point with a country."""
    out: List[Tuple[Any, Any]] = []
    offset = None
    while True:
        points, next_offset = client.scroll(
            collection_name=collection,
            limit=batch,
            with_payload=["map_country"],
            offset=offset,
        )
        for p in points:
            country = p.payload.get("map_country") if p.payload else None
            if country:
                out.append((p.id, country))
        offset = next_offset
        if offset is None:
            break
    return out


def _qdrant_scan_tokens(client: QdrantClient, collection: str) -> Counter:
    """Token frequency in a Qdrant collection's payloads (set per point)."""
    counts: Counter = Counter()
    for _pid, val in _scroll_country_points(client, collection):
        for tok in set(tokenize_country_value(val)):
            counts[tok] += 1
    return counts


def _set_payload_with_retry(
    client: QdrantClient, collection: str, pid: Any, new_value: Any
) -> None:
    for attempt in range(5):
        try:
            client.set_payload(
                collection_name=collection,
                payload={"map_country": new_value},
                points=[pid],
                wait=False,
            )
            return
        except Exception as exc:
            wait = 2**attempt
            logger.warning(
                "Retry %d for %s point %s: %s (sleep %ds)",
                attempt + 1,
                collection,
                pid,
                exc,
                wait,
            )
            time.sleep(wait)
    raise RuntimeError(f"Failed to update {collection} point {pid}")


def fix_qdrant_collection(
    client: QdrantClient,
    collection: str,
    rewrite: Mapping[str, str],
    apply: bool,
) -> int:
    logger.info("[Qdrant] Scanning collection: %s", collection)
    all_pts = _scroll_country_points(client, collection)
    changes: List[Tuple[Any, Any, Any]] = [
        (pid, val, rewrite_country_value(val, rewrite))
        for pid, val in all_pts
        if needs_rewrite(val, rewrite)
    ]
    logger.info(
        "[Qdrant] %s: %d points scanned, %d need rewrite",
        collection,
        len(all_pts),
        len(changes),
    )
    for pid, old, new in changes[:MAX_ROW_PREVIEW]:
        logger.info("  point=%s  %r -> %r", pid, old, new)
    if len(changes) > MAX_ROW_PREVIEW:
        logger.info("  ...and %d more (omitted)", len(changes) - MAX_ROW_PREVIEW)
    if not apply:
        return len(changes)

    for pid, _old, new in changes:
        _set_payload_with_retry(client, collection, pid, new)
    return len(changes)


# ---------------------------------------------------------------------------
# Token collection + cluster reporting
# ---------------------------------------------------------------------------


def collect_all_tokens(
    pg_conn,
    qdrant_client: Optional[QdrantClient],
    data_source: str,
    skip_postgres: bool,
    skip_qdrant: bool,
) -> Counter:
    """Aggregate token counts across every source we plan to rewrite.

    PG and Qdrant counts are summed — this is a heuristic, not a true unique
    count, but it only affects winner selection (more common = more likely
    canonical) and is robust enough in practice.
    """
    counts: Counter = Counter()
    if not skip_postgres and pg_conn is not None:
        counts.update(_pg_scan_tokens(pg_conn, f"docs_{data_source}"))
    if not skip_qdrant and qdrant_client is not None:
        counts.update(_qdrant_scan_tokens(qdrant_client, f"documents_{data_source}"))
        counts.update(_qdrant_scan_tokens(qdrant_client, f"chunks_{data_source}"))
    return counts


def log_synonyms(token_counts: Mapping[str, int], synonyms: Mapping[str, str]) -> None:
    """Per-synonym preview — kept separate from auto-cluster output so the
    explicit human decisions are visually distinct from the heuristic ones."""
    if not synonyms:
        return
    logger.info("Applying %d explicit synonym renames:", len(synonyms))
    for old, new in sorted(synonyms.items()):
        logger.info(
            "[SYNONYM] %r (%d) -> %r (%d)",
            old,
            token_counts.get(old, 0),
            new,
            token_counts.get(new, 0),
        )


def log_clusters(
    token_counts: Mapping[str, int],
    rewrite: Mapping[str, str],
) -> None:
    """Print a per-cluster preview of what the rewrite will do."""
    if not rewrite:
        logger.info("No duplicate clusters found at the current threshold.")
        return

    by_winner: Dict[str, List[str]] = {}
    for variant, winner in rewrite.items():
        by_winner.setdefault(winner, []).append(variant)

    logger.info(
        "Found %d duplicate clusters covering %d variant rewrites:",
        len(by_winner),
        len(rewrite),
    )
    for winner, variants in sorted(by_winner.items()):
        members = [winner, *variants]
        total = sum(token_counts.get(m, 0) for m in members)
        logger.info(
            "[CLUSTER] winner=%r  (%d variants, ~%d source rows total)",
            winner,
            len(members),
            total,
        )
        # winner first, then losers — both shown with counts
        ordered = sorted(members, key=lambda m: -token_counts.get(m, 0))
        for form in ordered[:MAX_PER_CLUSTER_LOG]:
            tag = "WINNER" if form == winner else "rewrite"
            logger.info("    %-7s  %r  (%d)", tag, form, token_counts.get(form, 0))
        if len(ordered) > MAX_PER_CLUSTER_LOG:
            logger.info(
                "    ...and %d more variants (omitted)",
                len(ordered) - MAX_PER_CLUSTER_LOG,
            )


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------


def _qdrant_client() -> QdrantClient:
    host = os.getenv("QDRANT_HOST", "http://localhost:6333")
    host = host.replace("://qdrant:", "://localhost:")
    return QdrantClient(url=host, api_key=os.getenv("QDRANT_API_KEY"))


def _postgres_conn():
    import psycopg2

    try:
        from pipeline.db.postgres_client_base import build_postgres_dsn

        dsn = build_postgres_dsn()
    except ImportError:
        dsn = (
            f"host={os.environ.get('POSTGRES_HOST', 'localhost')} "
            f"port={os.environ.get('POSTGRES_PORT', '5432')} "
            f"user={os.environ.get('POSTGRES_USER', 'evidencelab')} "
            f"password={os.environ.get('POSTGRES_PASSWORD', 'evidencelab')} "
            f"dbname={os.environ.get('POSTGRES_DB', 'evidencelab')}"
        )
    # Auto-rewrite the Docker service hostname for host execution, same
    # trick as _qdrant_client(). build_postgres_dsn() forces 'postgres' when
    # /.dockerenv exists, but on the host the .env may still carry the
    # Docker name from a previous compose run.
    dsn = dsn.replace("host=postgres ", "host=localhost ")
    return psycopg2.connect(dsn)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collapse near-duplicate variants of country names across "
            "Postgres + Qdrant."
        )
    )
    parser.add_argument(
        "--data-source",
        default="wfp",
        help="Data source name (default: wfp). Drives table + collection names.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. Default is dry-run — nothing is written.",
    )
    parser.add_argument(
        "--skip-postgres", action="store_true", help="Skip PostgreSQL updates."
    )
    parser.add_argument(
        "--skip-qdrant", action="store_true", help="Skip Qdrant updates."
    )
    parser.add_argument(
        "--min-group-size",
        type=int,
        default=2,
        help=(
            "Only collapse clusters with at least this many distinct surface "
            "forms (default: 2)."
        ),
    )
    parser.add_argument(
        "--skip-synonyms",
        action="store_true",
        help=(
            "Skip the explicit SYNONYM_RENAMES table (e.g. Tanzania -> "
            "United Republic of Tanzania). Use this to apply only the "
            "auto-detected trivial-variant cleanup."
        ),
    )
    return parser.parse_args()


def _open_connections(args: argparse.Namespace):
    pg_conn = None if args.skip_postgres else _postgres_conn()
    qdrant = None if args.skip_qdrant else _qdrant_client()
    return pg_conn, qdrant


def _log_summary(
    args: argparse.Namespace,
    pg_stats: Dict[str, int],
    qdrant_docs: int,
    qdrant_chunks: int,
) -> None:
    label = "applied" if args.apply else "would change"
    mode = "APPLY" if args.apply else "DRY-RUN"
    logger.info("-" * 60)
    logger.info(" Summary  [%s]", mode)
    logger.info(
        "   PG  docs.map_country rows %s:           %d",
        label,
        pg_stats["map_country_rows"],
    )
    logger.info(
        "   PG  docs.raw_metadata.Country rows %s:  %d",
        label,
        pg_stats["raw_metadata_rows"],
    )
    logger.info(
        "   Qdrant documents_%s points %s:         %d",
        args.data_source,
        label,
        qdrant_docs,
    )
    logger.info(
        "   Qdrant chunks_%s    points %s:         %d",
        args.data_source,
        label,
        qdrant_chunks,
    )
    if not args.apply:
        logger.info(" Re-run with --apply to actually write the changes.")
    logger.info("=" * 60)


def main() -> int:
    args = _parse_args()
    env_path = os.path.join(os.path.dirname(__file__), "../../.env")
    load_dotenv(env_path)

    mode = "APPLY" if args.apply else "DRY-RUN"
    logger.info("=" * 60)
    logger.info(" Duplicate country variant cleanup  [%s]", mode)
    logger.info(
        " data_source=%s  min_group_size=%d  synonyms=%s",
        args.data_source,
        args.min_group_size,
        "off" if args.skip_synonyms else "on",
    )
    logger.info("=" * 60)

    pg_conn, qdrant = _open_connections(args)
    try:
        token_counts = collect_all_tokens(
            pg_conn,
            qdrant,
            args.data_source,
            skip_postgres=args.skip_postgres,
            skip_qdrant=args.skip_qdrant,
        )
        auto_rewrite = build_rewrite_map(
            token_counts, min_group_size=args.min_group_size
        )
        synonyms = {} if args.skip_synonyms else SYNONYM_RENAMES
        rewrite = merge_with_synonyms(auto_rewrite, synonyms)

        log_clusters(token_counts, auto_rewrite)
        log_synonyms(token_counts, synonyms)

        pg_stats = {"map_country_rows": 0, "raw_metadata_rows": 0}
        if not args.skip_postgres and pg_conn is not None and rewrite:
            pg_stats = fix_postgres(
                pg_conn, args.data_source, rewrite, apply=args.apply
            )

        qdrant_docs = qdrant_chunks = 0
        if not args.skip_qdrant and qdrant is not None and rewrite:
            qdrant_docs = fix_qdrant_collection(
                qdrant, f"documents_{args.data_source}", rewrite, apply=args.apply
            )
            qdrant_chunks = fix_qdrant_collection(
                qdrant, f"chunks_{args.data_source}", rewrite, apply=args.apply
            )

        _log_summary(args, pg_stats, qdrant_docs, qdrant_chunks)
    finally:
        if pg_conn is not None:
            pg_conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
