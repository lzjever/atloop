"""Memory compressor for preventing unbounded growth."""

import json
import logging
from difflib import SequenceMatcher
from typing import Any, Dict, List

from atloop.memory.state import AgentState

logger = logging.getLogger(__name__)


class MemoryCompressor:
    """Compress old memory to prevent unbounded growth."""

    # Default configuration (will be overridden by config if provided)
    # These are kept for backward compatibility
    ATTEMPTS_KEEP_RECENT = 10
    DECISIONS_KEEP_RECENT = 5
    IMPORTANT_DECISIONS_KEEP = 20
    MILESTONES_KEEP = 20
    LEARNINGS_KEEP = 10

    @staticmethod
    def compress_if_needed(state: AgentState, memory_config=None, llm_client=None) -> bool:
        """
        Compress memory if it exceeds limits.

        Phase 4: Enhanced with LLM compression and deduplication.

        Args:
            state: Agent state
            memory_config: Optional MemoryConfig instance (if None, uses defaults)
            llm_client: Optional LLMClient for LLM compression (if None, LLM compression is skipped)

        Returns:
            True if compression was performed, False otherwise
        """
        # Use config values if provided, otherwise use defaults
        if memory_config:
            attempts_keep = memory_config.attempts_keep_recent
            decisions_keep = memory_config.decisions_keep_recent
            important_decisions_keep = memory_config.important_decisions_keep
            milestones_keep = memory_config.milestones_keep
            learnings_keep = memory_config.learnings_keep
        else:
            attempts_keep = MemoryCompressor.ATTEMPTS_KEEP_RECENT
            decisions_keep = MemoryCompressor.DECISIONS_KEEP_RECENT
            important_decisions_keep = MemoryCompressor.IMPORTANT_DECISIONS_KEEP
            milestones_keep = MemoryCompressor.MILESTONES_KEEP
            learnings_keep = MemoryCompressor.LEARNINGS_KEEP

        compressed = False

        # 1. Based-rule compression (existing logic)
        # Compress attempts
        if len(state.memory.attempts) > attempts_keep:
            MemoryCompressor._compress_attempts(state, attempts_keep)
            compressed = True

        # Compress decisions
        if len(state.memory.decisions) > decisions_keep:
            MemoryCompressor._compress_decisions(state, decisions_keep)
            compressed = True

        # Trim important_decisions (keep most recent)
        if len(state.memory.important_decisions) > important_decisions_keep:
            state.memory.important_decisions = state.memory.important_decisions[
                -important_decisions_keep:
            ]
            logger.info(
                f"[MemoryCompressor] 修剪 important_decisions 到 {important_decisions_keep} 个"
            )
            compressed = True

        # Trim milestones (keep most recent)
        if len(state.memory.milestones) > milestones_keep:
            state.memory.milestones = state.memory.milestones[-milestones_keep:]
            logger.info(f"[MemoryCompressor] 修剪 milestones 到 {milestones_keep} 个")
            compressed = True

        # Trim learnings (keep most recent)
        if len(state.memory.learnings) > learnings_keep:
            state.memory.learnings = state.memory.learnings[-learnings_keep:]
            logger.info(f"[MemoryCompressor] 修剪 learnings 到 {learnings_keep} 个")
            compressed = True

        # Phase 4: 2. LLM compression (if enabled and threshold exceeded)
        if memory_config and memory_config.llm_compression_enabled and llm_client:
            try:
                # Estimate memory size using new interface
                memory_context = state.memory.get_formatted_context(
                    state=state,
                    max_length=999999,
                )
                memory_size = len(memory_context)

                if memory_size > memory_config.llm_compression_threshold:
                    logger.info(
                        f"[MemoryCompressor] Memory size ({memory_size} chars) exceeds LLM compression threshold ({memory_config.llm_compression_threshold}), triggering LLM compression"
                    )
                    MemoryCompressor._compress_with_llm(state, memory_config, llm_client)
                    compressed = True
            except Exception as e:
                logger.warning(
                    f"[MemoryCompressor] LLM compression failed: {e}, continuing with rule-based compression only"
                )

        # Phase 4: 3. Deduplication (if enabled)
        if memory_config and memory_config.deduplication_enabled:
            try:
                if MemoryCompressor._deduplicate_memory(state, memory_config):
                    compressed = True
            except Exception as e:
                logger.warning(
                    f"[MemoryCompressor] Deduplication failed: {e}, continuing without deduplication"
                )

        # Phase 5: Compress modified files content (handled in AgentLoop._compress_modified_files_if_needed)
        # This is called automatically after each file modification, so we don't need to do it here

        return compressed

    @staticmethod
    def _compress_attempts(state: AgentState, keep_recent: int = None) -> None:
        """Compress old attempts, keeping only recent ones."""
        if keep_recent is None:
            keep_recent = MemoryCompressor.ATTEMPTS_KEEP_RECENT
        if len(state.memory.attempts) <= keep_recent:
            return

        recent = state.memory.attempts[-keep_recent:]
        old = state.memory.attempts[:-keep_recent]

        # Generate summary of old attempts
        summary = MemoryCompressor._summarize_attempts(old)

        # Create compressed record
        compressed_record = {
            "step": 0,
            "type": "compressed",
            "summary": summary,
            "original_count": len(old),
            "compressed_at_step": state.step,
            "files": [],  # No files in compressed record
            "success": None,  # Mixed results
            "results": [],
        }

        # Replace with compressed + recent
        state.memory.attempts = [compressed_record] + recent
        logger.info(
            f"[MemoryCompressor] 压缩了 {len(old)} 个旧 attempts，保留 {len(recent)} 个最近的"
        )

    @staticmethod
    def _compress_decisions(state: AgentState, keep_recent: int = None) -> None:
        """Compress old decisions, keeping only recent ones."""
        if keep_recent is None:
            keep_recent = MemoryCompressor.DECISIONS_KEEP_RECENT
        if len(state.memory.decisions) <= keep_recent:
            return

        recent = state.memory.decisions[-keep_recent:]
        old = state.memory.decisions[:-keep_recent]

        # Generate summary of old decisions
        summary = MemoryCompressor._summarize_decisions(old)

        # Add summary to learnings
        learning_entry = f"[Step {state.step}] 历史决策总结: {summary}"
        state.memory.learnings.append(learning_entry)

        # Keep only recent decisions
        state.memory.decisions = recent
        logger.info(
            f"[MemoryCompressor] 压缩了 {len(old)} 个旧 decisions，保留 {len(recent)} 个最近的"
        )

    @staticmethod
    def _summarize_attempts(attempts: List[Dict[str, Any]]) -> str:
        """Summarize a list of attempts."""
        if not attempts:
            return "无历史尝试"

        total = len(attempts)
        successful = sum(1 for a in attempts if a.get("success", False))
        files_modified = set()
        tools_used = set()

        for a in attempts:
            files_modified.update(a.get("files", []))
            for result in a.get("results", []):
                tools_used.add(result.get("tool", "unknown"))

        return (
            f"历史 {total} 次尝试：成功 {successful} 次，"
            f"修改了 {len(files_modified)} 个文件，使用了 {len(tools_used)} 种工具"
        )

    @staticmethod
    def _summarize_decisions(decisions: List[Dict[str, Any]]) -> str:
        """
        Summarize a list of decisions, extracting key factual information.
        
        NOTE: Only extracts factual information, NOT LLM's thinking process.
        """
        if not decisions:
            return "无历史决策"

        total = len(decisions)
        total_actions = sum(len(d.get("actions", [])) for d in decisions)
        
        # ✓ 改进：提取关键事实信息
        key_facts = []
        
        # 统计 stop_reason 分布
        stop_reasons = {}
        for d in decisions:
            reason = d.get("stop_reason", "unknown")
            stop_reasons[reason] = stop_reasons.get(reason, 0) + 1
        
        # 统计验证结果
        verification_results = {
            "success": 0,
            "failure": 0,
            "unknown": 0,
        }
        for d in decisions:
            verification = d.get("verification_success")
            if verification is True:
                verification_results["success"] += 1
            elif verification is False:
                verification_results["failure"] += 1
            else:
                verification_results["unknown"] += 1
        
        # 统计常用工具
        tools_used = {}
        for d in decisions:
            actions = d.get("actions", [])
            for action in actions:
                if isinstance(action, dict):
                    tool = action.get("tool", "unknown")
                    tools_used[tool] = tools_used.get(tool, 0) + 1
        
        # 构建摘要
        summary_parts = [f"历史 {total} 个决策，共执行了 {total_actions} 个动作"]
        
        if stop_reasons:
            reasons_str = ", ".join([f"{k}:{v}" for k, v in stop_reasons.items()])
            summary_parts.append(f"停止原因分布: {reasons_str}")
        
        if verification_results["success"] > 0 or verification_results["failure"] > 0:
            summary_parts.append(
                f"验证结果: 成功 {verification_results['success']} 次, "
                f"失败 {verification_results['failure']} 次"
            )
        
        if tools_used:
            top_tools = sorted(tools_used.items(), key=lambda x: x[1], reverse=True)[:3]
            tools_str = ", ".join([f"{tool}({count})" for tool, count in top_tools])
            summary_parts.append(f"常用工具: {tools_str}")
        
        return "。".join(summary_parts)

    # Phase 4: LLM Compression

    @staticmethod
    def _compress_with_llm(state: AgentState, memory_config, llm_client) -> None:
        """
        Use LLM to compress old memory history.

        Args:
            state: Agent state
            memory_config: MemoryConfig instance
            llm_client: LLMClient instance for compression
        """
        # Keep recent N decisions (configurable, default 10)
        recent_count = 10
        if len(state.memory.decisions) <= recent_count:
            return

        old_decisions = state.memory.decisions[:-recent_count]
        recent_decisions = state.memory.decisions[-recent_count:]

        if not old_decisions:
            return

        logger.info(f"[MemoryCompressor] 开始 LLM 压缩: {len(old_decisions)} 个旧决策")

        try:
            # ✓ 改进：过滤掉不应反馈给 LLM 的字段
            # 只保留事实信息，排除 LLM 的主观内容（current_step_thoughts, plan, llm_output）
            filtered_decisions = []
            for decision in old_decisions:
                # 只保留事实信息，排除 LLM 的主观内容
                filtered = {
                    "step": decision.get("step"),
                    "stop_reason": decision.get("stop_reason"),
                    "actions_count": decision.get("actions_count"),
                    "verification_success": decision.get("verification_success"),
                    "actions": decision.get("actions", []),  # 动作列表是事实
                    # ❌ 明确排除以下字段（防止反馈循环）：
                    # - current_step_thoughts (LLM 思考过程)
                    # - plan (LLM 计划，已在 memory.plan 中)
                    # - llm_output (完整 LLM 输出)
                }
                filtered_decisions.append(filtered)

            # Build compression prompt
            # Limit the data size to avoid exceeding LLM context
            max_data_size = 50000  # 50KB of decision data
            decisions_json = json.dumps(filtered_decisions, ensure_ascii=False, indent=2)
            if len(decisions_json) > max_data_size:
                # Truncate if too large
                decisions_json = decisions_json[:max_data_size] + "\n... [数据已截断]"

            compression_prompt = f"""请将以下历史决策压缩为简洁的摘要，保留关键信息：

{decisions_json}

要求：
1. 保留任务目标、关键决策、重要里程碑
2. 移除重复和冗余信息
3. 保留工具执行结果的关键信息（错误、成功状态）
4. 摘要长度控制在 {memory_config.llm_compression_target // 2} 字符以内
5. 使用结构化格式（Markdown）
6. ⚠️ **重要**：只提取事实信息（工具、动作、结果），不要包含任何 LLM 的思考过程、假设或推理

注意：这些是历史决策的事实信息（工具、动作、结果），不包含 LLM 的思考过程。

输出格式：
## 压缩摘要
[摘要内容 - 只包含事实信息]

## 关键信息
- 任务目标：...
- 关键决策：...
- 重要里程碑：..."""

            # Call LLM for compression
            # Use a simple completion call (not plan_and_act)
            # lexilux 2.1.0: complete(messages, *, system=..., params=ChatParams, **kwargs)
            from lexilux import ChatParams

            chat_params = ChatParams(temperature=0.3, max_tokens=4000)

            # Use LLM client's chat directly
            result = llm_client.chat.complete(
                compression_prompt,
                system="你是一个记忆压缩专家。请将历史决策压缩为简洁的摘要，保留关键信息。注意：只处理事实信息，不包含 LLM 的思考过程。",
                params=chat_params,
            )

            compressed_summary = result.text

            # Create compressed record
            compressed_record = {
                "type": "llm_compressed",
                "summary": compressed_summary,
                "original_count": len(old_decisions),
                "compressed_at_step": state.step,
                "compression_target": memory_config.llm_compression_target,
            }

            # Replace with compressed + recent
            state.memory.decisions = [compressed_record] + recent_decisions
            logger.info(
                f"[MemoryCompressor] ✓ LLM 压缩完成: {len(old_decisions)} 个决策压缩为摘要，保留 {len(recent_decisions)} 个最近的"
            )

        except Exception as e:
            logger.error(f"[MemoryCompressor] LLM 压缩失败: {e}，回退到基于规则的压缩")
            # Fallback to rule-based compression
            MemoryCompressor._compress_decisions(state, recent_count)

    # Phase 4: Deduplication

    @staticmethod
    def _deduplicate_memory(state: AgentState, memory_config) -> bool:
        """
        Deduplicate similar memory items.

        Args:
            state: Agent state
            memory_config: MemoryConfig instance

        Returns:
            True if deduplication was performed, False otherwise
        """
        deduplicated = False

        # Deduplicate decisions
        if len(state.memory.decisions) > 1:
            unique_decisions = []
            seen_signatures = set()

            for decision in state.memory.decisions:
                signature = MemoryCompressor._get_decision_signature(decision)
                if signature not in seen_signatures:
                    seen_signatures.add(signature)
                    unique_decisions.append(decision)
                else:
                    # Check similarity with existing decisions
                    similar = False
                    for existing in unique_decisions:
                        similarity = MemoryCompressor._calculate_similarity(decision, existing)
                        if similarity >= memory_config.deduplication_similarity_threshold:
                            # Merge similar decisions (keep the more recent one)
                            similar = True
                            break

                    if not similar:
                        # Not similar enough, keep it
                        unique_decisions.append(decision)
                    else:
                        deduplicated = True

            if deduplicated:
                original_count = len(state.memory.decisions)
                state.memory.decisions = unique_decisions
                logger.info(
                    f"[MemoryCompressor] 去重完成: {original_count} 个决策 -> {len(unique_decisions)} 个唯一决策"
                )

        # Deduplicate attempts (similar logic)
        if len(state.memory.attempts) > 1:
            unique_attempts = []
            seen_attempt_signatures = set()

            for attempt in state.memory.attempts:
                # Skip compressed records
                if attempt.get("type") == "compressed" or attempt.get("type") == "llm_compressed":
                    unique_attempts.append(attempt)
                    continue

                signature = MemoryCompressor._get_attempt_signature(attempt)
                if signature not in seen_attempt_signatures:
                    seen_attempt_signatures.add(signature)
                    unique_attempts.append(attempt)
                else:
                    # Check similarity
                    similar = False
                    for existing in unique_attempts:
                        if existing.get("type") in ["compressed", "llm_compressed"]:
                            continue
                        similarity = MemoryCompressor._calculate_attempt_similarity(
                            attempt, existing
                        )
                        if similarity >= memory_config.deduplication_similarity_threshold:
                            similar = True
                            break

                    if not similar:
                        unique_attempts.append(attempt)
                    else:
                        deduplicated = True

            if deduplicated:
                original_count = len(state.memory.attempts)
                state.memory.attempts = unique_attempts
                logger.info(
                    f"[MemoryCompressor] 去重完成: {original_count} 个尝试 -> {len(unique_attempts)} 个唯一尝试"
                )

        return deduplicated

    @staticmethod
    def _get_decision_signature(decision: Dict[str, Any]) -> str:
        """Get a signature for a decision (for deduplication)."""
        # Create signature from key fields
        step = decision.get("step", "")
        # ✓ 更新：使用 current_step_thoughts 而不是 thought_summary
        # 支持向后兼容：如果 current_step_thoughts 不存在，尝试 thought_summary
        thought = (
            decision.get("current_step_thoughts", "") or 
            decision.get("thought_summary", "")  # 向后兼容
        )[:50]  # First 50 chars
        actions_count = len(decision.get("actions", []))
        stop_reason = decision.get("stop_reason", "")

        return f"{step}:{thought}:{actions_count}:{stop_reason}"

    @staticmethod
    def _get_attempt_signature(attempt: Dict[str, Any]) -> str:
        """Get a signature for an attempt (for deduplication)."""
        step = attempt.get("step", "")
        files = sorted(attempt.get("files", []))
        files_str = ",".join(files[:5])  # First 5 files
        success = attempt.get("success", False)

        return f"{step}:{files_str}:{success}"

    @staticmethod
    def _calculate_similarity(decision1: Dict[str, Any], decision2: Dict[str, Any]) -> float:
        """Calculate similarity between two decisions (0.0-1.0)."""
        # Compare key fields
        # ✓ 更新：使用 current_step_thoughts 而不是 thought_summary
        # 支持向后兼容：如果 current_step_thoughts 不存在，尝试 thought_summary
        thought1 = str(
            decision1.get("current_step_thoughts", "") or 
            decision1.get("thought_summary", "")  # 向后兼容
        )
        thought2 = str(
            decision2.get("current_step_thoughts", "") or 
            decision2.get("thought_summary", "")  # 向后兼容
        )

        actions1 = decision1.get("actions", [])
        actions2 = decision2.get("actions", [])

        # Calculate text similarity for current_step_thoughts
        if thought1 and thought2:
            similarity = SequenceMatcher(None, thought1, thought2).ratio()
        else:
            similarity = 0.0

        # Boost similarity if actions are similar
        if actions1 and actions2:
            # Simple comparison: same number of actions and same tools
            tools1 = [a.get("tool", "") for a in actions1 if isinstance(a, dict)]
            tools2 = [a.get("tool", "") for a in actions2 if isinstance(a, dict)]
            if tools1 == tools2:
                similarity = min(1.0, similarity + 0.2)

        return similarity

    @staticmethod
    def _calculate_attempt_similarity(attempt1: Dict[str, Any], attempt2: Dict[str, Any]) -> float:
        """Calculate similarity between two attempts (0.0-1.0)."""
        # Compare files modified
        files1 = set(attempt1.get("files", []))
        files2 = set(attempt2.get("files", []))

        if not files1 and not files2:
            return 1.0  # Both empty

        if not files1 or not files2:
            return 0.0

        # Jaccard similarity
        intersection = len(files1 & files2)
        union = len(files1 | files2)

        if union == 0:
            return 1.0

        return intersection / union
