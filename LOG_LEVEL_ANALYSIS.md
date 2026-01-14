# 日志级别分析：LLM 指令解析/执行相关

## 分类原则

### 业务正常情况（可恢复，应该降级）
这些是 LLM 输出不完美但 agent loop 可以处理的情况：
- Placeholder missing → 会在下一轮 retry
- Placeholder replacement incomplete → 部分成功，会 retry
- JSON parsing issues (recoverable) → json-repair 可以修复
- Actions reference placeholders but no blocks found → 会在下一轮提供

### 真正的错误（应该保持）
这些是真正的错误，需要用户注意：
- Type mismatches → 逻辑错误，需要修复
- Critical errors that break execution → 系统错误
- 真正的系统错误 → 需要修复

## 需要降级的日志

### 1. PlaceholderReplacer
- `Missing placeholder` (line 226-229) → warning → **debug**
- `Found missing placeholders` (line 237-240) → warning → **debug**
- `Placeholder replacement incomplete` (line 356-360, 409-413) → warning → **debug**

### 2. LLMClient
- `Actions reference placeholders but no blocks found` (line 744-754) → warning → **debug**

### 3. PlanPhase
- `No file_contents received from LLM, but actions reference placeholders` (line 375-378) → warning → **debug**
- `Placeholder replacement incomplete` (line 462) → warning → **debug**
- `No successful actions after placeholder replacement` (line 470-473) → warning → **info** (这是状态信息，不是错误)

## 应该保持的日志

### 1. PlaceholderReplacer
- `Type mismatches` (line 243-246, 345, 398) → **保持 error** (真正的错误)

### 2. PlanPhase
- `CRITICAL: actions still have unreplaced placeholders after replacement` (line 510) → **保持 error** (逻辑错误)

## Console 输出建议

### Minimal 模式
- 不显示可恢复的 placeholder/JSON 解析警告
- 只显示真正的错误（type mismatches, critical errors）

### Verbose 模式
- 可以显示可恢复的警告，但使用 info 级别（不是 warning）
- 真正的错误仍然显示为 error

### Debug 模式
- 显示所有日志（包括 debug 级别）
