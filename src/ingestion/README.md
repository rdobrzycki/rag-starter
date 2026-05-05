# Ingestion Package

AWS Lambda ingestion service for validating documents, extracting text, creating embeddings, and storing vectors in Qdrant.

## Quick Start

```bash
# Install ingestion dependencies from the repository root
(cd src/ingestion && uv sync --extra dev)

# Run the local SAM workflow from the repository root
task local:sam:up
task local:sam:build
task local:sam:invoke
```

See [docs/ingestion/INGESTION_README.md](../../docs/ingestion/INGESTION_README.md) for the service overview and [docs/ingestion/INGESTION_LOCAL_DEV.md](../../docs/ingestion/INGESTION_LOCAL_DEV.md) for local workflows.
