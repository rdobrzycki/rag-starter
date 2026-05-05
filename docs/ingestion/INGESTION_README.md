# Ingestion Service

Lambda-based ingestion pipeline for validating uploaded documents, extracting text, chunking content, generating embeddings with Bedrock, and writing vectors to Qdrant.

## Local Quick Start

```bash
# From the repository root
(cd src/ingestion && uv sync --extra dev)
task local:sam:up
task local:sam:build
task local:sam:invoke
```

## Testing

```bash
task test:unit:ingestion
task test:coverage:ingestion
task local:test:integration:ingestion
```

## Local Development

Use [INGESTION_LOCAL_DEV.md](INGESTION_LOCAL_DEV.md) for the LocalStack, SAM, and Qdrant workflow.

## Service Notes

- The Lambda runtime code lives in `src/ingestion/lambda_handler/`.
- LocalStack handles S3, SSM, and Secrets Manager for local development.
- Bedrock calls use real AWS credentials even in local development.

For packaging and deploying the ingestion Lambda into a real AWS account, follow [AWS Deployment](../AWS_DEPLOYMENT.md).
