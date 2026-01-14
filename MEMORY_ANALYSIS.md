# Memory/Prompt 分析报告

## 问题发现

### 1. Diff 重复问题 ⚠️ **严重**

**问题描述**：
- Diff 在 prompt 中出现了**两次**，导致大量 token 浪费
- 第一次：在 `⚠️ Current State` 部分（memory context 中，最多 2000 字符）
- 第二次：在 `### Current Diff` 部分（prompt template 中，完整 diff）

**代码位置**：
1. `atloop/memory/formatter.py:632-640` - `_format_current_state()` 方法中包含 diff（最多 2000 字符）
2. `atloop/llm/client.py:308` - `build_user_message()` 中 `{CURRENT_DIFF}` 占位符被替换为完整 diff
3. `atloop/llm/prompts/en/developer.txt:397-398` - Prompt template 中有 `{CURRENT_DIFF}` 占位符

**影响**：
- 如果 diff 有 240 行（如 train.py），会重复出现两次
- 浪费大量 token（可能数千个 token）
- 增加 LLM 处理负担

### 2. Current State 注入时机

**Current State 什么时候进去的**：
- `MemoryFormatter.format()` 方法（第 304 行）会调用 `_format_current_state()`
- 这个方法在每次 `PlanPhase.execute()` 时被调用（第 57-68 行）
- 返回的 `memory_context` 被传入 `build_user_message()` 作为 `{STATE_SUMMARY}`（第 172 行）
- 所以 Current State 是作为 memory 的一部分，在每次 PLAN 阶段都会被注入

**包含内容**：
- Last Error
- Current Diff（最多 2000 字符）
- Test Results

## 建议修复方案

### 方案 1：从 Memory Current State 中移除 Diff（推荐）✅

**理由**：
- Prompt template 中已经有专门的 `{CURRENT_DIFF}` 占位符
- Memory 中的 Current State 应该只包含状态信息，不需要完整 diff
- 保持单一数据源原则

**修改**：
```python
# atloop/memory/formatter.py
def _format_current_state(self, state: "AgentState") -> str:
    """格式化当前状态"""
    parts = ["### ⚠️ Current State"]

    # Last Error
    if state.last_error.summary:
        parts.append(f"**Last Error**: {state.last_error.summary}")
    else:
        parts.append("**Last Error**: None")

    # Current Diff - 只显示摘要，不显示完整内容
    # 完整 diff 在 prompt template 的 {CURRENT_DIFF} 中
    if state.artifacts.current_diff:
        diff_lines = state.artifacts.current_diff.count('\n')
        parts.append(f"**Current Diff**: {diff_lines} lines changed (see Current Diff section below)")
    else:
        parts.append("**Current Diff**: No changes")

    # Test Results
    if state.artifacts.test_results:
        parts.append(f"**Test Results**: {state.artifacts.test_results}")
    else:
        parts.append("**Test Results**: No verification command available")

    return "\n".join(parts)
```

### 方案 2：从 Prompt Template 中移除 {CURRENT_DIFF}

**理由**：
- Memory 中已经有 Current State，包含 diff
- 避免重复

**修改**：
- 从 `atloop/llm/prompts/en/developer.txt` 中移除 `### Current Diff` 部分
- 从 `build_user_message()` 中移除 `current_diff` 参数处理

**缺点**：
- 如果 memory 被截断，可能丢失 diff 信息
- 不符合单一职责原则（memory 应该只包含状态，不应该包含完整 diff）

### 方案 3：差异化显示（折中方案）

**Memory 中**：只显示 diff 摘要（文件列表、行数统计）
**Prompt 中**：显示完整 diff

**优点**：
- 既避免完全重复，又保留完整信息
- Memory 中可以看到概览，Prompt 中可以看到详情

## 其他发现

### 1. Recent Error 也可能重复

检查发现：
- `{RECENT_ERROR}` 在 prompt template 中（第 393 行）
- `⚠️ Current State` 中也有 `Last Error`

但这两个可能不同：
- `{RECENT_ERROR}` 来自 `context_pack.recent_error`（可能被截断）
- `Last Error` 来自 `state.last_error.summary`（完整错误）

**建议**：保持现状，但需要确认它们是否真的不同

### 2. Test Results 也可能重复

检查发现：
- `{TEST_RESULTS}` 在 prompt template 中（第 403 行）
- `⚠️ Current State` 中也有 `Test Results`

**建议**：统一到一个地方，避免重复

## 推荐实施步骤

1. **立即修复**：实施方案 1（从 Memory Current State 中移除完整 diff）
2. **后续优化**：检查 Recent Error 和 Test Results 是否也需要去重
3. **添加验证**：在测试中验证 diff 不会重复出现

## 代码修改位置

1. `atloop/atloop/memory/formatter.py:621-650` - `_format_current_state()` 方法
2. （可选）`atloop/atloop/llm/prompts/en/developer.txt:397-400` - 如果采用方案 2
