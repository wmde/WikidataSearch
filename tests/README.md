# Tests

This folder contains backend tests split into three layers:

- **Unit (`tests/unit`)**: Fast isolated tests with stubs/mocks. Use these for quick local checks while coding.
- **Integration (`tests/integration`)**: Route-level tests against a running local API server.
- **Analysis/Benchmark (`tests/analysis`)**: Slower split-analysis style checks for retrieval behavior.

## What Is Covered

### Unit (`tests/unit`)

- Route validation behavior for `item`, `property`, and `similarity` handlers.
- Search-call argument wiring (filters, lowercased language, `ks_K` behavior).
- Error-path checks (`422` cases like invalid `instanceof`, too many IDs, disabled vectors).
- Helper logic in search services (similarity merging, dedup behavior, keyword cleaning).

### Integration (`tests/integration`)

- Local HTTP endpoint contracts (status codes, payload shape, result limits).
- Route behavior for `/languages`, `/item/query/`, `/property/query/`, `/similarity-score/`.
- Validation responses for invalid request shapes (empty query, oversized `K`, etc.).
- Split-analysis style API checks (`lang=all` vs language-specific behavior).

### Analysis/Benchmark (`tests/analysis`)

- V1 vs V2 runtime sampling across multilingual query sets.
- Top-N similarity proxy comparisons.
- Language exposure metrics for raw similarity results.
- Expanded-`K` recall checks (whether larger `K` recovers V1-only IDs).

## Setup

From project root:

```bash
uv sync --locked
```

## Common Commands

Run recommended fast suite (unit + integration):

```bash
uv run pytest -q tests/unit tests/integration
```

Run unit tests only:

```bash
uv run pytest -q tests/unit
```

Run integration tests only:

```bash
uv run pytest -q tests/integration -m integration -rs
```

Run analysis/benchmark tests only:

```bash
uv run pytest -q tests/analysis/test_split_benchmark.py -m "analysis and benchmark" -rs
```

Run all tests:

```bash
uv run pytest -q tests
```

## Notes

- Integration tests are local-only and expect the API at `http://127.0.0.1:8080`.
- Analysis/benchmark tests require valid Astra/Jina keys in `.env` or `tests/.env`.
