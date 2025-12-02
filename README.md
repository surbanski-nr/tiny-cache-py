# tiny-cache-py

Python Client library for interacting with the Tiny Cache gRPC service.

## Local Development

```yaml
cp ../tiny-cache/*_pb2*.py .

pip install -e .

# Test it
python -c "
import asyncio
from tiny_cache_py import CacheClient

async def test():
    client = CacheClient()
    await client.set('test', 'hello')
    value = await client.get('test') 
    print(f'Got: {value}')

asyncio.run(test())
"
```

## Build and install from source

```yaml
python setup.py sdist bdist_wheel
pip install dist/tiny-cache-py-0.1.0.tar.gz
python test_client.py
```
