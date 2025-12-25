import asyncio
import logging
from typing import Optional, Dict, Any, Union
import grpc
from grpc import StatusCode
from . import cache_pb2
from . import cache_pb2_grpc

logger = logging.getLogger(__name__)

class CacheError(Exception):
    """Base exception for cache operations"""
    pass

class CacheConnectionError(CacheError):
    """Raised when cache service is unavailable"""
    pass

class CacheValidationError(CacheError):
    """Raised when input validation fails"""
    pass

class CacheTimeoutError(CacheError):
    """Raised when request times out"""
    pass

class CacheNotFoundError(CacheError):
    """Raised when requested key is not found"""
    pass

class CacheInvalidArgumentError(CacheError):
    """Raised when invalid arguments are provided"""
    pass

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
        default_ttl: int = 3600,
        use_ssl: bool = False,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize cache client.
        
        Args:
            server_address: gRPC server address (e.g., "localhost:50051")
            max_retries: Maximum number of retry attempts for failed requests
            retry_delay: Initial delay between retries (exponential backoff)
            timeout: Request timeout in seconds
            default_ttl: Default TTL for cache entries
            use_ssl: Whether to use SSL/TLS connection
        """
        address = server_address.strip()
        if not address:
            raise CacheValidationError("Server address cannot be empty")

        if address.startswith("grpc://"):
            address = address[len("grpc://") :]
            use_ssl = False
        elif address.startswith("grpcs://"):
            address = address[len("grpcs://") :]
            use_ssl = True

        if address.startswith("["):
            bracket_end = address.find("]")
            if bracket_end == -1:
                raise CacheValidationError("Invalid IPv6 server address")
            self.host = address[1:bracket_end]
            port_part = address[bracket_end + 1 :]
            if not port_part:
                self.port = 50051
            elif port_part.startswith(":"):
                self.port = int(port_part[1:])
            else:
                raise CacheValidationError("Invalid IPv6 server address")
        else:
            if ":" in address:
                host_part, port_part = address.rsplit(":", 1)
                self.host = host_part
                self.port = int(port_part)
            else:
                self.host = address
                self.port = 50051

        if not self.host:
            raise CacheValidationError("Server host cannot be empty")
        if not (1 <= self.port <= 65535):
            raise CacheValidationError("Server port must be between 1 and 65535")
        self.timeout = timeout
        self.default_ttl = default_ttl
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.use_ssl = use_ssl
        self.logger = logger or logging.getLogger(__name__)
        
        self._channel: Optional[grpc.aio.Channel] = None
        self._stub: Optional[cache_pb2_grpc.CacheServiceStub] = None
        self._closed = False
        self._last_health_check = 0.0
        self._health_check_interval = 30.0  # seconds
        
        self.logger.debug(f"Initialized CacheClient for {self.host}:{self.port}")

    def _target(self) -> str:
        host = self.host
        if ":" in host:
            host = f"[{host}]"
        return f"{host}:{self.port}"

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def connect(self) -> None:
        """Establish connection to cache service"""
        if self._channel is not None and self._stub is not None and not self._closed:
            self.logger.debug("Already connected to cache service")
            return

        if self._channel is not None and self._stub is None and not self._closed:
            self.logger.debug("Channel exists without stub, rebuilding stub")
            self._stub = cache_pb2_grpc.CacheServiceStub(self._channel)
            return
            
        url = self._target()
        self.logger.info(f"Connecting to cache service at {url}")
        
        if self.use_ssl:
            credentials = grpc.ssl_channel_credentials()
            self._channel = grpc.aio.secure_channel(url, credentials)
            self.logger.debug("Using SSL/TLS connection")
        else:
            self._channel = grpc.aio.insecure_channel(url)
            self.logger.debug("Using insecure connection")
            
        self._stub = cache_pb2_grpc.CacheServiceStub(self._channel)
        self._closed = False
        self.logger.info(f"Successfully connected to cache service at {url}")

    async def close(self) -> None:
        """Close connection to cache service"""
        if self._channel and not self._closed:
            self.logger.info("Closing connection to cache service")
            await self._channel.close()
            self._channel = None
            self._stub = None
            self._closed = True
            self.logger.debug("Cache client connection closed")

    def _validate_key(self, key: str) -> None:
        """Validate cache key"""
        if not isinstance(key, str):
            raise CacheValidationError("Key must be a string")
        if not key:
            raise CacheValidationError("Key cannot be empty")
        if len(key) > 250:
            raise CacheValidationError("Key too long (max 250 characters)")

    def _validate_value(self, value: Any) -> str:
        """Validate and convert value to string"""
        if value is None:
            raise CacheValidationError("Value cannot be None")
        
        if isinstance(value, str):
            return value
        elif isinstance(value, (int, float, bool)):
            return str(value)
        elif isinstance(value, bytes):
            try:
                return value.decode('utf-8')
            except UnicodeDecodeError:
                raise CacheValidationError("Bytes value must be valid UTF-8")
        else:
            try:
                return str(value)
            except Exception as e:
                raise CacheValidationError(f"Cannot convert value to string: {e}")

    async def _execute_with_retry(self, operation, *args, **kwargs):
        """Execute operation with retry logic"""
        if self._closed:
            raise CacheConnectionError("Client is closed")
            
        # Ensure we have a healthy connection
        await self._ensure_connection()

        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await asyncio.wait_for(
                    operation(*args, **kwargs),
                    timeout=self.timeout
                )
            except grpc.RpcError as e:
                last_exception = e
                if e.code() == StatusCode.UNAVAILABLE:
                    if attempt < self.max_retries:
                        self.logger.warning(f"Cache service unavailable, retrying ({attempt + 1}/{self.max_retries})")
                        # Try to reconnect on unavailable error
                        try:
                            await self._reconnect()
                        except Exception as reconnect_error:
                            self.logger.warning(f"Reconnection attempt failed: {reconnect_error}")
                        await asyncio.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                    self.logger.error("Cache service unavailable after all retries")
                    raise CacheConnectionError("Cache service unavailable after retries")
                elif e.code() == StatusCode.INVALID_ARGUMENT:
                    self.logger.error(f"Invalid argument error: {e.details()}")
                    raise CacheInvalidArgumentError(f"Invalid argument: {e.details()}")
                elif e.code() == StatusCode.RESOURCE_EXHAUSTED:
                    self.logger.error(f"Cache resource exhausted: {e.details()}")
                    raise CacheError(f"Cache full: {e.details()}")
                else:
                    self.logger.error(f"Unexpected gRPC error {e.code()}: {e.details()}")
                    raise CacheError(f"gRPC error: {e.details()}")
            except asyncio.TimeoutError:
                last_exception = CacheTimeoutError("Request timeout")
                if attempt < self.max_retries:
                    self.logger.warning(f"Request timeout, retrying ({attempt + 1}/{self.max_retries})")
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                    continue
                self.logger.error("Request timeout after all retries")
                raise CacheTimeoutError("Request timeout after retries")
            except Exception as e:
                raise CacheError(f"Unexpected error: {e}")
        
        # If we get here, all retries failed
        if last_exception:
            raise last_exception

    async def get(self, key: str) -> Optional[str]:
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
        self._validate_key(key)
        self.logger.debug(f"Getting value for key: {key}")
        
        async def _get_operation():
            response = await self._stub.Get(cache_pb2.CacheKey(key=key))
            if response.found:
                self.logger.debug(f"Cache hit for key: {key}")
                try:
                    return response.value.decode('utf-8')
                except UnicodeDecodeError as e:
                    raise CacheError("Cache value is not valid UTF-8") from e
            else:
                self.logger.debug(f"Cache miss for key: {key}")
            return None
            
        return await self._execute_with_retry(_get_operation)

    async def get_bytes(self, key: str) -> Optional[bytes]:
        """
        Get raw bytes value from cache.
        """
        self._validate_key(key)
        self.logger.debug(f"Getting raw value for key: {key}")

        async def _get_operation():
            response = await self._stub.Get(cache_pb2.CacheKey(key=key))
            if response.found:
                self.logger.debug(f"Cache hit for key: {key}")
                return response.value
            self.logger.debug(f"Cache miss for key: {key}")
            return None

        return await self._execute_with_retry(_get_operation)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to store
            ttl: Time to live in seconds (None for default)
            
        Returns:
            True if successful
            
        Raises:
            CacheValidationError: If key or value is invalid
            CacheConnectionError: If service is unavailable
            CacheError: For other errors
        """
        self._validate_key(key)
        validated_value = self._validate_value(value)
        
        if ttl is None:
            ttl = self.default_ttl
        elif ttl < 0:
            raise CacheValidationError("TTL must be non-negative")
        
        self.logger.debug(f"Setting value for key: {key}, ttl: {ttl}")
        
        async def _set_operation():
            response = await self._stub.Set(cache_pb2.CacheItem(
                key=key,
                value=validated_value.encode('utf-8'),
                ttl=ttl
            ))
            success = response.status == "OK"
            if success:
                self.logger.debug(f"Successfully set value for key: {key}")
            return success
            
        return await self._execute_with_retry(_set_operation)

    async def set_bytes(
        self,
        key: str,
        value: bytes,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Store raw bytes value in cache.
        """
        self._validate_key(key)
        if value is None:
            raise CacheValidationError("Value cannot be None")
        if not isinstance(value, (bytes, bytearray, memoryview)):
            raise CacheValidationError("Value must be bytes")

        value_bytes = bytes(value)

        if ttl is None:
            ttl = self.default_ttl
        elif ttl < 0:
            raise CacheValidationError("TTL must be non-negative")

        self.logger.debug(f"Setting raw value for key: {key}, ttl: {ttl}")

        async def _set_operation():
            response = await self._stub.Set(
                cache_pb2.CacheItem(
                    key=key,
                    value=value_bytes,
                    ttl=ttl,
                )
            )
            success = response.status == "OK"
            if success:
                self.logger.debug(f"Successfully set raw value for key: {key}")
            return success

        return await self._execute_with_retry(_set_operation)

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if key was deleted, False if key didn't exist
            
        Raises:
            CacheValidationError: If key is invalid
            CacheConnectionError: If service is unavailable
            CacheError: For other errors
        """
        self._validate_key(key)
        self.logger.debug(f"Deleting key: {key}")
        
        async def _delete_operation():
            response = await self._stub.Delete(cache_pb2.CacheKey(key=key))
            success = response.status == "OK"
            if success:
                self.logger.debug(f"Successfully deleted key: {key}")
            else:
                self.logger.debug(f"Key not found for deletion: {key}")
            return success
            
        return await self._execute_with_retry(_delete_operation)

    async def stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
            
        Raises:
            CacheConnectionError: If service is unavailable
            CacheError: For other errors
        """
        self.logger.debug("Requesting cache statistics")
        
        async def _stats_operation():
            response = await self._stub.Stats(cache_pb2.Empty())
            stats = {
                "size": response.size,
                "hits": response.hits,
                "misses": response.misses,
                "hit_rate": response.hits / (response.hits + response.misses) if (response.hits + response.misses) > 0 else 0
            }
            self.logger.debug(f"Retrieved cache stats: {stats}")
            return stats
            
        return await self._execute_with_retry(_stats_operation)

    async def ping(self) -> bool:
        """
        Check if cache service is available.
        
        Returns:
            True if service is available
        """
        self.logger.debug("Pinging cache service")
        try:
            # Use direct gRPC call to avoid retry logic
            await asyncio.wait_for(
                self._stub.Stats(cache_pb2.Empty()),
                timeout=5.0
            )
            self.logger.debug("Ping successful")
            return True
        except Exception as e:
            self.logger.debug(f"Ping failed: {e}")
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
        import time
        
        # Skip health check if we just did one recently
        current_time = time.time()
        if current_time - self._last_health_check < self._health_check_interval:
            return True
            
        try:
            # Use a direct gRPC call without retry logic to avoid infinite recursion
            response = await asyncio.wait_for(
                self._stub.Stats(cache_pb2.Empty()),
                timeout=5.0  # Short timeout for health check
            )
            self._last_health_check = current_time
            return True
        except Exception as e:
            self.logger.warning(f"Health check failed: {e}")
            return False
    
    async def _ensure_connection(self) -> None:
        """Ensure we have a healthy connection, reconnecting if necessary"""
        if not self.is_connected():
            self.logger.debug("No connection, establishing new connection")
            await self.connect()
            return
            
        # Check connection health periodically
        if not await self._check_connection_health():
            self.logger.warning("Connection health check failed, attempting reconnection")
            await self._reconnect()
    
    async def _reconnect(self) -> None:
        """Reconnect to the cache service"""
        self.logger.info("Reconnecting to cache service")
        try:
            # Close existing connection
            if self._channel and not self._closed:
                await self._channel.close()
                
            # Reset connection state
            self._channel = None
            self._stub = None
            self._closed = False
            
            # Establish new connection
            await self.connect()
            self.logger.info("Successfully reconnected to cache service")
            
        except Exception as e:
            self.logger.error(f"Failed to reconnect: {e}")
            raise CacheConnectionError(f"Reconnection failed: {e}")
