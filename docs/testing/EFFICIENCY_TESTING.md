# RAG Efficiency Testing

Efficiency tests measure both **RAG quality** (faithfulness, relevancy, context precision/recall via [DeepEval](https://docs.confident-ai.com/)) and **query latency** (p50/p95/p99) against a running API.

## Prerequisites

- A running RAG API (local or deployed). See [API Local Dev](../api/API_LOCAL_DEV.md).
- Extra test dependencies installed:

```bash
cd src
uv sync --extra efficiency
```

## Running Tests

### CLI (recommended — outputs JSON + optional PoV report)

```bash
python -m tests.efficiency.cli \
  --api-url http://localhost:8000 \
  --output results.json \
  --test-types all          # all | quality | performance
```

Generate a markdown PoV report alongside JSON:

```bash
python -m tests.efficiency.cli \
  --api-url http://localhost:8000 \
  --output results.json \
  --pov report.md
```

### Pytest (individual test runs)

```bash
cd src
uv run pytest src/api/tests/efficiency/ -m efficiency -v
```

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--api-url` | `http://localhost:8000` | RAG API base URL |
| `--output` | `efficiency_results.json` | JSON results output path |
| `--test-types` | `all` | `all`, `quality`, or `performance` |
| `--pov` | *(none)* | Optional markdown PoV report path |
| `--max-quality-cases` | `15` | Number of test cases used for quality metrics |

## Quality Metrics

Measured via [DeepEval](https://docs.confident-ai.com/) with a threshold of **0.7** for each:

| Metric | Description |
|--------|-------------|
| `faithfulness` | Answer is grounded in retrieved context |
| `answer_relevancy` | Answer addresses the question |
| `contextual_precision` | Retrieved chunks ranked by relevance |
| `contextual_recall` | Expected content present in retrieved context |

## Performance Thresholds

| Metric | Pass condition |
|--------|---------------|
| P95 query latency | < 5 000 ms |

## Test Fixtures

Test cases live in `src/api/tests/efficiency/fixtures/test_cases.json`. Each entry has:

```json
{
  "input": "What is the refund policy?",
  "expected_output": "Refunds are processed within 5 business days."
}
```

Add domain-specific cases to improve coverage of your ingested documents.

## Output Format

The JSON output (`--output`) contains:

```json
{
  "summary": { "passed": true, "quality_passed": true, "performance_passed": true },
  "quality": {
    "faithfulness": 0.85,
    "answer_relevancy": 0.91,
    "contextual_precision": 0.78,
    "contextual_recall": 0.82
  },
  "performance": { "p50_ms": 820, "p95_ms": 1340, "p99_ms": 2100 }
}
```
