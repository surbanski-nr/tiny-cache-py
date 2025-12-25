# Codebase overview

## Purpose

`tiny-cache-py` is an async Python client library for the `tiny-cache` gRPC service. It wraps the generated gRPC stub with:

- Connection lifecycle management (`connect()`, `close()`, async context manager)
- Basic input validation for keys/values
- Simple retry + backoff for transient failures
- A small exception hierarchy to normalize failures

This repository is a client library, not a backend service. There is no frontend code in this repo.

## Repository layout (tracked files)

- `tiny_cache_py/`
  - `tiny_cache_py/client.py`: the main `CacheClient` implementation and custom exceptions
  - `tiny_cache_py/__init__.py`: package exports
- `cache.proto`: the gRPC service contract used by the client (source proto)
- `tests/`
  - `tests/test_client.py`: unit-style tests (mostly stubbed gRPC calls)
  - `tests/test_integration.py`: tests that require a running `tiny-cache` server
  - `tests/benchmark_client.py`: a benchmark script (requires a running server)
- Tooling/config:
  - `pyproject.toml`, `setup.py`, `requirements*.txt`
  - `Makefile`, `pytest.ini`, `mypy.ini`, `.gitignore`

## Generated gRPC code

The client imports `tiny_cache_py.cache_pb2` and `tiny_cache_py.cache_pb2_grpc`. These are generated from the `.proto` (typically via `make proto`).

## Primary runtime entry point

`tiny_cache_py/client.py` defines:

- `CacheClient`: async gRPC client with `get`, `set`, `delete`, `stats`, `ping`
- Exceptions: `CacheError` (base) and more specific subclasses used by the client

The `CacheClient` currently owns several responsibilities in one module:

- Parsing the server address and creating the gRPC channel/stub
- Input validation and value encoding/decoding
- Retry logic and connection health checking
- Mapping some gRPC failures into custom exceptions

## Testing

- Unit tests primarily mock the gRPC stub and validate client behavior in isolation (`tests/test_client.py`).
- Integration tests require a running `tiny-cache` server on `localhost:50051` (`tests/test_integration.py`).

## Tooling

- Formatting: `black` (configured in `pyproject.toml`)
- Type checking: `mypy` (configured in `pyproject.toml` and `mypy.ini`)
- Testing: `pytest` (configured in `pyproject.toml` and `pytest.ini`)

See `docs/code-review.md` for improvement opportunities and gaps between config, docs, and behavior.

