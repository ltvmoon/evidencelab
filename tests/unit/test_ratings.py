"""Tests for ratings schemas and validation."""

import uuid

import pytest
from pydantic import ValidationError

from ui.backend.auth.schemas import (
    VALID_RATING_TYPES,
    VALID_RESPONSE_STATUSES,
    RatingCreate,
    RatingRead,
    RatingResponseUpdate,
)


class TestRatingCreate:
    """Tests for the RatingCreate schema."""

    def test_valid_rating_minimal(self):
        """A minimal rating with required fields only."""
        r = RatingCreate(
            rating_type="search_result",
            reference_id="abc-123",
            score=4,
        )
        assert r.rating_type == "search_result"
        assert r.reference_id == "abc-123"
        assert r.score == 4
        assert r.item_id is None
        assert r.comment is None
        assert r.context is None
        assert r.url is None

    def test_valid_rating_all_fields(self):
        """A rating with all optional fields populated."""
        r = RatingCreate(
            rating_type="ai_summary",
            reference_id=str(uuid.uuid4()),
            item_id="chunk-xyz",
            score=5,
            comment="Very helpful summary.",
            context={"query": "test query", "filters": {}},
            url="https://example.com/search?q=test",
        )
        assert r.rating_type == "ai_summary"
        assert r.score == 5
        assert r.comment == "Very helpful summary."
        assert r.url == "https://example.com/search?q=test"

    @pytest.mark.parametrize("rtype", sorted(VALID_RATING_TYPES))
    def test_all_valid_rating_types(self, rtype: str):
        """Each valid rating type should be accepted."""
        r = RatingCreate(rating_type=rtype, reference_id="ref", score=3)
        assert r.rating_type == rtype

    def test_invalid_rating_type(self):
        """An unknown rating_type should be rejected."""
        with pytest.raises(ValidationError, match="rating_type"):
            RatingCreate(rating_type="invalid_type", reference_id="ref", score=3)

    def test_score_too_low(self):
        """Score below 1 should be rejected."""
        with pytest.raises(ValidationError, match="score"):
            RatingCreate(rating_type="search_result", reference_id="ref", score=0)

    def test_score_too_high(self):
        """Score above 5 should be rejected."""
        with pytest.raises(ValidationError, match="score"):
            RatingCreate(rating_type="search_result", reference_id="ref", score=6)

    @pytest.mark.parametrize("score", [1, 2, 3, 4, 5])
    def test_valid_score_range(self, score: int):
        """Scores 1-5 should all be accepted."""
        r = RatingCreate(rating_type="search_result", reference_id="ref", score=score)
        assert r.score == score

    def test_comment_max_length(self):
        """Comment exceeding 2000 chars should be rejected."""
        with pytest.raises(ValidationError, match="comment"):
            RatingCreate(
                rating_type="search_result",
                reference_id="ref",
                score=3,
                comment="x" * 2001,
            )

    def test_comment_at_max_length(self):
        """Comment at exactly 2000 chars should be accepted."""
        r = RatingCreate(
            rating_type="search_result",
            reference_id="ref",
            score=3,
            comment="x" * 2000,
        )
        assert len(r.comment) == 2000

    def test_reference_id_max_length(self):
        """reference_id exceeding 255 chars should be rejected."""
        with pytest.raises(ValidationError, match="reference_id"):
            RatingCreate(
                rating_type="search_result",
                reference_id="x" * 256,
                score=3,
            )

    def test_item_id_max_length(self):
        """item_id exceeding 255 chars should be rejected."""
        with pytest.raises(ValidationError, match="item_id"):
            RatingCreate(
                rating_type="search_result",
                reference_id="ref",
                item_id="x" * 256,
                score=3,
            )

    def test_url_max_length(self):
        """url exceeding 2000 chars should be rejected."""
        with pytest.raises(ValidationError, match="url"):
            RatingCreate(
                rating_type="search_result",
                reference_id="ref",
                score=3,
                url="https://example.com/" + "x" * 2000,
            )

    def test_context_jsonb_depth_limit(self):
        """Deeply nested context dict should be rejected."""
        deep = {"a": "leaf"}
        for _ in range(14):
            deep = {"nested": deep}
        with pytest.raises(ValidationError, match="depth"):
            RatingCreate(
                rating_type="search_result",
                reference_id="ref",
                score=3,
                context=deep,
            )

    def test_context_jsonb_size_limit(self):
        """Extremely large context payload should be rejected."""
        huge = {"data": "x" * 1_100_000}
        with pytest.raises(ValidationError, match="size"):
            RatingCreate(
                rating_type="search_result",
                reference_id="ref",
                score=3,
                context=huge,
            )

    def test_context_normal_ok(self):
        """A reasonably sized context dict should be accepted."""
        ctx = {"query": "test", "results_snapshot": [{"id": i} for i in range(50)]}
        r = RatingCreate(
            rating_type="search_result",
            reference_id="ref",
            score=3,
            context=ctx,
        )
        assert r.context["query"] == "test"


