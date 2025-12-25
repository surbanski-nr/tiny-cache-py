# Code review TODOs

This is an intentionally exhaustive TODO list, split into small items. Each item includes the rationale and a concrete suggestion.

## Packaging and distribution

- [ ] Ensure generated gRPC modules are available in a clean checkout.
  - Why: `tiny_cache_py/client.py` imports `tiny_cache_py.cache_pb2` and `tiny_cache_py.cache_pb2_grpc`, but these files are not tracked; a fresh clone cannot import the package unless protobuf generation has been run.
  - Suggestion: Either commit the generated files, generate them as part of the build (PEP 517/setuptools hook), or vendor the proto and generate during `sdist`/`wheel` creation.

- [ ] Decide whether `cache.proto` in this repo is the source of truth.
  - Why: `cache.proto` is tracked here, but `Makefile:proto` generates code from `../tiny-cache/cache.proto`, which can drift from the tracked schema.
  - Suggestion: Pick one source of truth: vendor the server proto into this repo (and generate from it), or remove the tracked `cache.proto` and document the external dependency clearly.

- [ ] Align `pyproject.toml` and `setup.py` packaging metadata (or remove one).
  - Why: There are two packaging configurations with conflicting fields (versioning, dependencies, classifiers, URLs). This creates ambiguity for maintainers and users and risks publishing inconsistent artifacts.
  - Suggestion: Prefer `pyproject.toml` as the single source (PEP 517). If `setup.py` is kept for compatibility, make it a thin shim that reads metadata from `pyproject.toml`.

- [ ] Align package classifiers and project URLs between packaging files.
  - Why: `pyproject.toml` and `setup.py` declare different development status and repository URLs, which can confuse users and tooling.
  - Suggestion: Keep classifiers, URLs, authorship, and keywords consistent across the chosen packaging source(s).

- [ ] Align the declared versioning strategy.
  - Why: `pyproject.toml` declares `dynamic = ["version"]` via `setuptools_scm`, while `setup.py` hardcodes `version="0.1.0"`.
  - Suggestion: Use one strategy consistently. If using `setuptools_scm`, remove the hardcoded version and document tagging conventions.

- [ ] Unify dependency declarations across `pyproject.toml`, `requirements.txt`, and `setup.py`.
  - Why: Runtime and dev dependencies are duplicated in three places with different version ranges, which will drift over time.
  - Suggestion: Choose a single primary source of dependencies (commonly `pyproject.toml`), then generate requirements files from it or keep requirements as constraints only.

- [ ] Align dev dependency sets between `requirements-dev.txt` and `pyproject.toml` optional deps.
  - Why: The dev dependency lists differ (for example, coverage and lint tools), increasing the chance that one path breaks.
  - Suggestion: Either derive `requirements-dev.txt` from `pyproject.toml` (or vice versa) or document why they differ.

- [ ] Decide whether to pin or range-limit dependencies in requirements.
  - Why: `pyproject.toml` uses ranges while `requirements-dev.txt` pins versions; this impacts reproducibility and upgrade cadence.
  - Suggestion: Use pinned dev requirements for reproducible local tooling and CI, and use compatible ranges in published package metadata.

- [ ] Move `grpcio-tools` out of runtime dependencies if it is not required at runtime.
  - Why: The runtime client only needs `grpcio` and `protobuf`; `grpcio-tools` is typically needed only for code generation.
  - Suggestion: Keep `grpcio-tools` in dev/optional dependencies only (`[project.optional-dependencies]`), and remove it from `requirements.txt` and runtime `install_requires` unless there is a documented runtime need.

- [ ] Fix `setup.py` `package_data` / proto packaging intent.
  - Why: `setup.py` includes `package_data={"tiny_cache_py": ["*.proto"]}` but the repo proto is at the root and the generated code is in `tiny_cache_py/`.
  - Suggestion: If the proto should ship, store it under `tiny_cache_py/` (or include it via `MANIFEST.in`). If not, remove the proto packaging stanza.

