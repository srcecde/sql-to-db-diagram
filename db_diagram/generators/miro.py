"""Miro API generator - creates editable shapes directly on a Miro board."""

from dataclasses import dataclass
from html import escape as html_escape
import httpx

from db_diagram.models import PositionedSchema, PositionedTable, Column, get_qualified_table_name


MIRO_API_BASE = "https://api.miro.com/v2"


@dataclass
class MiroOptions:
    """Options for Miro generation."""
    header_color: str = "#1a365d"
    column_color: str = "#ffffff"
    pk_color: str = "#fef3c7"
    fk_color: str = "#dbeafe"
    border_color: str = "#1e3a5f"
    text_color: str = "#1a1a1a"
    header_text_color: str = "#ffffff"


@dataclass
class MiroResult:
    """Result of Miro generation."""
    board_id: str
    board_url: str
    tables_created: int
    connectors_created: int
    shape_ids: dict[str, str]  # table_name -> shape_id


class MiroGenerator:
    """Generator that creates database diagrams on Miro boards."""

    def __init__(self, access_token: str, board_id: str):
        """Initialize with Miro credentials.

        Args:
            access_token: Miro OAuth access token with boards:write scope
            board_id: ID of the Miro board to create shapes on
        """
        self.access_token = access_token
        self.board_id = board_id
        self.client = httpx.Client(
            base_url=MIRO_API_BASE,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def generate(
        self,
        schema: PositionedSchema,
        options: MiroOptions | None = None,
    ) -> MiroResult:
        """Generate Miro shapes from a positioned schema.

        Args:
            schema: The positioned schema to visualize
            options: Optional styling options

        Returns:
            MiroResult with details about created items
        """
        opts = options or MiroOptions()

        # Track created shape IDs for connectors
        table_shape_ids: dict[str, str] = {}
        column_shape_ids: dict[str, dict[str, str]] = {}
        # Map from simple table name to qualified name(s) for FK resolution
        table_name_to_qualified: dict[str, list[str]] = {}

        # Create shapes for each table
        for table in schema.tables:
            qualified_name = get_qualified_table_name(table)
            table_id, col_ids = self._create_table_shape(table, opts)
            table_shape_ids[qualified_name] = table_id
            column_shape_ids[qualified_name] = col_ids

            # Track simple name -> qualified name mapping
            if table.name not in table_name_to_qualified:
                table_name_to_qualified[table.name] = []
            table_name_to_qualified[table.name].append(qualified_name)

        # Create connectors for foreign key relationships
        connectors_created = 0
        for table in schema.tables:
            source_qualified = get_qualified_table_name(table)
            for fk in table.foreign_keys:
                # Resolve FK target qualified name
                target_qualified = fk.referenced_table
                if target_qualified not in column_shape_ids:
                    candidates = table_name_to_qualified.get(fk.referenced_table, [])
                    if len(candidates) == 1:
                        target_qualified = candidates[0]
                    elif len(candidates) > 1 and table.schema:
                        same_schema = next((c for c in candidates if c.startswith(f"{table.schema}.")), None)
                        target_qualified = same_schema or candidates[0]
                    elif candidates:
                        target_qualified = candidates[0]

                source_cols = column_shape_ids.get(source_qualified)
                target_cols = column_shape_ids.get(target_qualified)

                if source_cols and target_cols:
                    # Connect from FK column to referenced table's column
                    source_id = source_cols.get(fk.columns[0])
                    target_id = (
                        target_cols.get(fk.referenced_columns[0])
                        or table_shape_ids.get(target_qualified)
                    )

                    if source_id and target_id:
                        self._create_connector(source_id, target_id)
                        connectors_created += 1

        # Get board URL
        board_url = f"https://miro.com/app/board/{self.board_id}/"

        return MiroResult(
            board_id=self.board_id,
            board_url=board_url,
            tables_created=len(schema.tables),
            connectors_created=connectors_created,
            shape_ids=table_shape_ids,
        )

    def _create_table_shape(
        self,
        table: PositionedTable,
        opts: MiroOptions,
    ) -> tuple[str, dict[str, str]]:
        """Create shapes for a table (header + column rows).

        Returns:
            Tuple of (header_shape_id, {column_name: shape_id})
        """
        column_ids: dict[str, str] = {}
        row_height = 30
        header_height = 36

        # Create header shape (table name)
        header_id = self._create_shape(
            x=table.x + table.width / 2,
            y=table.y + header_height / 2,
            width=table.width,
            height=header_height,
            content=f"<strong>{html_escape(table.name)}</strong>",
            fill_color=opts.header_color,
            text_color=opts.header_text_color,
            border_color=opts.border_color,
        )

        # Create column shapes
        for i, col in enumerate(table.columns):
            label = self._format_column_label(col)
            fill_color = self._get_column_color(col, opts)

            col_y = table.y + header_height + (i * row_height) + row_height / 2

            col_id = self._create_shape(
                x=table.x + table.width / 2,
                y=col_y,
                width=table.width,
                height=row_height,
                content=html_escape(label),
                fill_color=fill_color,
                text_color=opts.text_color,
                border_color=opts.border_color,
            )
            column_ids[col.name] = col_id

        return header_id, column_ids

    def _create_shape(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        content: str,
        fill_color: str,
        text_color: str,
        border_color: str,
    ) -> str:
        """Create a rectangle shape on the Miro board.

        Returns:
            The shape ID
        """
        response = self.client.post(
            f"/boards/{self.board_id}/shapes",
            json={
                "data": {
                    "shape": "rectangle",
                    "content": content,
                },
                "style": {
                    "fillColor": fill_color,
                    "fontFamily": "open_sans",
                    "fontSize": "14",
                    "textAlign": "left",
                    "textAlignVertical": "middle",
                    "borderColor": border_color,
                    "borderWidth": "1.0",
                    "borderOpacity": "1.0",
                    "borderStyle": "normal",
                    "fillOpacity": "1.0",
                    "color": text_color,
                },
                "position": {
                    "x": x,
                    "y": y,
                    "origin": "center",
                },
                "geometry": {
                    "width": width,
                    "height": height,
                },
            },
        )
        response.raise_for_status()
        return response.json()["id"]

    def _create_connector(self, start_id: str, end_id: str) -> str:
        """Create a connector between two shapes.

        Returns:
            The connector ID
        """
        response = self.client.post(
            f"/boards/{self.board_id}/connectors",
            json={
                "startItem": {
                    "id": start_id,
                    "snapTo": "right",
                },
                "endItem": {
                    "id": end_id,
                    "snapTo": "left",
                },
                "style": {
                    "strokeColor": "#64748b",
                    "strokeWidth": "1.0",
                    "startStrokeCap": "none",
                    "endStrokeCap": "arrow",
                },
                "shape": "elbowed",
            },
        )
        response.raise_for_status()
        return response.json()["id"]

    def _format_column_label(self, col: Column) -> str:
        """Format column label with type and constraints."""
        label = f"{col.name}: {col.type}"
        tags: list[str] = []

        if col.primary_key:
            tags.append("PK")
        if col.references:
            tags.append("FK")
        if not col.nullable and not col.primary_key:
            tags.append("NN")
        if col.unique:
            tags.append("UQ")

        if tags:
            label += f" [{', '.join(tags)}]"

        return label

    def _get_column_color(self, col: Column, opts: MiroOptions) -> str:
        """Get background color for a column."""
        if col.primary_key:
            return opts.pk_color
        if col.references:
            return opts.fk_color
        return opts.column_color

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self) -> "MiroGenerator":
        return self

    def __exit__(self, *args) -> None:
        self.close()


def generate_miro(
    schema: PositionedSchema,
    access_token: str,
    board_id: str,
    options: MiroOptions | None = None,
) -> MiroResult:
    """Convenience function to generate Miro shapes from a schema.

    Args:
        schema: The positioned schema to visualize
        access_token: Miro OAuth access token
        board_id: Miro board ID
        options: Optional styling options

    Returns:
        MiroResult with details about created items
    """
    with MiroGenerator(access_token, board_id) as generator:
        return generator.generate(schema, options)
