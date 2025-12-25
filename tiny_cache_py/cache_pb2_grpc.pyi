from typing import Any, Awaitable, Optional, Sequence, Tuple

from . import cache_pb2


class CacheServiceStub:
    def __init__(self, channel: Any) -> None: ...

    def Get(
        self,
        request: cache_pb2.CacheKey,
        timeout: Optional[float] = ...,
        metadata: Optional[Sequence[Tuple[str, str]]] = ...,
    ) -> Awaitable[cache_pb2.CacheValue]: ...

    def Set(
        self,
        request: cache_pb2.CacheItem,
        timeout: Optional[float] = ...,
        metadata: Optional[Sequence[Tuple[str, str]]] = ...,
    ) -> Awaitable[cache_pb2.CacheResponse]: ...

    def Delete(
        self,
        request: cache_pb2.CacheKey,
        timeout: Optional[float] = ...,
        metadata: Optional[Sequence[Tuple[str, str]]] = ...,
    ) -> Awaitable[cache_pb2.CacheResponse]: ...

    def Stats(
        self,
        request: cache_pb2.Empty,
        timeout: Optional[float] = ...,
        metadata: Optional[Sequence[Tuple[str, str]]] = ...,
    ) -> Awaitable[cache_pb2.CacheStats]: ...

