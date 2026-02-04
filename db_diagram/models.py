"""Intermediate representation for database schemas."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ForeignKeyReference:
    """Reference to another table's column."""
    table: str
    column: str
    schema: str | None = None
    constraint_name: str | None = None


@dataclass
class Column:
    """Database column definition."""
    name: str
    type: str
    nullable: bool = True
    primary_key: bool = False
    unique: bool = False
    default_value: str | None = None
    references: ForeignKeyReference | None = None


@dataclass
class ForeignKey:
    """Foreign key constraint."""
    columns: list[str]
    referenced_table: str
    referenced_columns: list[str]
    name: str | None = None


@dataclass
class Index:
    """Database index."""
    name: str
    columns: list[str]
    unique: bool = False


@dataclass
class Table:
    """Database table definition."""
    name: str
    columns: list[Column] = field(default_factory=list)
    primary_key: list[str] | None = None
    foreign_keys: list[ForeignKey] = field(default_factory=list)
    indexes: list[Index] = field(default_factory=list)
    schema: str | None = None


@dataclass
class Schema:
    """Complete database schema."""
    tables: list[Table] = field(default_factory=list)
    dialect: Literal["postgresql", "mysql", "sqlserver", "sqlite"] = "postgresql"


@dataclass
class PositionedTable(Table):
    """Table with layout position."""
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0


@dataclass
class PositionedSchema:
    """Schema with positioned tables."""
    tables: list[PositionedTable] = field(default_factory=list)
    dialect: Literal["postgresql", "mysql", "sqlserver", "sqlite"] = "postgresql"


def get_qualified_table_name(table: Table | PositionedTable) -> str:
    """Get a qualified table name for use as a unique key.

    Returns "schema.name" if schema is present, otherwise just "name".
    """
    return f"{table.schema}.{table.name}" if table.schema else table.name
