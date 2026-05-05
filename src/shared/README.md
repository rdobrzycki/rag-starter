# Shared Utilities

Shared helpers used by both the API and the ingestion Lambda.

## What Is Here

- `correlation.py`: request correlation IDs
- `logging.py`: structured logging with correlation ID injection
- `retry.py`: exponential backoff for transient failures
- `chunking.py`: text chunking helpers for embeddings

## Start Here

Most consumers only need these entrypoints:

```python
from shared.correlation import get_or_create_correlation_id, set_correlation_id
from shared.logging import setup_logging
from shared.retry import retry_with_backoff
```

Minimal example:

```python
setup_logging(service="rag-api")

correlation_id = get_or_create_correlation_id()
set_correlation_id(correlation_id)

@retry_with_backoff(operation_name="bedrock_embed")
def call_dependency() -> None:
    pass
```

## Correlation IDs

Use correlation IDs to trace one request across API, Lambda, Qdrant, and Bedrock.

Main functions:

- `get_or_create_correlation_id(source=None)`
- `set_correlation_id(correlation_id)`
- `get_correlation_id()`
- `reset_correlation_id()`

Why it works well:

- async-safe via `ContextVar`
- isolated across threads and async tasks
- easy to set in middleware or handlers

Typical API flow:

```python
correlation_id = get_or_create_correlation_id(request.headers.get("X-Request-ID"))
set_correlation_id(correlation_id)
response.headers["X-Request-ID"] = correlation_id
```

## Logging

`setup_logging()` configures structured logs and injects the active correlation ID into each record.

JSON logs include:

- `timestamp`
- `level`
- `message`
- `service`
- `logger`
- `correlation_id`
- `exception` when present

Use JSON logs for deployed services and plain text only when debugging locally.

## Retry

`retry_with_backoff()` wraps transient dependency calls.

Typical use:

```python
@retry_with_backoff(
    max_retries=3,
    base_delay=1.0,
    max_delay=30.0,
    retryable_exceptions=(ConnectionError, TimeoutError),
    operation_name="qdrant_upsert",
)
def upsert() -> None:
    pass
```

Use it for external boundaries such as Bedrock, Qdrant, SSM, or Secrets Manager.

## Chunking

`chunking.py` contains the shared text splitting logic used before embedding generation.

Use it when:

- document text must be broken into overlapping windows
- API and ingestion need consistent chunk boundaries
- tests need deterministic chunking behavior

## Testing Notes

These utilities are intentionally test-friendly.

- set and reset correlation IDs directly in tests
- use retry decorators around fake transient failures
- keep chunking assertions deterministic

If you only need repo-wide verification, run from the repository root:

```bash
task test:unit
```
