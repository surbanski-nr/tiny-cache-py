"""
Integration tests for tiny-cache-py client.

These tests require a running tiny-cache server.
Run the server first: cd ../tiny-cache && python server.py
"""

import asyncio
import pytest
import time
from tiny_cache_py import CacheClient, CacheConnectionError, CacheValidationError


@pytest.mark.integration
class TestCacheClientIntegration:
    """Integration tests that require a running cache server"""
    
    async def _create_client(self):
        """Helper method to create a cache client for testing"""
        client = CacheClient(
            server_address="localhost:50051",
            timeout=5.0,
            max_retries=2
        )
        await client.connect()
        return client
    
    @pytest.mark.asyncio
    async def test_basic_operations(self):
        """Test basic cache operations"""
        client = await self._create_client()
        try:
            key = "test_key"
            value = "test_value"
            
            result = await client.set(key, value, ttl=60)
            assert result is True
            
            retrieved = await client.get(key)
            assert retrieved == value
            
            deleted = await client.delete(key)
            assert deleted is True
            
            retrieved = await client.get(key)
            assert retrieved is None
            
            deleted = await client.delete(key)
            assert deleted is False
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_ttl_expiration(self):
        """Test TTL expiration"""
        client = await self._create_client()
        try:
            key = "ttl_test_key"
            value = "ttl_test_value"
            
            await client.set(key, value, ttl=1)
            
            retrieved = await client.get(key)
            assert retrieved == value
            
            await asyncio.sleep(2)
            
            retrieved = await client.get(key)
            assert retrieved is None
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_stats(self):
        """Test stats functionality"""
        client = await self._create_client()
        try:
            stats = await client.stats()
            assert isinstance(stats, dict)
            assert "size" in stats
            assert "hits" in stats
            assert "misses" in stats
            assert "hit_rate" in stats
            
            await client.set("stats_test", "value", ttl=60)
            await client.get("stats_test")
            await client.get("nonexistent")
            
            new_stats = await client.stats()
            assert new_stats["size"] >= stats["size"]
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_ping(self):
        """Test ping functionality"""
        client = await self._create_client()
        try:
            result = await client.ping()
            assert result is True
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test using client as context manager"""
        async with CacheClient("localhost:50051") as client:
            await client.set("context_test", "value")
            result = await client.get("context_test")
            assert result == "value"
    
    @pytest.mark.asyncio
    async def test_connection_recovery(self):
        """Test connection recovery after network issues"""
        client = CacheClient("localhost:50051", max_retries=3)
        
        await client.set("recovery_test", "value")
        result = await client.get("recovery_test")
        assert result == "value"
        
        if client._channel:
            await client._channel.close()
            client._channel = None
            client._stub = None
        
        await client.set("recovery_test2", "value2")
        result = await client.get("recovery_test2")
        assert result == "value2"
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent cache operations"""
        client = await self._create_client()
        try:
            async def set_and_get(i):
                key = f"concurrent_key_{i}"
                value = f"concurrent_value_{i}"
                await client.set(key, value)
                result = await client.get(key)
                return result == value
            
            tasks = [set_and_get(i) for i in range(10)]
            results = await asyncio.gather(*tasks)
            
            assert all(results)
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_large_values(self):
        """Test handling of large values"""
        client = await self._create_client()
        try:
            key = "large_value_test"
            large_value = "x" * (1024 * 1024)
            
            await client.set(key, large_value)
            result = await client.get(key)
            assert result == large_value
            
            await client.delete(key)
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_special_characters(self):
        """Test keys and values with special characters"""
        client = await self._create_client()
        try:
            test_cases = [
                ("unicode_key_🔑", "unicode_value_🎯"),
                ("spaces in key", "spaces in value"),
                ("key-with-dashes", "value-with-dashes"),
                ("key_with_underscores", "value_with_underscores"),
                ("key.with.dots", "value.with.dots"),
            ]
            
            for key, value in test_cases:
                await client.set(key, value)
                result = await client.get(key)
                assert result == value, f"Failed for key: {key}"
                await client.delete(key)
        finally:
            await client.close()


@pytest.mark.integration
class TestCacheClientErrorHandling:
    """Integration tests for error handling"""
    
    @pytest.mark.asyncio
    async def test_connection_to_invalid_server(self):
        """Test connection to non-existent server"""
        client = CacheClient("localhost:59999", timeout=1.0, max_retries=1)
        
        with pytest.raises(CacheConnectionError):
            await client.get("test_key")
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_validation_errors(self):
        """Test input validation errors"""
        client = CacheClient("localhost:50051")
        
        with pytest.raises(CacheValidationError):
            await client.get(123)
        
        with pytest.raises(CacheValidationError):
            await client.get("")
        
        with pytest.raises(CacheValidationError):
            await client.get("x" * 300)
        
        with pytest.raises(CacheValidationError):
            await client.set("test", None)
        
        with pytest.raises(CacheValidationError):
            await client.set("test", "value", ttl=-1)
        
        await client.close()


@pytest.mark.integration
class TestCacheClientPerformance:
    """Basic performance tests"""
    
    async def _create_client(self):
        """Helper method to create a cache client for testing"""
        client = CacheClient("localhost:50051")
        await client.connect()
        return client
    
    @pytest.mark.asyncio
    async def test_throughput(self):
        """Test basic throughput"""
        client = await self._create_client()
        try:
            num_operations = 100
            start_time = time.time()
            
            for i in range(num_operations):
                await client.set(f"perf_key_{i}", f"perf_value_{i}")
            
            set_time = time.time() - start_time
            
            start_time = time.time()
            for i in range(num_operations):
                result = await client.get(f"perf_key_{i}")
                assert result == f"perf_value_{i}"
            
            get_time = time.time() - start_time
            
            print(f"Set throughput: {num_operations / set_time:.2f} ops/sec")
            print(f"Get throughput: {num_operations / get_time:.2f} ops/sec")
            
            for i in range(num_operations):
                await client.delete(f"perf_key_{i}")
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_latency(self):
        """Test operation latency"""
        client = await self._create_client()
        try:
            key = "latency_test_key"
            value = "latency_test_value"
            
            start_time = time.time()
            await client.set(key, value)
            set_latency = (time.time() - start_time) * 1000
            
            start_time = time.time()
            result = await client.get(key)
            get_latency = (time.time() - start_time) * 1000
            
            assert result == value
            
            print(f"Set latency: {set_latency:.2f} ms")
            print(f"Get latency: {get_latency:.2f} ms")
            
            assert set_latency < 100
            assert get_latency < 100
            
            # Clean up
            await client.delete(key)
        finally:
            await client.close()
