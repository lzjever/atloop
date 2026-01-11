"""Tests for MemoryCompressor improvements."""

import pytest
from unittest.mock import Mock, MagicMock

from atloop.memory.compressor import MemoryCompressor
from atloop.memory.state import AgentState, Memory


class TestMemoryCompressorFiltering:
    """Test that _compress_with_llm filters out current_step_thoughts."""

    def test_compress_with_llm_filters_current_step_thoughts(self):
        """Test that _compress_with_llm filters out current_step_thoughts before sending to LLM."""
        # Create state with decisions containing current_step_thoughts
        state = AgentState(step=20)
        state.memory.decisions = [
            {
                "step": 1,
                "current_step_thoughts": "I think the error is caused by...",
                "plan": ["Step 1", "Step 2"],
                "actions": [{"tool": "run", "args": {"cmd": "ls"}}],
                "stop_reason": "continue",
                "llm_output": "full output",
            },
            {
                "step": 2,
                "current_step_thoughts": "Let me try a different approach...",
                "plan": ["Step 3"],
                "actions": [{"tool": "read_file", "args": {"path": "test.py"}}],
                "stop_reason": "continue",
                "llm_output": "full output 2",
            },
        ] * 6  # 12 decisions total, will trigger compression (keep 10 recent)

        # Mock LLM client
        mock_llm_client = Mock()
        mock_result = Mock()
        mock_result.text = "Compressed summary"
        mock_llm_client.chat.complete = Mock(return_value=mock_result)

        # Mock memory config
        mock_memory_config = Mock()
        mock_memory_config.llm_compression_target = 10000

        # Call compression
        MemoryCompressor._compress_with_llm(state, mock_memory_config, mock_llm_client)

        # Verify LLM was called
        assert mock_llm_client.chat.complete.called

        # Get the prompt that was sent to LLM
        call_args = mock_llm_client.chat.complete.call_args
        compression_prompt = call_args[0][0]  # First positional argument

        # ✅ Verify that current_step_thoughts is NOT in the prompt
        assert "current_step_thoughts" not in compression_prompt
        assert "I think the error is caused by" not in compression_prompt
        assert "Let me try a different approach" not in compression_prompt

        # ✅ Verify that plan is NOT in the prompt
        assert '"plan"' not in compression_prompt or "Step 1" not in compression_prompt

        # ✅ Verify that llm_output is NOT in the prompt
        assert "full output" not in compression_prompt

        # ✅ Verify that factual information IS in the prompt
        assert "step" in compression_prompt
        assert "stop_reason" in compression_prompt
        assert "actions" in compression_prompt
        assert "run" in compression_prompt or "read_file" in compression_prompt

        # ✅ Verify system prompt emphasizes facts only
        system_prompt = call_args[1]["system"]  # system keyword argument
        assert "事实信息" in system_prompt or "factual" in system_prompt.lower()
        assert "思考过程" in system_prompt or "thinking" in system_prompt.lower()

    def test_compress_with_llm_preserves_factual_information(self):
        """Test that _compress_with_llm preserves factual information."""
        state = AgentState(step=15)
        state.memory.decisions = [
            {
                "step": 1,
                "current_step_thoughts": "Some thinking...",
                "actions": [{"tool": "write_file", "args": {"path": "test.py"}}],
                "actions_count": 1,
                "stop_reason": "continue",
                "verification_success": True,
            },
        ] * 12

        mock_llm_client = Mock()
        mock_result = Mock()
        mock_result.text = "Compressed"
        mock_llm_client.chat.complete = Mock(return_value=mock_result)

        mock_memory_config = Mock()
        mock_memory_config.llm_compression_target = 10000

        MemoryCompressor._compress_with_llm(state, mock_memory_config, mock_llm_client)

        # Get the prompt
        call_args = mock_llm_client.chat.complete.call_args
        compression_prompt = call_args[0][0]

        # Verify factual information is present
        assert "step" in compression_prompt
        assert "stop_reason" in compression_prompt
        assert "actions_count" in compression_prompt
        assert "verification_success" in compression_prompt
        assert "write_file" in compression_prompt


