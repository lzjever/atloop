# 架构重构总结：从结构上解决 Memory/Prompt 重复问题

## 重构原则

这次重构遵循**设计最佳实践**，从架构层面解决问题，而不是简单的 workaround。

### 核心设计原则

1. **职责分离 (Separation of Concerns)**
   - Memory Formatter：只负责格式化 memory 相关信息
   - Artifacts：通过 Prompt Template 占位符显示完整内容
   - 清晰的边界，单一职责

2. **单一数据源 (Single Source of Truth)**
   - 每个信息只在一个地方显示完整内容
   - Memory Context 中的 Current State 只显示摘要
   - 完整内容通过 Prompt Template 占位符显示

3. **数据流清晰 (Clear Data Flow)**
   ```
   State.memory → MemoryFormatter → Memory Context (摘要)
   State.artifacts → ContextPack → Prompt Template (完整内容)
   ```

## 重构内容

### 1. 重新定义 Current State 的职责

**之前（问题）**：
- Current State 包含完整 diff（最多 2000 字符）
- Prompt Template 也包含完整 diff
- 导致重复

**现在（解决）**：
- Current State 只显示摘要：
  - Error: 只显示第一行（错误类型和位置）
  - Diff: 只显示统计信息（行数、文件列表）
  - Test Results: 只显示状态（通过/失败/未知）
- 完整内容在 Prompt Template 的专门 section 中显示

### 2. 添加辅助方法

新增 `_extract_files_from_diff()` 方法：
- 从 diff 中提取修改的文件列表
- 支持 Git diff 格式（处理 a/ 和 b/ 前缀）
- 用于生成摘要信息

### 3. 更新文档说明

在 Prompt Template 中明确说明：
- Current State 只包含摘要
- 完整内容在下面的专门 section 中

## 架构改进

### 职责边界清晰

```
┌─────────────────────────────────────┐
│      Memory Formatter               │
│  - Critical Warnings                │
│  - Task Overview                    │
│  - Execution Plan                  │
│  - Important Context                │
│  - Recent Activity                  │
│  - Tool Execution Results           │
│  - Modified Files Content           │
│  - Current State (摘要)             │
│  - Next Steps Guidance              │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│      Prompt Template                │
│  - {STATE_SUMMARY} ← Memory Context │
│  - {CURRENT_DIFF} ← Artifacts       │
│  - {RECENT_ERROR} ← Artifacts       │
│  - {TEST_RESULTS} ← Artifacts       │
└─────────────────────────────────────┘
```

### 数据流清晰

1. **Memory 数据流**：
   ```
   State.memory → MemoryFormatter.format() → Memory Context
   ```
   - 包含历史状态、计划、上下文
   - Current State 只包含摘要

2. **Artifacts 数据流**：
   ```
   State.artifacts → ContextPackBuilder.build() → Prompt Template placeholders
   ```
   - 包含当前状态（diff, errors, test results）
   - 完整内容

## 为什么这是架构改进而不是 workaround

### Workaround 的特征：
- ❌ 临时修复，不解决根本问题
- ❌ 增加复杂性，不减少复杂性
- ❌ 违反设计原则
- ❌ 难以维护和扩展

### 这次重构的特征：
- ✅ **解决根本问题**：重新定义职责边界，消除重复的根本原因
- ✅ **减少复杂性**：清晰的职责分离，单一数据源
- ✅ **符合设计原则**：职责分离、单一数据源、清晰的数据流
- ✅ **易于维护**：职责清晰，修改影响范围小
- ✅ **易于扩展**：未来添加新的 artifact 类型更容易

## 预期效果

1. **Token 节省**：
   - 消除 diff 重复：节省数千 token（取决于 diff 大小）
   - Error 和 Test Results 也可能有轻微节省

2. **代码质量**：
   - 职责清晰，易于理解
   - 单一数据源，易于维护
   - 符合 SOLID 原则

3. **可扩展性**：
   - 未来添加新的 artifact 类型时，只需在 Prompt Template 添加占位符
   - Memory Formatter 不需要修改

## 测试验证

- ✅ 现有测试通过
- ✅ 功能不破坏
- ✅ 架构改进验证通过

## 后续优化建议

1. **Recent Error 优化**：
   - 检查 `{RECENT_ERROR}` 和 Current State 中的 Last Error 是否也需要类似处理
   - 如果两者来源不同，保持现状；如果相同，考虑统一

2. **Test Results 优化**：
   - 检查 `{TEST_RESULTS}` 和 Current State 中的 Test Results 是否也需要类似处理

3. **监控和验证**：
   - 在实际运行中监控 token 使用量
   - 验证 diff 不再重复
   - 收集反馈，进一步优化
