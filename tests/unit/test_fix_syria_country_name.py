"""Unit tests for the Syria country rename helpers.

Locks in the token-precise rewrite logic so a future tweak can't
accidentally mangle 'Syrian Arab Republic' (which contains 'Syria' as
a substring) or rewrite a body-text mention of Syria.
"""

import importlib.util
from pathlib import Path

import pytest

# Load the script as a module — it lives under scripts/fixes/, not
# under a package, so we import via spec.
_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "fixes"
    / "fix_syria_country_name.py"
)
_spec = importlib.util.spec_from_file_location("fix_syria_country_name", _SCRIPT_PATH)
fix_syria = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fix_syria)


@pytest.mark.unit
class TestRewriteCountryString:
    """String form: '; '-separated country lists."""

    def test_bare_token_in_list_is_rewritten(self):
        assert (
            fix_syria.rewrite_country("Türkiye; Syria")
            == "Türkiye; Syrian Arab Republic"
        )

    def test_bare_token_alone_is_rewritten(self):
        assert fix_syria.rewrite_country("Syria") == "Syrian Arab Republic"

    def test_already_correct_value_is_unchanged(self):
        # Idempotence — value must come back identical (same object even).
        v = "Türkiye; Syrian Arab Republic"
        assert fix_syria.rewrite_country(v) is v

    def test_syrian_arab_republic_substring_is_not_partially_rewritten(self):
        # 'Syrian Arab Republic' contains 'Syria' as a substring; the
        # token-precise rewrite must leave it alone.
        v = "Iraq; Syrian Arab Republic; Lebanon"
        assert fix_syria.rewrite_country(v) is v

    def test_body_text_mention_in_value_is_not_rewritten(self):
        # If someone ever crammed prose into the country field, the
        # rewriter still only touches an EXACT 'Syria' token. A token
        # like 'Syrian crisis' would not be rewritten because its
        # stripped form != 'Syria'.
        v = "Syrian crisis context"
        assert fix_syria.rewrite_country(v) is v

    def test_multi_position_token(self):
        assert (
            fix_syria.rewrite_country("Syria; Iraq; Türkiye")
            == "Syrian Arab Republic; Iraq; Türkiye"
        )

    def test_empty_and_none_passthrough(self):
        assert fix_syria.rewrite_country("") == ""
        assert fix_syria.rewrite_country(None) is None


@pytest.mark.unit
class TestRewriteCountryList:
    """List form: some Qdrant payloads store countries as a list."""

    def test_bare_token_in_list_is_rewritten(self):
        assert fix_syria.rewrite_country(["Türkiye", "Syria"]) == [
            "Türkiye",
            "Syrian Arab Republic",
        ]

    def test_already_correct_list_is_unchanged(self):
        v = ["Türkiye", "Syrian Arab Republic"]
        assert fix_syria.rewrite_country(v) is v

    def test_list_without_syria_is_unchanged(self):
        v = ["Bangladesh", "Chad", "Iraq"]
        assert fix_syria.rewrite_country(v) is v

    def test_non_string_items_in_list_are_passed_through(self):
        # Defensive — never crash on weird payload contents, just leave
        # non-string items alone.
        v = ["Syria", None, 42]
        assert fix_syria.rewrite_country(v) == ["Syrian Arab Republic", None, 42]


@pytest.mark.unit
class TestNeedsRewrite:
    def test_true_for_bare_token(self):
        assert fix_syria.needs_rewrite("Türkiye; Syria") is True

    def test_false_for_full_name(self):
        assert fix_syria.needs_rewrite("Syrian Arab Republic") is False

    def test_false_for_unrelated_value(self):
        assert fix_syria.needs_rewrite("Iraq; Lebanon") is False

    def test_false_for_none(self):
        assert fix_syria.needs_rewrite(None) is False
