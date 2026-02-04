"""Layout engine using NetworkX for graph-based table positioning."""

from dataclasses import dataclass
from typing import Literal

import networkx as nx

from db_diagram.models import Schema, Table, PositionedSchema, PositionedTable, get_qualified_table_name


@dataclass
class LayoutOptions:
    """Options for layout calculation."""
    char_width: int = 8
    row_height: int = 26
    padding: int = 20
    min_table_width: int = 150
    node_gap: int = 80
    rank_gap: int = 120
    direction: Literal["TB", "LR"] = "TB"


def layout_schema(
    schema: Schema,
    options: LayoutOptions | None = None,
) -> PositionedSchema:
    """Calculate positions for all tables in a schema."""
    opts = options or LayoutOptions()

    # Create directed graph
    g = nx.DiGraph()

    # Calculate dimensions for each table
    table_dims: dict[str, tuple[float, float]] = {}
    # Map from simple table name to qualified name(s) for FK resolution
    table_name_to_qualified: dict[str, list[str]] = {}

    for table in schema.tables:
        qualified_name = get_qualified_table_name(table)
        dims = _calculate_table_dimensions(table, opts)
        table_dims[qualified_name] = dims
        g.add_node(qualified_name, width=dims[0], height=dims[1])

        # Track simple name -> qualified name mapping for FK lookup
        if table.name not in table_name_to_qualified:
            table_name_to_qualified[table.name] = []
        table_name_to_qualified[table.name].append(qualified_name)

    # Add edges for foreign key relationships
    for table in schema.tables:
        source_qualified = get_qualified_table_name(table)
        for fk in table.foreign_keys:
            # Try to resolve FK target: first check if already qualified
            target_qualified = fk.referenced_table
            if target_qualified not in table_dims:
                # Look up by simple name
                candidates = table_name_to_qualified.get(fk.referenced_table, [])
                if len(candidates) == 1:
                    target_qualified = candidates[0]
                elif len(candidates) > 1 and table.schema:
                    # Prefer same schema
                    same_schema = next((c for c in candidates if c.startswith(f"{table.schema}.")), None)
                    target_qualified = same_schema or candidates[0]
                elif candidates:
                    target_qualified = candidates[0]

            if target_qualified in table_dims:
                g.add_edge(source_qualified, target_qualified)

    # Use hierarchical layout
    if len(g.nodes) > 0:
        positions = _hierarchical_layout(g, table_dims, opts)
    else:
        positions = {}

    # Create positioned tables
    positioned_tables: list[PositionedTable] = []
    for table in schema.tables:
        qualified_name = get_qualified_table_name(table)
        dims = table_dims[qualified_name]
        pos = positions.get(qualified_name, (0.0, 0.0))

        positioned_tables.append(
            PositionedTable(
                name=table.name,
                schema=table.schema,
                columns=table.columns,
                primary_key=table.primary_key,
                foreign_keys=table.foreign_keys,
                indexes=table.indexes,
                x=pos[0],
                y=pos[1],
                width=dims[0],
                height=dims[1],
            )
        )

    return PositionedSchema(tables=positioned_tables, dialect=schema.dialect)


def _calculate_table_dimensions(
    table: Table,
    opts: LayoutOptions,
) -> tuple[float, float]:
    """Calculate width and height for a table."""
    # Calculate width based on longest line
    header_length = len(table.name)

    column_lengths = []
    for col in table.columns:
        line = f"{col.name}: {col.type}"
        if col.primary_key:
            line += " PK"
        if col.references:
            line += " FK"
        if not col.nullable and not col.primary_key:
            line += " NN"
        column_lengths.append(len(line))

    max_length = max([header_length] + column_lengths) if column_lengths else header_length
    width = max(opts.min_table_width, max_length * opts.char_width + opts.padding * 2)

    # Height: header + columns
    header_height = opts.row_height + 4
    columns_height = len(table.columns) * opts.row_height
    height = header_height + columns_height + opts.padding

    return (width, height)


def _hierarchical_layout(
    g: nx.DiGraph,
    table_dims: dict[str, tuple[float, float]],
    opts: LayoutOptions,
) -> dict[str, tuple[float, float]]:
    """Create a hierarchical layout for the graph."""
    positions: dict[str, tuple[float, float]] = {}

    # Find root nodes (nodes with no incoming edges from other tables)
    # or use topological generations for DAG-like structure
    try:
        # Try to get topological generations (works for DAGs)
        generations = list(nx.topological_generations(g))
    except nx.NetworkXUnfeasible:
        # Graph has cycles, use connected components approach
        generations = _get_generations_with_cycles(g)

    if opts.direction == "TB":
        # Top to bottom layout
        y_offset = 20.0
        for gen_idx, generation in enumerate(generations):
            # Calculate total width of this generation
            total_width = sum(table_dims[node][0] for node in generation)
            total_width += (len(generation) - 1) * opts.node_gap

            # Start x position (centered)
            x_offset = 20.0

            # Sort nodes in generation for consistent layout
            sorted_nodes = sorted(generation)

            for node in sorted_nodes:
                width, height = table_dims[node]
                positions[node] = (x_offset, y_offset)
                x_offset += width + opts.node_gap

            # Move to next row
            max_height = max(table_dims[node][1] for node in generation) if generation else 0
            y_offset += max_height + opts.rank_gap
    else:
        # Left to right layout
        x_offset = 20.0
        for gen_idx, generation in enumerate(generations):
            # Calculate total height of this generation
            total_height = sum(table_dims[node][1] for node in generation)
            total_height += (len(generation) - 1) * opts.node_gap

            y_offset = 20.0

            sorted_nodes = sorted(generation)

            for node in sorted_nodes:
                width, height = table_dims[node]
                positions[node] = (x_offset, y_offset)
                y_offset += height + opts.node_gap

            # Move to next column
            max_width = max(table_dims[node][0] for node in generation) if generation else 0
            x_offset += max_width + opts.rank_gap

    return positions


def _get_generations_with_cycles(g: nx.DiGraph) -> list[set[str]]:
    """Get generations for a graph that may have cycles."""
    # Use strongly connected components and condense
    # Then do topological sort on condensed graph

    # Simple fallback: just put all nodes in rows based on in-degree
    in_degrees = dict(g.in_degree())

    # Group by in-degree level
    levels: dict[int, set[str]] = {}
    for node, degree in in_degrees.items():
        if degree not in levels:
            levels[degree] = set()
        levels[degree].add(node)

    # Return sorted by in-degree
    return [levels[k] for k in sorted(levels.keys())]
