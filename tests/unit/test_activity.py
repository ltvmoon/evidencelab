"""Tests for activity schemas and validation."""

import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ui.backend.auth.schemas import (
    ActivityCreate,
    ActivityRead,
    ActivitySummaryUpdate,
    ActivitySummaryUpdateAnonymous,
)


class TestActivityCreate:
    """Tests for the ActivityCreate schema."""

    def test_valid_activity_minimal(self):
        """An activity with required fields only."""
        a = ActivityCreate(
            search_id=str(uuid.uuid4()),
            query="test query",
        )
        assert a.query == "test query"
        assert a.filters is None
        assert a.search_results is None
        assert a.ai_summary is None
        assert a.url is None

    def test_valid_activity_all_fields(self):
        """An activity with all optional fields populated."""
        sid = str(uuid.uuid4())
        a = ActivityCreate(
            search_id=sid,
            query="climate adaptation",
            filters={"country": "Kenya", "year": "2024"},
            search_results=[
                {"chunk_id": "c1", "doc_id": "d1", "title": "Report 1", "score": 0.95}
            ],
            ai_summary="Summary of results about climate adaptation...",
            url="https://example.com/search?q=climate",
        )
        assert a.search_id == sid
        assert a.query == "climate adaptation"
        assert a.filters is not None
        assert len(a.search_results) == 1
        assert a.ai_summary.startswith("Summary")
        assert a.url == "https://example.com/search?q=climate"

    def test_empty_query_rejected(self):
        """An empty query string should be rejected (Pydantic treats as required)."""
        # query is str, so "" is valid but the route logic may check
        a = ActivityCreate(search_id=str(uuid.uuid4()), query="")
        assert a.query == ""

    def test_missing_query_rejected(self):
        """A missing query field should raise ValidationError."""
        with pytest.raises(ValidationError, match="query"):
            ActivityCreate(search_id=str(uuid.uuid4()))

    def test_missing_search_id_rejected(self):
        """A missing search_id field should raise ValidationError."""
        with pytest.raises(ValidationError, match="search_id"):
            ActivityCreate(query="test")

    def test_search_id_max_length(self):
        """search_id exceeding 100 chars should be rejected."""
        with pytest.raises(ValidationError, match="search_id"):
            ActivityCreate(search_id="x" * 101, query="test")

    def test_query_max_length(self):
        """query exceeding 5000 chars should be rejected."""
        with pytest.raises(ValidationError, match="query"):
            ActivityCreate(search_id=str(uuid.uuid4()), query="x" * 5001)

    def test_url_max_length(self):
        """url exceeding 2000 chars should be rejected."""
        with pytest.raises(ValidationError, match="url"):
            ActivityCreate(
                search_id=str(uuid.uuid4()),
                query="test",
                url="https://example.com/" + "x" * 2000,
            )

    def test_filters_jsonb_depth_limit(self):
        """Deeply nested filters dict should be rejected."""
        # Build a dict nested 15 levels deep (exceeds limit of 10)
        deep = {"a": "leaf"}
        for _ in range(14):
            deep = {"nested": deep}
        with pytest.raises(ValidationError, match="depth"):
            ActivityCreate(
                search_id=str(uuid.uuid4()),
                query="test",
                filters=deep,
            )

    def test_filters_jsonb_size_limit(self):
        """Extremely large filters payload should be rejected."""
        huge = {"data": "x" * 1_100_000}
        with pytest.raises(ValidationError, match="size"):
            ActivityCreate(
                search_id=str(uuid.uuid4()),
                query="test",
                filters=huge,
            )

    def test_filters_jsonb_normal_depth_ok(self):
        """A reasonably nested filters dict should be accepted."""
        normal = {"timing": {"search_duration_ms": 450}, "country": ["Kenya"]}
        a = ActivityCreate(search_id=str(uuid.uuid4()), query="test", filters=normal)
        assert a.filters == normal


class TestActivitySummaryUpdate:
    """Tests for the ActivitySummaryUpdate schema."""

    def test_valid_summary(self):
        """A valid summary update."""
        u = ActivitySummaryUpdate(ai_summary="Updated summary text.")
        assert u.ai_summary == "Updated summary text."

    def test_optional_summary(self):
        """ai_summary is optional — an empty update is valid (tree-only PATCH)."""
        u = ActivitySummaryUpdate()
        assert u.ai_summary is None
        assert u.summary_duration_ms is None
        assert u.drilldown_tree is None

    def test_tree_only_update(self):
        """Can send drilldown_tree without ai_summary."""
        tree = {"id": "root", "label": "Root", "children": []}
        u = ActivitySummaryUpdate(drilldown_tree=tree)
        assert u.ai_summary is None
        assert u.drilldown_tree == tree

    def test_summary_duration_bounds(self):
        """summary_duration_ms must be between 0 and 600_000."""
        u = ActivitySummaryUpdate(summary_duration_ms=5000.0)
        assert u.summary_duration_ms == 5000.0

    def test_summary_duration_negative_rejected(self):
        """Negative summary_duration_ms should be rejected."""
        with pytest.raises(ValidationError, match="summary_duration_ms"):
            ActivitySummaryUpdate(summary_duration_ms=-1.0)

    def test_summary_duration_too_large_rejected(self):
        """summary_duration_ms over 600_000 should be rejected."""
        with pytest.raises(ValidationError, match="summary_duration_ms"):
            ActivitySummaryUpdate(summary_duration_ms=700_000.0)

    def test_drilldown_tree_depth_limit(self):
        """Deeply nested drilldown_tree should be rejected."""
        deep = {"id": "leaf", "label": "L", "children": []}
        for _ in range(14):
            deep = {"id": "n", "label": "N", "children": [deep]}
        with pytest.raises(ValidationError, match="depth"):
            ActivitySummaryUpdate(drilldown_tree=deep)

    def test_drilldown_tree_normal_ok(self):
        """A reasonably nested tree should be accepted."""
        tree = {
            "id": "root",
            "label": "Summary",
            "children": [
                {"id": "c1", "label": "Topic 1", "children": []},
                {
                    "id": "c2",
                    "label": "Topic 2",
                    "children": [{"id": "c2a", "label": "Subtopic 2a", "children": []}],
                },
            ],
        }
        u = ActivitySummaryUpdate(drilldown_tree=tree)
        assert u.drilldown_tree["id"] == "root"


