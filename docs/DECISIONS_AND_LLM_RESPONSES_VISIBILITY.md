# decisions 和 llm_responses 的可见性分析

## 关键发现

**重要澄清**：虽然 `decisions` 和 `llm_responses` 都被标记为 "DEBUG-ONLY"，但它们的实际可见性是不同的：

- ✅ **`decisions`**：**部分可见**给 LLM（只显示事实信息）
- ❌ **`llm_responses`**：**完全不可见**给 LLM

---

## 1. decisions 的可见性

### 1.1 标记为 DEBUG-ONLY，但实际部分可见

```python
# memory/state.py:79
decisions: List[Dict[str, Any]] = field(default_factory=list)
# WARNING: Contains current_step_thoughts - DO NOT feed back to LLM
```

**注释说明**：包含 `current_step_thoughts`，不要反馈给 LLM。

### 1.2 实际在 MemorySummarizer 中的处理

```python
# memory/summarizer.py:209-226
# Recent Steps Summary (FACTS ONLY - no LLM interpretations)
# NOTE: We intentionally do NOT show current_step_thoughts or LLM plans here
# to prevent feedback loops where LLM's previous hypotheses become "facts"
if state.memory.decisions:
    parts.append("## Recent Steps (Facts Only)")
    for decision in state.memory.decisions[-3:]:  # ← 显示最近 3 个
        step = decision.get("step", "?")
        actions = decision.get("actions", [])
        actions_count = len(actions)
        stop_reason = decision.get("stop_reason", "?")
        
        # Show only factual information: what tools were called
        tools_used = [a.get("tool", "?") for a in actions[:3]]
        tools_str = ", ".join(tools_used)
        if len(actions) > 3:
            tools_str += f" ... (+{len(actions) - 3} more)"
        
        parts.append(f"- Step {step}: {actions_count} actions [{tools_str}] ({stop_reason})")
```

### 1.3 LLM 可以看到的 decisions 信息

✅ **可见**（事实信息）：
- `step`：步骤号
- `actions_count`：动作数量
- `tools_used`：使用的工具列表（前 3 个）
- `stop_reason`：停止原因（continue/done/fail）

❌ **不可见**（LLM 的主观内容）：
- `current_step_thoughts`：当前步骤的思考过程
- `plan`：LLM 生成的计划
- `llm_output`：完整的 LLM 输出

### 1.4 示例

**存储的 decision**：
```python
{
    "step": 5,
    "current_step_thoughts": "I think the error is caused by...",  # ← LLM 看不到
    "plan": ["Step 1", "Step 2"],  # ← LLM 看不到
    "actions": [
        {"tool": "run", "args": {"cmd": "ls"}},
        {"tool": "read_file", "args": {"path": "test.py"}},
    ],
    "stop_reason": "continue",
    "llm_output": "..."  # ← LLM 看不到
}
```

**LLM 在 Memory Summary 中看到的**：
```
## Recent Steps (Facts Only)
- Step 5: 2 actions [run, read_file] (continue)
```

---

## 2. llm_responses 的可见性

### 2.1 标记为 DEBUG-ONLY，完全不可见

```python
# memory/state.py:82
llm_responses: List[Dict[str, Any]] = field(default_factory=list)
# WARNING: Contains current_step_thoughts - DO NOT feed back to LLM
```

### 2.2 实际在 MemorySummarizer 中的处理

```python
# memory/summarizer.py:228-229
# NOTE: llm_responses are NOT shown to LLM to prevent feedback loops
# They are preserved in memory for debugging only
```

**关键发现**：`llm_responses` **完全不参与** Memory Summary 的生成，LLM 完全看不到。

---

## 3. 设计意图 vs 实际实现

### 3.1 设计意图

根据注释，`decisions` 和 `llm_responses` 都应该：
- ❌ 不反馈给 LLM
- 📝 仅用于调试/日志

### 3.2 实际实现

| 字段 | 设计意图 | 实际实现 | 可见性 |
|------|----------|----------|--------|
| `decisions` | DEBUG-ONLY，不反馈 | **部分可见**（只显示事实） | ✅ 部分可见 |
| `llm_responses` | DEBUG-ONLY，不反馈 | **完全不可见** | ❌ 完全不可见 |

### 3.3 为什么 decisions 部分可见？

