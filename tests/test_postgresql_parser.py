"""Tests for PostgreSQL parser."""

import pytest
from db_diagram.parsers.postgresql import PostgreSQLParser


class TestPostgreSQLParser:
    """Tests for the PostgreSQL parser."""

    @pytest.fixture
    def parser(self):
        return PostgreSQLParser()

    def test_parses_simple_table(self, parser):
        sql = """
            CREATE TABLE users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL
            );
        """
        schema = parser.parse(sql)

        assert len(schema.tables) == 1
        assert schema.tables[0].name == "users"
        assert len(schema.tables[0].columns) == 2
        assert schema.tables[0].columns[0].name == "id"
        assert schema.tables[0].columns[0].primary_key is True

    def test_parses_schema_qualified_table_names(self, parser):
        sql = """
            CREATE TABLE public.users (
                id SERIAL PRIMARY KEY
            );
            CREATE TABLE audit.users (
                id SERIAL PRIMARY KEY
            );
        """
        schema = parser.parse(sql)

        assert len(schema.tables) == 2
        assert schema.tables[0].name == "users"
        assert schema.tables[0].schema == "public"
        assert schema.tables[1].name == "users"
        assert schema.tables[1].schema == "audit"

    def test_parses_inline_foreign_key(self, parser):
        sql = """
            CREATE TABLE orders (
                id SERIAL PRIMARY KEY,
                user_id INT REFERENCES users(id)
            );
        """
        schema = parser.parse(sql)

        assert len(schema.tables[0].foreign_keys) == 1
        assert schema.tables[0].foreign_keys[0].columns == ["user_id"]
        assert schema.tables[0].foreign_keys[0].referenced_table == "users"
        assert schema.tables[0].foreign_keys[0].referenced_columns == ["id"]

    def test_parses_table_level_foreign_key(self, parser):
        sql = """
            CREATE TABLE orders (
                id SERIAL PRIMARY KEY,
                user_id INT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        """
        schema = parser.parse(sql)

        assert len(schema.tables[0].foreign_keys) == 1
        assert schema.tables[0].foreign_keys[0].referenced_table == "users"

    def test_unique_constraint_naming(self, parser):
        sql = """
            CREATE TABLE products (
                id SERIAL PRIMARY KEY,
                sku VARCHAR(50),
                upc VARCHAR(50),
                UNIQUE (sku),
                UNIQUE (upc)
            );
        """
        schema = parser.parse(sql)
        index_names = [i.name for i in schema.tables[0].indexes]

        assert len(index_names) == 2
        assert index_names[0] != index_names[1]
        assert "sku" in index_names[0]
        assert "upc" in index_names[1]
