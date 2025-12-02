import asyncio
import sys
sys.path.insert(0, '.')  # Use local version

from tiny_cache_py import CacheClient

async def test_cache():
    client = CacheClient("localhost", 50051)
    
    print("Testing set...")
    await client.set("test_key", "hello world")
    
    print("Testing get...")
    value = await client.get("test_key")
    print(f"Retrieved: {value}")
    
    print("Testing non-existent key...")
    missing = await client.get("missing_key")
    print(f"Missing key result: {missing}")

if __name__ == "__main__":
    asyncio.run(test_cache())