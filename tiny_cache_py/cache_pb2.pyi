class _CacheStatus:
    CACHE_STATUS_UNSPECIFIED: int
    OK: int
    ERROR: int


CacheStatus: _CacheStatus
CACHE_STATUS_UNSPECIFIED: int
OK: int
ERROR: int


class CacheKey:
    key: str
    def __init__(self, *, key: str = ...) -> None: ...


class CacheItem:
    key: str
    value: bytes
    ttl: int
    def __init__(self, *, key: str = ..., value: bytes = ..., ttl: int = ...) -> None: ...


class CacheValue:
    found: bool
    value: bytes
    def __init__(self, *, found: bool = ..., value: bytes = ...) -> None: ...


class CacheResponse:
    status: int
    def __init__(self, *, status: int = ...) -> None: ...


class CacheStats:
    size: int
    hits: int
    misses: int
    evictions: int
    hit_rate: float
    memory_usage_bytes: int
    max_memory_bytes: int
    max_items: int
    def __init__(
        self,
        *,
        size: int = ...,
        hits: int = ...,
        misses: int = ...,
        evictions: int = ...,
        hit_rate: float = ...,
        memory_usage_bytes: int = ...,
        max_memory_bytes: int = ...,
        max_items: int = ...,
    ) -> None: ...


class Empty:
    def __init__(self) -> None: ...
