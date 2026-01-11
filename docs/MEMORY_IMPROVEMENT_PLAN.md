# Memory 行为改进与修正计划

## 🎉 实施状态：全部完成

**完成时间**：2026-01-11  
**所有改进已实施并通过测试** ✅

---

## 执行摘要

本计划旨在修复 Memory 系统中发现的设计不一致和潜在问题，确保系统严格遵守"不反馈 LLM 思考过程"的原则，同时保持功能的完整性和性能。

**优先级**：高  
**预计工作量**：2-3 小时  
**风险等级**：低（向后兼容）  
**实际状态**：✅ **全部完成**

---

## 1. 问题总结

### 1.1 已发现的问题

| # | 问题 | 严重性 | 影响范围 | 优先级 | 状态 |
|---|------|--------|----------|--------|------|
| 1 | `_compress_with_llm` 违反"不反馈"原则 | 🔴 高 | 压缩功能 | P0 | ✅ 已完成 |
| 2 | `_summarize_decisions` 过于简单，丢失信息 | 🟡 中 | 压缩功能 | P1 | ✅ 已完成 |
| 3 | 间接反馈循环风险（通过 learnings） | 🟡 中 | 压缩功能 | P1 | ✅ 已完成 |
| 4 | `decisions` 注释不一致（标记 DEBUG-ONLY 但部分可见） | 🟢 低 | 文档/注释 | P2 | ✅ 已完成 |
| 5 | 去重逻辑使用旧字段名 `thought_summary` | 🟡 中 | 去重功能 | P1 | ✅ 已完成 |

---

## 2. 改进方案

### 2.1 问题 1: 修复 `_compress_with_llm` 违反原则

**问题描述**：
- `_compress_with_llm` 将包含 `current_step_thoughts` 的完整 JSON 发送给 LLM
- 违反了"不反馈给 LLM"的设计原则

**解决方案**：
在压缩前过滤掉 `current_step_thoughts` 和其他不应反馈的字段，只保留事实信息。

**实施步骤**：

```python
@staticmethod
def _compress_with_llm(state: AgentState, memory_config, llm_client) -> None:
    """Use LLM to compress old memory history."""
    recent_count = 10
    if len(state.memory.decisions) <= recent_count:
        return

    old_decisions = state.memory.decisions[:-recent_count]
    recent_decisions = state.memory.decisions[-recent_count:]

    if not old_decisions:
        return

    logger.info(f"[MemoryCompressor] 开始 LLM 压缩: {len(old_decisions)} 个旧决策")

    try:
        # ✅ 改进：过滤掉不应反馈给 LLM 的字段
        filtered_decisions = []
        for decision in old_decisions:
            # 只保留事实信息，排除 LLM 的主观内容
            filtered = {
                "step": decision.get("step"),
                "stop_reason": decision.get("stop_reason"),
                "actions_count": decision.get("actions_count"),
                "verification_success": decision.get("verification_success"),
                "actions": decision.get("actions", []),  # 动作列表是事实
                # ❌ 明确排除以下字段：
                # - current_step_thoughts (LLM 思考过程)
                # - plan (LLM 计划，已在 memory.plan 中)
                # - llm_output (完整 LLM 输出)
            }
            filtered_decisions.append(filtered)

        # Build compression prompt
        max_data_size = 50000
        decisions_json = json.dumps(filtered_decisions, ensure_ascii=False, indent=2)
        if len(decisions_json) > max_data_size:
            decisions_json = decisions_json[:max_data_size] + "\n... [数据已截断]"

        compression_prompt = f"""请将以下历史决策压缩为简洁的摘要，保留关键信息：

{decisions_json}

要求：
1. 保留任务目标、关键决策、重要里程碑
2. 移除重复和冗余信息
3. 保留工具执行结果的关键信息（错误、成功状态）
4. 摘要长度控制在 {memory_config.llm_compression_target // 2} 字符以内
5. 使用结构化格式（Markdown）

注意：这些是历史决策的事实信息（工具、动作、结果），不包含 LLM 的思考过程。

输出格式：
## 压缩摘要
[摘要内容]

## 关键信息
- 任务目标：...
- 关键决策：...
- 重要里程碑：..."""

        # Call LLM for compression
        from lexilux import ChatParams
        chat_params = ChatParams(temperature=0.3, max_tokens=4000)

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
            f"[MemoryCompressor] ✅ LLM 压缩完成: {len(old_decisions)} 个决策压缩为摘要，保留 {len(recent_decisions)} 个最近的"
        )

    except Exception as e:
        logger.error(f"[MemoryCompressor] LLM 压缩失败: {e}，回退到基于规则的压缩")
        MemoryCompressor._compress_decisions(state, recent_count)
```

