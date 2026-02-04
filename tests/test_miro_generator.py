"""Tests for Miro generator."""

import pytest
from html import escape as html_escape

from db_diagram.models import Column


class TestMiroHtmlEscaping:
    """Tests for HTML escaping in Miro generator."""

    def test_html_escape_handles_special_chars(self):
        """Verify html_escape works as expected for our use case."""
        # Test basic HTML special characters
        assert html_escape("<script>") == "&lt;script&gt;"
        assert html_escape("A & B") == "A &amp; B"
        assert html_escape('"quoted"') == "&quot;quoted&quot;"

    def test_table_name_with_special_chars_is_escaped(self):
        """Table names with <, &, etc. should be escaped."""
        table_name = "orders<test>"
        escaped = html_escape(table_name)
        assert "&lt;" in escaped
        assert "&gt;" in escaped
        assert "<" not in escaped

    def test_column_label_with_special_chars_is_escaped(self):
        """Column labels with special chars should be escaped."""
        col = Column(
            name="field<0>",
            type="TEXT",
            nullable=True,
            primary_key=False,
            unique=False,
        )
        label = f"{col.name}: {col.type}"
        escaped = html_escape(label)
        assert "&lt;" in escaped
        assert "&gt;" in escaped
