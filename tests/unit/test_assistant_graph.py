"""Unit tests for the deepagents research assistant graph."""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

# Mock the heavy imports that assistant_graph pulls in transitively.
# search -> search_models -> google_vertex_reranker -> google.cloud
_mock_search = ModuleType("ui.backend.services.search")
_mock_search_fn = MagicMock(return_value=[])
_mock_search.search_chunks = _mock_search_fn
sys.modules.setdefault("ui.backend.services.search", _mock_search)

from ui.backend.services.assistant_graph import (  # noqa: E402
    SearchTracker,
    _build_search_tool,
    _format_search_result,
    build_research_agent,
)


class _FakeScoredPoint:
    """Mimics a Qdrant ScoredPoint for testing."""

    def __init__(self, id, score, payload):
        self.id = id
        self.score = score
        self.payload = payload


def _make_scored_point(chunk_id, doc_id, title="Doc", text="T", score=0.9, **extra):
    payload = {"doc_id": doc_id, "title": title, "text": text, **extra}
    return _FakeScoredPoint(id=chunk_id, score=score, payload=payload)


class TestFormatSearchResult:
    """Tests for _format_search_result."""

    def test_formats_scored_point(self):
        point = _make_scored_point("c1", "d1", "Title", "Content", 0.85)
        result = _format_search_result(point)

        assert result["chunk_id"] == "c1"
        assert result["doc_id"] == "d1"
        assert result["title"] == "Title"
        assert result["text"] == "Content"
        assert result["score"] == 0.85

    def test_handles_dict_input(self):
        data = {
            "chunk_id": "c1",
            "doc_id": "d1",
            "title": "Title",
            "text": "Content",
            "score": 0.9,
        }
        result = _format_search_result(data)

        assert result["doc_id"] == "d1"
        assert result["title"] == "Title"


class TestSearchTracker:
    """Tests for the SearchTracker class."""

    def test_search_tracks_results(self):
        _mock_search_fn.reset_mock()
        _mock_search_fn.return_value = [
            _make_scored_point("c1", "d1", "Doc 1", "Content", 0.9),
            _make_scored_point("c2", "d2", "Doc 2", "Content", 0.8),
        ]

        tracker = SearchTracker(data_source="test")
        results = tracker.search("food security")

        assert len(results) == 2
        assert len(tracker.all_results) == 2
        assert len(tracker.per_query) == 1
        assert tracker.per_query[0]["query"] == "food security"
        assert tracker.per_query[0]["result_count"] == 2

    def test_deduplicates_across_queries(self):
        _mock_search_fn.reset_mock()
        _mock_search_fn.side_effect = [
            [_make_scored_point("c1", "d1", score=0.9)],
            [
                _make_scored_point("c1", "d1", score=0.9),
                _make_scored_point("c2", "d2", score=0.8),
            ],
        ]

        tracker = SearchTracker()
        tracker.search("query 1")
        tracker.search("query 2")

        # c1 should appear only once even though returned by both queries
        assert len(tracker.all_results) == 2
        chunk_ids = [r["chunk_id"] for r in tracker.all_results]
        assert chunk_ids.count("c1") == 1

    def test_tracks_multiple_queries(self):
        _mock_search_fn.reset_mock()
        _mock_search_fn.side_effect = [
            [_make_scored_point("c1", "d1", score=0.9)],
            [_make_scored_point("c2", "d2", score=0.8)],
        ]

        tracker = SearchTracker()
        tracker.search("query 1")
        tracker.search("query 2")

        assert len(tracker.per_query) == 2
        assert tracker.per_query[0]["query"] == "query 1"
        assert tracker.per_query[1]["query"] == "query 2"

    def test_handles_search_error(self):
        _mock_search_fn.reset_mock()
        _mock_search_fn.side_effect = Exception("Connection error")

        tracker = SearchTracker()
        results = tracker.search("bad query")

        assert results == []
        assert len(tracker.per_query) == 1
        assert tracker.per_query[0]["result_count"] == 0

    def test_get_sources_deduplicates_by_doc_id(self):
        _mock_search_fn.reset_mock()
        _mock_search_fn.side_effect = None
        _mock_search_fn.return_value = [
            _make_scored_point("c1", "d1", "Doc A", "Text 1", 0.9),
            _make_scored_point("c2", "d1", "Doc A", "Text 2", 0.8),
            _make_scored_point("c3", "d2", "Doc B", "Text 3", 0.7),
        ]

        tracker = SearchTracker()
        tracker.search("query")
        sources = tracker.get_sources()

        # d1 should appear only once
        assert len(sources) == 2
        doc_ids = [s["docId"] for s in sources]
        assert "d1" in doc_ids
        assert "d2" in doc_ids

    def test_get_sources_sorted_by_score(self):
        _mock_search_fn.reset_mock()
        _mock_search_fn.side_effect = None
        _mock_search_fn.return_value = [
            _make_scored_point("c1", "d1", "Low", "Text", 0.3),
            _make_scored_point("c2", "d2", "High", "Text", 0.9),
        ]

        tracker = SearchTracker()
        tracker.search("query")
        sources = tracker.get_sources()

        assert sources[0]["docId"] == "d2"  # highest score first
        assert sources[1]["docId"] == "d1"

    def test_get_sources_truncates_long_text(self):
        _mock_search_fn.reset_mock()
        _mock_search_fn.side_effect = None
        long_text = "x" * 300
        _mock_search_fn.return_value = [
            _make_scored_point("c1", "d1", "Doc", long_text, 0.9),
        ]

        tracker = SearchTracker()
        tracker.search("query")
        sources = tracker.get_sources()

        assert len(sources[0]["text"]) < 300
        assert sources[0]["text"].endswith("...")

    def test_get_new_queries_returns_only_new(self):
        _mock_search_fn.reset_mock()
        _mock_search_fn.side_effect = [
            [_make_scored_point("c1", "d1", score=0.9)],
            [_make_scored_point("c2", "d2", score=0.8)],
            [_make_scored_point("c3", "d3", score=0.7)],
        ]

        tracker = SearchTracker()
        tracker.search("query 1")
        tracker.search("query 2")

        # First call returns both queries
        new = tracker.get_new_queries()
        assert len(new) == 2
        assert new[0]["query"] == "query 1"
        assert new[1]["query"] == "query 2"

        # Second call returns nothing (no new queries)
        new = tracker.get_new_queries()
        assert len(new) == 0

        # After another search, returns only the new one
        tracker.search("query 3")
        new = tracker.get_new_queries()
        assert len(new) == 1
        assert new[0]["query"] == "query 3"


