"""
Performance benchmarks for tiny-cache-py client.

Run with: python tests/benchmark_client.py

Requires a running tiny-cache server:
cd ../tiny-cache && python server.py
"""

import asyncio
import time
import statistics
import argparse
from typing import List, Dict, Any
from tiny_cache_py import CacheClient


class CacheBenchmark:
    """Performance benchmark suite for cache client"""
    
    def __init__(self, server_address: str = "localhost:50051"):
        self.server_address = server_address
        self.client = None
        self.results = {}
    
    async def setup(self):
        """Setup benchmark environment"""
        self.client = CacheClient(self.server_address, timeout=10.0)
        await self.client.connect()
        print(f"Connected to cache server at {self.server_address}")
    
    async def teardown(self):
        """Cleanup benchmark environment"""
        if self.client:
            await self.client.close()
    
    async def benchmark_set_operations(self, num_ops: int = 1000, value_size: int = 100) -> Dict[str, Any]:
        """Benchmark SET operations"""
        print(f"Benchmarking {num_ops} SET operations (value size: {value_size} bytes)...")
        
        value = "x" * value_size
        latencies = []
        
        start_time = time.time()
        
        for i in range(num_ops):
            key = f"bench_set_{i}"
            op_start = time.time()
            await self.client.set(key, value, ttl=3600)
            latencies.append((time.time() - op_start) * 1000)  # ms
        
        total_time = time.time() - start_time
        
        return {
            "operation": "SET",
            "num_operations": num_ops,
            "value_size_bytes": value_size,
            "total_time_sec": total_time,
            "throughput_ops_sec": num_ops / total_time,
            "avg_latency_ms": statistics.mean(latencies),
            "median_latency_ms": statistics.median(latencies),
            "p95_latency_ms": self._percentile(latencies, 95),
            "p99_latency_ms": self._percentile(latencies, 99),
            "min_latency_ms": min(latencies),
            "max_latency_ms": max(latencies)
        }
    
    async def benchmark_get_operations(self, num_ops: int = 1000) -> Dict[str, Any]:
        """Benchmark GET operations"""
        print(f"Benchmarking {num_ops} GET operations...")
        
        # Pre-populate cache
        for i in range(num_ops):
            await self.client.set(f"bench_get_{i}", f"value_{i}", ttl=3600)
        
        latencies = []
        hits = 0
        
        start_time = time.time()
        
        for i in range(num_ops):
            key = f"bench_get_{i}"
            op_start = time.time()
            result = await self.client.get(key)
            latencies.append((time.time() - op_start) * 1000)  # ms
            if result is not None:
                hits += 1
        
        total_time = time.time() - start_time
        
        return {
            "operation": "GET",
            "num_operations": num_ops,
            "total_time_sec": total_time,
            "throughput_ops_sec": num_ops / total_time,
            "hit_rate": hits / num_ops,
            "avg_latency_ms": statistics.mean(latencies),
            "median_latency_ms": statistics.median(latencies),
            "p95_latency_ms": self._percentile(latencies, 95),
            "p99_latency_ms": self._percentile(latencies, 99),
            "min_latency_ms": min(latencies),
            "max_latency_ms": max(latencies)
        }
    
    async def benchmark_mixed_operations(self, num_ops: int = 1000, read_ratio: float = 0.8) -> Dict[str, Any]:
        """Benchmark mixed read/write operations"""
        print(f"Benchmarking {num_ops} mixed operations (read ratio: {read_ratio})...")
        
        # Pre-populate some data
        for i in range(int(num_ops * 0.5)):
            await self.client.set(f"bench_mixed_{i}", f"value_{i}", ttl=3600)
        
        latencies = []
        operations = []
        
        start_time = time.time()
        
        for i in range(num_ops):
            if (i / num_ops) < read_ratio:
                # GET operation
                key = f"bench_mixed_{i % int(num_ops * 0.5)}"
                op_start = time.time()
                await self.client.get(key)
                operations.append("GET")
            else:
                # SET operation
                key = f"bench_mixed_{i}"
                op_start = time.time()
                await self.client.set(key, f"value_{i}", ttl=3600)
                operations.append("SET")
            
            latencies.append((time.time() - op_start) * 1000)  # ms
        
        total_time = time.time() - start_time
        
        return {
            "operation": "MIXED",
            "num_operations": num_ops,
            "read_ratio": read_ratio,
            "total_time_sec": total_time,
            "throughput_ops_sec": num_ops / total_time,
            "avg_latency_ms": statistics.mean(latencies),
            "median_latency_ms": statistics.median(latencies),
            "p95_latency_ms": self._percentile(latencies, 95),
            "p99_latency_ms": self._percentile(latencies, 99),
            "min_latency_ms": min(latencies),
            "max_latency_ms": max(latencies)
        }
    
    async def benchmark_concurrent_operations(self, num_clients: int = 10, ops_per_client: int = 100) -> Dict[str, Any]:
        """Benchmark concurrent operations with multiple clients"""
        print(f"Benchmarking concurrent operations ({num_clients} clients, {ops_per_client} ops each)...")
        
        async def client_worker(client_id: int) -> List[float]:
            client = CacheClient(self.server_address)
            await client.connect()
            
            latencies = []
            
            for i in range(ops_per_client):
                key = f"bench_concurrent_{client_id}_{i}"
                value = f"value_{client_id}_{i}"
                
                # Mixed operations
                op_start = time.time()
                if i % 2 == 0:
                    await client.set(key, value, ttl=3600)
                else:
                    await client.get(key)
                latencies.append((time.time() - op_start) * 1000)
            
            await client.close()
            return latencies
        
        start_time = time.time()
        
        # Run concurrent clients
        tasks = [client_worker(i) for i in range(num_clients)]
        all_latencies = await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        
        # Flatten latencies
        flat_latencies = [lat for client_lats in all_latencies for lat in client_lats]
        total_ops = num_clients * ops_per_client
        
        return {
            "operation": "CONCURRENT",
            "num_clients": num_clients,
            "ops_per_client": ops_per_client,
            "total_operations": total_ops,
            "total_time_sec": total_time,
            "throughput_ops_sec": total_ops / total_time,
            "avg_latency_ms": statistics.mean(flat_latencies),
            "median_latency_ms": statistics.median(flat_latencies),
            "p95_latency_ms": self._percentile(flat_latencies, 95),
            "p99_latency_ms": self._percentile(flat_latencies, 99),
            "min_latency_ms": min(flat_latencies),
            "max_latency_ms": max(flat_latencies)
        }
    
    async def benchmark_value_sizes(self, sizes: List[int] = None) -> List[Dict[str, Any]]:
        """Benchmark operations with different value sizes"""
        if sizes is None:
            sizes = [100, 1024, 10240, 102400]  # 100B, 1KB, 10KB, 100KB
        
        results = []
        
        for size in sizes:
            print(f"Benchmarking value size: {size} bytes...")
            result = await self.benchmark_set_operations(num_ops=100, value_size=size)
            results.append(result)
        
        return results
    
    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile of data"""
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def print_results(self, result: Dict[str, Any]):
        """Print benchmark results in a formatted way"""
        print(f"\n{'='*60}")
        print(f"Benchmark Results: {result['operation']}")
        print(f"{'='*60}")
        
        if 'num_operations' in result:
            print(f"Operations:        {result['num_operations']:,}")
        if 'value_size_bytes' in result:
            print(f"Value Size:        {result['value_size_bytes']:,} bytes")
        if 'num_clients' in result:
            print(f"Concurrent Clients: {result['num_clients']}")
        if 'read_ratio' in result:
            print(f"Read Ratio:        {result['read_ratio']:.1%}")
        if 'hit_rate' in result:
            print(f"Hit Rate:          {result['hit_rate']:.1%}")
        
        print(f"Total Time:        {result['total_time_sec']:.2f} seconds")
        print(f"Throughput:        {result['throughput_ops_sec']:,.0f} ops/sec")
        print(f"Avg Latency:       {result['avg_latency_ms']:.2f} ms")
        print(f"Median Latency:    {result['median_latency_ms']:.2f} ms")
        print(f"95th Percentile:   {result['p95_latency_ms']:.2f} ms")
        print(f"99th Percentile:   {result['p99_latency_ms']:.2f} ms")
        print(f"Min Latency:       {result['min_latency_ms']:.2f} ms")
        print(f"Max Latency:       {result['max_latency_ms']:.2f} ms")
    
    async def run_all_benchmarks(self):
        """Run all benchmark suites"""
        print("Starting comprehensive benchmark suite...")
        
        # Basic operations
        set_result = await self.benchmark_set_operations(1000)
        self.print_results(set_result)
        
        get_result = await self.benchmark_get_operations(1000)
        self.print_results(get_result)
        
        # Mixed workload
        mixed_result = await self.benchmark_mixed_operations(1000, 0.8)
        self.print_results(mixed_result)
        
        # Concurrent operations
        concurrent_result = await self.benchmark_concurrent_operations(10, 100)
        self.print_results(concurrent_result)
        
        # Different value sizes
        print(f"\n{'='*60}")
        print("Value Size Benchmark")
        print(f"{'='*60}")
        
        size_results = await self.benchmark_value_sizes()
        for result in size_results:
            print(f"\nValue Size: {result['value_size_bytes']:,} bytes")
            print(f"Throughput: {result['throughput_ops_sec']:,.0f} ops/sec")
            print(f"Avg Latency: {result['avg_latency_ms']:.2f} ms")


async def main():
    """Main benchmark runner"""
    parser = argparse.ArgumentParser(description="Benchmark tiny-cache-py client")
    parser.add_argument("--server", default="localhost:50051", help="Cache server address")
    parser.add_argument("--operations", type=int, default=1000, help="Number of operations per benchmark")
    parser.add_argument("--benchmark", choices=["set", "get", "mixed", "concurrent", "sizes", "all"], 
                       default="all", help="Specific benchmark to run")
    
    args = parser.parse_args()
    
    benchmark = CacheBenchmark(args.server)
    
    try:
        await benchmark.setup()
        
        if args.benchmark == "set":
            result = await benchmark.benchmark_set_operations(args.operations)
            benchmark.print_results(result)
        elif args.benchmark == "get":
            result = await benchmark.benchmark_get_operations(args.operations)
            benchmark.print_results(result)
        elif args.benchmark == "mixed":
            result = await benchmark.benchmark_mixed_operations(args.operations)
            benchmark.print_results(result)
        elif args.benchmark == "concurrent":
            result = await benchmark.benchmark_concurrent_operations()
            benchmark.print_results(result)
        elif args.benchmark == "sizes":
            results = await benchmark.benchmark_value_sizes()
            for result in results:
                benchmark.print_results(result)
        else:  # all
            await benchmark.run_all_benchmarks()
    
    except Exception as e:
        print(f"Benchmark failed: {e}")
        return 1
    
    finally:
        await benchmark.teardown()
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))