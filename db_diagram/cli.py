"""Command-line interface for db-diagram."""

import os
from pathlib import Path
from typing import Literal

import click

from db_diagram.parsers import PostgreSQLParser
from db_diagram.layout import layout_schema
from db_diagram.layout.networkx_layout import LayoutOptions
from db_diagram.generators import generate_drawio, generate_miro


@click.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o", "--output",
    type=click.Path(path_type=Path),
    help="Output file path (default: <input>.drawio). Not used for miro format.",
)
@click.option(
    "-f", "--format",
    type=click.Choice(["drawio", "miro"]),
    default="drawio",
    help="Output format (default: drawio)",
)
@click.option(
    "-d", "--dialect",
    type=click.Choice(["postgresql", "postgres"]),
    default="postgresql",
    help="SQL dialect (default: postgresql)",
)
@click.option(
    "--direction",
    type=click.Choice(["TB", "LR"]),
    default="TB",
    help="Layout direction: TB (top-bottom) or LR (left-right)",
)
@click.option(
    "--miro-token",
    envvar="MIRO_ACCESS_TOKEN",
    help="Miro API access token (or set MIRO_ACCESS_TOKEN env var)",
)
@click.option(
    "--miro-board-id",
    envvar="MIRO_BOARD_ID",
    help="Miro board ID to create shapes on (or set MIRO_BOARD_ID env var)",
)
@click.version_option(version="0.1.0")
def main(
    input_file: Path,
    output: Path | None,
    format: Literal["drawio", "miro"],
    dialect: str,
    direction: Literal["TB", "LR"],
    miro_token: str | None,
    miro_board_id: str | None,
) -> None:
    """Convert SQL schemas to editable diagrams.

    INPUT_FILE is the path to a SQL file containing CREATE TABLE statements.

    \b
    Examples:
      # Generate Draw.io diagram
      db-diagram schema.sql -o diagram.drawio

      # Generate directly on Miro board
      db-diagram schema.sql -f miro --miro-token TOKEN --miro-board-id BOARD_ID

      # Using environment variables for Miro
      export MIRO_ACCESS_TOKEN=your_token
      export MIRO_BOARD_ID=your_board_id
      db-diagram schema.sql -f miro
    """
    try:
        # Read input file
        sql = input_file.read_text()

        # Select parser
        if dialect in ("postgresql", "postgres"):
            parser = PostgreSQLParser()
        else:
            raise click.ClickException(f"Unsupported dialect: {dialect}")

        click.echo(f"Parsing {dialect} SQL...")
        schema = parser.parse(sql)
        click.echo(f"Found {len(schema.tables)} tables")

        # Layout
        click.echo("Calculating layout...")
        layout_opts = LayoutOptions(direction=direction)
        positioned_schema = layout_schema(schema, layout_opts)

        # Generate output
        if format == "drawio":
            output_content = generate_drawio(positioned_schema)
            default_ext = ".drawio"

            # Determine output path
            output_path = output or input_file.with_suffix(default_ext)

            # Write output
            output_path.write_text(output_content)
            click.echo(f"Diagram saved to: {output_path}")

        elif format == "miro":
            # Validate Miro credentials
            if not miro_token:
                raise click.ClickException(
                    "Miro access token required. Use --miro-token or set MIRO_ACCESS_TOKEN env var.\n"
                    "Get your token at: https://developers.miro.com/docs/getting-started"
                )
            if not miro_board_id:
                raise click.ClickException(
                    "Miro board ID required. Use --miro-board-id or set MIRO_BOARD_ID env var.\n"
                    "Find board ID in the URL: https://miro.com/app/board/<BOARD_ID>/"
                )

            click.echo(f"Creating shapes on Miro board {miro_board_id}...")
            result = generate_miro(
                positioned_schema,
                access_token=miro_token,
                board_id=miro_board_id,
            )
            click.echo(f"Created {result.tables_created} tables and {result.connectors_created} connectors")
            click.echo(f"View your diagram at: {result.board_url}")

        else:
            raise click.ClickException(f"Unsupported format: {format}")

        # Print summary
        click.echo("\nSummary:")
        for table in schema.tables:
            fk_count = len(table.foreign_keys)
            index_count = len(table.indexes)
            parts = [f"{len(table.columns)} columns"]
            if fk_count > 0:
                parts.append(f"{fk_count} FK")
            if index_count > 0:
                parts.append(f"{index_count} indexes")
            click.echo(f"  - {table.name}: {', '.join(parts)}")

    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(str(e))


if __name__ == "__main__":
    main()
