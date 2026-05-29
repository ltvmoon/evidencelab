"""Google Vertex AI reranker via Discovery Engine Ranking API."""

import logging
from typing import List, Optional

from google.api_core import exceptions as gax_exceptions

logger = logging.getLogger(__name__)


class RerankerUnavailableError(RuntimeError):
    """Raised when an external reranker is temporarily unavailable.

    Distinct from arbitrary errors so callers can fall back to no-rerank
    on known-transient cases (e.g. Google ``503 UNAVAILABLE``,
    ``DEADLINE_EXCEEDED``) without swallowing real bugs.
    """


# Errors we treat as transient and recoverable: search should still succeed
# (without the rerank step) rather than 500 to the user. Anything else
# propagates so an unexpected bug isn't silently masked.
_TRANSIENT_RERANK_ERRORS = (
    gax_exceptions.ServiceUnavailable,
    gax_exceptions.DeadlineExceeded,
    gax_exceptions.GatewayTimeout,
    gax_exceptions.InternalServerError,
)


def rerank_with_google_vertex(
    query: str, documents: List[str], model_id: str
) -> List[float]:
    """Rerank documents using the Vertex AI Ranking API (Discovery Engine).

    Raises ``RerankerUnavailableError`` on transient Google-side outages
    (``503 UNAVAILABLE``, ``DEADLINE_EXCEEDED``, ``504``, ``500``) so the
    caller can fall back to returning the unranked results instead of
    bubbling a 500 to the user.
    """
    from google.cloud import (
        discoveryengine_v1 as discoveryengine,  # type: ignore[attr-defined]
    )

    from pipeline.utilities.google_vertex_client import _load_gcp_project_id

    project_id = _load_gcp_project_id()
    client = discoveryengine.RankServiceClient()
    ranking_config = client.ranking_config_path(
        project=project_id,
        location="global",
        ranking_config="default_ranking_config",
    )
    records = [
        discoveryengine.RankingRecord(id=str(i), content=doc)
        for i, doc in enumerate(documents)
    ]
    request = discoveryengine.RankRequest(
        ranking_config=ranking_config,
        model=model_id,
        top_n=len(documents),
        query=query,
        records=records,
    )
    try:
        response = client.rank(request=request)
    except _TRANSIENT_RERANK_ERRORS as exc:
        raise RerankerUnavailableError(
            f"Vertex Discovery Engine rank API unavailable: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    # Map scores back to original document order
    scores: List[Optional[float]] = [None] * len(documents)
    for record in response.records:
        idx = int(record.id)
        scores[idx] = record.score
    return [s if s is not None else 0.0 for s in scores]
