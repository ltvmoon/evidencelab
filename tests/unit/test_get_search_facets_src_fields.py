"""Unit tests for query-narrowed faceting on src_* fields.

Locks in the fix for the bug where the Evaluation Category filter showed
counts like ``(CE: 1, DE: 1)`` while the search returned hundreds of
results — the old path read ``src_evaluation_category`` directly from the
Qdrant chunk payloads, but the field was only denormalised onto a tiny
fraction of chunks. The fix routes ``src_*`` field counting through PG
JSONB lookups using the matching doc_ids, so counts reflect the actual
document set the search produced.
"""

from collections import Counter
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from ui.backend.services.search import _facet_counter_for_field
from ui.backend.utils.facet_helpers import (
    count_src_jsonb_field_for_doc_ids as _count_src_field_from_pg,
)
from ui.backend.utils.facet_helpers import count_sys_field_for_doc_ids


def _count_sys_language_from_pg(pg, doc_ids):
    return count_sys_field_for_doc_ids(pg, "sys_language", doc_ids)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeCursor:
    """Mimics psycopg2 cursor for one query at a time."""

    def __init__(self):
        self.last_sql: str = ""
        self.last_params = None
        self.next_rows: list = []

    def execute(self, sql, params=None):
        self.last_sql = sql
        self.last_params = list(params) if params is not None else None

    def fetchall(self):
        return list(self.next_rows)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeConn:
    def __init__(self, cursor: _FakeCursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _make_pg(rows: list):
    """Build a fake PG client that returns *rows* on the next fetchall()."""
    pg = MagicMock()
    pg.docs_table = "docs_test"
    cursor = _FakeCursor()
    cursor.next_rows = rows

    @contextmanager
    def _get_conn():
        yield _FakeConn(cursor)

    pg._get_conn = _get_conn
    pg._cursor = cursor  # for assertions
    return pg


# ---------------------------------------------------------------------------
# _count_src_field_from_pg
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCountSrcFieldFromPG:
    def test_returns_counter_keyed_by_value(self):
        pg = _make_pg([("CE",), ("DE",), ("DE",), ("IE",)])
        out = _count_src_field_from_pg(
            pg, "Evaluation category", ["d1", "d2", "d3", "d4"]
        )
        assert out == Counter({"DE": 2, "CE": 1, "IE": 1})

    def test_skips_null_and_empty_values(self):
        pg = _make_pg([("CE",), (None,), ("",), ("CE",)])
        out = _count_src_field_from_pg(
            pg, "Evaluation category", ["d1", "d2", "d3", "d4"]
        )
        assert out == Counter({"CE": 2})

    def test_returns_empty_counter_for_no_doc_ids(self):
        pg = _make_pg([])
        # Don't even hit the DB if there are no doc_ids to look up.
        out = _count_src_field_from_pg(pg, "Evaluation category", [])
        assert out == Counter()

    def test_passes_raw_key_as_first_parameter_not_interpolated(self):
        pg = _make_pg([("CE",)])
        _count_src_field_from_pg(pg, "Evaluation category", ["d1", "d2"])
        # The raw key must travel as a parameter, not in the SQL string —
        # otherwise we'd reintroduce a SQL-injection foothold for any future
        # caller that forgets the config-side validation.
        assert pg._cursor.last_params == ["Evaluation category", "d1", "d2"]
        assert "Evaluation category" not in pg._cursor.last_sql

    def test_uses_in_clause_with_correct_placeholder_count(self):
        pg = _make_pg([])
        _count_src_field_from_pg(pg, "Quality rating", ["a", "b", "c"])
        # %s for the raw key + 3 for the doc IDs = 4 total
        assert pg._cursor.last_sql.count("%s") == 4


# ---------------------------------------------------------------------------
# _count_sys_language_from_pg
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCountSysLanguageFromPG:
    def test_counts_codes(self):
        pg = _make_pg([("en",), ("en",), ("fr",), ("",), (None,)])
        out = _count_sys_language_from_pg(pg, ["d1", "d2", "d3", "d4", "d5"])
        # Empty / null filtered out — language-name normalisation happens
        # later in _format_facet_list.
        assert out == Counter({"en": 2, "fr": 1})

    def test_empty_doc_ids_short_circuits(self):
        pg = _make_pg([])
        assert _count_sys_language_from_pg(pg, []) == Counter()


# ---------------------------------------------------------------------------
# _facet_counter_for_field — strategy router
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFacetCounterForField:
    def test_sys_language_routes_to_pg(self):
        pg = _make_pg([("en",), ("en",)])
        counter = _facet_counter_for_field(
            core_field="language",
            storage_field="sys_language",
            unique_docs=[{"sys_language": "ignored"}],  # must NOT be used
            doc_ids=["d1", "d2"],
            pg=pg,
            src_field_mapping={},
        )
        assert counter == Counter({"en": 2})
        assert "sys_language" in pg._cursor.last_sql

    def test_src_field_with_mapping_routes_to_pg(self):
        pg = _make_pg([("CE",), ("DE",), ("DE",)])
        counter = _facet_counter_for_field(
            core_field="src_evaluation_category",
            storage_field="src_evaluation_category",
            unique_docs=[
                # Out-of-date / partial chunk data should be IGNORED in
                # favour of the PG truth.
                {"src_evaluation_category": "stale"},
            ],
            doc_ids=["d1", "d2", "d3"],
            pg=pg,
            src_field_mapping={"src_evaluation_category": "Evaluation category"},
        )
        assert counter == Counter({"DE": 2, "CE": 1})

    def test_src_field_without_mapping_falls_back_to_payload_aggregation(self):
        # No mapping configured for this src_* field — fall back to the
        # legacy in-memory aggregation over the Qdrant payloads.
        counter = _facet_counter_for_field(
            core_field="src_unmapped",
            storage_field="src_unmapped",
            unique_docs=[
                {"src_unmapped": "X"},
                {"src_unmapped": "X"},
                {"src_unmapped": "Y"},
            ],
            doc_ids=["d1", "d2", "d3"],
            pg=_make_pg([]),
            src_field_mapping={},
        )
        assert counter == Counter({"X": 2, "Y": 1})

    def test_map_field_uses_payload_aggregation(self):
        # Plain map_* fields read from the Qdrant payload as before.
        counter = _facet_counter_for_field(
            core_field="country",
            storage_field="map_country",
            unique_docs=[
                {"map_country": "Kenya"},
                {"map_country": "Kenya"},
                {"map_country": "Niger"},
            ],
            doc_ids=["d1", "d2", "d3"],
            pg=None,
            src_field_mapping={},
        )
        assert counter == Counter({"Kenya": 2, "Niger": 1})

    def test_sys_language_with_no_pg_falls_back_to_payload(self):
        # Defensive: if pg isn't a PostgresClient, the strategy router
        # must not crash — fall back to payload aggregation.
        counter = _facet_counter_for_field(
            core_field="language",
            storage_field="sys_language",
            unique_docs=[{"sys_language": "en"}, {"sys_language": "en"}],
            doc_ids=["d1", "d2"],
            pg=None,
            src_field_mapping={},
        )
        assert counter == Counter({"en": 2})