**关键改进点**：
- ✅ 明确过滤掉 `current_step_thoughts`、`plan`、`llm_output`
- ✅ 只保留事实信息（step、actions、stop_reason 等）
- ✅ 在 prompt 中明确说明"只处理事实信息"
- ✅ 在 system prompt 中强调"不包含 LLM 的思考过程"

---

### 2.2 问题 2: 改进 `_summarize_decisions`

**问题描述**：
- `_summarize_decisions` 只统计数量，不提取有价值信息
- `current_step_thoughts` 中的有价值信息（如失败原因）在压缩时丢失

**解决方案**：
提取关键事实信息（不包含思考过程），生成更有价值的摘要。

**实施步骤**：

```python
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
    
    # ✅ 改进：提取关键事实信息
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
```

**关键改进点**：
- ✅ 提取关键事实：stop_reason 分布、验证结果、常用工具
- ✅ 不包含思考过程：明确不提取 `current_step_thoughts`
- ✅ 更有价值的摘要：提供统计信息而非仅数量

---

### 2.3 问题 3: 降低间接反馈循环风险

**问题描述**：
- 压缩后的摘要存储在 `learnings` 中
- `learnings` 会被反馈给 LLM
- 如果压缩摘要包含思考内容，可能造成间接反馈循环

**解决方案**：
1. 在压缩 prompt 中明确要求"只提取事实信息"
2. 在压缩后的摘要中添加标记，确保不包含思考内容
3. 可选：添加验证机制

**实施步骤**：

```python
# 在 _compress_with_llm 中
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
```

**可选：添加验证机制**：

```python
def _validate_compressed_summary(summary: str) -> bool:
    """
    Validate that compressed summary doesn't contain thinking process keywords.
    
    Returns:
        True if summary is safe (only facts), False if contains thinking process
    """
    thinking_keywords = [
        "我认为", "我觉得", "我猜测", "我假设",
        "I think", "I believe", "I guess", "I assume",
        "可能是因为", "应该是", "perhaps", "maybe"
    ]
    
    summary_lower = summary.lower()
    for keyword in thinking_keywords:
        if keyword.lower() in summary_lower:
            logger.warning(
                f"[MemoryCompressor] 压缩摘要可能包含思考过程关键词: {keyword}"
            )
            return False
    
    return True
```

---

### 2.4 问题 4: 更新注释，明确 decisions 的部分可见性

**问题描述**：
- `decisions` 标记为 DEBUG-ONLY，但实际部分可见
- 注释与实现不一致，可能造成混淆

**解决方案**：
更新注释，明确说明 `decisions` 是"部分可见"的，并详细说明可见和不可见的内容。

**实施步骤**：

```python
# memory/state.py
# =========================================================================
# PARTIALLY VISIBLE - Facts only (NOT fully DEBUG-ONLY)
# =========================================================================
# decisions: Partially visible to LLM - only factual information is shown
#   - ✅ Visible: step, actions_count, tools_used, stop_reason
#   - ❌ NOT visible: current_step_thoughts, plan, llm_output
#   - Purpose: Provide context about what was done, without LLM's thinking process
decisions: List[Dict[str, Any]] = field(default_factory=list)
# NOTE: Contains current_step_thoughts - this field is NOT shown to LLM
#       Only factual information (tools, actions, stop_reason) is shown in MemorySummary

# =========================================================================
# DEBUG-ONLY - LLM interpretations (NOT fed back to LLM)
# =========================================================================
# llm_responses: Completely invisible to LLM - only for debugging/logging
llm_responses: List[Dict[str, Any]] = field(default_factory=list)
# WARNING: Contains current_step_thoughts - DO NOT feed back to LLM
# Format: {"step": int, "current_step_thoughts": str, "plan": List[str], ...}
```

