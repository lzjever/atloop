# 日志级别重构总结：降低 LLM 指令解析/执行相关的日志级别

## 重构原则

这次重构遵循**设计最佳实践**，从架构层面解决问题：

1. **区分业务正常情况和真正错误**：
   - 业务正常情况：LLM 输出不完美但 agent loop 可以处理（可恢复）
   - 真正错误：需要用户注意的系统错误（不可恢复）

2. **日志级别对应严重程度**：
   - `debug`: 业务正常情况，agent loop 可以处理（如 missing placeholder）
   - `info`: 状态信息，可恢复的错误（如 placeholder replacement incomplete）
   - `warning`: 需要关注但可恢复的情况（保留给真正的警告）
   - `error`: 真正的错误，需要修复（如 type mismatches）

3. **Console 输出过滤**：
   - Minimal/Verbose 模式：不显示可恢复的 LLM 解析错误（避免红色 fail 框）
   - Debug 模式：显示所有日志

## 已实施的修改

### 1. PlaceholderReplacer (placeholder_replacer.py)

**降级的日志**：
- `Missing placeholder` (line 226-229) → **warning → debug**
- `Found missing placeholders` (line 237-240) → **warning → debug**
- `Placeholder replacement incomplete` (line 356-360, 409-413) → **warning → debug**

**保持的日志**：
- `Type mismatches` → **保持 error** (真正的错误)

### 2. LLMClient (llm/client.py)

**降级的日志**：
- `Actions reference placeholders but no blocks found` (line 744-754) → **warning → debug**

### 3. PlanPhase (orchestrator/phases/plan.py)

**降级的日志**：
- `No file_contents received from LLM, but actions reference placeholders` (line 375-378) → **warning → debug**
- `Placeholder replacement incomplete` (line 462) → **warning → info**
- `No successful actions after placeholder replacement` (line 470-473) → **warning → info**

**新增标记**：
- Placeholder 相关错误现在标记为 `recoverable=True`，确保 workflow 正确处理

### 4. Workflow (orchestrator/workflow/workflow.py)

**降级的日志**：
- `Phase returned recoverable error` (line 377-378) → **warning → info**
- `Classified error as recoverable` (line 390-391) → **warning → info**
- `Treating exception as recoverable` (line 459-460) → **warning → info**

### 5. ErrorClassifier (orchestrator/error_handler.py)

**新增模式**：
- 添加了 LLM 指令解析相关的 recoverable 模式：
  - "placeholder"
  - "missing placeholder"
  - "placeholder replacement incomplete"
  - "will retry"
  - "json"
  - "parse"
  - "incomplete"
  - "no file_contents received"
  - "no successful actions after placeholder"

### 6. ErrorComponent (output/console/components/error.py)

**新增过滤逻辑**：
- 检查 `ErrorEvent.recoverable` 字段
- 对于可恢复的 LLM 解析错误（placeholder/JSON 相关），在 minimal/verbose 模式下**不显示红色 fail 框**
- 返回 `None` 来跳过显示，因为这些是业务正常情况

**显示逻辑**：
- 可恢复错误：使用黄色样式（如果显示）
- 致命错误：使用红色样式

## 架构改进

### 清晰的错误分类

```
业务正常情况（可恢复）:
├── Missing placeholder → debug
├── Placeholder replacement incomplete → debug/info
├── JSON parsing issues (recoverable) → debug
└── Actions reference placeholders but no blocks → debug

真正错误（不可恢复）:
├── Type mismatches → error
├── Critical system errors → error
└── Fatal errors → error
```

### Console 输出策略

**Minimal 模式**：
- 不显示可恢复的 placeholder/JSON 解析警告
- 只显示真正的错误（红色 fail 框）

**Verbose 模式**：
- 不显示可恢复的 placeholder/JSON 解析警告
- 显示真正的错误（红色 fail 框）
- 显示状态信息（info 级别）

**Debug 模式**：
- 显示所有日志（包括 debug 级别）

## 预期效果

1. **用户体验改善**：
   - 不再看到大量红色 fail 框（这些是业务正常情况）
   - 日志更清晰，只显示真正需要关注的问题
   - 减少用户焦虑（不会觉得程序有问题）

2. **日志清晰度**：
   - Debug 级别：详细的调试信息（业务正常情况）
   - Info 级别：状态信息（可恢复的错误）
   - Warning 级别：需要关注但可恢复的情况
   - Error 级别：真正的错误

3. **可维护性**：
   - 清晰的错误分类
   - 易于添加新的 recoverable 模式
   - 符合日志最佳实践

## 测试建议

1. **验证日志级别**：
   - 运行一个会产生 missing placeholder 的场景
   - 检查日志中是否使用 debug 级别
   - 检查 console 输出是否不显示红色 fail 框

2. **验证错误分类**：
   - 测试 type mismatch（应该显示为 error）
   - 测试 missing placeholder（应该不显示红色 fail 框）

3. **验证不同模式**：
   - Minimal 模式：不应该显示可恢复错误
   - Verbose 模式：不应该显示可恢复错误
   - Debug 模式：应该显示所有日志
