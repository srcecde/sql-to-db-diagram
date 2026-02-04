"""Tests for layout engine."""

import pytest
from db_diagram.models import Schema, Table, Column, ForeignKey
from db_diagram.layout.networkx_layout import layout_schema


class TestLayoutSchema:
    """Tests for the layout engine."""

    def test_handles_tables_with_same_name_in_different_schemas(self):
        schema = Schema(
            dialect="postgresql",
            tables=[
                Table(
                    name="users",
                    schema="public",
                    columns=[
                        Column(name="id", type="SERIAL", primary_key=True, nullable=False),
                        Column(name="name", type="VARCHAR(100)", nullable=False),
                    ],
                ),
                Table(
                    name="users",
                    schema="audit",
                    columns=[
                        Column(name="id", type="SERIAL", primary_key=True, nullable=False),
                        Column(name="action", type="VARCHAR(50)", nullable=False),
                    ],
                ),
            ],
        )

        positioned = layout_schema(schema)

        # Both tables should exist with different positions
        assert len(positioned.tables) == 2

        public_users = next((t for t in positioned.tables if t.schema == "public"), None)
        audit_users = next((t for t in positioned.tables if t.schema == "audit"), None)

        assert public_users is not None, "public.users should exist"
        assert audit_users is not None, "audit.users should exist"

        # They should have different positions
        same_position = public_users.x == audit_users.x and public_users.y == audit_users.y
        assert not same_position, "Tables should have different positions"

    def test_resolves_fk_to_same_schema_when_ambiguous(self):
        schema = Schema(
            dialect="postgresql",
            tables=[
                Table(
                    name="users",
                    schema="public",
                    columns=[
                        Column(name="id", type="SERIAL", primary_key=True, nullable=False),
                    ],
                ),
                Table(
                    name="users",
                    schema="audit",
                    columns=[
                        Column(name="id", type="SERIAL", primary_key=True, nullable=False),
                    ],
                ),
                Table(
                    name="orders",
                    schema="public",
                    columns=[
                        Column(name="id", type="SERIAL", primary_key=True, nullable=False),
                        Column(name="user_id", type="INT", nullable=False),
                    ],
                    foreign_keys=[
                        ForeignKey(
                            columns=["user_id"],
                            referenced_table="users",  # Unqualified
                            referenced_columns=["id"],
                        ),
                    ],
                ),
            ],
        )

        # Should not throw - FK should resolve to public.users
        positioned = layout_schema(schema)
        assert len(positioned.tables) == 3
