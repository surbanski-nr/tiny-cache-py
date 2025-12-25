import asyncio
import logging

from tiny_cache_py import CacheClient, CacheError, CacheConnectionError

logging.basicConfig(level=logging.INFO)


async def test_cache():
    """Comprehensive test of cache client functionality"""
    print("=== Tiny Cache Python Client Test ===\n")

    try:
        async with CacheClient("localhost:50051", timeout=5.0) as client:
            print("✓ Connected to cache service")

            if await client.ping():
                print("✓ Cache service is responding")
            else:
                print("✗ Cache service not responding")
                return

            # Test set operation
            print("\n--- Testing SET operations ---")
            success = await client.set("test_key", "hello world", ttl=60)
            print(f"Set 'test_key': {'✓' if success else '✗'}")

            success = await client.set("number_key", 42)
            print(f"Set 'number_key' (int): {'✓' if success else '✗'}")

            success = await client.set("bool_key", True)
            print(f"Set 'bool_key' (bool): {'✓' if success else '✗'}")

            # Test get operation
            print("\n--- Testing GET operations ---")
            value = await client.get("test_key")
            print(f"Get 'test_key': {value}")

            value = await client.get("number_key")
            print(f"Get 'number_key': {value}")

            value = await client.get("bool_key")
            print(f"Get 'bool_key': {value}")

            missing = await client.get("missing_key")
            print(f"Get 'missing_key': {missing}")

            # Test delete operation
            print("\n--- Testing DELETE operations ---")
            deleted = await client.delete("test_key")
            print(f"Delete 'test_key': {'✓' if deleted else '✗'}")

            value = await client.get("test_key")
            print(f"Get deleted key: {value}")

            deleted = await client.delete("non_existent")
            print(f"Delete non-existent key: {'✓' if deleted else '✗'}")

            # Test stats
            print("\n--- Testing STATS operation ---")
            stats = await client.stats()
            print(f"Cache stats: {stats}")

            # Test error handling
            print("\n--- Testing error handling ---")
            try:
                await client.set("", "empty key")
            except CacheError as e:
                print(f"✓ Caught expected error for empty key: {e}")

            try:
                await client.set("test", None)
            except CacheError as e:
                print(f"✓ Caught expected error for None value: {e}")

            # Test TTL
            print("\n--- Testing TTL functionality ---")
            await client.set("ttl_key", "expires soon", ttl=2)
            print("Set key with 2s TTL")

            value = await client.get("ttl_key")
            print(f"Immediate get: {value}")

            print("Waiting 3 seconds...")
            await asyncio.sleep(3)

            value = await client.get("ttl_key")
            print(f"Get after TTL: {value}")

            print("\n✓ All tests completed successfully!")

    except CacheConnectionError as e:
        print(f"✗ Connection error: {e}")
        print("Make sure the cache service is running on localhost:50051")
    except CacheError as e:
        print(f"✗ Cache error: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")


async def test_connection_pooling():
    """Test connection pooling and reuse"""
    print("\n=== Testing Connection Pooling ===")

    client = CacheClient("localhost:50051")

    try:
        await client.connect()
        print("✓ Connected")

        for i in range(5):
            await client.set(f"pool_test_{i}", f"value_{i}")
            value = await client.get(f"pool_test_{i}")
            print(f"Operation {i+1}: {value}")

        print("✓ Connection pooling test completed")

    finally:
        await client.close()
        print("✓ Connection closed")


if __name__ == "__main__":
    asyncio.run(test_cache())
    asyncio.run(test_connection_pooling())

