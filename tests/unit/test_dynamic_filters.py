"""Tests for _add_dynamic_filters in ui.backend.routes.search."""

from unittest.mock import patch

from ui.backend.routes.search import _add_dynamic_filters

MOCK_FILTER_FIELDS = {
    "organization": "Organization",
    "title": "Document Title",
    "published_year": "Year Published",
    "document_type": "Document Type",
    "country": "Country",
    "src_geographic_scope": "Geographic Scope",
    "tag_sdg": "United Nations Sustainable Development Goals",
    "tag_cross_cutting_theme": "Cross-cutting Themes",
    "language": "Language",
}


def _make_query_params(params: dict):
    """Simulate Starlette QueryParams (dict-like with .items())."""
    return params


@patch(
    "ui.backend.routes.search.get_filter_fields",
    return_value=MOCK_FILTER_FIELDS,
)
def test_picks_up_src_fields(mock_get):
    core = {}
    _add_dynamic_filters(
        core,
        _make_query_params({"src_geographic_scope": "Global"}),
        "uneg",
    )
    assert core == {"src_geographic_scope": "Global"}


@patch(
    "ui.backend.routes.search.get_filter_fields",
    return_value=MOCK_FILTER_FIELDS,
)
def test_picks_up_tag_fields(mock_get):
    core = {}
    _add_dynamic_filters(
        core,
        _make_query_params({"tag_sdg": "sdg1,sdg3"}),
        "uneg",
    )
    assert core == {"tag_sdg": "sdg1,sdg3"}


@patch(
    "ui.backend.routes.search.get_filter_fields",
    return_value=MOCK_FILTER_FIELDS,
)
def test_picks_up_multiple_dynamic_fields(mock_get):
    core = {}
    _add_dynamic_filters(
        core,
        _make_query_params(
            {
                "src_geographic_scope": "Regional",
                "tag_cross_cutting_theme": "gender_equality",
            }
        ),
        "uneg",
    )
    assert core == {
        "src_geographic_scope": "Regional",
        "tag_cross_cutting_theme": "gender_equality",
    }


@patch(
    "ui.backend.routes.search.get_filter_fields",
    return_value=MOCK_FILTER_FIELDS,
)
def test_ignores_params_not_in_config(mock_get):
    core = {}
    _add_dynamic_filters(
        core,
        _make_query_params({"unknown_field": "value"}),
        "uneg",
    )
    assert core == {}


@patch(
    "ui.backend.routes.search.get_filter_fields",
    return_value=MOCK_FILTER_FIELDS,
)
def test_does_not_duplicate_hardcoded_core_fields(mock_get):
    core = {"organization": "UNDP"}
    _add_dynamic_filters(
        core,
        _make_query_params(
            {
                "organization": "WFP",
                "country": "Kenya",
                "tag_sdg": "sdg5",
            }
        ),
        "uneg",
    )
    # organization and country are hardcoded — should not be overwritten
    assert core == {"organization": "UNDP", "tag_sdg": "sdg5"}


@patch(
    "ui.backend.routes.search.get_filter_fields",
    return_value=MOCK_FILTER_FIELDS,
)
def test_ignores_empty_values(mock_get):
    core = {}
    _add_dynamic_filters(
        core,
        _make_query_params({"src_geographic_scope": "", "tag_sdg": "sdg1"}),
        "uneg",
    )
    assert core == {"tag_sdg": "sdg1"}


@patch(
    "ui.backend.routes.search.get_filter_fields",
    return_value=MOCK_FILTER_FIELDS,
)
def test_defaults_to_uneg_when_no_data_source(mock_get):
    core = {}
    _add_dynamic_filters(
        core,
        _make_query_params({"tag_sdg": "sdg2"}),
    )
    mock_get.assert_called_once_with("uneg")
    assert core == {"tag_sdg": "sdg2"}


@patch(
    "ui.backend.routes.search.get_filter_fields",
    return_value=MOCK_FILTER_FIELDS,
)
def test_preserves_existing_core_filters(mock_get):
    core = {"organization": "UNICEF", "title": "Report"}
    _add_dynamic_filters(
        core,
        _make_query_params({"src_geographic_scope": "National"}),
        "uneg",
    )
    assert core == {
        "organization": "UNICEF",
        "title": "Report",
        "src_geographic_scope": "National",
    }