- [ ] Add a CI/build-time check that the generated gRPC code matches the proto.
  - Why: Without an automated check, `cache_pb2*.py` can silently drift from `cache.proto`.
  - Suggestion: In CI, regenerate protobuf code and compare it to what is shipped (or validate a checksum).

## Protobuf/runtime compatibility

- [ ] Pin or constrain protobuf versions to avoid gencode/runtime major mismatches.
  - Why: The generated `cache_pb2.py` in the workspace requires protobuf runtime major version 6, but the current environment had protobuf runtime major version 5, causing import-time failures.
  - Suggestion: Document and enforce a compatible `protobuf` runtime range that matches the generator version, and regenerate code using the same major version used at runtime.

- [ ] Pin `grpcio-tools` (generator) to a compatible protobuf major.
  - Why: The generated code embeds assumptions about the protobuf runtime major.
  - Suggestion: Treat `grpcio-tools` and `protobuf` as a compatible pair and document the supported combinations.

- [ ] Document the supported Python versions and verify dependency availability for those versions.
  - Why: Classifiers target Python 3.8-3.12, but local development environments may differ; protobuf/grpc wheels availability varies by Python version.
  - Suggestion: Add a supported-version matrix in docs and validate via CI (tox/nox) for those Python versions.

## Tooling and configuration

- [ ] Remove duplication between `pyproject.toml` and `mypy.ini`.
  - Why: Mypy settings exist in both files; it is easy for them to diverge and produce surprising results.
  - Suggestion: Keep all mypy settings in `pyproject.toml` (or `mypy.ini`) and delete the other.

- [ ] Remove duplication between `pyproject.toml` and `pytest.ini`.
  - Why: Pytest settings exist in both files; if one is ignored or partially read, test discovery and defaults can change unexpectedly.
  - Suggestion: Keep pytest settings in `pyproject.toml` (preferred) and delete `pytest.ini`, or fix `pytest.ini` and remove pytest settings from `pyproject.toml`.

- [ ] Decide on a single `pytest-asyncio` mode (`strict` vs `auto`) and document it.
  - Why: Different asyncio modes change how fixtures and event loops behave, and mixing modes makes failures harder to debug.
  - Suggestion: Prefer `strict` for predictable behavior, and ensure tests comply.

## Public API correctness and usability

- [ ] Fix `test_client.py` usage of `CacheClient` constructor.
  - Why: `CacheClient("localhost", 50051, timeout=5.0)` passes `50051` into the `max_retries` parameter, not the port, which makes the script misleading and potentially harmful.
  - Suggestion: Update usage to `CacheClient("localhost:50051", timeout=5.0)` or redesign the constructor to accept `host` and `port` explicitly.

- [ ] Remove `sys.path` manipulation from `test_client.py`.
  - Why: `sys.path.insert(0, '.')` is a common source of import confusion and hides packaging issues.
  - Suggestion: Convert the script into an `examples/` module runnable as `python -m ...`, or ensure users install the package (`pip install -e .`) before running it.

- [ ] Make `CacheClient.is_connected()` reflect both channel and stub readiness.
  - Why: It currently checks only `_channel` and `_closed`; `_stub` can be `None` and still report "connected", which can lead to attribute errors on RPC calls.
  - Suggestion: Treat the client as connected only when both `_channel` and `_stub` are present and the client is not closed.

- [ ] Make `connect()` robust when `_channel` exists but `_stub` does not.
  - Why: `connect()` short-circuits when `_channel` is not `None`, even if the stub was cleared, leaving the client in a broken state.
  - Suggestion: Consider "connected" only when channel and stub are set, and re-create the stub if missing.

- [ ] Decide whether `CacheClient.get` returns text, bytes, or both.
  - Why: The method is annotated as `Optional[str]` but may return raw `bytes` when decoding fails; this breaks type expectations and can cause runtime errors downstream.
  - Suggestion: Choose one of:
    - Always return `bytes` (and offer a `get_text()` helper)
    - Always return `str` (and raise on non-UTF8 bytes)
    - Return `Optional[Union[str, bytes]]` and document it explicitly

