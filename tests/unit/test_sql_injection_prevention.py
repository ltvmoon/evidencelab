"""Tests that sort_by and taxonomy filter parameters cannot inject SQL.

Regression tests for GitHub issue #264: SQL injection via sort_by
parameter interpolated into raw SQL, and taxonomy filter codes
interpolated into jsonb_path_exists expressions.
"""

from unittest.mock import MagicMock, patch

import pytest

from pipeline.db.postgres_client_docs import PostgresDocMixin


@pytest.fixture()
def client():
    """Create a PostgresDocMixin with mocked DB connection."""
    with patch.object(PostgresDocMixin, "__init__", lambda self: None):
        c = PostgresDocMixin.__new__(PostgresDocMixin)
        c.docs_table = "docs_test"
        c.data_source = "test"

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        c._get_conn = MagicMock(return_value=mock_conn)
        c._mock_cursor = mock_cursor
        return c


def _get_executed_sql(client):
    """Return the SQL string from the last cur.execute call."""
    return client._mock_cursor.execute.call_args[0][0]


# -- sort_by whitelist tests --------------------------------------------------


class TestSortByWhitelist:
    """sort_by must resolve to a hardcoded SQL fragment via dict lookup."""

    @pytest.mark.unit
    def test_sort_by_year(self, client):
        client._get_paginated_documents_impl(
            page=1,
            page_size=10,
            filters={},
            filter_map={},
            sort_by="year",
            sort_order="asc",
        )
        sql = _get_executed_sql(client)
        assert "ORDER BY map_published_year ASC" in sql

    @pytest.mark.unit
    def test_sort_by_title(self, client):
        client._get_paginated_documents_impl(
            page=1,
            page_size=10,
            filters={},
            filter_map={},
            sort_by="title",
            sort_order="desc",
        )
        sql = _get_executed_sql(client)
        assert "ORDER BY map_title DESC" in sql

    @pytest.mark.unit
    def test_sort_by_sdg(self, client):
        client._get_paginated_documents_impl(
            page=1,
            page_size=10,
            filters={},
            filter_map={},
            sort_by="sdg",
            sort_order="asc",
        )
        sql = _get_executed_sql(client)
        assert "ORDER BY COALESCE(sys_taxonomies->'sdg'" in sql

    @pytest.mark.unit
    def test_sort_by_cross_cutting_theme(self, client):
        client._get_paginated_documents_impl(
            page=1,
            page_size=10,
            filters={},
            filter_map={},
            sort_by="cross_cutting_theme",
            sort_order="asc",
        )
        sql = _get_executed_sql(client)
        assert "ORDER BY COALESCE(sys_taxonomies->'cross_cutting_theme'" in sql

    @pytest.mark.unit
    def test_sort_by_last_updated(self, client):
        client._get_paginated_documents_impl(
            page=1,
            page_size=10,
            filters={},
            filter_map={},
            sort_by="last_updated",
            sort_order="desc",
        )
        sql = _get_executed_sql(client)
        assert "ORDER BY COALESCE(to_timestamp(sys_last_updated)" in sql

    @pytest.mark.unit
    def test_sort_by_injection_falls_back_to_default(self, client):
        """Malicious sort_by value must not appear in generated SQL."""
        payload = "year'; DROP TABLE docs_test; --"
        client._get_paginated_documents_impl(
            page=1,
            page_size=10,
            filters={},
            filter_map={},
            sort_by=payload,
            sort_order="asc",
        )
        sql = _get_executed_sql(client)
        assert payload not in sql
        assert "DROP TABLE" not in sql
        assert "ORDER BY map_published_year ASC" in sql

    @pytest.mark.unit
    def test_sort_by_unknown_value_falls_back_to_default(self, client):
        client._get_paginated_documents_impl(
            page=1,
            page_size=10,
            filters={},
            filter_map={},
            sort_by="nonexistent_field",
            sort_order="asc",
        )
        sql = _get_executed_sql(client)
        assert "ORDER BY map_published_year ASC" in sql

    @pytest.mark.unit
    def test_sort_order_injection_normalised(self, client):
        """Malicious sort_order must not appear in generated SQL."""
        client._get_paginated_documents_impl(
            page=1,
            page_size=10,
            filters={},
            filter_map={},
            sort_by="year",
            sort_order="desc; DROP TABLE docs_test;--",
        )
        sql = _get_executed_sql(client)
        assert "DROP TABLE" not in sql
        assert "ORDER BY map_published_year ASC" in sql


# -- taxonomy clause tests ----------------------------------------------------


class TestTaxonomyClauseParameterised:
    """Taxonomy codes must be passed as query parameters, never interpolated."""

    @pytest.mark.unit
    def test_sdg_codes_are_parameterised(self):
        params = []
        clause = PostgresDocMixin._taxonomy_clause("sdg", ["sdg1", "sdg5"], params)
        assert clause is not None
        assert "sdg1" not in clause
        assert "sdg5" not in clause
        assert "%s" in clause
        assert params == ["sdg1", "sdg5"]

    @pytest.mark.unit
    def test_cross_cutting_theme_parameterised(self):
        params = []
        clause = PostgresDocMixin._taxonomy_clause(
            "cross_cutting_theme", ["gender"], params
        )
        assert clause is not None
        assert "gender" not in clause
        assert "%s" in clause
        assert params == ["gender"]

    @pytest.mark.unit
    def test_injection_in_code_value_is_parameterised(self):
        payload = "x')) OR 1=1 --"
        params = []
        clause = PostgresDocMixin._taxonomy_clause("sdg", [payload], params)
        assert clause is not None
        assert payload not in clause
        assert params == [payload]

    @pytest.mark.unit
    def test_disallowed_taxonomy_key_returns_none(self):
        params = []
        clause = PostgresDocMixin._taxonomy_clause("malicious_key", ["value"], params)
        assert clause is None
        assert params == []

    @pytest.mark.unit
    def test_empty_codes_returns_none(self):
        params = []
        clause = PostgresDocMixin._taxonomy_clause("sdg", [], params)
        assert clause is None

    @pytest.mark.unit
    def test_single_string_value_converted_to_list(self):
        params = []
        clause = PostgresDocMixin._taxonomy_clause("sdg", "sdg3", params)
        assert clause is not None
        assert params == ["sdg3"]

    @pytest.mark.unit
    def test_uses_jsonb_path_vars(self):
        params = []
        clause = PostgresDocMixin._taxonomy_clause("sdg", ["sdg1"], params)
        assert "jsonb_build_object" in clause
        assert "$v" in clause
