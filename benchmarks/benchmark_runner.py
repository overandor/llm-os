"""
Benchmark Discipline Framework for LLM OS
"""

import time
import json
import statistics
from typing import Dict, List, Any, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class BenchmarkResult:
    benchmark_name: str
    implementation: str
    duration_ms: float
    memory_mb: float
    success: bool
    error: str = ""
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class BenchmarkSuite:
    name: str
    results: List[BenchmarkResult]
    timestamp: str
    environment: Dict[str, Any]
    
    def add_result(self, result: BenchmarkResult):
        self.results.append(result)
    
    def get_summary(self) -> Dict[str, Any]:
        successful = [r for r in self.results if r.success]
        if not successful:
            return {"error": "No successful benchmarks"}
        durations = [r.duration_ms for r in successful]
        memory = [r.memory_mb for r in successful]
        return {
            "total_benchmarks": len(self.results),
            "successful": len(successful),
            "failed": len(self.results) - len(successful),
            "avg_duration_ms": statistics.mean(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "avg_memory_mb": statistics.mean(memory),
            "success_rate": len(successful) / len(self.results)
        }


class BenchmarkRunner:
    def __init__(self, suite_name: str, output_dir: str = "benchmarks/results"):
        self.suite_name = suite_name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.suite = BenchmarkSuite(
            name=suite_name,
            results=[],
            timestamp=datetime.utcnow().isoformat(),
            environment=self._get_environment()
        )
    
    def _get_environment(self) -> Dict[str, Any]:
        import platform
        import sys
        return {
            "python_version": sys.version,
            "platform": platform.platform(),
            "processor": platform.processor(),
            "machine": platform.machine()
        }
    
    def run_benchmark(self, name: str, func: Callable, iterations: int = 10, warmup: int = 2) -> BenchmarkResult:
        print(f"Running benchmark: {name}")
        for _ in range(warmup):
            try: func()
            except: pass
        durations = []
        memory_usage = []
        for i in range(iterations):
            try:
                import tracemalloc
                tracemalloc.start()
                start = time.perf_counter()
                result = func()
                end = time.perf_counter()
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                duration_ms = (end - start) * 1000
                memory_mb = peak / (1024 * 1024)
                durations.append(duration_ms)
                memory_usage.append(memory_mb)
            except Exception as e:
                return BenchmarkResult(
                    benchmark_name=name,
                    implementation=self.suite_name,
                    duration_ms=0,
                    memory_mb=0,
                    success=False,
                    error=str(e)
                )
        avg_duration = statistics.mean(durations)
        avg_memory = statistics.mean(memory_usage)
        result = BenchmarkResult(
            benchmark_name=name,
            implementation=self.suite_name,
            duration_ms=avg_duration,
            memory_mb=avg_memory,
            success=True,
            metadata={"iterations": iterations, "durations": durations, "memory_samples": memory_usage}
        )
        self.suite.add_result(result)
        print(f"  Duration: {avg_duration:.2f}ms | Memory: {avg_memory:.2f}MB")
        return result
    
    def save_results(self, filename: str = None):
        if filename is None:
            filename = f"{self.suite_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        output_path = self.output_dir / filename
        with open(output_path, 'w') as f:
            json.dump({"suite": asdict(self.suite), "summary": self.suite.get_summary()}, f, indent=2)
        print(f"Results saved to: {output_path}")
        return output_path
    
    def print_summary(self):
        summary = self.suite.get_summary()
        print("\n" + "="*50)
        print(f"Benchmark Suite: {self.suite_name}")
        print("="*50)
        print(f"Total Benchmarks: {summary['total_benchmarks']}")
        print(f"Successful: {summary['successful']}")
        print(f"Failed: {summary['failed']}")
        print(f"Success Rate: {summary['success_rate']:.1%}")
        print(f"Avg Duration: {summary.get('avg_duration_ms', 0):.2f}ms")
        print(f"Avg Memory: {summary.get('avg_memory_mb', 0):.2f}MB")
        print("="*50)


def benchmark_vm_creation():
    from llm_os.server import VMInstance
    def benchmark_create():
        vm = VMInstance()
        return True
    return benchmark_create


def main():
    runner = BenchmarkRunner("llm_os")
    print("Starting benchmark suite...")
    runner.run_benchmark("vm_creation", benchmark_vm_creation(), iterations=50)
    runner.print_summary()
    runner.save_results()


if __name__ == "__main__":
    main()
