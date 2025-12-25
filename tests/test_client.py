import pytest
import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import grpc
from grpc import StatusCode

from tiny_cache_py import (
    CacheClient,
    CacheError,
    CacheConnectionError,
    CacheValidationError,
    CacheTimeoutError,
    CacheNotFoundError,
    CacheInvalidArgumentError
)
from tiny_cache_py import cache_pb2


class TestCacheClientInit:
    """Test CacheClient initialization and configuration."""
    
    def test_init_with_defaults(self):
        """Test client initialization with default parameters."""
        client = CacheClient()
        assert client.host == "localhost"
        assert client.port == 50051
        assert client.timeout == 30.0
        assert client.max_retries == 3
        assert client.retry_delay == 1.0
        assert client.default_ttl == 3600
        assert not client.use_ssl
        assert client._channel is None
        assert client._stub is None
        assert client._closed is False

    def test_init_with_server_address(self):
        """Test client initialization with server address."""
        client = CacheClient("example.com:8080")
        assert client.host == "example.com"
        assert client.port == 8080

    def test_init_with_server_address_no_port(self):
        """Test client initialization with server address without port."""
        client = CacheClient("example.com")
        assert client.host == "example.com"
        assert client.port == 50051

    def test_init_with_custom_params(self):
        """Test client initialization with custom parameters."""
        client = CacheClient(
            server_address="cache.example.com:9090",
            max_retries=5,
            retry_delay=2.0,
            timeout=60.0,
            default_ttl=7200,
            use_ssl=True
        )
        assert client.host == "cache.example.com"
        assert client.port == 9090
        assert client.max_retries == 5
        assert client.retry_delay == 2.0
        assert client.timeout == 60.0
        assert client.default_ttl == 7200
        assert client.use_ssl is True


class TestCacheClientValidation:
    """Test input validation methods."""
    
    def test_validate_key_valid(self):
        """Test key validation with valid keys."""
        client = CacheClient()
        # Should not raise any exception
        client._validate_key("valid_key")
        client._validate_key("key123")
        client._validate_key("a" * 250)  # Max length

    def test_validate_key_invalid_type(self):
        """Test key validation with invalid types."""
        client = CacheClient()
        with pytest.raises(CacheValidationError, match="Key must be a string"):
            client._validate_key(123)
        with pytest.raises(CacheValidationError, match="Key must be a string"):
            client._validate_key(None)

    def test_validate_key_empty(self):
        """Test key validation with empty key."""
        client = CacheClient()
        with pytest.raises(CacheValidationError, match="Key cannot be empty"):
            client._validate_key("")

    def test_validate_key_too_long(self):
        """Test key validation with too long key."""
        client = CacheClient()
        long_key = "a" * 251
        with pytest.raises(CacheValidationError, match="Key too long"):
            client._validate_key(long_key)

    def test_validate_value_string(self):
        """Test value validation with string values."""
        client = CacheClient()
        assert client._validate_value("test") == "test"
        assert client._validate_value("") == ""

    def test_validate_value_numeric(self):
        """Test value validation with numeric values."""
        client = CacheClient()
        assert client._validate_value(123) == "123"
        assert client._validate_value(45.67) == "45.67"
        assert client._validate_value(True) == "True"
        assert client._validate_value(False) == "False"

    def test_validate_value_bytes(self):
        """Test value validation with bytes values."""
        client = CacheClient()
        assert client._validate_value(b"test") == "test"
        assert client._validate_value("test".encode('utf-8')) == "test"

    def test_validate_value_bytes_invalid_utf8(self):
        """Test value validation with invalid UTF-8 bytes."""
        client = CacheClient()
        invalid_bytes = b'\xff\xfe'
        with pytest.raises(CacheValidationError, match="Bytes value must be valid UTF-8"):
            client._validate_value(invalid_bytes)

    def test_validate_value_none(self):
        """Test value validation with None."""
        client = CacheClient()
        with pytest.raises(CacheValidationError, match="Value cannot be None"):
            client._validate_value(None)

    def test_validate_value_complex_object(self):
        """Test value validation with complex objects."""
        client = CacheClient()
        # Should convert to string
        assert client._validate_value([1, 2, 3]) == "[1, 2, 3]"
        assert client._validate_value({"key": "value"}) == "{'key': 'value'}"


