# tiny-cache-py

A Python client library for the tiny-cache gRPC service, providing efficient distributed caching with connection pooling and comprehensive error handling.

## Features

- **Complete API Coverage**: Get, Set, Delete, Stats, and Ping operations
- **Connection Pooling**: Efficient resource management with persistent channels
- **Error Handling**: Comprehensive exception handling with custom error types
- **Type Safety**: Full type hints and input validation
- **Retry Logic**: Exponential backoff for transient failures
- **Async Support**: Built for high-performance async applications
- **SSL/TLS Support**: Secure connections to cache servers

## Installation

```bash
pip install tiny-cache-py
```

For development:
```bash
git clone <repository>
cd tiny-cache-py
pip install -e .
```

## Quick Start

```python
import asyncio
from tiny_cache_py import CacheClient

async def main():
    async with CacheClient("localhost:50051") as client:
        # Set a value with TTL
        await client.set("key1", "value1", ttl=300)
        
        # Get a value
        value = await client.get("key1")
        print(f"Retrieved: {value}")
        
        # Get cache statistics
        stats = await client.stats()
        print(f"Cache stats: {stats}")

asyncio.run(main())
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `CACHE_SERVER_ADDRESS` | localhost:50051 | gRPC server address |
| `CACHE_MAX_RETRIES` | 3 | Maximum retry attempts |
| `CACHE_TIMEOUT` | 30.0 | Request timeout in seconds |

## API

### CacheClient Methods

- `get(key: str) → Optional[str]`: Retrieve cached value
- `set(key: str, value: Any, ttl: Optional[int]) → bool`: Store value with optional TTL (seconds; `None` uses default, `0` disables expiry)
- `delete(key: str) → bool`: Remove cached entry
- `stats() → Dict[str, Any]`: Get cache statistics
- `ping() → bool`: Check server availability

### Error Handling

```python
from tiny_cache_py import (
    CacheError,
    CacheConnectionError,
    CacheValidationError,
    CacheTimeoutError
)

try:
    value = await client.get("key")
except CacheConnectionError:
    print("Connection failed")
except CacheTimeoutError:
    print("Request timed out")
```

### Metadata (Correlation IDs)

Pass gRPC metadata per call (or set `default_metadata` on the client) to carry correlation IDs:

```python
await client.get("key", metadata=[("x-correlation-id", "req-123")])
```

## Development

### Setup

```bash
# Setup environment
python -m venv venv
. ./venv/bin/activate
pip install -r requirements-dev.txt

# Generate protobuf files
make proto

# Run tests
make test

# Run with coverage
make test-coverage
```

### Testing

```bash
# Run all tests
pytest

# Note: pytest-asyncio runs in strict mode; async tests must be marked with
# @pytest.mark.asyncio.

# Run specific test categories
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only

# Run benchmarks
python benchmarks/benchmark_client.py
```

### Code Quality

```bash
# Type checking
make lint

# Code formatting
make format

# All quality checks
make quality
```

## Performance

- **Throughput**: 10,000+ operations/second (local network)
- **Latency**: <5ms average (local network)
- **Concurrent Clients**: Supports hundreds of concurrent connections
- **Memory Efficient**: Minimal overhead with connection pooling

## Compatibility

- Python 3.8 - 3.13
- gRPC 1.50.0+
- Compatible with tiny-cache server v0.1.0+

## License

MIT License - see [`LICENSE`](LICENSE) file for details.
