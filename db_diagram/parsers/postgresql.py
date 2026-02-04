"""PostgreSQL DDL parser using sqlglot."""

import sqlglot
from sqlglot import exp

from db_diagram.models import (
    Schema,
    Table,
    Column,
    ForeignKey,
    ForeignKeyReference,
    Index,
)


class PostgreSQLParser:
    """Parser for PostgreSQL DDL statements."""

    def parse(self, sql: str) -> Schema:
        """Parse SQL DDL and return a Schema."""
        statements = sqlglot.parse(sql, dialect="postgres")
        tables: list[Table] = []
        index_statements: list[exp.Create] = []

        for stmt in statements:
            if stmt is None:
                continue
            if isinstance(stmt, exp.Create):
                if stmt.kind == "TABLE":
                    tables.append(self._parse_create_table(stmt))
                elif stmt.kind == "INDEX":
                    index_statements.append(stmt)

        # Attach indexes to tables
        for index_stmt in index_statements:
            self._attach_index(tables, index_stmt)

        return Schema(tables=tables, dialect="postgresql")

    def _parse_create_table(self, stmt: exp.Create) -> Table:
        """Parse a CREATE TABLE statement."""
        # stmt.this is a sqlglot Schema object containing the table definition
        # stmt.this.this is the table identifier, stmt.this.expressions are columns
        schema_obj = stmt.this
        if not schema_obj:
            return Table(name="unknown")

        table_identifier = schema_obj.this
        table_name = table_identifier.name if table_identifier else "unknown"
        schema_name = getattr(table_identifier, "db", None) if table_identifier else None

        columns: list[Column] = []
        foreign_keys: list[ForeignKey] = []
        indexes: list[Index] = []
        primary_key_columns: list[str] = []

        # Process columns and constraints from schema_obj.expressions
        for expression in schema_obj.expressions or []:
            if isinstance(expression, exp.ColumnDef):
                column = self._parse_column(expression)
                columns.append(column)

                if column.primary_key:
                    primary_key_columns.append(column.name)

                if column.references:
                    # Build qualified name if schema present
                    qualified_ref_table = (
                        f"{column.references.schema}.{column.references.table}"
                        if column.references.schema
                        else column.references.table
                    )
                    foreign_keys.append(
                        ForeignKey(
                            columns=[column.name],
                            referenced_table=qualified_ref_table,
                            referenced_columns=[column.references.column],
                            name=column.references.constraint_name,
                        )
                    )

            elif isinstance(expression, exp.PrimaryKey):
                # Table-level PRIMARY KEY constraint
                primary_key_columns = [
                    col.name for col in expression.expressions if hasattr(col, "name")
                ]

            elif isinstance(expression, exp.ForeignKey):
                # Table-level FOREIGN KEY constraint
                fk = self._parse_foreign_key_constraint(expression)
                if fk:
                    foreign_keys.append(fk)

            elif isinstance(expression, exp.UniqueColumnConstraint):
                # Table-level UNIQUE constraint - columns are in expression.this.expressions
                unique_schema = expression.this
                if unique_schema:
                    unique_cols = [
                        col.name for col in unique_schema.expressions if hasattr(col, "name")
                    ]
                else:
                    unique_cols = []
                if unique_cols:
                    indexes.append(
                        Index(
                            name=f"{table_name}_{'_'.join(unique_cols)}_unique",
                            columns=unique_cols,
                            unique=True,
                        )
                    )

        # Mark primary key columns
        for col in columns:
            if col.name in primary_key_columns:
                col.primary_key = True
                col.nullable = False

        return Table(
            name=table_name,
            schema=schema_name,
            columns=columns,
            primary_key=primary_key_columns if primary_key_columns else None,
            foreign_keys=foreign_keys,
            indexes=indexes,
        )

    def _parse_column(self, col_def: exp.ColumnDef) -> Column:
        """Parse a column definition."""
        name = col_def.name
        data_type = self._type_to_string(col_def.args.get("kind"))

        nullable = True
        primary_key = False
        unique = False
        default_value: str | None = None
        references: ForeignKeyReference | None = None

        # Process column constraints
        for constraint in col_def.constraints or []:
            constraint_kind = constraint.kind

            if isinstance(constraint_kind, exp.NotNullColumnConstraint):
                nullable = False
            elif isinstance(constraint_kind, exp.PrimaryKeyColumnConstraint):
                primary_key = True
                nullable = False
            elif isinstance(constraint_kind, exp.UniqueColumnConstraint):
                unique = True
            elif isinstance(constraint_kind, exp.DefaultColumnConstraint):
                default_value = self._expr_to_string(constraint_kind.this)
            elif isinstance(constraint_kind, exp.Reference):
                # constraint_kind.this is a Schema object containing the table and columns
                ref_schema_obj = constraint_kind.this
                if ref_schema_obj:
                    ref_table = ref_schema_obj.this  # The Table expression
                    ref_cols = ref_schema_obj.expressions or []  # The column references
                    if ref_table:
                        table_name = ref_table.name if hasattr(ref_table, "name") else str(ref_table)
                        col_name = ref_cols[0].name if ref_cols and hasattr(ref_cols[0], "name") else "id"
                        # Get schema if present
                        ref_schema_name = getattr(ref_table, "db", None)
                        references = ForeignKeyReference(
                            table=table_name,
                            column=col_name,
                            schema=ref_schema_name,
                        )

        return Column(
            name=name,
            type=data_type,
            nullable=nullable,
            primary_key=primary_key,
            unique=unique,
            default_value=default_value,
            references=references,
        )

    def _parse_foreign_key_constraint(self, fk: exp.ForeignKey) -> ForeignKey | None:
        """Parse a table-level FOREIGN KEY constraint."""
        local_cols = [
            col.name for col in fk.expressions if hasattr(col, "name")
        ]

        reference = fk.args.get("reference")
        if not reference:
            return None

        # reference.this is a Schema object, reference.this.this is the actual Table
        ref_schema_obj = reference.this
        if not ref_schema_obj:
            return None

        ref_table = ref_schema_obj.this  # The actual Table expression
        ref_cols = ref_schema_obj.expressions or []  # Column references

        if not ref_table:
            return None

        table_name = ref_table.name if hasattr(ref_table, "name") else str(ref_table)
        # Get schema if present
        ref_schema = getattr(ref_table, "db", None)
        # Build qualified name if schema present
        qualified_table_name = f"{ref_schema}.{table_name}" if ref_schema else table_name

        referenced_columns = [
            col.name if hasattr(col, "name") else str(col) for col in ref_cols
        ] or ["id"]

        return ForeignKey(
            columns=local_cols,
            referenced_table=qualified_table_name,
            referenced_columns=referenced_columns,
        )

    def _type_to_string(self, data_type: exp.DataType | None) -> str:
        """Convert a data type expression to string."""
        if not data_type:
            return "UNKNOWN"

        type_name = data_type.this.name if data_type.this else "UNKNOWN"

        # Get type parameters (e.g., VARCHAR(255), NUMERIC(10,2))
        params = []
        for expr in data_type.expressions or []:
            if isinstance(expr, exp.DataTypeParam):
                params.append(str(expr.this))
            elif hasattr(expr, "name"):
                params.append(expr.name)
            else:
                params.append(str(expr))

        if params:
            return f"{type_name}({', '.join(params)})"

        return type_name

    def _expr_to_string(self, expr: exp.Expression | None) -> str:
        """Convert an expression to string."""
        if expr is None:
            return ""

        if isinstance(expr, exp.Literal):
            if expr.is_string:
                return f"'{expr.this}'"
            return str(expr.this)

        if isinstance(expr, exp.Boolean):
            return "TRUE" if expr.this else "FALSE"

        if isinstance(expr, exp.Null):
            return "NULL"

        if isinstance(expr, exp.Anonymous):
            return f"{expr.this}()"

        return str(expr)

    def _attach_index(self, tables: list[Table], index_stmt: exp.Create) -> None:
        """Attach an index to its table."""
        # Get table name from the index
        table_expr = index_stmt.this
        if not table_expr:
            return

        # For CREATE INDEX, the table is in args
        table_ref = index_stmt.args.get("this")
        if isinstance(table_ref, exp.Index):
            table_name_expr = table_ref.args.get("table")
            if table_name_expr:
                table_name = table_name_expr.name if hasattr(table_name_expr, "name") else str(table_name_expr)
                table_schema = getattr(table_name_expr, "db", None)
            else:
                return

            index_name = table_ref.name if hasattr(table_ref, "name") else "unnamed_index"

            # Get columns from the index
            columns = []
            for col in table_ref.expressions or []:
                if hasattr(col, "name"):
                    columns.append(col.name)
                else:
                    columns.append(str(col))

            # Find the table and add the index (match by schema if present)
            for table in tables:
                # Check if table name matches (with optional schema)
                table_matches = (
                    (table.schema == table_schema and table.name == table_name)
                    if table_schema
                    else table.name == table_name
                )
                if table_matches:
                    is_unique = any(
                        isinstance(prop, exp.UniqueColumnConstraint)
                        for prop in index_stmt.args.get("properties", {}).get("expressions", [])
                    ) if index_stmt.args.get("properties") else False

                    # Check for UNIQUE keyword in the statement
                    if "unique" in str(index_stmt).lower().split("index")[0]:
                        is_unique = True

                    table.indexes.append(
                        Index(
                            name=index_name,
                            columns=columns,
                            unique=is_unique,
                        )
                    )
                    break
