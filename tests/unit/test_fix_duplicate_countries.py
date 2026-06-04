"""Unit tests for the duplicate-country cleanup helpers.

These pin down the pure functions that decide which surface forms get
collapsed and how rewrites are applied. The DB / Qdrant code paths are
exercised via the same helpers, so locking these in covers the safety-
critical behaviour without needing live services.
"""

import importlib.util
from pathlib import Path

import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "fixes"
    / "fix_duplicate_countries.py"
)
_spec = importlib.util.spec_from_file_location("fix_duplicate_countries", _SCRIPT_PATH)
fix_dupes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fix_dupes)


@pytest.mark.unit
class TestCanonicalKey:
    def test_trims_whitespace(self):
        assert fix_dupes.canonical_key("India ") == fix_dupes.canonical_key("India")

    def test_collapses_internal_whitespace(self):
        assert fix_dupes.canonical_key("South  Sudan") == fix_dupes.canonical_key(
            "South Sudan"
        )

    def test_casefolds(self):
        assert fix_dupes.canonical_key("INDIA") == fix_dupes.canonical_key("india")

    def test_strips_trailing_punctuation(self):
        assert fix_dupes.canonical_key("India,") == fix_dupes.canonical_key("India.")
        assert fix_dupes.canonical_key("India;") == fix_dupes.canonical_key("India")

    def test_diacritics_preserved(self):
        # Türkiye and Turkiye must NOT collide — they may be the same country
        # to a human but the script does not own that judgement.
        assert fix_dupes.canonical_key("Türkiye") != fix_dupes.canonical_key("Turkiye")

    def test_non_string_returns_empty(self):
        assert fix_dupes.canonical_key(None) == ""
        assert fix_dupes.canonical_key(42) == ""


@pytest.mark.unit
class TestTokenize:
    def test_splits_on_separator(self):
        assert fix_dupes.tokenize_country_value("Nepal; India") == ["Nepal", "India"]

    def test_strips_parts(self):
        # Trailing empty token after the final '; ' is dropped.
        assert fix_dupes.tokenize_country_value("Nepal; India; ") == ["Nepal", "India"]
        # Each part is .strip()-ed individually.
        assert fix_dupes.tokenize_country_value("  Nepal;  India  ") == [
            "Nepal",
            "India",
        ]

    def test_single_value_preserves_whitespace(self):
        # Critical: single-value rows must NOT be stripped here. Production
        # bucketizes them as-is, so "Bolivia " and "Bolivia" appear as two
        # distinct dropdown entries — they have to stay distinct tokens
        # for the clustering logic to detect them.
        assert fix_dupes.tokenize_country_value("Bolivia ") == ["Bolivia "]
        assert fix_dupes.tokenize_country_value("  India  ") == ["  India  "]

    def test_single_value(self):
        assert fix_dupes.tokenize_country_value("India") == ["India"]

    def test_list_passthrough(self):
        assert fix_dupes.tokenize_country_value(["India", " Nepal "]) == [
            "India",
            "Nepal",
        ]

    def test_empty_and_none(self):
        assert fix_dupes.tokenize_country_value("") == []
        assert fix_dupes.tokenize_country_value(None) == []


