#!/usr/bin/env python3
"""Profile memory formatting performance.

Usage:
    uv run python scripts/profile_memory_formatting.py
"""

import cProfile
import pstats

# Add project root to path
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from atloop.memory.formatter import MemoryFormatter
from atloop.memory.state import AgentState, Artifacts, LastError, Memory
from atloop.orchestrator.budget import BudgetUsed


def create_test_state(step: int, num_tool_results: int = 10) -> AgentState:
    """Create a test state for profiling."""
    memory = Memory()
    memory.tool_results_history = [
        {
            "step": i,
            "tool": "read_file",
            "args": {"path": f"file{i}.py"},
            "result": {
                "ok": True,
                "stdout": f"Content of file{i}.py with some text " * 50,
            },
        }
        for i in range(num_tool_results)
    ]
    memory.attempts = [{"step": i, "actions": [f"action{i}"]} for i in range(step)]
    memory.modified_files_content = [
        {
            "path": f"file{i}.py",
            "content": f"Content of modified file{i}.py " * 30,
            "last_modified_step": i,
            "size": len(f"Content of modified file{i}.py " * 30),
            "importance_score": 0.5,
        }
        for i in range(min(5, step))
    ]

    return AgentState(
        step=step,
        phase="PLAN",
        memory=memory,
        artifacts=Artifacts(),
        last_error=LastError(),
        budget_used=BudgetUsed(),
    )


def profile_formatting():
    """Profile memory formatting performance."""
    formatter = MemoryFormatter()
    state = create_test_state(step=10, num_tool_results=20)

    # Profile formatting
    profiler = cProfile.Profile()
    profiler.enable()

    # Format multiple times to test caching
    for _ in range(5):
        result = formatter.format(state)
        assert result is not None

    profiler.disable()

    # Print stats
    stats = pstats.Stats(profiler)
    stats.sort_stats("cumulative")
    print("\n=== Memory Formatting Profile (Top 20) ===")
    stats.print_stats(20)

    # Print cache stats
    cache_stats = formatter.get_cache_stats()
    print("\n=== Cache Statistics ===")
    print(f"Hits: {cache_stats['hits']}")
    print(f"Misses: {cache_stats['misses']}")
    print(f"Hit Rate: {cache_stats['hit_rate']}%")
    print(f"Cache Size: {cache_stats['cache_size']}")


if __name__ == "__main__":
    profile_formatting()
