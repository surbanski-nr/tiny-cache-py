# Client behavior specification

This document describes the behavior of the current `CacheClient` implementation (not an aspirational design).

## Configuration and defaults

`CacheClient` defaults:

- `server_address`: `"localhost:50051"`
- `timeout`: `30.0` seconds (per operation; implemented via `asyncio.wait_for`)
- `max_retries`: `3` (total attempts = `max_retries + 1`)
- `retry_delay`: `1.0` seconds (exponential backoff multiplier)
- `default_ttl`: `3600` seconds
- `use_ssl`: `False`

## Connection lifecycle

- `await client.connect()` creates a single async gRPC channel and stub.
- `await client.close()` closes the channel, clears stub references, and marks the client as closed.
- `async with CacheClient(...) as client:` calls `connect()` on enter and `close()` on exit.

## Input validation

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

## Operations

### `get(key) -> Optional[str]`

- Validates `key`.
- Calls `CacheService.Get`.
- If `found == false`, returns `None`.
- If `found == true`, attempts to decode the returned bytes as UTF-8.
  - On decode failure, the current implementation returns the raw bytes even though the return type annotation says `Optional[str]`.

### `set(key, value, ttl=None) -> bool`

- Validates `key` and converts `value` to `str` then encodes it as UTF-8 bytes.
- TTL behavior:
  - If `ttl is None`, uses `default_ttl`.
  - If `ttl < 0`, raises `CacheValidationError`.
- Calls `CacheService.Set`.
- Returns `True` iff `CacheResponse.status == "OK"`.

### `delete(key) -> bool`

- Validates `key`.
- Calls `CacheService.Delete`.
- Returns `True` iff `CacheResponse.status == "OK"`, otherwise `False`.

### `stats() -> Dict[str, Any]`

- Calls `CacheService.Stats`.
- Returns:
  - `size`, `hits`, `misses` from the proto response
  - `hit_rate` computed as `hits / (hits + misses)` (or `0` when both are `0`)

### `ping() -> bool`

- Calls `CacheService.Stats` with a short timeout and returns `True` on success.
- Returns `False` on any exception.

## Retries, timeouts, and reconnection

- Each high-level operation (`get`, `set`, `delete`, `stats`) uses `_execute_with_retry(...)`.
- `_execute_with_retry`:
  - Ensures a connection exists (and runs a periodic health check).
  - Wraps the operation coroutine in `asyncio.wait_for(..., timeout=self.timeout)`.
  - Retries on:
    - `grpc.StatusCode.UNAVAILABLE` (with reconnection attempt + backoff)
    - `asyncio.TimeoutError` (with backoff)
  - Maps some gRPC status codes to custom exceptions.

## Error model

- `CacheValidationError`: input validation failures (key/value/ttl)
- `CacheConnectionError`: service unavailable or reconnect failures
- `CacheTimeoutError`: operation timed out after retries
- `CacheInvalidArgumentError`: maps `grpc.StatusCode.INVALID_ARGUMENT`
- `CacheError`: all other unexpected failures (generic wrapper)