- [ ] Make value handling symmetric for `set` and `get`.
  - Why: `set` forces values into UTF-8 bytes, but `get` can return bytes from the server that were not produced by this client.
  - Suggestion: Introduce explicit codecs (text/bytes/JSON) and store codec choice in the client configuration.

- [ ] Add a first-class binary API if bytes support is required.
  - Why: The proto contract uses `bytes`, so binary values are a natural use case for caches.
  - Suggestion: Add `get_bytes()` / `set_bytes()` (or a `Codec` interface) rather than overloading the text methods.

- [ ] Revisit server address parsing.
  - Why: The current split-on-colon logic fails for IPv6 targets and other gRPC target syntaxes.
  - Suggestion: Accept a full gRPC target string and pass it through unchanged, or implement robust parsing (including IPv6 bracket form).

- [ ] Clarify the meaning of `default_ttl` and TTL units/semantics.
  - Why: TTL is an `int32` in the proto, but server-side semantics (0 meaning no TTL vs immediate expiry) are not documented here.
  - Suggestion: Document TTL behavior in `docs/specification.md` and align validation rules to the server contract.

- [ ] Decide whether `delete` should expose "not found" distinctly.
  - Why: The library defines `CacheNotFoundError` but does not use it; `delete` returns `False` for non-OK statuses.
  - Suggestion: Either remove `CacheNotFoundError`, or add an option like `delete(..., raise_on_missing=True)`.

## Typing and mypy compliance

- [ ] Add type annotations to all public and internal methods to satisfy strict mypy.
  - Why: `mypy` is configured with strict options, but methods such as `__aenter__`, `__aexit__`, and `_execute_with_retry` are missing full type signatures.
  - Suggestion: Annotate return types and callable parameters (for `_execute_with_retry`, consider `Callable[[], Awaitable[T]]` with a `TypeVar`).

- [ ] Add a `py.typed` marker if this package intends to be type-checked by downstream users.
  - Why: Shipping type hints without `py.typed` can lead to type checkers treating the package as untyped.
  - Suggestion: Add `tiny_cache_py/py.typed` and include it in package data.

- [ ] Remove unused imports and dead code.
  - Why: `tiny_cache_py/client.py` imports `Union` but does not use it; `CacheNotFoundError` is currently unused.
  - Suggestion: Remove unused imports and either use or remove unused exceptions.

- [ ] Avoid type drift between implementation and docs.
  - Why: The README advertises method signatures and behaviors that do not exactly match the code (for example, environment-based configuration that is not implemented).
  - Suggestion: Keep `docs/specification.md` and README in sync with the implemented API.

## Connection management and concurrency

- [ ] Make `connect()` concurrency-safe.
  - Why: If multiple coroutines call operations concurrently on a disconnected client, they can race through `connect()` and create multiple channels, leaking resources.
  - Suggestion: Use an `asyncio.Lock` around connection establishment and reconnection.

- [ ] Make `_reconnect()` concurrency-safe and idempotent.
  - Why: Multiple failing operations may attempt reconnection simultaneously, leading to churn and inconsistent client state.
  - Suggestion: Gate reconnection with the same lock and short-circuit if another reconnect already succeeded.

- [ ] Ensure connection health checks do not run when the stub is missing.
  - Why: `_check_connection_health()` assumes `_stub` is always present, which is not guaranteed by the current `is_connected()` implementation.
  - Suggestion: If `_stub` is `None`, rebuild it (or reconnect) before running health checks.

- [ ] Consider waiting for channel readiness during `connect()`.
  - Why: `connect()` currently constructs the channel/stub but does not wait for readiness; the first real RPC then becomes the readiness probe.
  - Suggestion: Optionally `await channel.channel_ready()` with a timeout, and surface a clear connection error if it fails.

- [ ] Make health checking configurable.
  - Why: The current health check uses `Stats` and is hardcoded to a 30-second interval, which may not match all workloads.
  - Suggestion: Expose `health_check_interval` (and possibly the health check strategy) via constructor parameters.

