"""
Unit tests for ParseProcessor glyph contamination detection and pypdf fallback.

Tests cover:
- _fix_glyph_contamination: glyph detection threshold and pypdf rebuild
"""

from unittest.mock import MagicMock, patch

from pipeline.processors.parsing.parser import ParseProcessor
from pipeline.processors.parsing.parser_constants import PAGE_SEPARATOR


def _make_parser():
    """Create a ParseProcessor without initialising Docling converter."""
    with patch.object(ParseProcessor, "setup"):
        p = ParseProcessor.__new__(ParseProcessor)
        p.name = "ParseProcessor"
        return p


class TestGlyphDetection:
    """Test _fix_glyph_contamination detects and fixes glyph content."""

    def test_no_glyphs_unchanged(self, tmp_path):
        """Clean markdown should not be modified."""
        md = tmp_path / "doc.md"
        original = "This is a perfectly clean document with real text content."
        md.write_text(original)

        parser = _make_parser()
        result = parser._fix_glyph_contamination(md, str(tmp_path / "doc.pdf"))

        assert result is False
        assert md.read_text() == original

    def test_below_threshold_unchanged(self, tmp_path):
        """Markdown with glyphs below 30% threshold should not trigger fallback."""
        md = tmp_path / "doc.md"
        real_text = "A" * 800
        glyph_text = "/gid00028/gid01154" * 10  # 180 chars = ~18% of 980
        original = real_text + glyph_text
        md.write_text(original)

        parser = _make_parser()
        result = parser._fix_glyph_contamination(md, str(tmp_path / "doc.pdf"))

        assert result is False
        assert md.read_text() == original

    @patch("pipeline.processors.parsing.parser.PdfReader")
    def test_glyph_contamination_triggers_fallback(self, mock_reader_cls, tmp_path):
        """Markdown with >30% glyphs should be rebuilt from pypdf."""
        md = tmp_path / "doc.md"
        # 90% glyphs
        glyph_text = "/gid00028" * 100  # 900 chars
        real_text = "X" * 100
        md.write_text(glyph_text + real_text)

        # Mock pypdf
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Page one content here."
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Page two content here."
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page1, mock_page2]
        mock_reader_cls.return_value = mock_reader

        pdf_path = str(tmp_path / "doc.pdf")
        parser = _make_parser()
        result = parser._fix_glyph_contamination(md, pdf_path)

        assert result is True
        rebuilt = md.read_text()
        assert "Page one content here." in rebuilt
        assert "Page two content here." in rebuilt
        assert PAGE_SEPARATOR in rebuilt
        assert "/gid00028" not in rebuilt
        mock_reader_cls.assert_called_once_with(pdf_path)

    def test_non_pdf_not_called(self, tmp_path):
        """The method itself works on any file, but the caller gates on .pdf.

        Verify the method returns False for content without glyphs (simulating
        a non-PDF that would never have glyph contamination).
        """
        md = tmp_path / "doc.md"
        md.write_text("Normal DOCX content without any glyph patterns.")

        parser = _make_parser()
        result = parser._fix_glyph_contamination(md, str(tmp_path / "doc.docx"))

        assert result is False

    @patch("pipeline.processors.parsing.parser.PdfReader")
    def test_pypdf_empty_keeps_original(self, mock_reader_cls, tmp_path):
        """If pypdf extracts no text, keep the original markdown."""
        md = tmp_path / "doc.md"
        original = "/gid00028" * 200  # heavy glyphs
        md.write_text(original)

        mock_reader = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        mock_reader.pages = [mock_page]
        mock_reader_cls.return_value = mock_reader

        parser = _make_parser()
        result = parser._fix_glyph_contamination(md, str(tmp_path / "doc.pdf"))

        assert result is False
        assert md.read_text() == original

    @patch("pipeline.processors.parsing.parser.PdfReader")
    def test_pypdf_exception_keeps_original(self, mock_reader_cls, tmp_path):
        """If pypdf raises, keep the original markdown."""
        md = tmp_path / "doc.md"
        original = "/gid00028" * 200
        md.write_text(original)

        mock_reader_cls.side_effect = Exception("corrupt pdf")

        parser = _make_parser()
        result = parser._fix_glyph_contamination(md, str(tmp_path / "doc.pdf"))

        assert result is False
        assert md.read_text() == original

    def test_short_content_skipped(self, tmp_path):
        """Very short markdown files should be skipped."""
        md = tmp_path / "doc.md"
        md.write_text("/gid00028" * 5)  # 45 chars, below 200 min

        parser = _make_parser()
        result = parser._fix_glyph_contamination(md, str(tmp_path / "doc.pdf"))

        assert result is False
