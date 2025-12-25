# Architecture

## What this repo is (and is not)

- This is a Python client library for a gRPC cache service.
- There is no backend service implementation in this repository.
- There is no frontend code in this repository.

Because of that, applying "hexagonal architecture for backend" and "feature sliced design for frontend" is mostly about:

- Keeping clean boundaries between "core logic" (API, validation, retries, serialization) and "infrastructure" (gRPC transport)
- Organizing code so it can grow without a single module accumulating unrelated responsibilities

## Current structure

The current implementation is centered around `tiny_cache_py/client.py`:

- `CacheClient` mixes several concerns:
  - gRPC channel + stub lifecycle
  - input validation
  - value serialization (string-oriented)
  - retry logic and reconnection
  - connection health checking
  - error mapping and logging

This is fine for a small codebase, but it limits testability and makes future extensions (alternate serialization, metadata, multiple transports, pooling) harder.

## Suggested target architecture (hexagonal-inspired)

For a client library, a pragmatic hexagonal-style shape can look like:

- Domain / core:
  - A stable "port" (interface) that defines cache operations and error semantics
  - Serialization concerns (how values become bytes and back)
  - Retry policy definitions (what is retryable, backoff strategy)
- Adapters / infrastructure:
  - gRPC transport implementation (channel, stub, call options, metadata)
  - Optional health checking mechanism

### Suggested module layout

If the library grows, consider splitting into:

- `tiny_cache_py/errors.py`: exception hierarchy
- `tiny_cache_py/config.py`: configuration and env-based defaults (if supported)
- `tiny_cache_py/serialization.py`: value codecs (text, bytes, JSON)
- `tiny_cache_py/retry.py`: retry/backoff policies
- `tiny_cache_py/transports/grpc.py`: gRPC channel + stub adapter
- `tiny_cache_py/client.py`: small orchestration layer that composes the above

This keeps the public API (`CacheClient`) stable while allowing internal refactors and easier testing.

## Frontend: feature sliced design

No frontend exists in this repo. If a frontend is added later, feature sliced design is easiest to apply when:

- UI code is separated into `shared/`, `entities/`, `features/`, `widgets/`, `pages/`, `app/`
- Cross-cutting concerns (API clients, types, design system) live in `shared/`

Until a frontend exists, the best action is to keep frontend-related structure out of this repository to avoid false architecture signals.