- [ ] Consider using standard gRPC health checking instead of `Stats`.
  - Why: A dedicated health endpoint avoids coupling liveness to the stats RPC and keeps semantics clear.
  - Suggestion: Use the gRPC Health Checking Protocol if the server supports it, or add a dedicated `Ping` RPC to the proto.

## Retry logic and error mapping

- [ ] Preserve exception causes when wrapping errors.
  - Why: Current code raises new exceptions without chaining, which loses root-cause information.
  - Suggestion: Use `raise ... from e` consistently when converting exceptions.

- [ ] Do not swallow cancellation.
  - Why: Catch-all `except Exception` blocks can convert cancellation into `CacheError`, breaking cooperative cancellation patterns in async applications.
  - Suggestion: Add `except asyncio.CancelledError: raise` before generic exception handling.

- [ ] Map additional gRPC status codes explicitly.
  - Why: Real-world gRPC failures include `DEADLINE_EXCEEDED`, `UNAUTHENTICATED`, `PERMISSION_DENIED`, etc. The current mapping is partial.
  - Suggestion: Add a mapping table and document which errors are retryable vs fatal.

- [ ] Prefer gRPC timeouts/deadlines over `asyncio.wait_for` where possible.
  - Why: `asyncio.wait_for` cancels the coroutine and can lead to `CANCELLED` errors instead of `DEADLINE_EXCEEDED`.
  - Suggestion: Pass `timeout=` to gRPC calls (or use per-call deadlines) and treat `DEADLINE_EXCEEDED` as `CacheTimeoutError`.

- [ ] Add jitter to exponential backoff.
  - Why: Pure exponential backoff can synchronize many clients and amplify load spikes after an outage.
  - Suggestion: Apply random jitter (full or equal jitter) to retry delays.

- [ ] Make retry policy configurable per operation.
  - Why: Different operations and deployments may require different retry budgets and status-code policies.
  - Suggestion: Accept a `RetryPolicy` object or per-call overrides for timeout/max retries.

## Logging and observability

- [ ] Avoid eager string formatting in log calls.
  - Why: f-strings are evaluated even if the log level is disabled, adding unnecessary overhead.
  - Suggestion: Use logger parameterized formatting (`logger.debug("...", arg)`).

- [ ] Remove unused module-level logger in `tiny_cache_py/client.py` (or use it consistently).
  - Why: There is a module-level `logger` and a per-instance `self.logger`; keeping both without a clear reason adds noise.
  - Suggestion: Keep only one logging pattern (prefer `self.logger` for configurability).

- [ ] Review log levels for library-embedded logging.
  - Why: Logging `info` on every connect/reconnect may be too noisy for a client library.
  - Suggestion: Move high-frequency logs to `debug` and keep `info` for notable state changes or failures.

- [ ] Add a strategy for correlation IDs / request identifiers.
  - Why: Troubleshooting distributed systems benefits from correlating client-side retries and failures to server logs.
  - Suggestion: Support optional gRPC metadata injection per call (or via interceptors) to carry correlation IDs.

## Test suite structure and reliability

- [ ] Fix the `pytest.ini` section header or remove the file.
  - Why: `pytest.ini` uses `[tool:pytest]` which is typically for `setup.cfg`; this can cause pytest to ignore settings and change test discovery behavior.
  - Suggestion: Use `[pytest]` in `pytest.ini`, or remove it and keep configuration only in `pyproject.toml`.

- [ ] Ensure `pytest` does not collect the root `test_client.py` as a test module.
  - Why: It is a manual script and currently breaks test collection when imported.
  - Suggestion: Rename it (for example `examples/manual_client_test.py`) or configure `python_files` and `testpaths` correctly.

- [ ] Separate unit and integration tests cleanly.
  - Why: `Makefile:test` currently runs all tests, including integration tests that require a running server.
  - Suggestion: Add `make test-unit` and `make test-integration` targets, and make `make test` default to unit tests.

- [ ] Apply the `unit` marker consistently (or remove it).
  - Why: README suggests running `pytest -m unit`, but only a small subset of tests are marked `unit`, which makes the command misleading.
  - Suggestion: Mark all unit tests with `@pytest.mark.unit`, or use directory-based selection (`tests/unit`, `tests/integration`) instead of markers.