@pytest.mark.unit
class TestBuildRewriteMap:
    def test_most_common_wins(self):
        counts = {"India": 10, "india": 2, "India ": 1}
        rewrite = fix_dupes.build_rewrite_map(counts)
        assert rewrite == {"india": "India", "India ": "India"}

    def test_winner_not_in_map(self):
        counts = {"India": 10, "india": 1}
        assert "India" not in fix_dupes.build_rewrite_map(counts)

    def test_singleton_cluster_left_alone(self):
        counts = {"India": 5, "Nepal": 3}
        assert fix_dupes.build_rewrite_map(counts) == {}

    def test_diacritic_tiebreak_prefers_non_ascii(self):
        # Equal counts — non-ASCII variant should win the tie-break.
        counts = {"Türkiye": 3, "Turkiye": 3}
        # canonical keys differ (diacritics preserved), so no rewrite.
        # Force them into the same cluster by using values that only differ
        # in casing — diacritic tiebreak applies there.
        counts2 = {"São Tomé": 2, "são tomé": 2}
        rewrite = fix_dupes.build_rewrite_map(counts2)
        assert rewrite == {"são tomé": "São Tomé"}
        # And the original diacritic-different pair stays untouched:
        assert fix_dupes.build_rewrite_map(counts) == {}

    def test_min_group_size_threshold(self):
        counts = {"India": 10, "india": 2}
        assert fix_dupes.build_rewrite_map(counts, min_group_size=3) == {}
        assert fix_dupes.build_rewrite_map(counts, min_group_size=2) == {
            "india": "India"
        }

    def test_three_way_cluster(self):
        counts = {"India": 10, "india": 2, "India,": 1}
        rewrite = fix_dupes.build_rewrite_map(counts, min_group_size=3)
        assert rewrite == {"india": "India", "India,": "India"}


@pytest.mark.unit
class TestRewriteCountryValue:
    def test_simple_string_rewrite(self):
        rewrite = {"india": "India"}
        assert fix_dupes.rewrite_country_value("india", rewrite) == "India"

    def test_multi_value_string(self):
        rewrite = {"india": "India"}
        assert (
            fix_dupes.rewrite_country_value("Nepal; india", rewrite) == "Nepal; India"
        )

    def test_intra_value_dedup(self):
        # After rewrite, the same canonical token appears twice — collapse it.
        rewrite = {"india": "India"}
        assert (
            fix_dupes.rewrite_country_value("India; india; Nepal", rewrite)
            == "India; Nepal"
        )

    def test_preserves_order(self):
        rewrite = {"india": "India"}
        assert (
            fix_dupes.rewrite_country_value("Nepal; india; India; Bhutan", rewrite)
            == "Nepal; India; Bhutan"
        )

    def test_idempotent_returns_same_object(self):
        # No-op rewrites preserve identity so callers can cheaply skip writes.
        rewrite = {"india": "India"}
        v = "India; Nepal"
        assert fix_dupes.rewrite_country_value(v, rewrite) is v

    def test_idempotent_under_repeated_application(self):
        rewrite = {"india": "India"}
        once = fix_dupes.rewrite_country_value("Nepal; india", rewrite)
        twice = fix_dupes.rewrite_country_value(once, rewrite)
        assert once == twice == "Nepal; India"

    def test_list_value(self):
        rewrite = {"india": "India"}
        assert fix_dupes.rewrite_country_value(["Nepal", "india"], rewrite) == [
            "Nepal",
            "India",
        ]

    def test_list_dedup_after_rewrite(self):
        rewrite = {"india": "India"}
        assert fix_dupes.rewrite_country_value(
            ["India", "india", "Nepal"], rewrite
        ) == ["India", "Nepal"]

    def test_list_with_non_strings_passes_through(self):
        rewrite = {"india": "India"}
        v = ["India", None, 42]
        assert fix_dupes.rewrite_country_value(v, rewrite) is v

    def test_empty_and_none_passthrough(self):
        assert fix_dupes.rewrite_country_value("", {"a": "b"}) == ""
        assert fix_dupes.rewrite_country_value(None, {"a": "b"}) is None


@pytest.mark.unit
class TestSynonymRenamesTable:
    """The hardcoded SYNONYM_RENAMES table is a deliberate human decision;
    these tests lock in the entries so an accidental edit shows up loudly."""

    def test_tanzania(self):
        assert fix_dupes.SYNONYM_RENAMES["Tanzania"] == "United Republic of Tanzania"

    def test_kyrgyzstan(self):
        assert fix_dupes.SYNONYM_RENAMES["Kyrgyzstan"] == "Kyrgyz Republic"

    def test_bare_congo_is_roc(self):
        # Bare "Congo" must point to RoC (Brazzaville), not DRC. Getting
        # this backwards would silently corrupt country attribution.
        assert fix_dupes.SYNONYM_RENAMES["Congo"] == "Republic of the Congo"

    def test_drc_missing_the_is_drc(self):
        assert (
            fix_dupes.SYNONYM_RENAMES["Democratic Republic of Congo"]
            == "Democratic Republic of the Congo"
        )

    def test_burkina(self):
        assert fix_dupes.SYNONYM_RENAMES["Burkina"] == "Burkina Faso"

    def test_nicarague(self):
        assert fix_dupes.SYNONYM_RENAMES["Nicarague"] == "Nicaragua"

    def test_zambabwe_is_zimbabwe(self):
        # 'Zambabwe' appears in a row that already lists 'Zambia', so the
        # typo refers to the *other* country, Zimbabwe. Inverting this
        # would silently misroute documents — lock it in.
        assert fix_dupes.SYNONYM_RENAMES["Zambabwe"] == "Zimbabwe"


