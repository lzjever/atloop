# 架构重构计划：解决 Memory/Prompt 重复问题

## 问题根源分析

### 当前架构的问题

1. **职责混乱**：
   - `MemoryFormatter` 既格式化 memory 信息，又格式化 artifacts（diff, errors, test results）
   - `Prompt Template` 也有占位符显示 artifacts（{CURRENT_DIFF}, {RECENT_ERROR}, {TEST_RESULTS}）
   - 导致同一信息在两个地方显示

2. **数据流不清晰**：
   ```
   State.memory → MemoryFormatter → Memory Context (包含 Current State with diff)
   State.artifacts → ContextPack → Prompt Template ({CURRENT_DIFF}, {RECENT_ERROR})
   ```
   两者重叠，导致重复

3. **违反单一数据源原则**：
   - Diff 在 Memory Current State 中显示（最多2000字符）
   - Diff 在 Prompt Template 的 {CURRENT_DIFF} 中显示（完整）
   - 重复浪费 token

## 正确的架构设计

### 核心原则

1. **职责分离**：
   - **Memory Formatter**：只负责格式化 memory 相关的信息（plan, context, activity, tool results, file content）
   - **Artifacts Formatter**：负责格式化 artifacts（diff, errors, test results）
   - **Prompt Template**：只负责结构化和占位符替换

2. **单一数据源**：
   - 每个信息只在一个地方显示
   - Memory Context 不包含 artifacts 的完整内容
   - Artifacts 通过 Prompt Template 的占位符显示

3. **清晰的边界**：
   - Memory = 历史状态、计划、上下文、活动记录
   - Artifacts = 当前状态（diff, errors, test results）

### 新架构设计

```
┌─────────────────────────────────────────────────────────┐
│                    AgentState                           │
│  ┌──────────────┐         ┌──────────────┐            │
│  │   Memory     │         │  Artifacts   │            │
│  │ - plan       │         │ - current_diff│           │
│  │ - context    │         │ - last_error  │            │
│  │ - activity   │         │ - test_results│           │
│  │ - tool_results│        └──────────────┘            │
│  └──────────────┘                                      │
└─────────────────────────────────────────────────────────┘
         │                        │
         │                        │
         ▼                        ▼
┌──────────────────┐    ┌──────────────────┐
│ MemoryFormatter  │    │ ContextPackBuilder│
│                  │    │                  │
│ 只格式化 Memory   │    │ 只格式化 Artifacts│
│ - Critical Warnings│   │ - Current Diff   │
│ - Task Overview  │    │ - Recent Error   │
│ - Execution Plan │    │ - Test Results   │
│ - Context        │    └──────────────────┘
│ - Activity       │              │
│ - Tool Results   │              │
│ - File Content   │              │
│ - State Summary  │              │
│   (不含完整diff)  │              │
└──────────────────┘              │
         │                        │
         │                        │
         └──────────┬─────────────┘
                    │
                    ▼
         ┌──────────────────┐
         │  Prompt Template  │
         │                  │
         │ {STATE_SUMMARY}  │ ← Memory Context
         │ {CURRENT_DIFF}   │ ← Artifacts
         │ {RECENT_ERROR}   │ ← Artifacts
         │ {TEST_RESULTS}   │ ← Artifacts
         └──────────────────┘
```

## 重构步骤

### Step 1: 重新定义 Current State 的职责

**Current State 应该只包含状态摘要，不包含完整内容**：