class TestSummarizeDecisions:
    """Test improved _summarize_decisions method."""

    def test_summarize_decisions_extracts_key_facts(self):
        """Test that _summarize_decisions extracts key factual information."""
        decisions = [
            {
                "step": 1,
                "actions": [{"tool": "run"}, {"tool": "read_file"}],
                "stop_reason": "continue",
                "verification_success": True,
            },
            {
                "step": 2,
                "actions": [{"tool": "write_file"}],
                "stop_reason": "continue",
                "verification_success": False,
            },
            {
                "step": 3,
                "actions": [{"tool": "run"}],
                "stop_reason": "done",
                "verification_success": True,
            },
        ]

        summary = MemoryCompressor._summarize_decisions(decisions)

        # ✅ Verify summary contains key facts
        assert "历史 3 个决策" in summary
        assert "共执行了" in summary
        assert "停止原因分布" in summary
        assert "continue" in summary
        assert "done" in summary
        assert "验证结果" in summary
        assert "成功" in summary
        assert "失败" in summary
        assert "常用工具" in summary

    def test_summarize_decisions_handles_empty_list(self):
        """Test that _summarize_decisions handles empty list."""
        summary = MemoryCompressor._summarize_decisions([])
        assert summary == "无历史决策"

    def test_summarize_decisions_does_not_extract_thinking(self):
        """Test that _summarize_decisions does NOT extract thinking process."""
        decisions = [
            {
                "step": 1,
                "current_step_thoughts": "I think the error is...",
                "actions": [{"tool": "run"}],
                "stop_reason": "continue",
            },
        ]

        summary = MemoryCompressor._summarize_decisions(decisions)

        # ✅ Verify thinking process is NOT in summary
        assert "current_step_thoughts" not in summary
        assert "I think the error is" not in summary


class TestDeduplicationLogic:
    """Test that deduplication uses current_step_thoughts."""

    def test_get_decision_signature_uses_current_step_thoughts(self):
        """Test that _get_decision_signature uses current_step_thoughts."""
        decision = {
            "step": 5,
            "current_step_thoughts": "Test thinking",
            "actions": [{"tool": "run"}],
            "stop_reason": "continue",
        }

        signature = MemoryCompressor._get_decision_signature(decision)

        # ✅ Verify signature uses current_step_thoughts
        assert "Test thinking" in signature
        assert "5" in signature
        assert "continue" in signature

    def test_get_decision_signature_backward_compatible(self):
        """Test that _get_decision_signature is backward compatible with thought_summary."""
        decision = {
            "step": 5,
            "thought_summary": "Old format thinking",  # Old field name
            "actions": [{"tool": "run"}],
            "stop_reason": "continue",
        }

        signature = MemoryCompressor._get_decision_signature(decision)

        # ✅ Verify signature uses thought_summary as fallback
        assert "Old format thinking" in signature

    def test_calculate_similarity_uses_current_step_thoughts(self):
        """Test that _calculate_similarity uses current_step_thoughts."""
        decision1 = {
            "current_step_thoughts": "I need to fix the error",
            "actions": [{"tool": "run"}],
        }
        decision2 = {
            "current_step_thoughts": "I need to fix the error",
            "actions": [{"tool": "run"}],
        }

        similarity = MemoryCompressor._calculate_similarity(decision1, decision2)

        # ✅ Verify similarity calculation uses current_step_thoughts
        assert similarity > 0.8  # Should be high similarity

    def test_calculate_similarity_backward_compatible(self):
        """Test that _calculate_similarity is backward compatible."""
        decision1 = {
            "thought_summary": "Old thinking",  # Old field name
            "actions": [{"tool": "run"}],
        }
        decision2 = {
            "thought_summary": "Old thinking",
            "actions": [{"tool": "run"}],
        }

        similarity = MemoryCompressor._calculate_similarity(decision1, decision2)

        # ✅ Verify similarity calculation works with old field name
        assert similarity > 0.8


class TestCompressionIntegration:
    """Integration tests for compression flow."""

    def test_compress_decisions_uses_improved_summarize(self):
        """Test that _compress_decisions uses improved _summarize_decisions."""
        state = AgentState(step=10)
        state.memory.decisions = [
            {
                "step": i,
                "actions": [{"tool": "run"}],
                "stop_reason": "continue" if i % 2 == 0 else "done",
                "verification_success": i % 3 == 0,
            }
            for i in range(8)  # 8 decisions, will trigger compression (keep 5)
        ]

        MemoryCompressor._compress_decisions(state, keep_recent=5)

        # Verify compression happened
        assert len(state.memory.decisions) == 5  # Kept 5 recent

        # Verify learnings contains improved summary
        assert len(state.memory.learnings) > 0
        learning = state.memory.learnings[-1]
        
        # ✅ Verify improved summary contains key facts
        assert "历史" in learning
        assert "停止原因分布" in learning or "验证结果" in learning or "常用工具" in learning


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
