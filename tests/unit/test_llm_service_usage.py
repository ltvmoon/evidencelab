"""Tests for ``summarize_usage_metadata`` in the LLM service layer.

Uses an in-process stand-in for ``UsageMetadataCallbackHandler`` so the
test runs without a live LangChain provider — we only care about the
shape we surface to the route layer.
"""

from types import SimpleNamespace

import pytest

from ui.backend.services.llm_service import summarize_usage_metadata


def _handler(usage_metadata):
    """Build a fake handler exposing the ``usage_metadata`` attribute."""
    return SimpleNamespace(usage_metadata=usage_metadata)


@pytest.mark.unit
class TestSummarizeUsageMetadata:
    """Shape of the dict passed back to the route layer."""

    def test_single_model_payload(self):
        """Standard case: provider reports one model with both token counts."""
        handler = _handler(
            {"gpt-4.1-mini": {"input_tokens": 1234, "output_tokens": 567}}
        )
        out = summarize_usage_metadata(handler, model_key="gpt-4.1-mini")
        assert out == {
            "llm_model": "gpt-4.1-mini",
            "prompt_tokens": 1234,
            "completion_tokens": 567,
        }

    def test_sums_across_multiple_models(self):
        """Agent that hit two models accumulates totals (single-model rate)."""
        handler = _handler(
            {
                "model-a": {"input_tokens": 100, "output_tokens": 50},
                "model-b": {"input_tokens": 25, "output_tokens": 10},
            }
        )
        out = summarize_usage_metadata(handler, model_key="model-a")
        assert out["prompt_tokens"] == 125
        assert out["completion_tokens"] == 60
        assert out["llm_model"] == "model-a"

    def test_empty_usage_returns_just_model(self):
        """No reported usage → only the model_key is surfaced."""
        handler = _handler({})
        out = summarize_usage_metadata(handler, model_key="gemini-2.5-flash")
        assert out == {"llm_model": "gemini-2.5-flash"}

    def test_missing_model_key_returns_only_tokens(self):
        """No model_key → still surface tokens if the provider reported them."""
        handler = _handler({"some-model": {"input_tokens": 10, "output_tokens": 5}})
        out = summarize_usage_metadata(handler, model_key=None)
        assert out == {"prompt_tokens": 10, "completion_tokens": 5}

    def test_handler_with_no_usage_metadata_attribute(self):
        """Defensive: an object lacking the attribute returns an empty payload."""

        class Bare:
            pass

        out = summarize_usage_metadata(Bare(), model_key="gpt-4.1-mini")
        assert out == {"llm_model": "gpt-4.1-mini"}

    def test_zero_token_counts_omitted(self):
        """Zero counts are not emitted — keeps the payload tight."""
        handler = _handler({"m": {"input_tokens": 0, "output_tokens": 0}})
        out = summarize_usage_metadata(handler, model_key="m")
        assert "prompt_tokens" not in out
        assert "completion_tokens" not in out
        assert out["llm_model"] == "m"

    def test_missing_keys_treated_as_zero(self):
        """Some providers only fill one side; the other should not break us."""
        handler = _handler({"m": {"input_tokens": 7}})
        out = summarize_usage_metadata(handler, model_key="m")
        assert out["prompt_tokens"] == 7
        assert "completion_tokens" not in out