class TestRatingRead:
    """Tests for the RatingRead schema."""

    def test_from_dict(self):
        """RatingRead should accept all fields including url."""
        uid = uuid.uuid4()
        rid = uuid.uuid4()
        data = {
            "id": rid,
            "user_id": uid,
            "user_email": "user@example.com",
            "user_display_name": "Test User",
            "rating_type": "search_result",
            "reference_id": "ref-123",
            "item_id": "chunk-1",
            "score": 4,
            "comment": "Good result",
            "context": {"query": "test"},
            "url": "https://example.com",
            "created_at": "2026-03-01T12:00:00Z",
            "updated_at": "2026-03-01T12:00:00Z",
        }
        r = RatingRead(**data)
        assert r.id == rid
        assert r.user_email == "user@example.com"
        assert r.url == "https://example.com"
        assert r.score == 4


class TestValidRatingTypes:
    """Tests for the VALID_RATING_TYPES constant."""

    def test_expected_types(self):
        """Ensure all expected rating types are present."""
        expected = {
            "search_result",
            "ai_summary",
            "doc_summary",
            "taxonomy",
            "heatmap",
            "chat",
            "assistant-basic",
            "assistant-deep-research",
            "page_feedback",
        }
        assert VALID_RATING_TYPES == expected

    def test_types_are_strings(self):
        """All types should be strings."""
        for t in VALID_RATING_TYPES:
            assert isinstance(t, str)


class TestRatingResponseUpdate:
    """Tests for the RatingResponseUpdate admin-triage schema."""

    def test_accepts_all_valid_statuses(self):
        """Every value in VALID_RESPONSE_STATUSES must be accepted."""
        for status in VALID_RESPONSE_STATUSES:
            payload = RatingResponseUpdate(response_status=status)
            assert payload.response_status == status

    def test_rejects_unknown_status(self):
        """Unknown status values raise ValidationError."""
        with pytest.raises(ValidationError) as exc:
            RatingResponseUpdate(response_status="bogus")
        assert "response_status must be one of" in str(exc.value)

    def test_empty_string_normalized_to_none(self):
        """Empty string status normalizes to None so callers can clear it."""
        payload = RatingResponseUpdate(response_status="")
        assert payload.response_status is None

    def test_none_status_allowed(self):
        """Explicitly passing None clears the status."""
        payload = RatingResponseUpdate(response_status=None, response_notes=None)
        assert payload.response_status is None
        assert payload.response_notes is None

    def test_notes_only_without_status(self):
        """Notes can be set without a status (e.g. a quick comment)."""
        payload = RatingResponseUpdate(response_notes="Need to follow up tomorrow")
        assert payload.response_status is None
        assert payload.response_notes == "Need to follow up tomorrow"

    def test_status_and_notes_together(self):
        """Both fields may be set in a single payload."""
        payload = RatingResponseUpdate(
            response_status="resolved",
            response_notes="Fixed in v1.6 — closing.",
        )
        assert payload.response_status == "resolved"
        assert payload.response_notes == "Fixed in v1.6 — closing."

    def test_notes_max_length_enforced(self):
        """Notes longer than 4000 chars are rejected."""
        with pytest.raises(ValidationError):
            RatingResponseUpdate(response_notes="x" * 4001)


class TestValidResponseStatuses:
    """Smoke check for the VALID_RESPONSE_STATUSES tuple."""

    def test_expected_set(self):
        """Must mirror the labels exposed to the frontend."""
        assert set(VALID_RESPONSE_STATUSES) == {
            "open",
            "acknowledged",
            "info_needed",
            "resolved",
            "wontfix",
        }

    def test_first_is_open(self):
        """`open` is documented as the default ordering anchor."""
        assert VALID_RESPONSE_STATUSES[0] == "open"
