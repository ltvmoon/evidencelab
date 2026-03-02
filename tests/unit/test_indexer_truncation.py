"""
Unit tests for IndexProcessor chunk validation and max_embed_tokens computation.

Tests cover:
- _compute_max_embed_tokens: config-driven token limit derivation
- _filter_valid_chunks: empty-chunk filtering and oversized-chunk rejection
"""

from unittest.mock import MagicMock, patch

import pytest

from pipeline.processors.indexing.indexer import IndexProcessor


class TestComputeMaxEmbedTokens:
    """Test _compute_max_embed_tokens derives the right token limit."""

    def _make_processor(self):
        """Create an IndexProcessor without triggering DB or model loading."""
        chunk_config = {
            "dense_model": "intfloat/multilingual-e5-large",
            "max_tokens": 450,
        }
        with patch("pipeline.processors.indexing.indexer.get_db"), patch(
            "pipeline.processors.indexing.indexer.PostgresClient"
        ):
            return IndexProcessor(chunk_config=chunk_config)

    def test_uses_smallest_model_limit(self):
        """When multiple models have max_tokens, use the smallest."""
        proc = self._make_processor()
        fake_vectors = {
            "azure_small": {"max_tokens": 8192},
            "azure_large": {"max_tokens": 8192},
            "e5_large": {"max_tokens": 512},
        }
        with patch("pipeline.processors.indexing.indexer.DB_VECTORS", fake_vectors):
            result = proc._compute_max_embed_tokens(
                ["azure_small", "azure_large", "e5_large"]
            )
        assert result == 512

    def test_single_model_with_max_tokens(self):
        """Single target model with max_tokens configured."""
        proc = self._make_processor()
        fake_vectors = {"azure_small": {"max_tokens": 8192}}
        with patch("pipeline.processors.indexing.indexer.DB_VECTORS", fake_vectors):
            result = proc._compute_max_embed_tokens(["azure_small"])
        assert result == 8192

    def test_raises_when_model_missing_max_tokens(self):
        """Models without max_tokens raise ValueError."""
        proc = self._make_processor()
        fake_vectors = {"e5_large": {"size": 1024, "model_id": "e5"}}
        with patch("pipeline.processors.indexing.indexer.DB_VECTORS", fake_vectors):
            with pytest.raises(ValueError, match="no 'max_tokens'"):
                proc._compute_max_embed_tokens(["e5_large"])

    def test_raises_when_model_not_in_registry(self):
        """A target not in DB_VECTORS raises ValueError."""
        proc = self._make_processor()
        fake_vectors = {"azure_small": {"max_tokens": 8192}}
        with patch("pipeline.processors.indexing.indexer.DB_VECTORS", fake_vectors):
            with pytest.raises(ValueError, match="no 'max_tokens'"):
                proc._compute_max_embed_tokens(["azure_small", "nonexistent"])


class TestFilterValidChunks:
    """Test _filter_valid_chunks removes empty chunks and rejects oversized ones."""

    def _make_processor(self, max_embed_tokens=None):
        chunk_config = {
            "dense_model": "intfloat/multilingual-e5-large",
            "max_tokens": 450,
        }
        with patch("pipeline.processors.indexing.indexer.get_db"), patch(
            "pipeline.processors.indexing.indexer.PostgresClient"
        ):
            proc = IndexProcessor(chunk_config=chunk_config)
        # Mock tokenizer: each word = 1 token (split on whitespace)
        mock_tok = MagicMock()
        mock_tok.encode.side_effect = lambda text, **kw: text.split()
        proc._tokenizer = mock_tok
        if max_embed_tokens is not None:
            proc._max_embed_tokens = max_embed_tokens
        return proc

    def test_filters_empty_chunks(self):
        """Chunks with empty or whitespace-only text are removed."""
        proc = self._make_processor(max_embed_tokens=100000)
        chunks = [
            {"text": "valid text"},
            {"text": ""},
            {"text": "   "},
            {"text": "also valid"},
        ]
        result = proc._filter_valid_chunks(chunks)
        assert len(result) == 2
        assert result[0]["text"] == "valid text"
        assert result[1]["text"] == "also valid"

    def test_rejects_oversized_chunks(self):
        """Chunks exceeding max_embed_tokens raise ValueError."""
        proc = self._make_processor(max_embed_tokens=5)
        # 10 words = 10 tokens (mock tokenizer splits on whitespace)
        long_text = " ".join(["word"] * 10)
        chunks = [{"text": long_text}]
        with pytest.raises(ValueError, match="exceed embedding model limit"):
            proc._filter_valid_chunks(chunks)

    def test_does_not_reject_short_chunks(self):
        """Chunks within the limit are left unchanged."""
        proc = self._make_processor(max_embed_tokens=100)
        text = "short chunk"
        chunks = [{"text": text}]
        result = proc._filter_valid_chunks(chunks)
        assert result[0]["text"] == text

    def test_exact_boundary_passes(self):
        """A chunk exactly at the limit is not rejected."""
        proc = self._make_processor(max_embed_tokens=5)
        text = " ".join(["word"] * 5)  # 5 tokens
        chunks = [{"text": text}]
        result = proc._filter_valid_chunks(chunks)
        assert result[0]["text"] == text

    def test_mixed_chunks_oversized_causes_failure(self):
        """Any oversized chunk causes the entire batch to fail."""
        proc = self._make_processor(max_embed_tokens=5)
        chunks = [
            {"text": "short"},
            {"text": " ".join(["word"] * 10)},  # 10 tokens > 5
            {"text": "normal length text here"},
            {"text": " ".join(["word"] * 8)},  # 8 tokens > 5
        ]
        with pytest.raises(ValueError, match="2 chunk\\(s\\) exceed"):
            proc._filter_valid_chunks(chunks)

    def test_aborts_when_max_embed_tokens_not_set(self):
        """Raises ValueError when _max_embed_tokens is not set."""
        proc = self._make_processor()
        # Remove _max_embed_tokens to test abort
        if hasattr(proc, "_max_embed_tokens"):
            delattr(proc, "_max_embed_tokens")
        chunks = [{"text": "any text"}]
        with pytest.raises(ValueError, match="_max_embed_tokens not set"):
            proc._filter_valid_chunks(chunks)
