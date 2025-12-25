# API contract

This client communicates with the `tiny-cache` server using gRPC. The contract is defined by the Protocol Buffers schema in `cache.proto`.

## gRPC schema (current)

`cache.proto` defines a single `CacheService` with four RPCs:

- `Get(CacheKey) -> CacheValue`
- `Set(CacheItem) -> CacheResponse`
- `Delete(CacheKey) -> CacheResponse`
- `Stats(Empty) -> CacheStats`

Messages:

- `CacheKey`: `key: string`
- `CacheItem`: `key: string`, `value: bytes`, `ttl: int32`
- `CacheValue`: `found: bool`, `value: bytes`
- `CacheResponse`: `status: CacheStatus`
- `CacheStats`: `size: int32`, `hits: int32`, `misses: int32`, `evictions: int32`, `hit_rate: double`, `memory_usage_bytes: int64`, `max_memory_bytes: int64`, `max_items: int32`

Enums:

- `CacheStatus`: `CACHE_STATUS_UNSPECIFIED`, `OK`, `ERROR`

## Client mapping

The `CacheClient` methods map to the RPCs as follows:

- `CacheClient.get(key)` calls `CacheService.Get(CacheKey)` and returns:
  - `None` when `CacheValue.found == false`
  - Otherwise it decodes and returns `CacheValue.value` (see `docs/specification.md` for details)
- `CacheClient.get_bytes(key)` calls `CacheService.Get(CacheKey)` and returns raw `bytes` when `CacheValue.found == true`
- `CacheClient.set(key, value, ttl)` calls `CacheService.Set(CacheItem)` and returns `True` when `CacheResponse.status == CacheStatus.OK`
- `CacheClient.set_bytes(key, value, ttl)` calls `CacheService.Set(CacheItem)` and returns `True` when `CacheResponse.status == CacheStatus.OK`
- `CacheClient.delete(key)` calls `CacheService.Delete(CacheKey)` and returns `True` when `CacheResponse.status == CacheStatus.OK`
- `CacheClient.stats()` calls `CacheService.Stats(Empty)` and converts the response to a Python `dict`
- `CacheClient.ping()` currently uses `Stats` as a liveness check because there is no dedicated `Ping` RPC in the schema

## Notes

- The contract represents values as raw `bytes`. The client exposes both:
  - Text helpers (`get`/`set`) that encode/decode UTF-8
  - Binary helpers (`get_bytes`/`set_bytes`) that round-trip `bytes` without decoding
- `CacheResponse.status` is an enum. The `tiny-cache` reference server uses `CacheStatus.OK` for successful operations.
- The client currently uses `Stats` for connection health checking because the server does not expose the standard gRPC Health Checking Protocol.
