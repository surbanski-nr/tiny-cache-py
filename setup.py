from setuptools import setup, find_packages

setup(
    name="tiny-cache-py",
    version="0.1.0",
    description="Python client for tiny-cache gRPC service",
    author="Szymon Urbański",
    author_email="122265380+surbanski-nr@users.noreply.github.com",
    url="https://github.com/surbanski-nr/tiny-cache-py",
    packages=find_packages(),
    install_requires=[
        "grpcio>=1.76.0",
        "grpcio-tools>=1.76.0,<2.0.0",
        "protobuf>=6.31.1,<7.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-asyncio>=0.21.1",
            "black>=23.12.1",
            "mypy>=1.8.0",
        ]
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Caching",
    ],
    keywords="cache grpc client distributed-cache",
    include_package_data=True,
    package_data={
        "tiny_cache_py": ["*.proto"],
    },
)
