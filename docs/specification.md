# Client behavior specification

This document describes the behavior of the current `CacheClient` implementation (not an aspirational design).

## Configuration and defaults

`CacheClient` defaults:

- `server_address`: `"localhost:50051"`
- `timeout`: `30.0` seconds (per RPC deadline via gRPC `timeout=...`)
- `connect_timeout`: `None` (when set, `connect()` waits for channel readiness up to this deadline)
- `max_retries`: `3` (total attempts = `max_retries + 1`)
- `retry_delay`: `1.0` seconds (base delay; exponential backoff with jitter)
- `default_ttl`: `3600` seconds
- `use_ssl`: `False`
- `health_check_interval`: `30.0` seconds (set to `0`/`None` to disable)
- `health_check_timeout`: `5.0` seconds
- `health_check_method`: `"stats"` (or `"grpc_health"` when `grpcio-health-checking` is installed)
- `default_metadata`: `None`

## Connection lifecycle

- `await client.connect()` is concurrency-safe and reuses a single async gRPC channel and stub.
- `await client.close()` closes the channel, clears stub references, and marks the client as closed.
- `async with CacheClient(...) as client:` calls `connect()` on enter and `close()` on exit.

## Input validation

### Server address parsing

- Supports `grpc://host:port` (forces insecure channel) and `grpcs://host:port` (forces TLS) prefixes.
- Supports bracket-form IPv6 targets like `[::1]:50051`.

### Key validation

`_validate_key(key)` enforces:

- `key` must be a `str`
- `key` must be non-empty
- `len(key)` must be `<= 250`

### Value handling

`_validate_value(value)` converts most inputs to `str`:

- `str` stays `str`
- `int`, `float`, `bool` convert via `str(value)`
- `bytes` are decoded as UTF-8; invalid UTF-8 raises `CacheValidationError`
- Other objects convert via `str(value)` (conversion failures raise `CacheValidationError`)

Binary values are supported via dedicated methods:

- `get_bytes(...)` returns raw bytes without decoding
- `set_bytes(...)` stores bytes-like values without UTF-8 encoding

## Operations

All RPC-like methods accept per-call overrides:

- `timeout`: overrides the client default RPC deadline (must be positive)
- `max_retries` / `retry_delay`: override the retry budget/backoff
- `metadata`: extra gRPC metadata tuples (merged with `default_metadata`)

### `get(key, ...) -> Optional[str]`

- Validates `key`.
- Calls `CacheService.Get`.
- If `found == false`, returns `None`.
- If `found == true`, decodes the returned bytes as UTF-8 and returns `str`.
  - On decode failure, raises `CacheError`.

### `get_bytes(key, ...) -> Optional[bytes]`

- Validates `key`.
- Calls `CacheService.Get`.
- If `found == false`, returns `None`.
- If `found == true`, returns the raw `bytes` value without decoding.

### `set(key, value, ttl=None, ...) -> bool`

- Validates `key` and converts `value` to `str` then encodes it as UTF-8 bytes.
- TTL behavior:
  - If `ttl is None`, uses `default_ttl`.
  - If `ttl == 0`, the server treats it as "no expiration".
  - If `ttl < 0`, raises `CacheValidationError`.
- Calls `CacheService.Set`.
- Returns `True` iff `CacheResponse.status == CacheStatus.OK`.

### `set_bytes(key, value, ttl=None, ...) -> bool`

- Validates `key`.
- Validates `value` is `bytes`, `bytearray`, or `memoryview` and stores the raw bytes.
- TTL behavior matches `set(...)`.
- Calls `CacheService.Set`.
- Returns `True` iff `CacheResponse.status == CacheStatus.OK`.

### `delete(key, ...) -> bool`

- Validates `key`.
- Calls `CacheService.Delete`.
- Delete is idempotent: the reference server responds with `CacheStatus.OK` even when the key is missing.
- Returns `True` iff `CacheResponse.status == CacheStatus.OK`.

### `stats(...) -> Dict[str, Any]`

- Calls `CacheService.Stats`.
- Returns a `dict` containing:
  - `size`, `hits`, `misses`, `evictions`, `hit_rate`
  - `memory_usage_bytes`, `max_memory_bytes`, `max_items`

### `ping(...) -> bool`

- Ensures a connection exists, then calls `CacheService.Stats` with a short timeout and returns `True` on success.
- Returns `False` on any exception.

## Retries, timeouts, and reconnection

- Each high-level operation (`get`, `get_bytes`, `set`, `set_bytes`, `delete`, `stats`) uses `_execute_with_retry(...)`.
- `_execute_with_retry`:
  - Ensures a connection exists (and runs a periodic health check).
  - Retries on:
    - `grpc.StatusCode.UNAVAILABLE` (with reconnection attempt + jittered exponential backoff)
    - `grpc.StatusCode.DEADLINE_EXCEEDED` (with backoff)
  - Propagates cancellation (`asyncio.CancelledError`) without wrapping.
  - Maps some gRPC status codes to custom exceptions.

## Error model

- `CacheValidationError`: input validation failures (key/value/ttl)
- `CacheConnectionError`: service unavailable or reconnect failures
- `CacheTimeoutError`: operation timed out after retries
- `CacheInvalidArgumentError`: maps `grpc.StatusCode.INVALID_ARGUMENT`
- `CacheError`: all other unexpected failures (generic wrapper)
