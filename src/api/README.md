# API Package

FastAPI service for semantic search, document management, collections, embeddings, and feedback.

## Quick Start

```bash
# Install API dependencies from the repository root
(cd src/api && uv sync --extra dev)

# Start the local API + Qdrant stack from the repository root
task local:api:up
task local:api:health
```

See [docs/api/API_README.md](../../docs/api/API_README.md) for the service overview and [docs/api/API_LOCAL_DEV.md](../../docs/api/API_LOCAL_DEV.md) for local workflows.