@pytest.mark.unit
class TestMergeWithSynonyms:
    def test_synonym_adds_to_auto_map(self):
        auto = {"india": "India"}
        synonyms = {"Tanzania": "United Republic of Tanzania"}
        merged = fix_dupes.merge_with_synonyms(auto, synonyms)
        assert merged == {
            "india": "India",
            "Tanzania": "United Republic of Tanzania",
        }

    def test_synonym_overrides_auto_for_same_source(self):
        # Auto would map X -> Y, but a synonym says X -> Z. The synonym wins.
        auto = {"Congo": "congo-auto-pick"}
        synonyms = {"Congo": "Republic of the Congo"}
        assert fix_dupes.merge_with_synonyms(auto, synonyms) == {
            "Congo": "Republic of the Congo"
        }

    def test_chain_is_flattened(self):
        # Auto: X -> Y, synonym: Y -> Z  =>  merged should give X -> Z.
        auto = {"India ": "India"}
        synonyms = {"India": "Republic of India"}
        merged = fix_dupes.merge_with_synonyms(auto, synonyms)
        assert merged == {
            "India ": "Republic of India",
            "India": "Republic of India",
        }

    def test_cycle_raises(self):
        # X -> Y, Y -> X is a real bug; surface it instead of looping forever.
        with pytest.raises(ValueError, match="cycle"):
            fix_dupes.merge_with_synonyms({"X": "Y"}, {"Y": "X"})

    def test_empty_synonyms_is_passthrough(self):
        auto = {"india": "India"}
        assert fix_dupes.merge_with_synonyms(auto, {}) == auto


@pytest.mark.unit
class TestRewriteWithSynonyms:
    """End-to-end: synonyms feed into the same rewrite path as auto clusters."""

    def test_synonym_applied_in_multi_value(self):
        rewrite = fix_dupes.merge_with_synonyms(
            {}, {"Tanzania": "United Republic of Tanzania"}
        )
        assert (
            fix_dupes.rewrite_country_value("Kenya; Tanzania; Uganda", rewrite)
            == "Kenya; United Republic of Tanzania; Uganda"
        )

    def test_synonym_applied_single_value(self):
        rewrite = fix_dupes.merge_with_synonyms({}, {"Congo": "Republic of the Congo"})
        assert (
            fix_dupes.rewrite_country_value("Congo", rewrite) == "Republic of the Congo"
        )

    def test_intra_row_dedup_after_synonym(self):
        # If a row already lists both the old and new form, synonym rewrite
        # collapses them to one entry.
        rewrite = fix_dupes.merge_with_synonyms(
            {}, {"Tanzania": "United Republic of Tanzania"}
        )
        assert (
            fix_dupes.rewrite_country_value(
                "Tanzania; United Republic of Tanzania; Kenya", rewrite
            )
            == "United Republic of Tanzania; Kenya"
        )


@pytest.mark.unit
class TestNeedsRewrite:
    def test_true_when_value_would_change(self):
        assert fix_dupes.needs_rewrite("india", {"india": "India"}) is True

    def test_false_when_no_match(self):
        assert fix_dupes.needs_rewrite("Nepal", {"india": "India"}) is False

    def test_false_for_none(self):
        assert fix_dupes.needs_rewrite(None, {"india": "India"}) is False