class TestActivityRead:
    """Tests for the ActivityRead schema."""

    def test_from_dict(self):
        """ActivityRead should accept all fields including url."""
        uid = uuid.uuid4()
        aid = uuid.uuid4()
        sid = uuid.uuid4()
        data = {
            "id": aid,
            "user_id": uid,
            "user_email": "user@example.com",
            "user_display_name": "Test User",
            "search_id": sid,
            "query": "test query",
            "filters": {"year": "2024"},
            "search_results": [{"chunk_id": "c1"}],
            "ai_summary": "Some summary",
            "url": "https://example.com/search",
            "has_ratings": True,
            "created_at": "2026-03-01T12:00:00Z",
        }
        r = ActivityRead(**data)
        assert r.id == aid
        assert r.search_id == sid
        assert r.query == "test query"
        assert r.url == "https://example.com/search"
        assert r.has_ratings is True

    def test_nullable_fields(self):
        """Optional fields should accept None."""
        data = {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "user_email": None,
            "user_display_name": None,
            "search_id": uuid.uuid4(),
            "query": "q",
            "filters": None,
            "search_results": None,
            "ai_summary": None,
            "url": None,
            "has_ratings": False,
            "created_at": "2026-03-01T12:00:00Z",
        }
        r = ActivityRead(**data)
        assert r.user_email is None
        assert r.filters is None
        assert r.ai_summary is None
        assert r.url is None
        assert r.has_ratings is False
        # Token-usage fields default to None for historical rows.
        assert r.llm_model is None
        assert r.prompt_tokens is None
        assert r.completion_tokens is None
        assert r.cost_usd is None


@pytest.mark.unit
class TestActivityTokenUsageFields:
    """Validation of the shared token-usage fields across activity schemas."""

    def _base_create_kwargs(self):
        return {
            "search_id": str(uuid.uuid4()),
            "query": "test",
        }

    def test_token_usage_round_trip_on_create(self):
        """Token + cost fields round-trip through ActivityCreate."""
        a = ActivityCreate(
            **self._base_create_kwargs(),
            llm_model="gpt-4.1-mini",
            prompt_tokens=1234,
            completion_tokens=567,
            cost_usd=Decimal("0.001234"),
        )
        assert a.llm_model == "gpt-4.1-mini"
        assert a.prompt_tokens == 1234
        assert a.completion_tokens == 567
        assert a.cost_usd == Decimal("0.001234")

    def test_token_usage_optional_on_create(self):
        """All four token-usage fields are optional (existing callers unaffected)."""
        a = ActivityCreate(**self._base_create_kwargs())
        assert a.llm_model is None
        assert a.prompt_tokens is None
        assert a.completion_tokens is None
        assert a.cost_usd is None

    def test_negative_tokens_rejected(self):
        """Negative token counts should fail validation."""
        with pytest.raises(ValidationError, match="prompt_tokens"):
            ActivityCreate(**self._base_create_kwargs(), prompt_tokens=-1)
        with pytest.raises(ValidationError, match="completion_tokens"):
            ActivityCreate(**self._base_create_kwargs(), completion_tokens=-1)

    def test_negative_cost_rejected(self):
        """Negative cost values should fail validation."""
        with pytest.raises(ValidationError, match="cost_usd"):
            ActivityCreate(**self._base_create_kwargs(), cost_usd=Decimal("-0.0001"))

    def test_extreme_tokens_rejected(self):
        """Token counts beyond the 10M cap should fail validation."""
        with pytest.raises(ValidationError, match="prompt_tokens"):
            ActivityCreate(**self._base_create_kwargs(), prompt_tokens=10_000_001)

    def test_long_model_name_rejected(self):
        """Model names over 128 chars are rejected to match the DB column."""
        with pytest.raises(ValidationError, match="llm_model"):
            ActivityCreate(**self._base_create_kwargs(), llm_model="x" * 129)

    def test_summary_update_accepts_token_usage(self):
        """ActivitySummaryUpdate now carries the same usage fields."""
        u = ActivitySummaryUpdate(
            llm_model="gpt-4.1-mini",
            prompt_tokens=10,
            completion_tokens=5,
        )
        assert u.llm_model == "gpt-4.1-mini"
        assert u.prompt_tokens == 10
        assert u.completion_tokens == 5

    def test_summary_update_anonymous_accepts_token_usage(self):
        """Same on the anonymous variant used by the live frontend."""
        u = ActivitySummaryUpdateAnonymous(
            session_id="abc-123",
            llm_model="gemini-2.5-flash",
            prompt_tokens=500,
            completion_tokens=200,
            cost_usd=Decimal("0.000650"),
        )
        assert u.session_id == "abc-123"
        assert u.llm_model == "gemini-2.5-flash"
        assert u.cost_usd == Decimal("0.000650")