**设计考虑**：
1. **提供上下文**：LLM 需要知道"之前做了什么"（工具、动作数）
2. **防止反馈循环**：不显示 LLM 的思考过程（`current_step_thoughts`）
3. **平衡**：在提供上下文和防止反馈循环之间取得平衡

**实际效果**：
- ✅ LLM 可以看到历史步骤的**事实**（做了什么工具、多少动作）
- ❌ LLM 看不到历史步骤的**思考过程**（为什么这样做）

---

## 4. 完整可见性矩阵

| Memory 字段 | 是否反馈给 LLM | 反馈内容 | 用途 |
|------------|---------------|----------|------|
| **FACTS** | | | |
| `created_files` | ✅ 是 | 文件列表 | 防止重复创建 |
| `modified_files_content` | ✅ 是 | 文件内容 | 提供上下文 |
| `tool_results_history` | ✅ 是 | 工具执行结果 | 提供执行历史 |
| `attempts` | ✅ 是 | 尝试记录和结果 | 提供执行历史 |
| `key_files` | ✅ 是 | 关键文件列表 | 提供上下文 |
| `notes` | ✅ 是 | 事实性笔记 | 提供上下文 |
| **LONG-TERM** | | | |
| `plan` | ✅ 是 | 当前计划 | 提供长期上下文 |
| `task_summary` | ✅ 是 | 任务摘要 | 提供长期上下文 |
| `important_decisions` | ✅ 是 | 重要决策（Top 5） | 提供长期上下文 |
| `milestones` | ✅ 是 | 里程碑（Top 5） | 提供长期上下文 |
| `learnings` | ✅ 是 | 经验总结（Top 3） | 提供长期上下文 |
| **DEBUG-ONLY** | | | |
| `decisions` | ⚠️ **部分可见** | 只显示事实（工具、动作数、stop_reason） | 提供最近步骤的事实信息 |
| `decisions.current_step_thoughts` | ❌ 否 | - | 调试/日志 |
| `decisions.plan` | ❌ 否 | - | 调试/日志 |
| `decisions.llm_output` | ❌ 否 | - | 调试/日志 |
| `llm_responses` | ❌ **完全不可见** | - | 调试/日志 |

---

## 5. 设计评估

### 5.1 当前设计的合理性

**优点**：
- ✅ **平衡设计**：`decisions` 部分可见，既提供了上下文，又防止了反馈循环
- ✅ **清晰分离**：`llm_responses` 完全不可见，避免任何风险
- ✅ **事实优先**：只显示客观事实，不显示主观思考

**潜在问题**：
- ⚠️ **注释不一致**：注释说"不反馈给 LLM"，但实际部分可见
- ⚠️ **可能混淆**：标记为 DEBUG-ONLY，但实际部分可见

### 5.2 建议

**建议 1：更新注释（高优先级）**

```python
# memory/state.py
decisions: List[Dict[str, Any]] = field(default_factory=list)
# NOTE: Partially visible to LLM - only factual information (tools, actions, stop_reason)
#       current_step_thoughts, plan, and llm_output are NOT shown to prevent feedback loops
```

**建议 2：考虑重命名或重新分类（中优先级）**

可以考虑将 `decisions` 重新分类为 "PARTIALLY_VISIBLE" 或 "FACTS_ONLY"，而不是 "DEBUG-ONLY"。

---

## 6. 总结

### 6.1 回答你的问题

**Q: decisions 和 llm_responses 是否只是作为 debug 信息存在？**

**A: 不完全正确**：
- `llm_responses`：✅ **是的**，完全作为 debug 信息，LLM 完全看不到
- `decisions`：⚠️ **部分正确**，虽然标记为 DEBUG-ONLY，但**部分可见**给 LLM（只显示事实信息）

**Q: 历史 decisions LLM 在循环过程中看不到吗？**

**A: 部分可见**：
- ✅ LLM **可以看到**：最近 3 个 decisions 的事实信息（步骤号、工具、动作数、stop_reason）
- ❌ LLM **看不到**：`current_step_thoughts`、`plan`、`llm_output` 等主观内容

### 6.2 设计理念

当前设计采用了**"事实可见，思考不可见"**的策略：
- **事实信息**（工具、动作、结果）→ 可见，帮助 LLM 了解历史
- **思考过程**（current_step_thoughts、plan）→ 不可见，防止反馈循环

这是一个**平衡设计**，既提供了必要的上下文，又避免了反馈循环的风险。

---

**报告完成时间**：2026-01-11  
**版本**：1.0
