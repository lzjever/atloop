"""Performance benchmarks for memory formatting."""

import time

import pytest

from atloop.memory.formatter import MemoryFormatter
from atloop.memory.state import AgentState, Artifacts, LastError, Memory
from atloop.orchestrator.budget import BudgetUsed


@pytest.mark.benchmark
class TestMemoryFormattingPerformance:
    """Performance benchmarks for memory formatting."""

    def test_format_small_memory(self):
        """Benchmark formatting small memory (early stage)."""
        state = self._create_small_state()
        formatter = MemoryFormatter()

        start = time.time()
        result = formatter.format(state)
        elapsed = time.time() - start

        assert result is not None
        assert len(result) > 0
        # Small memory should format quickly (< 1 second)
        assert elapsed < 1.0, f"Formatting took {elapsed:.3f}s, expected < 1.0s"

        # Check cache stats
        stats = formatter.get_cache_stats()
        assert stats["hits"] >= 0
        assert stats["misses"] >= 1

    def test_format_large_memory(self):
        """Benchmark formatting large memory (many steps)."""
        state = self._create_large_state()
        formatter = MemoryFormatter()

        start = time.time()
        result = formatter.format(state)
        elapsed = time.time() - start

        assert result is not None
        assert len(result) > 0
        # Large memory should still format in reasonable time (< 5 seconds)
        assert elapsed < 5.0, f"Formatting took {elapsed:.3f}s, expected < 5.0s"

    def test_format_caching_performance(self):
        """Test that caching improves performance."""
        state = self._create_medium_state()
        formatter = MemoryFormatter()

        # First call (cache miss)
        start = time.time()
        result1 = formatter.format(state)
        time1 = time.time() - start

        # Second call (cache hit)
        start = time.time()
        result2 = formatter.format(state)
        time2 = time.time() - start

        # Results should be identical
        assert result1 == result2

        # Second call should be faster (cached)
        # Allow some variance for timing, but cache should be significantly faster
        if time1 > 0.01:  # Only check if first call took meaningful time
            assert time2 < time1, f"Cache should be faster: {time2} < {time1}"

        # Check cache stats
        stats = formatter.get_cache_stats()
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
        assert stats["hit_rate"] > 0

    def _create_small_state(self) -> AgentState:
        """Create a small state for benchmarking."""
        return AgentState(
            step=1,
            phase="PLAN",
            memory=Memory(),
            artifacts=Artifacts(),
            last_error=LastError(),
            budget_used=BudgetUsed(),
        )

    def _create_medium_state(self) -> AgentState:
        """Create a medium-sized state for benchmarking."""
        memory = Memory()
        memory.tool_results_history = [
            {
                "step": i,
                "tool": "read_file",
                "args": {"path": f"file{i}.py"},
                "result": {"ok": True, "stdout": f"Content of file{i}.py" * 10},
            }
            for i in range(5)
        ]
        memory.attempts = [{"step": i, "actions": [f"action{i}"]} for i in range(5)]

        return AgentState(
            step=5,
            phase="ACT",
            memory=memory,
            artifacts=Artifacts(),
            last_error=LastError(),
            budget_used=BudgetUsed(),
        )

    def _create_large_state(self) -> AgentState:
        """Create a large state for benchmarking."""
        memory = Memory()
        memory.tool_results_history = [
            {
                "step": i,
                "tool": "read_file",
                "args": {"path": f"file{i}.py"},
                "result": {
                    "ok": True,
                    "stdout": f"Content of file{i}.py with lots of text " * 100,
                },
            }
            for i in range(20)
        ]
        memory.attempts = [{"step": i, "actions": [f"action{i}"]} for i in range(20)]
        memory.modified_files_content = [
            {
                "path": f"file{i}.py",
                "content": f"Content of modified file{i}.py " * 50,
                "last_modified_step": i,
                "size": len(f"Content of modified file{i}.py " * 50),
                "importance_score": 0.5,
            }
            for i in range(10)
        ]

        return AgentState(
            step=20,
            phase="VERIFY",
            memory=memory,
            artifacts=Artifacts(),
            last_error=LastError(),
            budget_used=BudgetUsed(),
        )