class TestBuildSearchTool:
    """Tests for _build_search_tool."""

    def test_tool_returns_formatted_results(self):
        _mock_search_fn.reset_mock()
        _mock_search_fn.side_effect = None
        _mock_search_fn.return_value = [
            _make_scored_point("c1", "d1", "Doc 1", "Content about food", 0.9),
        ]

        tracker = SearchTracker()
        tool_fn = _build_search_tool(tracker)
        result = tool_fn.invoke("food security")

        assert "Found 1 results" in result
        assert "Doc 1" in result
        assert "Content about food" in result

    def test_tool_returns_no_results_message(self):
        _mock_search_fn.reset_mock()
        _mock_search_fn.side_effect = None
        _mock_search_fn.return_value = []

        tracker = SearchTracker()
        tool_fn = _build_search_tool(tracker)
        result = tool_fn.invoke("nonexistent topic")

        assert "No results found" in result

    def test_tool_tracks_via_tracker(self):
        _mock_search_fn.reset_mock()
        _mock_search_fn.side_effect = None
        _mock_search_fn.return_value = [
            _make_scored_point("c1", "d1", score=0.9),
        ]

        tracker = SearchTracker()
        tool_fn = _build_search_tool(tracker)
        tool_fn.invoke("test query")

        assert len(tracker.per_query) == 1
        assert len(tracker.all_results) == 1


class TestBuildResearchAgent:
    """Tests for build_research_agent."""

    @patch("ui.backend.services.assistant_graph.create_agent")
    def test_creates_agent_and_tracker(self, mock_create):
        mock_agent = MagicMock()
        mock_create.return_value = mock_agent

        llm = MagicMock()
        agent, tracker = build_research_agent(llm, data_source="worldbank")

        assert agent is mock_agent
        assert isinstance(tracker, SearchTracker)
        assert tracker.data_source == "worldbank"

    @patch("ui.backend.services.assistant_graph.create_agent")
    def test_passes_search_tool_and_prompt(self, mock_create):
        mock_create.return_value = MagicMock()

        llm = MagicMock()
        build_research_agent(llm, data_source="worldbank")

        # Verify create_agent was called with model, tools, system_prompt
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs["model"] is llm
        assert len(call_kwargs.kwargs["tools"]) == 1
        assert "research assistant" in call_kwargs.kwargs["system_prompt"].lower()