- [ ] Make integration tests self-skipping when the server is not available.
  - Why: Integration tests should fail meaningfully in CI or developer environments when prerequisites are missing.
  - Suggestion: Add a fixture that checks connectivity and calls `pytest.skip(...)` when the server is unreachable.

- [ ] Remove hard-coded latency thresholds from integration tests or mark them as `slow`.
  - Why: Latency depends on machine load and environment; fixed thresholds are flaky.
  - Suggestion: Move performance expectations to benchmarks or make thresholds configurable and opt-in.

- [ ] Avoid printing from tests.
  - Why: Prints add noise in CI logs and can hide failures; pytest already provides reporting.
  - Suggestion: Use logging with appropriate levels or rely on assertions only.

- [ ] Remove non-ASCII decorative symbols from tests and examples.
  - Why: Project guidelines prohibit emoticons/unicode decorative symbols; current tests and examples include such characters in strings and output.
  - Suggestion: Replace them with plain ASCII equivalents.

- [ ] Use realistic invalid ports in integration tests.
  - Why: Using an out-of-range port can fail earlier than the intended "connection refused" scenario.
  - Suggestion: Use a valid but unused port (for example `localhost:59999`) and assert the expected error path.

- [ ] Add tests for concurrency edge cases.
  - Why: Connection establishment and reconnection are stateful and can race under load.
  - Suggestion: Add tests that run multiple concurrent operations from a disconnected state and assert only one channel is created.

- [ ] Add tests for cancellation propagation.
  - Why: Correct cancellation is important for async libraries used in servers and workers.
  - Suggestion: Cancel an in-flight `get` and assert `asyncio.CancelledError` is propagated.

## Documentation and examples

- [ ] Update README claims about connection pooling.
  - Why: The implementation uses a single persistent channel, not a pool.
  - Suggestion: Either implement pooling or change the wording to "persistent channel reuse".

- [ ] Remove or implement environment-variable configuration described in README.
  - Why: README lists `CACHE_SERVER_ADDRESS`, `CACHE_MAX_RETRIES`, `CACHE_TIMEOUT`, but the client does not read environment variables.
  - Suggestion: Add env parsing in a config module or delete the section to avoid misleading users.

- [ ] Fix README benchmark command path.
  - Why: README references a `benchmarks/` path that does not exist; the benchmark script is under `tests/`.
  - Suggestion: Update the path or move the benchmark script into a dedicated `benchmarks/` directory.

- [ ] Document proto generation expectations.
  - Why: The code depends on generated files, and generation currently depends on an external repo layout (`../tiny-cache`).
  - Suggestion: Add a doc section describing how to generate protobuf code and how to keep it in sync.

## Code style and maintainability

- [ ] Split `tiny_cache_py/client.py` into smaller modules if/when the feature set grows.
  - Why: A single large module mixing concerns becomes harder to navigate and test over time.
  - Suggestion: Introduce `errors.py`, `config.py`, `retry.py`, `serialization.py`, and a gRPC transport module.

- [ ] Replace inline `import time` inside `_check_connection_health`.
  - Why: Keeping imports at module scope improves readability and makes dependencies obvious.
  - Suggestion: Move `import time` to the top of `tiny_cache_py/client.py`.

- [ ] Make `Makefile:proto` portable across macOS and Linux.
  - Why: `sed -i` has different behavior across platforms, which can break proto generation for some developers.
  - Suggestion: Use a small Python script to rewrite imports, or use a portable `sed` invocation with platform detection.

- [ ] Prefer `time.perf_counter()` in benchmarks.
  - Why: `time.time()` has lower resolution and can be adjusted by the system clock; `perf_counter` is intended for timing.
  - Suggestion: Replace latency timing in `tests/benchmark_client.py` with `time.perf_counter()`.

- [ ] Remove unused fields in the benchmark suite.
  - Why: `CacheBenchmark.results` is initialized but not used.
  - Suggestion: Remove it or implement result aggregation/export (for example JSON output).
