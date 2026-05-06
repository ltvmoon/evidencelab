"""Unit tests for Google Vertex AI reranker (Discovery Engine)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from google.api_core import exceptions as gax_exceptions

from ui.backend.services.google_vertex_reranker import (
    RerankerUnavailableError,
    rerank_with_google_vertex,
)


def _make_fake_record(record_id: str, score: float) -> SimpleNamespace:
    return SimpleNamespace(id=record_id, score=score)


@patch("pipeline.utilities.google_vertex_client._load_gcp_project_id")
@patch("google.cloud.discoveryengine_v1", create=True)
def test_rerank_returns_scores_in_original_order(mock_de, mock_project):
    mock_project.return_value = "test-project"

    mock_client = MagicMock()
    mock_de.RankServiceClient.return_value = mock_client
    mock_client.ranking_config_path.return_value = (
        "projects/test-project/locations/global/rankingConfigs/default_ranking_config"
    )

    # API returns docs reordered: doc2 first, then doc0, then doc1
    mock_response = SimpleNamespace(
        records=[
            _make_fake_record("2", 0.95),
            _make_fake_record("0", 0.80),
            _make_fake_record("1", 0.60),
        ]
    )
    mock_client.rank.return_value = mock_response

    scores = rerank_with_google_vertex(
        query="test query",
        documents=["doc A", "doc B", "doc C"],
        model_id="semantic-ranker-default@latest",
    )

    assert len(scores) == 3
    # Scores should be mapped back to original positions
    assert scores[0] == 0.80  # doc0
    assert scores[1] == 0.60  # doc1
    assert scores[2] == 0.95  # doc2


@patch("pipeline.utilities.google_vertex_client._load_gcp_project_id")
@patch("google.cloud.discoveryengine_v1", create=True)
def test_rerank_builds_correct_request(mock_de, mock_project):
    mock_project.return_value = "my-project"

    mock_client = MagicMock()
    mock_de.RankServiceClient.return_value = mock_client
    mock_client.ranking_config_path.return_value = "config-path"
    mock_client.rank.return_value = SimpleNamespace(
        records=[
            _make_fake_record("0", 0.5),
            _make_fake_record("1", 0.3),
        ]
    )

    rerank_with_google_vertex(
        query="climate change",
        documents=["doc one", "doc two"],
        model_id="semantic-ranker-fast-004",
    )

    # Verify RankingRecord creation
    mock_de.RankingRecord.assert_any_call(id="0", content="doc one")
    mock_de.RankingRecord.assert_any_call(id="1", content="doc two")

    # Verify RankRequest creation
    call_kwargs = mock_de.RankRequest.call_args
    assert call_kwargs[1]["model"] == "semantic-ranker-fast-004"
    assert call_kwargs[1]["query"] == "climate change"
    assert call_kwargs[1]["top_n"] == 2


@patch("pipeline.utilities.google_vertex_client._load_gcp_project_id")
@patch("google.cloud.discoveryengine_v1", create=True)
def test_rerank_missing_doc_gets_zero_score(mock_de, mock_project):
    mock_project.return_value = "p"

    mock_client = MagicMock()
    mock_de.RankServiceClient.return_value = mock_client
    mock_client.ranking_config_path.return_value = "config"

    # API only returns one of two docs (missing doc index 1)
    mock_client.rank.return_value = SimpleNamespace(
        records=[_make_fake_record("0", 0.9)]
    )

    scores = rerank_with_google_vertex("q", ["a", "b"], "model")
    assert scores == [0.9, 0.0]


# ---------------------------------------------------------------------------
# Transient-failure fallback: known-recoverable Google errors get repackaged
# as RerankerUnavailableError so the search pipeline can fall back to the
# unranked results instead of bubbling a 500 to the user.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "transient_exc",
    [
        gax_exceptions.ServiceUnavailable("503 The service is currently unavailable."),
        gax_exceptions.DeadlineExceeded("504 Deadline exceeded."),
        gax_exceptions.GatewayTimeout("504 Gateway timeout."),
        gax_exceptions.InternalServerError("500 Internal."),
    ],
)
@patch("pipeline.utilities.google_vertex_client._load_gcp_project_id")
@patch("google.cloud.discoveryengine_v1", create=True)
def test_rerank_raises_unavailable_on_known_transient_errors(
    mock_de, mock_project, transient_exc
):
    mock_project.return_value = "p"
    mock_client = MagicMock()
    mock_de.RankServiceClient.return_value = mock_client
    mock_client.ranking_config_path.return_value = "config"
    mock_client.rank.side_effect = transient_exc

    with pytest.raises(RerankerUnavailableError) as excinfo:
        rerank_with_google_vertex("q", ["a", "b"], "model")

    # The original Google error must be preserved as the cause so SREs can
    # still see exactly which transient code fired.
    assert excinfo.value.__cause__ is transient_exc
    # And the message should name the kind of failure for log grep-ability.
    assert type(transient_exc).__name__ in str(excinfo.value)


@patch("pipeline.utilities.google_vertex_client._load_gcp_project_id")
@patch("google.cloud.discoveryengine_v1", create=True)
def test_rerank_does_not_swallow_real_bugs(mock_de, mock_project):
    """A non-transient error must still propagate — silently ignoring it
    would mask a real reranker bug behind the fallback."""
    mock_project.return_value = "p"
    mock_client = MagicMock()
    mock_de.RankServiceClient.return_value = mock_client
    mock_client.ranking_config_path.return_value = "config"
    mock_client.rank.side_effect = ValueError("malformed request")

    with pytest.raises(ValueError, match="malformed request"):
        rerank_with_google_vertex("q", ["a", "b"], "model")


@patch("pipeline.utilities.google_vertex_client._load_gcp_project_id")
@patch("google.cloud.discoveryengine_v1", create=True)
def test_rerank_permission_denied_propagates(mock_de, mock_project):
    """Auth/permission errors are not transient — they must surface so an
    operator notices the credential issue rather than seeing silent
    no-rerank fallback forever."""
    mock_project.return_value = "p"
    mock_client = MagicMock()
    mock_de.RankServiceClient.return_value = mock_client
    mock_client.ranking_config_path.return_value = "config"
    mock_client.rank.side_effect = gax_exceptions.PermissionDenied("403 nope")

    with pytest.raises(gax_exceptions.PermissionDenied):
        rerank_with_google_vertex("q", ["a", "b"], "model")
