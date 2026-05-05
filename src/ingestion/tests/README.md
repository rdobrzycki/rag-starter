# Ingestion Tests

## Summary

The ingestion test suite is local-first.

- `unit/`: mocked dependency tests for handler logic and processing steps
- `integration/`: local fault-tolerance tests with fake external boundaries

If you only want the main confidence path, run:

```bash
task test:unit:ingestion
task local:test:integration:ingestion
```

## Main Commands

Recommended commands:

```bash
task test:unit:ingestion
task test:unit:ingestion:handler
task test:unit:ingestion:retry
task test:coverage:ingestion
task local:test:integration:ingestion
```

Direct `pytest` equivalents:

```bash
cd src/ingestion && uv run pytest tests/unit/ -v
cd src/ingestion && uv run pytest tests/integration/test_fault_tolerance_local.py -v
```

## What The Suite Proves

### Unit

Unit tests cover:

- S3 event parsing
- file validation
- text extraction
- correlation IDs
- retry behavior
- configuration loading from AWS clients
- embedding and vector storage orchestration
- error handling and rejection cases

Key files:

- `test_handler.py`
- `test_retry.py`
- `test_extractors.py`
- `test_validators.py`
- `test_extension_points.py`

### Integration

The integration suite checks the local ingestion flow under retry and fault conditions.

It is designed to validate:

- retryable failures at external boundaries
- local orchestration behavior
- idempotency and fault tolerance

The canonical entrypoint is:

```bash
task local:test:integration:ingestion
```

This path stays local and does not require live staging infrastructure.
