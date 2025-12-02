import grpc
import cache_pb2, cache_pb2_grpc, asyncio

class CacheClient:
    def __init__(self, host="localhost", port=50051):
        self.url = f"{host}:{port}"

    async def get(self, key):
        async with grpc.aio.insecure_channel(self.url) as ch:
            stub = cache_pb2_grpc.CacheServiceStub(ch)
            resp = await stub.Get(cache_pb2.CacheKey(key=key))
            if resp.found:
                return resp.value.decode()
            return None

    async def set(self, key, value, ttl=3600):
        async with grpc.aio.insecure_channel(self.url) as ch:
            stub = cache_pb2_grpc.CacheServiceStub(ch)
            await stub.Set(cache_pb2.CacheItem(key=key, value=value.encode(), ttl=ttl))
