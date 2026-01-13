"""Compression policy interface and implementations."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from atloop.memory.state import AgentState, Memory


class CompressionPolicy(ABC):
    """压缩策略接口"""

    @abstractmethod
    def compress(self, memory: "Memory", target_size: int) -> "Memory":
        """
        压缩 memory，返回压缩后的 memory。

        Args:
            memory: 原始 memory
            target_size: 目标大小（字符数，基于格式化后的字符串长度）

        Returns:
            压缩后的 memory（修改后的实例）

        Note:
            - 压缩策略应该修改 memory 的内部数据结构
            - 不应该修改 memory 的接口
        """
        pass

    @abstractmethod
    def estimate_size(self, memory: "Memory", state: "AgentState") -> int:
        """
        估算 memory 格式化后的大小。

        Args:
            memory: Memory 实例
            state: AgentState 实例（用于格式化）

        Returns:
            估算的字符数
        """
        pass


class RuleBasedCompressionPolicy(CompressionPolicy):
    """基于规则的压缩策略"""

    def __init__(
        self,
        tool_results_keep_recent: int = 10,
        decisions_keep_recent: int = 5,
        important_decisions_keep: int = 20,
        milestones_keep: int = 20,
        learnings_keep: int = 10,
    ):
        """
        初始化基于规则的压缩策略。

        Args:
            tool_results_keep_recent: 保留最近 N 个工具结果
            decisions_keep_recent: 保留最近 N 个决策
            important_decisions_keep: 保留 Top N 个重要决策
            milestones_keep: 保留 Top N 个里程碑
            learnings_keep: 保留 Top N 个经验
        """
        self.tool_results_keep_recent = tool_results_keep_recent
        self.decisions_keep_recent = decisions_keep_recent
        self.important_decisions_keep = important_decisions_keep
        self.milestones_keep = milestones_keep
        self.learnings_keep = learnings_keep

    def compress(self, memory: "Memory", target_size: int) -> "Memory":
        """
        基于规则的压缩。

        压缩策略：
        1. 保留最近 N 个工具结果，压缩旧的为摘要
        2. 保留最近 N 个决策，压缩旧的为摘要
        3. 修剪其他字段到 Top N
        """
        # 1. 压缩 tool_results_history
        if len(memory.tool_results_history) > self.tool_results_keep_recent:
            self._compress_tool_results_history(memory)

        # 2. 压缩 decisions
        if len(memory.decisions) > self.decisions_keep_recent:
            self._compress_decisions(memory)

        # 3. 修剪其他字段
        if len(memory.important_decisions) > self.important_decisions_keep:
            memory.important_decisions = memory.important_decisions[
                -self.important_decisions_keep :
            ]

        if len(memory.milestones) > self.milestones_keep:
            memory.milestones = memory.milestones[-self.milestones_keep :]

        if len(memory.learnings) > self.learnings_keep:
            memory.learnings = memory.learnings[-self.learnings_keep :]

        return memory

    def estimate_size(self, memory: "Memory", state: "AgentState") -> int:
        """估算大小"""
        from atloop.memory.formatter import MemoryFormatter

        formatter = MemoryFormatter()
        formatted = formatter.format(state)
        return len(formatted)

    def _compress_tool_results_history(self, memory: "Memory") -> None:
        """压缩 tool_results_history"""
        if len(memory.tool_results_history) <= self.tool_results_keep_recent:
            return

        recent = memory.tool_results_history[-self.tool_results_keep_recent :]
        old = memory.tool_results_history[: -self.tool_results_keep_recent]

        # 生成摘要
        summary = self._summarize_tool_results(old)

        # 创建压缩记录
        compressed = {
            "type": "compressed",
            "summary": summary,
            "original_count": len(old),
            "compressed_at_step": getattr(memory, "_current_step", 0),
        }

        # 替换
        memory.tool_results_history = [compressed] + recent

    def _compress_decisions(self, memory: "Memory") -> None:
        """压缩 decisions"""
        if len(memory.decisions) <= self.decisions_keep_recent:
            return

        recent = memory.decisions[-self.decisions_keep_recent :]
        old = memory.decisions[: -self.decisions_keep_recent]

        # 生成摘要
        summary = self._summarize_decisions(old)

        # 添加到 learnings
        learning_entry = f"[Compressed] Historical decisions summary: {summary}"
        memory.learnings.append(learning_entry)

        # 保留最近的
        memory.decisions = recent

    def _summarize_tool_results(self, tool_results: list) -> str:
        """生成工具结果摘要"""
        if not tool_results:
            return "No historical tool results"

        total = len(tool_results)
        successful = sum(1 for r in tool_results if r.get("result", {}).get("ok", False))
        tools_used = set(r.get("tool", "unknown") for r in tool_results)

        return (
            f"Historical {total} tool executions: {successful} successful, "
            f"used {len(tools_used)} different tools: {', '.join(list(tools_used)[:5])}"
        )

    def _summarize_decisions(self, decisions: list) -> str:
        """生成决策摘要"""
        if not decisions:
            return "No historical decisions"

        total = len(decisions)
        total_actions = sum(len(d.get("actions", [])) for d in decisions)

        # 统计 stop_reason 分布
        stop_reasons = {}
        for d in decisions:
            reason = d.get("stop_reason", "unknown")
            stop_reasons[reason] = stop_reasons.get(reason, 0) + 1

        summary_parts = [f"Historical {total} decisions, {total_actions} total actions"]
        if stop_reasons:
            reasons_str = ", ".join([f"{k}:{v}" for k, v in stop_reasons.items()])
            summary_parts.append(f"Stop reasons: {reasons_str}")

        return ". ".join(summary_parts)


class ImportanceBasedCompressionPolicy(CompressionPolicy):
    """基于重要性的压缩策略"""

    def __init__(
        self,
        scorer: Optional[Any] = None,
        importance_threshold: float = 0.3,
    ):
        """
        初始化基于重要性的压缩策略。

        Args:
            scorer: ImportanceScorer 实例（可选，如果为None则创建默认实例）
            importance_threshold: 重要性阈值，低于此分数的条目将被压缩
        """
        try:
            from atloop.memory.scorer import ImportanceScorer

            self.scorer = scorer or ImportanceScorer()
        except ImportError:
            self.scorer = None
        self.importance_threshold = importance_threshold

    def compress(self, memory: "Memory", target_size: int) -> "Memory":
        """
        基于重要性的压缩。

        压缩策略：
        1. 计算每个工具结果的重要性分数
        2. 保留重要的，压缩不重要的
        """
        # 1. 压缩 tool_results_history（基于重要性）
        if len(memory.tool_results_history) > 10:
            self._compress_tool_results_by_importance(memory)

        # 2. 压缩 decisions（使用规则压缩，因为重要性计算复杂）
        if len(memory.decisions) > 5:
            # Use rule-based compression for decisions
            rule_policy = RuleBasedCompressionPolicy(decisions_keep_recent=5)
            rule_policy._compress_decisions(memory)

        # 3. 修剪其他字段（按重要性排序）
        if len(memory.important_decisions) > 20:
            # Sort by importance and keep top N
            sorted_decisions = sorted(
                memory.important_decisions,
                key=lambda x: x.get("importance", 0),
                reverse=True,
            )
            memory.important_decisions = sorted_decisions[:20]

        if len(memory.milestones) > 20:
            sorted_milestones = sorted(
                memory.milestones,
                key=lambda x: x.get("importance", 0),
                reverse=True,
            )
            memory.milestones = sorted_milestones[:20]

        if len(memory.learnings) > 10:
            memory.learnings = memory.learnings[-10:]

        return memory

    def estimate_size(self, memory: "Memory", state: "AgentState") -> int:
        """估算大小"""
        from atloop.memory.formatter import MemoryFormatter

        formatter = MemoryFormatter()
        formatted = formatter.format(state)
        return len(formatted)

    def _compress_tool_results_by_importance(self, memory: "Memory") -> None:
        """基于重要性压缩 tool_results_history"""
        if len(memory.tool_results_history) <= 10:
            return

        # 计算每个工具结果的重要性
        scored_results = []
        for result in memory.tool_results_history:
            # Skip compressed records
            if isinstance(result, dict) and result.get("type") == "compressed":
                scored_results.append((1.0, result))  # Keep compressed records
                continue

            score = self._calculate_importance(result)
            scored_results.append((score, result))

        # 排序
        scored_results.sort(key=lambda x: x[0], reverse=True)

        # 保留重要的（top 10 + 所有超过阈值的）
        important = []
        less_important = []

        for score, result in scored_results:
            if score >= self.importance_threshold or len(important) < 10:
                important.append(result)
            else:
                less_important.append(result)

        # 压缩不重要的
        if less_important:
            summary = self._summarize_tool_results(less_important)
            compressed = {
                "type": "compressed",
                "summary": summary,
                "original_count": len(less_important),
            }
            memory.tool_results_history = [compressed] + important
        else:
            memory.tool_results_history = important

    def _calculate_importance(self, result: Dict[str, Any]) -> float:
        """
        计算工具结果的重要性。

        Args:
            result: 工具结果字典

        Returns:
            重要性分数（0.0-1.0）
        """
        score = 0.0

        # 1. 错误结果更重要
        result_data = result.get("result", {})
        if not result_data.get("ok", True):
            score += 1.0

        # 2. 文件修改更重要
        tool = result.get("tool", "")
        if tool in ["write_file", "edit_file", "append_file"]:
            score += 0.5

        # 3. 最近的更重要（需要知道当前step，这里简化处理）
        step = result.get("step", 0)
        # Assume current step is step + 10 (simplified)
        recency = max(0, 1.0 - step / 20.0)
        score += recency * 0.3

        # 4. 有占位符的更重要（表示是文件内容）
        if result.get("placeholder"):
            score += 0.2

        return min(1.0, score)

    def _summarize_tool_results(self, tool_results: list) -> str:
        """生成工具结果摘要（复用RuleBasedCompressionPolicy的逻辑）"""
        rule_policy = RuleBasedCompressionPolicy()
        return rule_policy._summarize_tool_results(tool_results)
