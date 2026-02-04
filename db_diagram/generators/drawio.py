"""Draw.io XML generator."""

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape

from db_diagram.models import PositionedSchema, PositionedTable, Column


@dataclass
class DrawioOptions:
    """Options for Draw.io generation."""
    row_height: int = 26
    header_color: str = "#1a365d"
    column_color: str = "#ffffff"
    pk_color: str = "#fef3c7"
    fk_color: str = "#dbeafe"


_cell_id_counter = 0


def _next_id() -> str:
    """Generate next cell ID."""
    global _cell_id_counter
    _cell_id_counter += 1
    return f"cell-{_cell_id_counter}"


def _reset_id_counter() -> None:
    """Reset the ID counter."""
    global _cell_id_counter
    _cell_id_counter = 0


def generate_drawio(
    schema: PositionedSchema,
    options: DrawioOptions | None = None,
) -> str:
    """Generate Draw.io XML from a positioned schema."""
    opts = options or DrawioOptions()
    _reset_id_counter()

    cells: list[str] = []
    edges: list[str] = []
    table_id_map: dict[str, str] = {}
    column_id_map: dict[str, dict[str, str]] = {}

    # Generate table cells
    for table in schema.tables:
        table_cells, column_ids = _generate_table_cells(table, opts)
        cells.extend(table_cells)
        table_id_map[table.name] = column_ids["__table__"]
        column_id_map[table.name] = column_ids

    # Generate relationship edges
    for table in schema.tables:
        for fk in table.foreign_keys:
            source_table_cols = column_id_map.get(table.name)
            target_table_cols = column_id_map.get(fk.referenced_table)

            if source_table_cols and target_table_cols:
                source_col_id = source_table_cols.get(fk.columns[0])
                target_col_id = (
                    target_table_cols.get(fk.referenced_columns[0])
                    or target_table_cols.get("__table__")
                )

                if source_col_id and target_col_id:
                    edges.append(_generate_edge(source_col_id, target_col_id, fk.name))

    content = "\n".join(cells + edges)
    return _wrap_in_drawio_xml(content)


def _generate_table_cells(
    table: PositionedTable,
    opts: DrawioOptions,
) -> tuple[list[str], dict[str, str]]:
    """Generate cells for a table."""
    cells: list[str] = []
    column_ids: dict[str, str] = {}

    table_id = _next_id()
    column_ids["__table__"] = table_id

    header_height = opts.row_height + 4

    # Table container (swimlane style)
    cells.append(f'''
    <mxCell id="{table_id}" value="{escape(table.name)}" style="swimlane;fontStyle=1;childLayout=stackLayout;horizontal=1;startSize={header_height};horizontalStack=0;resizeParent=1;resizeParentMax=0;resizeLast=0;collapsible=0;marginBottom=0;fillColor={opts.header_color};fontColor=#ffffff;strokeColor=#1e3a5f;rounded=1;arcSize=8;" vertex="1" parent="1">
      <mxGeometry x="{table.x}" y="{table.y}" width="{table.width}" height="{table.height}" as="geometry"/>
    </mxCell>
  ''')

    # Column rows
    for i, col in enumerate(table.columns):
        col_id = _next_id()
        column_ids[col.name] = col_id

        label = _format_column_label(col)
        bg_color = _get_column_color(col, opts)
        is_last = i == len(table.columns) - 1

        cells.append(f'''
    <mxCell id="{col_id}" value="{escape(label)}" style="text;strokeColor=none;fillColor={bg_color};align=left;verticalAlign=middle;spacingLeft=8;spacingRight=4;overflow=hidden;rotatable=0;points=[[0,0.5],[1,0.5]];portConstraint=eastwest;fontFamily=monospace;fontSize=11;{"rounded=0;arcSize=0;" if is_last else ""}" vertex="1" parent="{table_id}">
      <mxGeometry y="{header_height + i * opts.row_height}" width="{table.width}" height="{opts.row_height}" as="geometry"/>
    </mxCell>
    ''')

    return cells, column_ids


def _format_column_label(col: Column) -> str:
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


def _get_column_color(col: Column, opts: DrawioOptions) -> str:
    """Get background color for a column."""
    if col.primary_key:
        return opts.pk_color
    if col.references:
        return opts.fk_color
    return opts.column_color


def _generate_edge(source_id: str, target_id: str, name: str | None = None) -> str:
    """Generate an edge (relationship line)."""
    edge_id = _next_id()
    label = escape(name) if name else ""

    return f'''
    <mxCell id="{edge_id}" value="{label}" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;endArrow=ERmany;endFill=0;startArrow=ERone;startFill=0;strokeWidth=1;strokeColor=#64748b;" edge="1" parent="1" source="{source_id}" target="{target_id}">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>
  '''


def _wrap_in_drawio_xml(content: str) -> str:
    """Wrap content in Draw.io XML structure."""
    timestamp = datetime.now(timezone.utc).isoformat()

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" modified="{timestamp}" agent="db-diagram-python" version="1.0">
  <diagram name="Database Schema" id="db-schema">
    <mxGraphModel dx="1000" dy="600" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1600" pageHeight="1200" math="0" shadow="0">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
{content}
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>'''
