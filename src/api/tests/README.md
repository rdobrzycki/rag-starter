# API Tests

## Summary

The API test suite is split into three layers:

- `unit/`: fast, isolated tests
- `integration/`: local end-to-end tests with fake Bedrock and in-memory Qdrant
- `efficiency/`: optional quality and performance checks against a running local API

If you only want the main confidence path, run:

```bash
task test:unit:api
task local:test:integration:api
```

## Main Commands

Recommended commands:

```bash
task test:unit:api
task local:test:integration:api
task test:coverage:api
task local:test:efficiency:performance
```

Direct `pytest` equivalents:

```bash
uv run pytest tests/unit/ -v
uv run pytest tests/integration/ -v
EFFICIENCY_API_URL=http://localhost:8080 uv run pytest tests/efficiency/ -v -m efficiency
```

## What Each Layer Proves

### Unit

Unit tests cover logic that should work without live services:

- rate limiting
- retry behavior
- request correlation
- chunking and parsing helpers
- config loading and defaults
- response validation and route behavior

### Integration

Integration tests prove the local application wiring works end to end without live AWS dependencies.

Main focus areas:

- core query and document flows
- API contract stability
- error handling
- data integrity and idempotency
- concurrency behavior
- health and readiness endpoints
- feedback endpoints

Key files:

- `test_core_rag_flows.py`
- `test_api_contract.py`
- `test_error_handling.py`
- `test_data_integrity.py`
- `test_concurrency.py`

### Efficiency

Efficiency tests run against a live local API and are useful when tuning quality or latency.

- `task local:test:efficiency` needs `OPENAI_API_KEY` for DeepEval quality metrics
- `task local:test:efficiency:performance` does not

## When To Run What

- Changing business logic or routing: run unit + integration
- Changing retry, middleware, or config behavior: run unit + integration
- Changing prompts or retrieval quality: run efficiency tests too
- Preparing a release: run coverage and the full local integration suite

## Test Helpers

Shared support lives in `conftest.py`.

Useful helpers include:

- fake dependency overrides for Bedrock, embeddings, LLM, and Qdrant
- concurrent request helpers
- response schema validation helpers

The important takeaway is that the integration suite is designed to stay local-first and does not require live Bedrock or Qdrant.
