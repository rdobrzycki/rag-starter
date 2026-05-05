# Ingestion Local Development

## Prerequisites

- Docker and Docker Compose
- AWS SAM CLI
- Python 3.13+
- AWS credentials with Bedrock access

## Quick Start

```bash
# From the repository root
(cd src/ingestion && uv sync --extra dev)
task local:sam:up
task local:sam:build
task local:s3:upload FILE_PATH="src/ingestion/local-dev/test-documents/sample.txt"
task local:sam:invoke
```

## Create the Local Collection

```bash
curl -X PUT "http://localhost:6333/collections/documents" \
  -H "Content-Type: application/json" \
  -d '{"vectors": {"size": 1024, "distance": "Cosine"}}'
```

## Debugging

```bash
task local:sam:up
task local:sam:build
task local:sam:debug
```

Set breakpoints in `src/ingestion/lambda_handler/handler.py`, then attach your debugger after the container starts.

## Verify Results

```bash
curl -X POST "http://localhost:6333/collections/documents/points/scroll" \
  -H "Content-Type: application/json" \
  -d '{"limit": 5}' | jq
```

## Cleanup

```bash
task local:sam:down
```

## Notes

- LocalStack handles S3, SSM, and Secrets Manager on `http://localhost:4566`.
- Qdrant runs locally on `http://localhost:6333`.
- Bedrock requests use your active AWS credentials even during local SAM runs.

## Troubleshooting

- LocalStack problems: `docker compose logs localstack`
- Missing S3 object: `task local:s3:list`
- Import problems after a rebuild: rerun `task local:sam:build`
- Credential issues: verify with `aws sts get-caller-identity`
