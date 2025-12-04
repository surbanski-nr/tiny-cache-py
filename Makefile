# tiny-cache-py Makefile
PROTOC=python -m grpc_tools.protoc
PYTHON=python
PIP=pip

# Default target
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

# Development setup
setup: ## Set up development environment
	$(PIP) install -r requirements-dev.txt
	$(PIP) install -e .

install: ## Install package in development mode
	$(PIP) install -e .

# Protocol buffer generation
proto: ## Generate protobuf files from server's cache.proto
	@echo "Generating protobuf files from server..."
	@if [ ! -f "../tiny-cache/cache.proto" ]; then \
		echo "Error: Server protobuf file not found at ../tiny-cache/cache.proto"; \
		echo "Please ensure the tiny-cache server project is in the parent directory"; \
		exit 1; \
	fi
	$(PROTOC) -I../tiny-cache --python_out=tiny_cache_py/ --grpc_python_out=tiny_cache_py/ ../tiny-cache/cache.proto
	@echo "Fixing protobuf imports..."
	sed -i 's/^import cache_pb2/from . import cache_pb2/' tiny_cache_py/cache_pb2_grpc.py
	@echo "Protobuf files generated successfully from server"

gen: proto ## Alias for proto target

# Testing
test: ## Run unit tests with pytest
	$(PYTHON) -m pytest tests/ -v

test-coverage: ## Run tests with coverage report
	$(PYTHON) -m pytest tests/ --cov=tiny_cache_py --cov-report=html --cov-report=term

benchmark: ## Run performance benchmarks (requires running server)
	$(PYTHON) tests/benchmark_client.py

# Code quality
lint: ## Run code linting with mypy
	$(PYTHON) -m mypy tiny_cache_py/

format: ## Format code with black
	$(PYTHON) -m black tiny_cache_py/ tests/

format-check: ## Check code formatting
	$(PYTHON) -m black --check tiny_cache_py/ tests/

quality: lint format-check ## Run all code quality checks

# Cleanup
clean: ## Clean generated files
	rm -f tiny_cache_py/cache_pb2.py tiny_cache_py/cache_pb2_grpc.py
	rm -rf build/ dist/ *.egg-info/ __pycache__/ .pytest_cache/ .coverage htmlcov/ .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Development workflow
dev: setup proto test ## Complete development setup and test

.PHONY: help setup install proto gen test test-coverage benchmark lint format format-check quality clean dev