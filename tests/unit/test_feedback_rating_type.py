"""Tests for the page_feedback rating type used by the feedback button."""

import pytest
from pydantic import ValidationError

from ui.backend.auth.schemas import VALID_RATING_TYPES, RatingCreate

pytestmark = pytest.mark.unit


class TestPageFeedbackRatingType:
    def test_page_feedback_in_valid_types(self):
        assert "page_feedback" in VALID_RATING_TYPES

    def test_rating_create_accepts_page_feedback(self):
        body = RatingCreate(
            rating_type="page_feedback",
            reference_id="https://example.com/search?q=foo",
            score=3,
            comment="The export button is hidden on mobile.",
            url="https://example.com/search?q=foo",
            context={"screenshot": "data:image/jpeg;base64,/9j/4AAQ"},
        )
        assert body.rating_type == "page_feedback"
        assert body.comment.startswith("The export")
        assert body.context["screenshot"].startswith("data:image/jpeg")

    def test_rating_create_rejects_unknown_type(self):
        with pytest.raises(ValidationError) as exc:
            RatingCreate(
                rating_type="not_a_real_type",
                reference_id="x",
                score=3,
            )
        assert "rating_type" in str(exc.value)

    def test_rating_create_rejects_oversized_screenshot(self):
        # Server cap is 200_000 chars when JSONB is serialized — anything larger
        # must be rejected before it hits Postgres.
        oversized = "x" * 201_000
        with pytest.raises(ValidationError):
            RatingCreate(
                rating_type="page_feedback",
                reference_id="x",
                score=3,
                context={"screenshot": oversized},
            )
