"""Tests for schema models."""

import pytest
from db_diagram.models import Table, get_qualified_table_name


class TestGetQualifiedTableName:
    """Tests for the get_qualified_table_name helper."""

    def test_returns_name_when_no_schema(self):
        table = Table(name="users")
        assert get_qualified_table_name(table) == "users"

    def test_returns_qualified_name_when_schema_present(self):
        table = Table(name="users", schema="public")
        assert get_qualified_table_name(table) == "public.users"

    def test_handles_none_schema(self):
        table = Table(name="users", schema=None)
        assert get_qualified_table_name(table) == "users"

    def test_handles_empty_string_schema(self):
        table = Table(name="users", schema="")
        assert get_qualified_table_name(table) == "users"