class TestCacheClientConnection:
    """Test connection management."""

    @pytest.mark.asyncio
    async def test_connect_insecure(self):
        """Test insecure connection establishment."""
        client = CacheClient("localhost:50051", use_ssl=False)
        
        with patch('grpc.aio.insecure_channel') as mock_channel, \
             patch('tiny_cache_py.cache_pb2_grpc.CacheServiceStub') as mock_stub:
            
            mock_channel_instance = AsyncMock()
            mock_channel.return_value = mock_channel_instance
            mock_stub_instance = Mock()
            mock_stub.return_value = mock_stub_instance
            
            await client.connect()
            
            mock_channel.assert_called_once_with("localhost:50051")
            mock_stub.assert_called_once_with(mock_channel_instance)
            assert client._channel == mock_channel_instance
            assert client._stub == mock_stub_instance
            assert not client._closed

    @pytest.mark.asyncio
    async def test_connect_secure(self):
        """Test secure connection establishment."""
        client = CacheClient("localhost:50051", use_ssl=True)
        
        with patch('grpc.aio.secure_channel') as mock_channel, \
             patch('grpc.ssl_channel_credentials') as mock_creds, \
             patch('tiny_cache_py.cache_pb2_grpc.CacheServiceStub') as mock_stub:
            
            mock_channel_instance = AsyncMock()
            mock_channel.return_value = mock_channel_instance
            mock_creds_instance = Mock()
            mock_creds.return_value = mock_creds_instance
            mock_stub_instance = Mock()
            mock_stub.return_value = mock_stub_instance
            
            await client.connect()
            
            mock_creds.assert_called_once()
            mock_channel.assert_called_once_with("localhost:50051", mock_creds_instance)
            mock_stub.assert_called_once_with(mock_channel_instance)

    @pytest.mark.asyncio
    async def test_connect_already_connected(self):
        """Test connecting when already connected."""
        client = CacheClient()
        client._channel = AsyncMock()
        
        with patch('grpc.aio.insecure_channel') as mock_channel:
            await client.connect()
            mock_channel.assert_not_called()

    @pytest.mark.asyncio
    async def test_close(self):
        """Test connection closing."""
        client = CacheClient()
        mock_channel = AsyncMock()
        client._channel = mock_channel
        client._stub = Mock()
        
        await client.close()
        
        mock_channel.close.assert_called_once()
        assert client._channel is None
        assert client._stub is None
        assert client._closed is True

    @pytest.mark.asyncio
    async def test_close_already_closed(self):
        """Test closing when already closed."""
        client = CacheClient()
        client._closed = True
        
        await client.close()
        # Should not raise any exception

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager functionality."""
        with patch.object(CacheClient, 'connect') as mock_connect, \
             patch.object(CacheClient, 'close') as mock_close:
            
            async with CacheClient() as client:
                assert isinstance(client, CacheClient)
            
            mock_connect.assert_called_once()
            mock_close.assert_called_once()

    def test_is_connected(self):
        """Test connection status check."""
        client = CacheClient()
        assert not client.is_connected()
        
        client._channel = AsyncMock()
        client._stub = AsyncMock()
        assert client.is_connected()
        
        client._closed = True
        assert not client.is_connected()


class TestCacheClientOperations:
    """Test cache operations with mocked gRPC calls."""

    @pytest.fixture
    def client_with_mock_stub(self):
        """Create a client with mocked stub."""
        client = CacheClient()
        client._stub = AsyncMock()
        client._channel = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_get_success(self, client_with_mock_stub):
        """Test successful get operation."""
        client = client_with_mock_stub
        
        # Mock successful response
        mock_response = Mock()
        mock_response.found = True
        mock_response.value = b"test_value"
        client._stub.Get.return_value = mock_response
        
        result = await client.get("test_key")
        
        assert result == "test_value"
        client._stub.Get.assert_called_once()
        call_args = client._stub.Get.call_args[0][0]
        assert call_args.key == "test_key"

    @pytest.mark.asyncio
    async def test_get_not_found(self, client_with_mock_stub):
        """Test get operation when key not found."""
        client = client_with_mock_stub
        
        # Mock not found response
        mock_response = Mock()
        mock_response.found = False
        client._stub.Get.return_value = mock_response
        
        result = await client.get("missing_key")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_invalid_key(self, client_with_mock_stub):
        """Test get operation with invalid key."""
        client = client_with_mock_stub
        
        with pytest.raises(CacheValidationError):
            await client.get("")

    @pytest.mark.asyncio
    async def test_set_success(self, client_with_mock_stub):
        """Test successful set operation."""
        client = client_with_mock_stub
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status = "OK"
        client._stub.Set.return_value = mock_response
        
        result = await client.set("test_key", "test_value", ttl=300)
        
        assert result is True
        client._stub.Set.assert_called_once()
        call_args = client._stub.Set.call_args[0][0]
        assert call_args.key == "test_key"
        assert call_args.value == b"test_value"
        assert call_args.ttl == 300

    @pytest.mark.asyncio
    async def test_set_with_default_ttl(self, client_with_mock_stub):
        """Test set operation with default TTL."""
        client = client_with_mock_stub
        
        mock_response = Mock()
        mock_response.status = "OK"
        client._stub.Set.return_value = mock_response
        
        await client.set("test_key", "test_value")
        
        call_args = client._stub.Set.call_args[0][0]
        assert call_args.ttl == client.default_ttl

    @pytest.mark.asyncio
    async def test_set_invalid_ttl(self, client_with_mock_stub):
        """Test set operation with invalid TTL."""
        client = client_with_mock_stub
        
        with pytest.raises(CacheValidationError, match="TTL must be non-negative"):
            await client.set("test_key", "test_value", ttl=-1)

    @pytest.mark.asyncio
    async def test_delete_success(self, client_with_mock_stub):
        """Test successful delete operation."""
        client = client_with_mock_stub
        
        mock_response = Mock()
        mock_response.status = "OK"
        client._stub.Delete.return_value = mock_response
        
        result = await client.delete("test_key")
        
        assert result is True
        client._stub.Delete.assert_called_once()
        call_args = client._stub.Delete.call_args[0][0]
        assert call_args.key == "test_key"

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client_with_mock_stub):
        """Test delete operation when key not found."""
        client = client_with_mock_stub
        
        mock_response = Mock()
        mock_response.status = "NOT_FOUND"
        client._stub.Delete.return_value = mock_response
        
        result = await client.delete("missing_key")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_stats_success(self, client_with_mock_stub):
        """Test successful stats operation."""
        client = client_with_mock_stub
        
        mock_response = Mock()
        mock_response.size = 100
        mock_response.hits = 80
        mock_response.misses = 20
        client._stub.Stats.return_value = mock_response
        
        result = await client.stats()
        
        expected = {
            "size": 100,
            "hits": 80,
            "misses": 20,
            "hit_rate": 0.8
        }
        assert result == expected

    @pytest.mark.asyncio
    async def test_stats_no_requests(self, client_with_mock_stub):
        """Test stats operation with no requests."""
        client = client_with_mock_stub
        
        mock_response = Mock()
        mock_response.size = 0
        mock_response.hits = 0
        mock_response.misses = 0
        client._stub.Stats.return_value = mock_response
        
        result = await client.stats()
        
        assert result["hit_rate"] == 0

    @pytest.mark.asyncio
    async def test_ping_success(self, client_with_mock_stub):
        """Test successful ping operation."""
        client = client_with_mock_stub
        
        mock_response = Mock()
        mock_response.size = 0
        mock_response.hits = 0
        mock_response.misses = 0
        client._stub.Stats.return_value = mock_response
        
        result = await client.ping()
        
        assert result is True

    @pytest.mark.asyncio
    async def test_ping_failure(self, client_with_mock_stub):
        """Test ping operation failure."""
        client = client_with_mock_stub
        
        client._stub.Stats.side_effect = Exception("Connection failed")
        
        result = await client.ping()
        
        assert result is False


class TestCacheClientErrorHandling:
    """Test error handling and retry logic."""

    @pytest.fixture
    def client_with_mock_stub(self):
        """Create a client with mocked stub."""
        client = CacheClient(max_retries=2, retry_delay=0.1)
        client._stub = AsyncMock()
        client._channel = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_grpc_unavailable_with_retry(self, client_with_mock_stub):
        """Test gRPC unavailable error with retry."""
        client = client_with_mock_stub
        
        # Disable health check and reconnection for this test
        client._last_health_check = time.time()  # Skip health check
        
        # Mock gRPC error
        grpc_error = grpc.RpcError()
        grpc_error.code = Mock(return_value=StatusCode.UNAVAILABLE)
        grpc_error.details = Mock(return_value="Service unavailable")
        
        # Mock both Get and Stats to prevent reconnection attempts
        client._stub.Get.side_effect = [grpc_error, grpc_error, grpc_error, grpc_error]
        client._stub.Stats.side_effect = grpc_error
        
        # Mock the reconnect method to prevent it from succeeding
        async def mock_reconnect():
            raise Exception("Reconnection failed")
        
        client._reconnect = mock_reconnect
        
        with pytest.raises(CacheConnectionError, match="Cache service unavailable after retries"):
            await client.get("test_key")
        
        # Verify that Get was called the expected number of times
        assert client._stub.Get.call_count >= 3

    @pytest.mark.asyncio
    async def test_grpc_invalid_argument(self, client_with_mock_stub):
        """Test gRPC invalid argument error."""
        client = client_with_mock_stub
        
        grpc_error = grpc.RpcError()
        grpc_error.code = Mock(return_value=StatusCode.INVALID_ARGUMENT)
        grpc_error.details = Mock(return_value="Invalid key format")
        
        client._stub.Get.side_effect = grpc_error
        
        with pytest.raises(CacheInvalidArgumentError, match="Invalid argument: Invalid key format"):
            await client.get("test_key")

    @pytest.mark.asyncio
    async def test_grpc_resource_exhausted(self, client_with_mock_stub):
        """Test gRPC resource exhausted error."""
        client = client_with_mock_stub
        
        grpc_error = grpc.RpcError()
        grpc_error.code = Mock(return_value=StatusCode.RESOURCE_EXHAUSTED)
        grpc_error.details = Mock(return_value="Cache full")
        
        client._stub.Get.side_effect = grpc_error
        
        with pytest.raises(CacheError, match="Cache full: Cache full"):
            await client.get("test_key")

    @pytest.mark.asyncio
    async def test_timeout_with_retry(self, client_with_mock_stub):
        """Test timeout error with retry."""
        client = client_with_mock_stub
        
        client._stub.Get.side_effect = [
            asyncio.TimeoutError(),
            asyncio.TimeoutError(),
            asyncio.TimeoutError()
        ]
        
        with pytest.raises(CacheTimeoutError, match="Request timeout after retries"):
            await client.get("test_key")
        
        assert client._stub.Get.call_count == 3

    @pytest.mark.asyncio
    async def test_client_closed_error(self):
        """Test operation on closed client."""
        client = CacheClient()
        client._closed = True
        
        with pytest.raises(CacheConnectionError, match="Client is closed"):
            await client.get("test_key")

    @pytest.mark.asyncio
    async def test_auto_connect_on_operation(self):
        """Test automatic connection on operation."""
        client = CacheClient()
        
        # Mock the connect method to set up the stub
        async def mock_connect():
            client._stub = AsyncMock()
            mock_response = Mock()
            mock_response.found = True
            mock_response.value = b"test_value"
            client._stub.Get.return_value = mock_response
        
        with patch.object(client, 'connect', side_effect=mock_connect) as mock_connect_spy:
            # This should trigger auto-connect since _stub is None
            result = await client.get("test_key")
            
            mock_connect_spy.assert_called_once()
            assert result == "test_value"

    @pytest.mark.asyncio
    async def test_unexpected_error(self, client_with_mock_stub):
        """Test unexpected error handling."""
        client = client_with_mock_stub
        
        client._stub.Get.side_effect = ValueError("Unexpected error")
        
        with pytest.raises(CacheError, match="Unexpected error: Unexpected error"):
            await client.get("test_key")


@pytest.mark.unit
class TestExceptionHierarchy:
    """Test exception class hierarchy."""
    
    def test_exception_inheritance(self):
        """Test that all exceptions inherit from CacheError."""
        assert issubclass(CacheConnectionError, CacheError)
        assert issubclass(CacheValidationError, CacheError)
        assert issubclass(CacheTimeoutError, CacheError)
        assert issubclass(CacheNotFoundError, CacheError)
        assert issubclass(CacheInvalidArgumentError, CacheError)

    def test_exception_messages(self):
        """Test exception messages."""
        error = CacheConnectionError("Connection failed")
        assert str(error) == "Connection failed"
        
        error = CacheValidationError("Invalid input")
        assert str(error) == "Invalid input"