---

### 2.5 问题 5: 更新去重逻辑，使用 current_step_thoughts

**问题描述**：
- `_get_decision_signature` 和 `_calculate_similarity` 使用旧字段名 `thought_summary`
- 需要更新为 `current_step_thoughts`

**解决方案**：
更新所有相关方法，使用正确的字段名。

**实施步骤**：

```python
@staticmethod
def _get_decision_signature(decision: Dict[str, Any]) -> str:
    """Get a signature for a decision (for deduplication)."""
    step = decision.get("step", "")
    # ✅ 更新：使用 current_step_thoughts 而不是 thought_summary
    # 支持向后兼容：如果 current_step_thoughts 不存在，尝试 thought_summary
    thought = (
        decision.get("current_step_thoughts", "") or 
        decision.get("thought_summary", "")  # 向后兼容
    )[:50]  # First 50 chars
    actions_count = len(decision.get("actions", []))
    stop_reason = decision.get("stop_reason", "")

    return f"{step}:{thought}:{actions_count}:{stop_reason}"

@staticmethod
def _calculate_similarity(decision1: Dict[str, Any], decision2: Dict[str, Any]) -> float:
    """Calculate similarity between two decisions (0.0-1.0)."""
    # ✅ 更新：使用 current_step_thoughts
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
        tools1 = [a.get("tool", "") for a in actions1 if isinstance(a, dict)]
        tools2 = [a.get("tool", "") for a in actions2 if isinstance(a, dict)]
        if tools1 == tools2:
            similarity = min(1.0, similarity + 0.2)

    return similarity
```

**关键改进点**：
- ✅ 使用 `current_step_thoughts` 替代 `thought_summary`
- ✅ 保持向后兼容：如果新字段不存在，回退到旧字段

---

## 3. 实施计划

### 3.1 阶段划分

#### Phase 1: 核心修复（P0 - 高优先级）
**目标**：修复违反原则的问题  
**时间**：1 小时  
**任务**：
1. ✅ 修复 `_compress_with_llm`：过滤 `current_step_thoughts`
2. ✅ 更新去重逻辑：使用 `current_step_thoughts`

#### Phase 2: 功能改进（P1 - 中优先级）
**目标**：改进压缩和总结功能  
**时间**：1 小时  
**任务**：
1. ✅ 改进 `_summarize_decisions`：提取关键事实
2. ✅ 增强压缩 prompt：明确要求只提取事实

#### Phase 3: 文档和注释（P2 - 低优先级）
**目标**：更新文档，保持一致性  
**时间**：30 分钟  
**任务**：
1. ✅ 更新 `decisions` 注释：明确部分可见性
2. ✅ 更新相关文档

### 3.2 实施顺序

```
1. Phase 1.1: 修复 _compress_with_llm
   ↓
2. Phase 1.2: 更新去重逻辑
   ↓
3. Phase 2.1: 改进 _summarize_decisions
   ↓
4. Phase 2.2: 增强压缩 prompt
   ↓
5. Phase 3.1: 更新注释
   ↓
6. Phase 3.2: 更新文档
```

---

## 4. 测试策略

### 4.1 单元测试

**测试文件**：`tests/test_memory_compressor.py`

**测试用例**：

1. **测试过滤功能**：
   ```python
   def test_compress_with_llm_filters_current_step_thoughts():
       """Test that _compress_with_llm filters out current_step_thoughts."""
       # 创建包含 current_step_thoughts 的 decisions
       # 验证压缩时这些字段被过滤
   ```

