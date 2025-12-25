import asyncio
import logging
import random
import time
from types import TracebackType
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
)
import grpc
from grpc import StatusCode
from . import cache_pb2
from . import cache_pb2_grpc
from .config import parse_server_address
from .errors import (
    CacheError,
    CacheConnectionError,
    CacheInvalidArgumentError,
    CacheTimeoutError,
    CacheValidationError,
)
from .serialization import coerce_text_value, normalize_bytes_value, validate_key

T = TypeVar("T")

class CacheClient:
    """
    Async gRPC client for tiny-cache service.
    
    Features:
    - Connection pooling with persistent channel
    - Complete API implementation (get, set, delete, stats)
    - Comprehensive error handling
    - Type hints and input validation
    - Configurable timeouts and retry logic
    """
    
    def __init__(
        self,
        server_address: str = "localhost:50051",
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 30.0,
        connect_timeout: Optional[float] = None,
        default_ttl: int = 3600,
        use_ssl: bool = False,
        logger: Optional[logging.Logger] = None,
        health_check_interval: Optional[float] = 30.0,
        health_check_timeout: float = 5.0,
        health_check_method: str = "stats",
        default_metadata: Optional[Sequence[Tuple[str, str]]] = None,
    ):
        """
        Initialize cache client.
        
        Args:
            server_address: gRPC server address (e.g., "localhost:50051")
            max_retries: Maximum number of retry attempts for failed requests
            retry_delay: Initial delay between retries (exponential backoff)
            timeout: Request timeout in seconds
            connect_timeout: Optional channel readiness timeout in seconds
            default_ttl: Default TTL for cache entries
            use_ssl: Whether to use SSL/TLS connection
            health_check_interval: Seconds between health checks (set to 0/None to disable)
            health_check_timeout: Health check timeout in seconds
            health_check_method: Health check strategy ("stats" or "grpc_health")
            default_metadata: Default gRPC metadata for all calls
        """
        self.host, self.port, self.use_ssl = parse_server_address(server_address, use_ssl)
        self.timeout = timeout
        self.connect_timeout = connect_timeout
        self.default_ttl = default_ttl
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.logger = logger or logging.getLogger(__name__)
        self._default_metadata = tuple(default_metadata) if default_metadata else None
        
        self._channel: Optional[grpc.aio.Channel] = None
        self._stub: Optional[cache_pb2_grpc.CacheServiceStub] = None
        self._closed = False
        self._connection_lock = asyncio.Lock()
        self._last_health_check = 0.0
        if health_check_interval is not None and health_check_interval < 0:
            raise CacheValidationError("Health check interval must be non-negative")
        if health_check_timeout <= 0:
            raise CacheValidationError("Health check timeout must be positive")
        if health_check_method not in {"stats", "grpc_health"}:
            raise CacheValidationError("Health check method must be 'stats' or 'grpc_health'")
        if health_check_method == "grpc_health":
            try:
                import grpc_health.v1.health_pb2
                import grpc_health.v1.health_pb2_grpc
            except ImportError as exc:
                raise CacheValidationError(
                    "Health check method 'grpc_health' requires grpcio-health-checking"
                ) from exc
        self._health_check_interval = health_check_interval
        self._health_check_timeout = health_check_timeout
        self._health_check_method = health_check_method
        
        self.logger.debug("Initialized CacheClient for %s:%s", self.host, self.port)

    def _target(self) -> str:
        host = self.host
        if ":" in host:
            host = f"[{host}]"
        return f"{host}:{self.port}"

    def _merge_metadata(
        self,
        metadata: Optional[Sequence[Tuple[str, str]]],
    ) -> Optional[Tuple[Tuple[str, str], ...]]:
        if metadata is None:
            return self._default_metadata
        extra = tuple(metadata)
        if self._default_metadata is None:
            return extra
        return (*self._default_metadata, *extra)

    async def __aenter__(self) -> "CacheClient":
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        await self.close()

    async def connect(self) -> None:
        """Establish connection to cache service"""
        async with self._connection_lock:
            await self._connect_locked()

    async def _connect_locked(self) -> None:
        if self._channel is not None and self._stub is not None and not self._closed:
            self.logger.debug("Already connected to cache service")
            return

        if self._channel is not None and self._stub is None and not self._closed:
            self.logger.debug("Channel exists without stub, rebuilding stub")
            self._stub = cache_pb2_grpc.CacheServiceStub(self._channel)
            return

        url = self._target()
        self.logger.debug("Connecting to cache service at %s", url)

        if self.use_ssl:
            credentials = grpc.ssl_channel_credentials()
            self._channel = grpc.aio.secure_channel(url, credentials)
            self.logger.debug("Using SSL/TLS connection")
        else:
            self._channel = grpc.aio.insecure_channel(url)
            self.logger.debug("Using insecure connection")

        if self.connect_timeout is not None:
            try:
                await asyncio.wait_for(
                    self._channel.channel_ready(),
                    timeout=self.connect_timeout,
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                await self._channel.close()
                self._channel = None
                raise CacheConnectionError(
                    f"Channel not ready within {self.connect_timeout} seconds"
                ) from e

        self._stub = cache_pb2_grpc.CacheServiceStub(self._channel)
        self._closed = False
        self.logger.debug("Successfully connected to cache service at %s", url)

    async def close(self) -> None:
        """Close connection to cache service"""
        if self._channel and not self._closed:
            self.logger.debug("Closing connection to cache service")
            await self._channel.close()
            self._channel = None
            self._stub = None
            self._closed = True
            self.logger.debug("Cache client connection closed")

    def _validate_key(self, key: str) -> None:
        validate_key(key)

    def _validate_value(self, value: Any) -> str:
        return coerce_text_value(value)

    async def _execute_with_retry(
        self,
        operation: Callable[[], Awaitable[T]],
        *,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
    ) -> T:
        """Execute operation with retry logic"""
        if self._closed:
            raise CacheConnectionError("Client is closed")

        effective_max_retries = self.max_retries if max_retries is None else max_retries
        effective_retry_delay = self.retry_delay if retry_delay is None else retry_delay

        if effective_max_retries < 0:
            raise CacheValidationError("Max retries must be non-negative")
        if effective_retry_delay < 0:
            raise CacheValidationError("Retry delay must be non-negative")
            
        # Ensure we have a healthy connection
        await self._ensure_connection()

        last_exception: Optional[BaseException] = None
        
        for attempt in range(effective_max_retries + 1):
            try:
                return await operation()
            except asyncio.CancelledError:
                raise
            except grpc.RpcError as e:
                last_exception = e
                if e.code() == StatusCode.UNAVAILABLE:
                    if attempt < effective_max_retries:
                        self.logger.warning(
                            "Cache service unavailable, retrying (%s/%s)",
                            attempt + 1,
                            effective_max_retries,
                        )
                        # Try to reconnect on unavailable error
                        try:
                            expected_channel = self._channel
                            await self._reconnect(expected_channel=expected_channel)
                        except Exception as reconnect_error:
                            self.logger.warning("Reconnection attempt failed: %s", reconnect_error)
                        backoff = effective_retry_delay * (2 ** attempt)
                        await asyncio.sleep(random.uniform(0, backoff))
                        continue
                    self.logger.error("Cache service unavailable after all retries")
                    raise CacheConnectionError("Cache service unavailable after retries") from e
                elif e.code() == StatusCode.DEADLINE_EXCEEDED:
                    if attempt < effective_max_retries:
                        self.logger.warning(
                            "Request deadline exceeded, retrying (%s/%s)",
                            attempt + 1,
                            effective_max_retries,
                        )
                        backoff = effective_retry_delay * (2 ** attempt)
                        await asyncio.sleep(random.uniform(0, backoff))
                        continue
                    self.logger.error("Request deadline exceeded after all retries")
                    raise CacheTimeoutError(
                        f"Deadline exceeded after retries: {e.details()}"
                    ) from e
                elif e.code() == StatusCode.INVALID_ARGUMENT:
                    self.logger.error("Invalid argument error: %s", e.details())
                    raise CacheInvalidArgumentError(f"Invalid argument: {e.details()}") from e
                elif e.code() == StatusCode.PERMISSION_DENIED:
                    self.logger.error("Permission denied: %s", e.details())
                    raise CacheError(f"Permission denied: {e.details()}") from e
                elif e.code() == StatusCode.UNAUTHENTICATED:
                    self.logger.error("Unauthenticated: %s", e.details())
                    raise CacheError(f"Unauthenticated: {e.details()}") from e
                elif e.code() == StatusCode.CANCELLED:
                    raise asyncio.CancelledError() from e
                elif e.code() == StatusCode.RESOURCE_EXHAUSTED:
                    self.logger.error("Cache resource exhausted: %s", e.details())
                    raise CacheError(f"Cache full: {e.details()}") from e
                else:
                    self.logger.error("Unexpected gRPC error %s: %s", e.code(), e.details())
                    raise CacheError(f"gRPC error: {e.details()}") from e
            except asyncio.TimeoutError as e:
                last_exception = CacheTimeoutError("Request timeout")
                if attempt < effective_max_retries:
                    self.logger.warning(
                        "Request timeout, retrying (%s/%s)",
                        attempt + 1,
                        effective_max_retries,
                    )
                    backoff = effective_retry_delay * (2 ** attempt)
                    await asyncio.sleep(random.uniform(0, backoff))
                    continue
                self.logger.error("Request timeout after all retries")
                raise CacheTimeoutError("Request timeout after retries") from e
            except CacheError:
                raise
            except Exception as e:
                raise CacheError(f"Unexpected error: {e}") from e
	        
        # Defensive: we should never fall through without returning or raising.
        if last_exception is not None:
            raise CacheError("Operation failed after retries") from last_exception
        raise CacheError("Operation failed after retries")

    async def get(
        self,
        key: str,
        *,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
        metadata: Optional[Sequence[Tuple[str, str]]] = None,
    ) -> Optional[str]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Value if found, None if not found
            
        Raises:
            CacheValidationError: If key is invalid
            CacheConnectionError: If service is unavailable
            CacheError: For other errors
        """
        validate_key(key)
        call_timeout = self.timeout if timeout is None else timeout
        if call_timeout <= 0:
            raise CacheValidationError("Timeout must be positive")
        call_metadata = self._merge_metadata(metadata)
        self.logger.debug("Getting value for key: %s", key)
        
        async def _get_operation() -> Optional[str]:
            stub = self._stub
            if stub is None:
                raise CacheConnectionError("Cache client is not connected")
            response = await stub.Get(
                cache_pb2.CacheKey(key=key),
                timeout=call_timeout,
                metadata=call_metadata,
            )
            if response.found:
                self.logger.debug("Cache hit for key: %s", key)
                try:
                    return response.value.decode('utf-8')
                except UnicodeDecodeError as e:
                    raise CacheError("Cache value is not valid UTF-8") from e
            else:
                self.logger.debug("Cache miss for key: %s", key)
            return None
            
        return await self._execute_with_retry(
            _get_operation,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )

    async def get_bytes(
        self,
        key: str,
        *,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
        metadata: Optional[Sequence[Tuple[str, str]]] = None,
    ) -> Optional[bytes]:
        """
        Get raw bytes value from cache.
        """
        validate_key(key)
        call_timeout = self.timeout if timeout is None else timeout
        if call_timeout <= 0:
            raise CacheValidationError("Timeout must be positive")
        call_metadata = self._merge_metadata(metadata)
        self.logger.debug("Getting raw value for key: %s", key)

        async def _get_operation() -> Optional[bytes]:
            stub = self._stub
            if stub is None:
                raise CacheConnectionError("Cache client is not connected")
            response = await stub.Get(
                cache_pb2.CacheKey(key=key),
                timeout=call_timeout,
                metadata=call_metadata,
            )
            if response.found:
                self.logger.debug("Cache hit for key: %s", key)
                return response.value
            self.logger.debug("Cache miss for key: %s", key)
            return None

        return await self._execute_with_retry(
            _get_operation,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        *,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
        metadata: Optional[Sequence[Tuple[str, str]]] = None,
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to store
            ttl: Time to live in seconds (None for default_ttl, 0 disables expiry)
            
        Returns:
            True if successful
            
        Raises:
            CacheValidationError: If key or value is invalid
            CacheConnectionError: If service is unavailable
            CacheError: For other errors
        """
        validate_key(key)
        validated_value = coerce_text_value(value)
        call_timeout = self.timeout if timeout is None else timeout
        if call_timeout <= 0:
            raise CacheValidationError("Timeout must be positive")
        call_metadata = self._merge_metadata(metadata)
        
        if ttl is None:
            ttl = self.default_ttl
        elif ttl < 0:
            raise CacheValidationError("TTL must be non-negative")
        
        self.logger.debug("Setting value for key: %s, ttl: %s", key, ttl)
        
        async def _set_operation() -> bool:
            stub = self._stub
            if stub is None:
                raise CacheConnectionError("Cache client is not connected")
            response = await stub.Set(
                cache_pb2.CacheItem(
                    key=key,
                    value=validated_value.encode('utf-8'),
                    ttl=ttl,
                ),
                timeout=call_timeout,
                metadata=call_metadata,
            )
            success = response.status == cache_pb2.CacheStatus.OK
            if success:
                self.logger.debug("Successfully set value for key: %s", key)
            return success
            
        return await self._execute_with_retry(
            _set_operation,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )

    async def set_bytes(
        self,
        key: str,
        value: bytes,
        ttl: Optional[int] = None,
        *,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
        metadata: Optional[Sequence[Tuple[str, str]]] = None,
    ) -> bool:
        """
        Store raw bytes value in cache.

        Args:
            ttl: Time to live in seconds (None for default_ttl, 0 disables expiry)
        """
        validate_key(key)
        call_timeout = self.timeout if timeout is None else timeout
        if call_timeout <= 0:
            raise CacheValidationError("Timeout must be positive")
        call_metadata = self._merge_metadata(metadata)
        value_bytes = normalize_bytes_value(value)

        if ttl is None:
            ttl = self.default_ttl
        elif ttl < 0:
            raise CacheValidationError("TTL must be non-negative")

        self.logger.debug("Setting raw value for key: %s, ttl: %s", key, ttl)

        async def _set_operation() -> bool:
            stub = self._stub
            if stub is None:
                raise CacheConnectionError("Cache client is not connected")
            response = await stub.Set(
                cache_pb2.CacheItem(
                    key=key,
                    value=value_bytes,
                    ttl=ttl,
                ),
                timeout=call_timeout,
                metadata=call_metadata,
            )
            success = response.status == cache_pb2.CacheStatus.OK
            if success:
                self.logger.debug("Successfully set raw value for key: %s", key)
            return success

        return await self._execute_with_retry(
            _set_operation,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )

    async def delete(
        self,
        key: str,
        *,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
        metadata: Optional[Sequence[Tuple[str, str]]] = None,
    ) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if operation succeeded, False otherwise
            
        Raises:
            CacheValidationError: If key is invalid
            CacheConnectionError: If service is unavailable
            CacheError: For other errors
        """
        validate_key(key)
        call_timeout = self.timeout if timeout is None else timeout
        if call_timeout <= 0:
            raise CacheValidationError("Timeout must be positive")
        call_metadata = self._merge_metadata(metadata)
        self.logger.debug("Deleting key: %s", key)
        
        async def _delete_operation() -> bool:
            stub = self._stub
            if stub is None:
                raise CacheConnectionError("Cache client is not connected")
            response = await stub.Delete(
                cache_pb2.CacheKey(key=key),
                timeout=call_timeout,
                metadata=call_metadata,
            )
            if response.status == cache_pb2.CacheStatus.OK:
                self.logger.debug("Successfully deleted key: %s", key)
                return True
            self.logger.debug(
                "Delete returned status %s for key: %s",
                response.status,
                key,
            )
            return False
            
        return await self._execute_with_retry(
            _delete_operation,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )

    async def stats(
        self,
        *,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
        metadata: Optional[Sequence[Tuple[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
            
        Raises:
            CacheConnectionError: If service is unavailable
            CacheError: For other errors
        """
        self.logger.debug("Requesting cache statistics")
        call_timeout = self.timeout if timeout is None else timeout
        if call_timeout <= 0:
            raise CacheValidationError("Timeout must be positive")
        call_metadata = self._merge_metadata(metadata)
        
        async def _stats_operation() -> Dict[str, Any]:
            stub = self._stub
            if stub is None:
                raise CacheConnectionError("Cache client is not connected")
            response = await stub.Stats(
                cache_pb2.Empty(),
                timeout=call_timeout,
                metadata=call_metadata,
            )
            stats = {
                "size": response.size,
                "hits": response.hits,
                "misses": response.misses,
                "evictions": response.evictions,
                "hit_rate": response.hit_rate,
                "memory_usage_bytes": response.memory_usage_bytes,
                "max_memory_bytes": response.max_memory_bytes,
                "max_items": response.max_items,
            }
            self.logger.debug("Retrieved cache stats: %s", stats)
            return stats
            
        return await self._execute_with_retry(
            _stats_operation,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )

    async def ping(self, *, metadata: Optional[Sequence[Tuple[str, str]]] = None) -> bool:
        """
        Check if cache service is available.
        
        Returns:
            True if service is available
        """
        self.logger.debug("Pinging cache service")
        call_metadata = self._merge_metadata(metadata)
        try:
            if not self.is_connected():
                await self.connect()
            stub = self._stub
            if stub is None:
                return False
            await self._perform_health_check(timeout=5.0, metadata=call_metadata)
            self.logger.debug("Ping successful")
            return True
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.debug("Ping failed: %s", e)
            return False

    def is_connected(self) -> bool:
        """Check if client is connected"""
        return (
            self._channel is not None
            and self._stub is not None
            and not self._closed
        )
    
    async def _check_connection_health(self) -> bool:
        """Check if the connection is healthy by performing a lightweight operation"""
        if self._health_check_interval is None or self._health_check_interval <= 0:
            return True

        if self._stub is None:
            await self.connect()
            if self._stub is None:
                return False
        
        # Skip health check if we just did one recently
        current_time = time.time()
        if current_time - self._last_health_check < self._health_check_interval:
            return True
            
        try:
            await self._perform_health_check(
                timeout=self._health_check_timeout,
                metadata=self._default_metadata,
            )
            self._last_health_check = current_time
            return True
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.warning("Health check failed: %s", e)
            return False

    async def _perform_health_check(
        self,
        *,
        timeout: float,
        metadata: Optional[Tuple[Tuple[str, str], ...]],
    ) -> None:
        if self._health_check_method == "grpc_health":
            from grpc_health.v1 import health_pb2
            from grpc_health.v1 import health_pb2_grpc

            if self._channel is None:
                raise CacheConnectionError("Client is not connected")
            health_stub = health_pb2_grpc.HealthStub(self._channel)
            response = await health_stub.Check(
                health_pb2.HealthCheckRequest(service=""),
                timeout=timeout,
                metadata=metadata,
            )
            if response.status != health_pb2.HealthCheckResponse.SERVING:
                raise CacheConnectionError(
                    f"Health check returned status {response.status}"
                )
            return

        stub = self._stub
        if stub is None:
            raise CacheConnectionError("Client is not connected")
        await stub.Stats(
            cache_pb2.Empty(),
            timeout=timeout,
            metadata=metadata,
        )
    
    async def _ensure_connection(self) -> None:
        """Ensure we have a healthy connection, reconnecting if necessary"""
        if not self.is_connected():
            self.logger.debug("No connection, establishing new connection")
            await self.connect()
            return
            
        # Check connection health periodically
        expected_channel = self._channel
        if not await self._check_connection_health():
            self.logger.warning("Connection health check failed, attempting reconnection")
            await self._reconnect(expected_channel=expected_channel)
    
    async def _reconnect(self, expected_channel: Optional[grpc.aio.Channel] = None) -> None:
        """Reconnect to the cache service"""
        self.logger.info("Reconnecting to cache service")
        try:
            async with self._connection_lock:
                if (
                    expected_channel is not None
                    and self._channel is not expected_channel
                    and self.is_connected()
                ):
                    self.logger.debug("Reconnect already completed by another coroutine")
                    return

                # Close existing connection
                if self._channel and not self._closed:
                    await self._channel.close()

                # Reset connection state
                self._channel = None
                self._stub = None
                self._closed = False

                # Establish new connection
                await self._connect_locked()
                self.logger.info("Successfully reconnected to cache service")
            
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.error("Failed to reconnect: %s", e)
            raise CacheConnectionError(f"Reconnection failed: {e}") from e
