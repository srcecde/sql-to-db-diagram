# db-diagram (Python)

Convert SQL schemas to editable diagrams (Draw.io, Miro).

## Installation

```bash
uv sync
```

## Usage

### Draw.io Output (File-based)

```bash
uv run db-diagram <input.sql> -o <output.drawio>
```

### Miro Output (Direct API Integration)

Create editable shapes directly on a Miro board:

```bash
# Using command-line options
uv run db-diagram schema.sql -f miro --miro-token YOUR_TOKEN --miro-board-id BOARD_ID

# Using environment variables
export MIRO_ACCESS_TOKEN=your_token
export MIRO_BOARD_ID=your_board_id
uv run db-diagram schema.sql -f miro
```

#### Getting Miro Credentials

1. **Access Token**: Create a Miro app at https://developers.miro.com and generate an access token with `boards:write` scope
2. **Board ID**: Find in the board URL: `https://miro.com/app/board/<BOARD_ID>/`

### Options

| Option | Description |
|--------|-------------|
| `-o, --output` | Output file path (default: `<input>.drawio`) |
| `-f, --format` | Output format: `drawio` or `miro` |
| `-d, --dialect` | SQL dialect: `postgresql` |
| `--direction` | Layout direction: `TB` (top-bottom) or `LR` (left-right) |
| `--miro-token` | Miro API access token (or `MIRO_ACCESS_TOKEN` env var) |
| `--miro-board-id` | Miro board ID (or `MIRO_BOARD_ID` env var) |

## Features

- Parses PostgreSQL DDL (CREATE TABLE, CREATE INDEX, constraints)
- Extracts tables, columns, types, primary keys, foreign keys, indexes
- Auto-layouts tables using NetworkX graph algorithms
- **Draw.io**: Generates XML with editable, moveable table shapes
- **Miro**: Creates shapes directly on your board via REST API
- Foreign key relationships rendered as connectors

## Project Structure

```
db_diagram/
├── models.py              # Schema intermediate representation
├── parsers/
│   └── postgresql.py      # PostgreSQL DDL parser using sqlglot
├── layout/
│   └── networkx_layout.py # Graph layout using NetworkX
├── generators/
│   ├── drawio.py          # Draw.io XML generator
│   └── miro.py            # Miro REST API generator
└── cli.py                 # CLI entry point
```