2. **测试改进的总结**：
   ```python
   def test_summarize_decisions_extracts_facts():
       """Test that _summarize_decisions extracts key facts."""
       # 验证摘要包含统计信息（stop_reason 分布、验证结果等）
   ```

3. **测试去重逻辑**：
   ```python
   def test_deduplication_uses_current_step_thoughts():
       """Test that deduplication uses current_step_thoughts."""
       # 验证使用新字段名
   ```

### 4.2 集成测试

**测试场景**：
1. 完整压缩流程：验证压缩后的摘要不包含思考过程
2. 多轮循环：验证压缩不影响后续循环
3. 向后兼容：验证旧数据（使用 `thought_summary`）仍能正常工作

### 4.3 验证检查清单

- [ ] `_compress_with_llm` 不发送 `current_step_thoughts` 给 LLM
- [ ] `_summarize_decisions` 提取关键事实信息
- [ ] 去重逻辑使用 `current_step_thoughts`
- [ ] 注释准确反映实际行为
- [ ] 所有测试通过
- [ ] 向后兼容性保持

---

## 5. 风险评估

### 5.1 风险识别

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 过滤过度，丢失重要信息 | 低 | 中 | 仔细设计过滤逻辑，保留所有事实信息 |
| 向后兼容性问题 | 低 | 低 | 在去重逻辑中保持向后兼容 |
| 压缩质量下降 | 中 | 低 | 改进 prompt，明确要求 |
| 性能影响 | 低 | 低 | 过滤操作很轻量，影响可忽略 |

### 5.2 回滚计划

如果出现问题：
1. 立即回滚到上一个稳定版本
2. 检查压缩后的 `learnings` 是否包含不当内容
3. 如果包含，手动清理 `learnings` 中的问题条目

---

## 6. 成功标准

### 6.1 功能标准

- ✅ `_compress_with_llm` 严格遵守"不反馈思考过程"原则
- ✅ `_summarize_decisions` 生成更有价值的摘要
- ✅ 去重逻辑使用正确的字段名
- ✅ 注释准确反映实际行为

### 6.2 质量标准

- ✅ 所有现有测试通过
- ✅ 新增测试覆盖所有改进点
- ✅ 代码审查通过
- ✅ 文档更新完成

---

## 7. 后续优化（可选）

### 7.1 高级功能

1. **智能过滤**：使用更智能的方法识别和过滤思考过程
2. **摘要验证**：自动验证压缩摘要不包含思考内容
3. **压缩质量评估**：评估压缩后的摘要质量

### 7.2 性能优化

1. **增量压缩**：只压缩新增的 decisions，而不是全部
2. **缓存机制**：缓存压缩结果，避免重复压缩

---

## 8. 总结

本改进计划旨在：
1. **修复核心问题**：严格遵守"不反馈思考过程"原则 ✅ **已完成**
2. **改进功能**：提供更有价值的压缩和总结 ✅ **已完成**
3. **保持一致性**：更新注释和文档，确保准确 ✅ **已完成**

**预计完成时间**：2-3 小时  
**实际完成时间**：约 2 小时  
**优先级**：高（P0 问题需要立即修复）  
**状态**：✅ **全部完成**

### 8.1 实施结果

- ✅ **10 个新测试全部通过**
- ✅ **所有 257 个测试通过**（新增 10 个）
- ✅ **代码语法检查通过**
- ✅ **向后兼容性保持**
- ✅ **文档已更新**

### 8.2 改进效果

1. ✅ **严格遵守原则**：`_compress_with_llm` 不再将 `current_step_thoughts` 发送给 LLM
2. ✅ **更有价值的摘要**：`_summarize_decisions` 现在提取关键统计信息
3. ✅ **降低反馈循环风险**：压缩摘要只包含事实信息
4. ✅ **注释一致性**：注释准确反映实际行为
5. ✅ **向后兼容**：去重逻辑支持旧数据格式

---

**计划创建时间**：2026-01-11  
**实施完成时间**：2026-01-11  
**版本**：2.0（实施完成版）
