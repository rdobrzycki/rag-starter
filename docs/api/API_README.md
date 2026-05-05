# API Service

FastAPI service for semantic search, document ingestion, collection management, embeddings, and feedback.

## Quick Start

```bash
# From the repository root
(cd src/api && uv sync --extra dev)
task local:api:up
task local:api:health
task local:api:query QUERY="What is the privacy policy?"
```

## Endpoints

- `GET /health`: process liveness
- `GET /ready`: readiness checks for Qdrant and Bedrock
- `GET /metrics`: Prometheus metrics
- `POST /query`: answer generation with retrieved sources
- `POST /documents`: single-document ingestion
- `POST /documents/batch`: batch ingestion
- `DELETE /documents/{document_id}`: delete stored document chunks
- `GET /collections`: list collections
- `POST /collections`: create a collection
- `POST /embed`: generate a single embedding
- `POST /feedback`: store result feedback

## Configuration

Configure the service through `.env` at the repository root.

- `AWS_REGION`
- `BEDROCK_EMBED_MODEL_ID`
- `BEDROCK_LLM_MODEL_ID`
- `QDRANT_URL`
- `QDRANT_API_KEY`
- `QDRANT_COLLECTION`
- `RATE_LIMIT_*`
- `FEEDBACK_*`

See `.env.example` for the starting template.

## Testing

```bash
task test:unit:api
task test:coverage:api
task local:test:efficiency:performance
```

For day-to-day development flows, see [API Local Development](API_LOCAL_DEV.md).

For deploying the API into a real AWS account, follow [AWS Deployment](../AWS_DEPLOYMENT.md).
