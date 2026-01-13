"""Tests for CompressionPolicy."""

from atloop.memory.compression_policy import (
    ImportanceBasedCompressionPolicy,
    RuleBasedCompressionPolicy,
)
from atloop.memory.state import AgentState, Artifacts, BudgetUsed, LastError, Memory
from tests.memory.fixtures.sample_state import create_sample_state


class TestRuleBasedCompressionPolicy:
    """Tests for RuleBasedCompressionPolicy."""

    def test_rule_based_compression_tool_results(self):
        """Test compression of tool_results_history."""
        state = create_sample_state(step=20, stage="late")

        # Add many tool results
        for i in range(15):
            state.memory.tool_results_history.append(
                {
                    "step": 10 + i,
                    "tool": "run",
                    "args": {"cmd": f"command_{i}"},
                    "placeholder": None,
                    "result": {"ok": True, "exit_code": 0, "stdout": f"output_{i}", "stderr": ""},
                    "modified_files": [],
                }
            )

        policy = RuleBasedCompressionPolicy(tool_results_keep_recent=10)

        len(state.memory.tool_results_history)
        compressed_memory = policy.compress(state.memory, target_size=50000)

        # Should have compressed old results
        assert len(compressed_memory.tool_results_history) <= 11  # 10 recent + 1 compressed

        # Should have a compressed record
        compressed_records = [
            r
            for r in compressed_memory.tool_results_history
            if isinstance(r, dict) and r.get("type") == "compressed"
        ]
        assert len(compressed_records) == 1

    def test_rule_based_compression_decisions(self):
        """Test compression of decisions."""
        state = create_sample_state(step=10, stage="mid")

        # Add many decisions
        for i in range(10):
            state.memory.decisions.append(
                {
                    "step": i,
                    "actions_count": 2,
                    "stop_reason": "continue",
                    "actions": [{"tool": "run", "args": {"cmd": "test"}}],
                }
            )

        policy = RuleBasedCompressionPolicy(decisions_keep_recent=5)

        len(state.memory.decisions)
        compressed_memory = policy.compress(state.memory, target_size=50000)

        # Should have compressed old decisions
        assert len(compressed_memory.decisions) <= 5

        # Should have added to learnings
        assert len(compressed_memory.learnings) > 0

    def test_rule_based_compression_important_decisions(self):
        """Test trimming of important_decisions."""
        state = create_sample_state(step=10, stage="mid")

        # Add many important decisions
        for i in range(25):
            state.memory.important_decisions.append(
                {
                    "step": i,
                    "content": f"Decision {i}",
                    "importance": 0.5,
                }
            )

        policy = RuleBasedCompressionPolicy(important_decisions_keep=20)

        compressed_memory = policy.compress(state.memory, target_size=50000)

        # Should be trimmed to 20
        assert len(compressed_memory.important_decisions) == 20

    def test_compression_estimate_size(self):
        """Test size estimation."""
        state = create_sample_state(step=7, stage="mid")
        policy = RuleBasedCompressionPolicy()

        size = policy.estimate_size(state.memory, state)

        assert isinstance(size, int)
        assert size > 0

    def test_compression_preserves_important_data(self):
        """Test that compression preserves important data."""
        state = create_sample_state(step=10, stage="late")

        # Add important decisions and milestones
        state.memory.important_decisions = [
            {"step": 2, "content": "Initial plan", "importance": 0.9},
            {"step": 7, "content": "Created script", "importance": 0.8},
        ]
        state.memory.milestones = [
            {"step": 7, "content": "Milestone 1", "importance": 0.8},
        ]

        policy = RuleBasedCompressionPolicy()
        compressed_memory = policy.compress(state.memory, target_size=50000)

        # Important data should be preserved
        assert len(compressed_memory.important_decisions) == 2
        assert len(compressed_memory.milestones) == 1


class TestImportanceBasedCompressionPolicy:
    """Tests for ImportanceBasedCompressionPolicy."""

    def test_importance_based_compression(self):
        """Test importance-based compression."""

        # Create clean state
        state = AgentState(
            step=20,
            phase="PLAN",
            memory=Memory(),
            last_error=LastError(),
            artifacts=Artifacts(),
            budget_used=BudgetUsed(),
        )

        # Add many tool results with varying importance
        for i in range(20):
            # Mix of important (file operations) and less important (run commands)
            tool = "write_file" if i % 3 == 0 else "run"
            result = {
                "step": 10 + i,
                "tool": tool,
                "args": {"path": f"file_{i}.py"} if tool == "write_file" else {"cmd": f"cmd_{i}"},
                "placeholder": None,
                "result": {"ok": True, "exit_code": 0, "stdout": f"output_{i}", "stderr": ""},
                "modified_files": [f"file_{i}.py"] if tool == "write_file" else [],
            }
            state.memory.tool_results_history.append(result)

        len(state.memory.tool_results_history)
        policy = ImportanceBasedCompressionPolicy(importance_threshold=0.3)

        compressed_memory = policy.compress(state.memory, target_size=50000)

        # Should have compressed some results (keep top 10 + compressed)
        assert len(compressed_memory.tool_results_history) <= 11  # 10 + 1 compressed

        # File operations should be preserved (higher importance)
        file_ops = [
            r
            for r in compressed_memory.tool_results_history
            if isinstance(r, dict) and r.get("tool") == "write_file"
        ]
        assert len(file_ops) > 0  # At least some file operations should be preserved

    def test_importance_calculation(self):
        """Test importance calculation."""
        policy = ImportanceBasedCompressionPolicy()

        # Test error result (should have high importance)
        error_result = {
            "step": 10,
            "tool": "run",
            "result": {"ok": False, "exit_code": 1},
        }
        error_score = policy._calculate_importance(error_result)
        assert error_score >= 1.0

        # Test file operation (should have medium importance)
        file_result = {
            "step": 10,
            "tool": "write_file",
            "result": {"ok": True},
        }
        file_score = policy._calculate_importance(file_result)
        assert file_score >= 0.5

        # Test regular run command (should have lower importance)
        run_result = {
            "step": 10,
            "tool": "run",
            "result": {"ok": True},
        }
        run_score = policy._calculate_importance(run_result)
        assert run_score < file_score
