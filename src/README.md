# Source Workspace

This directory is the canonical uv workspace for the repository.

- Workspace definition: `pyproject.toml`
- Workspace lockfile: `uv.lock`

## Quick Start

```bash
# From the repository root
cd src
uv sync
uv run pytest api/tests/unit/ ingestion/tests/unit/ -q
```

## Packages

- `api/`: FastAPI service
- `ingestion/`: Lambda ingestion service
- `shared/`: Shared utilities used by both services
