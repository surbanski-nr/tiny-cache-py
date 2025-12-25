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
- `CacheResponse`: `status: string`
- `CacheStats`: `size: int64`, `hits: int64`, `misses: int64`

## Client mapping

The `CacheClient` methods map to the RPCs as follows:

- `CacheClient.get(key)` calls `CacheService.Get(CacheKey)` and returns:
  - `None` when `CacheValue.found == false`
  - Otherwise it decodes and returns `CacheValue.value` (see `docs/specification.md` for details)
- `CacheClient.set(key, value, ttl)` calls `CacheService.Set(CacheItem)` and returns `True` when `CacheResponse.status == "OK"`
- `CacheClient.delete(key)` calls `CacheService.Delete(CacheKey)` and returns `True` when `CacheResponse.status == "OK"`
- `CacheClient.stats()` calls `CacheService.Stats(Empty)` and converts the response to a Python `dict`
- `CacheClient.ping()` currently uses `Stats` as a liveness check because there is no dedicated `Ping` RPC in the schema

## Notes

- The contract represents values as raw `bytes`, but the current client API is primarily string-oriented (it encodes values as UTF-8). If the client should support binary values end-to-end, the Python API should expose `bytes` explicitly or provide a serializer interface.
- `CacheResponse.status` is a free-form string, not an enum. Both client and server need to agree on the exact values and meaning.

