# API Local Development

## Prerequisites

- Docker and Docker Compose
- Python 3.11+
- `uv`
- AWS credentials with Bedrock access
- A configured `.env` file in the repository root

`uv` can provision the required Python version for this workspace even if your system default `python3` is older. The repo pins Python 3.11 in [`.python-version`](../../.python-version).

## Quick Start

```bash
# From the repository root
cp .env.example .env
cd src && uv sync
cd ..

task local:api:up
task local:api:health
task local:api:query QUERY="What is the data retention policy?"
```

This runtime path is not zero-cloud: the local API runs against the local Qdrant container, but Bedrock calls use your active AWS credentials.

If you only want to confirm the repository works after cloning, use the test-first flow from [README.md](../../README.md):

```bash
cp .env.example .env
cd src && uv sync
cd ..
task test:unit
task local:test:integration
```

## Common Workflows

```bash
# Populate local Qdrant with sample data
task local:api:populate

# Follow logs
task local:api:logs

# Restart the API container
task local:api:restart

# Stop the local stack
task local:api:down
```

## Auto-Reload Workflow

```bash
# Keep Qdrant in Docker, run the API directly
docker compose stop api
(cd src/api && uv run uvicorn rag_api.main:app --reload --host 0.0.0.0 --port 8080)
```

## Testing

```bash
task test:unit:api
task test:coverage:api
task local:test:efficiency:performance
```

## Environment

The API reads its configuration from `.env` in the repository root. The main values are:

- `AWS_REGION`
- `BEDROCK_EMBED_MODEL_ID`
- `BEDROCK_LLM_MODEL_ID`
- `QDRANT_URL`
- `QDRANT_API_KEY`
- `QDRANT_COLLECTION`

For the local API runtime, the Bedrock-related variables must be set to real values:

- `AWS_REGION`
- `BEDROCK_EMBED_MODEL_ID`
- `BEDROCK_LLM_MODEL_ID`

## Troubleshooting

- API not responding: `docker compose ps api` and `task local:api:logs`
- Qdrant unavailable: `docker compose ps qdrant` and `curl http://localhost:6333`
- Bedrock auth problems: `aws sts get-caller-identity` and verify the active credentials
- Empty query results: populate sample data with `task local:api:populate`