```python
def _format_current_state(self, state: "AgentState") -> str:
    """格式化当前状态摘要
    
    注意：Current State 只包含状态摘要，完整内容在 Prompt Template 的占位符中显示。
    这样可以避免重复，并保持职责清晰。
    """
    parts = ["### ⚠️ Current State"]

    # Last Error - 只显示摘要
    if state.last_error.summary:
        # 只显示错误类型和关键信息，不显示完整堆栈
        error_summary = state.last_error.summary.split('\n')[0]  # 第一行
        if len(state.last_error.summary) > 200:
            error_summary += " (see Recent Errors section below for details)"
        parts.append(f"**Last Error**: {error_summary}")
    else:
        parts.append("**Last Error**: None")

    # Current Diff - 只显示统计信息
    if state.artifacts.current_diff:
        diff_lines = state.artifacts.current_diff.count('\n')
        diff_size = len(state.artifacts.current_diff)
        # 提取修改的文件
        files_changed = self._extract_files_from_diff(state.artifacts.current_diff)
        if files_changed:
            files_summary = ', '.join(files_changed[:3])
            if len(files_changed) > 3:
                files_summary += f" (+{len(files_changed) - 3} more)"
            parts.append(f"**Current Diff**: {diff_lines} lines in {len(files_changed)} file(s): {files_summary} (see Current Diff section below)")
        else:
            parts.append(f"**Current Diff**: {diff_lines} lines changed (see Current Diff section below)")
    else:
        parts.append("**Current Diff**: No changes")

    # Test Results - 只显示状态
    if state.artifacts.test_results:
        # 只显示通过/失败状态，不显示完整结果
        if "passed" in state.artifacts.test_results.lower() or "✓" in state.artifacts.test_results:
            parts.append("**Test Results**: ✓ Passed (see Test Results section below for details)")
        elif "failed" in state.artifacts.test_results.lower() or "❌" in state.artifacts.test_results:
            parts.append("**Test Results**: ❌ Failed (see Test Results section below for details)")
        else:
            parts.append("**Test Results**: ⚠️ Unknown (see Test Results section below for details)")
    else:
        parts.append("**Test Results**: No verification command available")

    return "\n".join(parts)
```

### Step 2: 明确 Memory Context 和 Artifacts 的边界

**Memory Context 应该包含**：
- ✅ Critical Warnings
- ✅ Task Overview
- ✅ Execution Plan
- ✅ Important Context
- ✅ Recent Activity
- ✅ Tool Execution Results
- ✅ Modified Files Content
- ✅ Current State (摘要，不含完整内容)
- ✅ Next Steps Guidance

**Artifacts (通过 Prompt Template 占位符显示)**：
- ✅ Current Diff (完整内容)
- ✅ Recent Error (完整内容)
- ✅ Test Results (完整内容)

### Step 3: 更新 Prompt Template 说明

在 Prompt Template 中明确说明：
- `{STATE_SUMMARY}` 包含 memory 信息，Current State 部分只包含摘要
- `{CURRENT_DIFF}`, `{RECENT_ERROR}`, `{TEST_RESULTS}` 包含完整内容

### Step 4: 添加辅助方法

```python
def _extract_files_from_diff(self, diff: str) -> List[str]:
    """从 diff 中提取修改的文件列表"""
    files = []
    for line in diff.split('\n')[:50]:  # 只检查前50行
        if line.startswith('+++ ') or line.startswith('--- '):
            file_path = line[4:].strip()
            if file_path and file_path not in files:
                files.append(file_path)
    return files
```

## 实施计划

### Phase 1: 重构 MemoryFormatter (高优先级)

1. 修改 `_format_current_state()` 只显示摘要
2. 添加 `_extract_files_from_diff()` 辅助方法
3. 更新文档说明职责边界

### Phase 2: 验证和测试

1. 运行现有测试确保不破坏功能
2. 验证 diff 不再重复
3. 检查 token 使用量是否减少

### Phase 3: 清理和优化

1. 检查 Recent Error 是否也需要类似处理
2. 检查 Test Results 是否也需要类似处理
3. 统一所有 artifacts 的处理方式

## 预期效果

1. **Token 节省**：消除 diff 重复，节省数千 token
2. **职责清晰**：Memory 和 Artifacts 职责明确
3. **易于维护**：单一数据源，修改更容易
4. **可扩展性**：未来添加新的 artifact 类型更容易

## 风险评估

- **低风险**：只是改变显示方式，不改变数据源
- **向后兼容**：Prompt Template 结构不变，只是内容来源更清晰
- **测试覆盖**：现有测试应该能覆盖大部分场景
