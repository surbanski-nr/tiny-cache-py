gen:
	python -m grpc_tools.protoc --python_out=tiny_cache_py/ --grpc_python_out=tiny_cache_py/ --pyi_out=tiny_cache_py/ cache.proto