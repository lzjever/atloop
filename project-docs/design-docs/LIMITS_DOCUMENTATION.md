# Limits 配置完整文档

本文档详细说明 `atloop/config/limits.py` 中所有配置项的含义、用途和影响。

## 概述

`limits.py` 集中管理所有运行时限制配置，包括：
- 工具执行输出的截断限制
- 错误信息的保留大小
- 记忆摘要的长度控制
- 上下文包的大小限制
- 事件日志的存储限制
- 报告生成的内容限制

**设计原则**：
1. 所有限制都在这里集中定义
2. 每个限制都有清晰的注释说明用途
3. 限制值应该根据实际需求合理设置，避免过大（浪费token）或过小（丢失信息）
4. 对于文件查看命令，需要更大的限制以确保LLM能看到完整内容

---

## 一、工具执行输出限制

### 1. `STDOUT_STDERR_LIMIT_NORMAL` (5000 字符 / 5KB)

**含义**：普通工具命令的标准输出和错误输出的最大字符数限制。

**用途**：
- 用于非文件查看命令（如 `ls`, `grep`, `find` 等）的 stdout/stderr 截断
- 当命令输出超过此限制时，会被截断以避免占用过多 token

**使用位置**：
- `atloop/orchestrator/agent_loop.py` - 处理工具执行结果时

**影响**：
- ✅ **太小**：可能丢失重要错误信息，导致 LLM 无法诊断问题
- ✅ **太大**：浪费 token，增加 API 调用成本，可能导致 prompt 过大
- ✅ **当前值 5KB**：适合大多数普通命令的输出

**示例**：
```python
# 如果命令输出 10000 字符，会被截断到 5000 字符
stdout = result.stdout[:STDOUT_STDERR_LIMIT_NORMAL]  # 只保留前 5KB
```

---

### 2. `STDOUT_STDERR_LIMIT_FILE_VIEW` (40000 字符 / 40KB)

**含义**：文件查看命令的输出限制，比普通命令大得多。

**用途**：
- 用于 `cat`, `head`, `tail`, `sed -n` 等文件查看命令
- 需要更大的限制以确保 LLM 能看到完整的文件内容来修复错误

**使用位置**：
- `atloop/orchestrator/agent_loop.py` - 检测到文件查看命令时使用此限制

**影响**：
- ✅ **为什么需要 40KB**：文件内容通常比命令输出大得多，需要足够空间来显示完整文件
- ✅ **太大**：如果文件非常大（如几 MB），仍然会被截断，但 40KB 已经足够显示大部分代码文件
- ✅ **太小**：无法看到完整文件，LLM 可能无法正确修复错误

**示例**：
```python
if is_file_view_command(cmd):
    limit = STDOUT_STDERR_LIMIT_FILE_VIEW  # 40KB
else:
    limit = STDOUT_STDERR_LIMIT_NORMAL  # 5KB
```

---

### 3. `STDOUT_STDERR_LIMIT_OTHER` (2000 字符 / 2KB)

**含义**：非 `run` 工具的输出限制（如 `write_file`, `edit_file` 等）。

**用途**：
- 用于文件操作工具的输出
- 这些工具的输出通常很短（成功/失败消息），不需要太多空间

**使用位置**：
- `atloop/orchestrator/agent_loop.py` - 处理非 run 工具的输出时

**影响**：
- ✅ **为什么只需要 2KB**：文件操作工具的输出通常是简单的确认消息，不需要太多空间
- ✅ **太大**：浪费 token
- ✅ **太小**：可能丢失重要错误信息

---

### 4. `ERROR_SUMMARY_LIMIT_NORMAL` (15000 字符 / 15KB)

**含义**：普通命令的错误摘要最大长度。

**用途**：
- 用于存储工具执行结果的错误摘要，传递给 LLM
- 比 stdout/stderr 限制大，因为错误信息需要更完整

**使用位置**：
- `atloop/orchestrator/agent_loop.py` - 构建错误摘要时

**影响**：
- ✅ **为什么需要 15KB**：错误信息通常包含完整的 traceback，需要足够空间
- ✅ **太大**：浪费 token
- ✅ **太小**：可能截断关键错误信息，导致 LLM 无法诊断问题

**示例**：
```python
error_summary = format_error(result)[:ERROR_SUMMARY_LIMIT_NORMAL]  # 最多 15KB
```

---

### 5. `ERROR_SUMMARY_LIMIT_FILE_VIEW` (30000 字符 / 30KB)

**含义**：文件查看命令的错误摘要限制，比普通命令大。

**用途**：
- 用于文件查看命令的错误摘要
- 文件查看命令的错误可能包含文件内容，需要更大空间

**使用位置**：
- `atloop/orchestrator/agent_loop.py` - 检测到文件查看命令时使用此限制

**影响**：
- ✅ **为什么需要 30KB**：文件查看命令的错误可能包含文件片段，需要更大空间
- ✅ **太大**：浪费 token
- ✅ **太小**：可能丢失包含文件内容的错误信息

---

### 6. `STDERR_TAIL_LIMIT` (5000 字符 / 5KB)

**含义**：stderr 尾部存储限制，用于详细错误分析。

**用途**：
- 存储 stderr 的尾部（最后 N 个字符）
- 用于详细错误分析，通常错误信息在 stderr 的末尾

**使用位置**：
- `atloop/orchestrator/agent_loop.py` - 提取 stderr 尾部时

**影响**：
- ✅ **为什么需要尾部**：很多错误信息（如 Python traceback）在输出的末尾
- ✅ **太大**：浪费 token
- ✅ **太小**：可能丢失关键错误信息

**示例**：
```python
stderr_tail = result.stderr[-STDERR_TAIL_LIMIT:]  # 最后 5KB
```

---

## 二、上下文包（Context Pack）限制

### 7. `RECENT_ERROR_LIMIT_NORMAL` (10000 字符 / 10KB)

**含义**：最近错误信息的最大长度，用于在 prompt 中传递给 LLM。

**用途**：
- 在 prompt 中传递给 LLM 的最近错误信息
- 用于普通错误（不包含文件内容）

**使用位置**：
- `atloop/retrieval/context_pack.py` - 构建上下文包时

**影响**：
- ✅ **为什么需要 10KB**：需要足够空间显示完整的错误信息
- ✅ **太大**：浪费 token
- ✅ **太小**：可能丢失关键错误信息

---

### 8. `RECENT_ERROR_LIMIT_FILE_CONTENT` (25000 字符 / 25KB)

**含义**：包含文件内容的错误信息限制，比普通错误大。

**用途**：
- 用于包含文件内容的错误信息
- 文件内容通常比纯错误信息大得多

**使用位置**：
- `atloop/retrieval/context_pack.py` - 检测到包含文件内容的错误时使用此限制

**影响**：
- ✅ **为什么需要 25KB**：包含文件内容的错误需要更大空间
- ✅ **太大**：浪费 token
- ✅ **太小**：可能丢失文件内容，导致 LLM 无法正确诊断问题

---

### 9. `DIFF_LIMIT` (5000 字符 / 5KB)

**含义**：Diff 信息的最大长度，用于显示文件变更。

**用途**：
- 用于显示文件变更的 diff 信息
- 传递给 LLM 以便了解文件修改历史

**使用位置**：
- `atloop/retrieval/context_pack.py` - 构建 diff 信息时

**影响**：
- ✅ **为什么需要 5KB**：diff 信息通常不会太长，5KB 足够显示大部分变更
- ✅ **太大**：浪费 token
- ✅ **太小**：可能丢失重要变更信息

---

### 10. `TEST_RESULTS_LIMIT` (8000 字符 / 8KB)

**含义**：测试结果的最大长度，用于存储测试/验证命令的输出（在 agent_loop 中）。

**用途**：
- 在 `agent_loop.py` 中存储测试/验证命令的输出
- 用于传递给 LLM 以便了解测试结果

**使用位置**：
- `atloop/orchestrator/agent_loop.py` - 处理测试结果时

**影响**：
- ✅ **为什么需要 8KB**：测试输出可能包含多个测试用例的结果，需要足够空间
- ✅ **太大**：浪费 token
- ✅ **太小**：可能丢失测试失败的关键信息

---

### 11. `TEST_RESULTS_LIMIT_CONTEXT` (5000 字符 / 5KB)

**含义**：测试结果的最大长度，用于在 context_pack 中（比 agent_loop 中的限制小）。

**用途**：
- 在 `context_pack.py` 中存储测试结果
- 比 `TEST_RESULTS_LIMIT` 小，因为 context pack 需要包含更多其他信息

**使用位置**：
- `atloop/retrieval/context_pack.py` - 构建上下文包时

**影响**：
- ✅ **为什么比 agent_loop 中的小**：context pack 需要包含更多信息，所以测试结果限制更小
- ✅ **太大**：占用过多 context pack 空间
- ✅ **太小**：可能丢失测试失败的关键信息

---

### 12. `CONTEXT_PACK_MAX_SIZE` (100 * 1024 字节 / 100KB)

**含义**：上下文包的最大总大小（字节数）。

**用途**：
- 限制整个上下文包的大小
- 防止上下文包过大导致 prompt 超过 API 限制

**使用位置**：
- `atloop/retrieval/context_pack.py` - 构建上下文包时检查总大小

**影响**：
- ✅ **为什么需要 100KB**：上下文包包含多个部分（错误、diff、测试结果等），需要足够空间
- ✅ **太大**：可能导致 prompt 超过 API 限制（如 32k token）
- ✅ **太小**：可能无法包含足够的上下文信息

**示例**：
```python
if total_size > CONTEXT_PACK_MAX_SIZE:
    # 截断或压缩内容
    truncate_context_pack()
```

---

## 三、记忆摘要（Memory Summary）限制

### 13. `MEMORY_SUMMARY_DEFAULT_LIMIT` (32000 字符 / 32KB)

**含义**：记忆摘要的默认最大长度（字符数）。

**用途**：
- 用于限制记忆摘要的长度
- 这是传递给 LLM 的长期记忆摘要的最大大小

**使用位置**：
- `atloop/orchestrator/agent_loop.py` - 调用 `MemorySummarizer.summarize()` 时
- `atloop/memory/summarizer.py` - 生成记忆摘要时

**影响**：
- ✅ **为什么需要 32KB**：长期记忆可能包含很多信息（计划、决策、里程碑等），需要足够空间
- ✅ **太大**：可能导致 prompt 超过 API 限制
- ✅ **太小**：可能丢失重要记忆，导致 LLM 重复执行已完成的任务

**示例**：
```python
memory_summary = MemorySummarizer.summarize(state, max_length=32000)
```

---

### 14. `MEMORY_SUMMARY_MIN_EFFECTIVE_LIMIT` (8000 字符 / 8KB)

**含义**：记忆摘要的最小有效长度，确保至少保留这么多字符。

**用途**：
- 确保至少保留这么多字符，以包含工具执行结果
- 即使设置了较小的 `max_length`，也会至少保留这么多字符

**使用位置**：
- `atloop/memory/summarizer.py` - 智能截断时确保至少保留此大小

**影响**：
- ✅ **为什么需要 8KB**：需要确保工具执行结果等重要信息不会被完全截断
- ✅ **太大**：可能强制保留过多信息，导致截断失效
- ✅ **太小**：可能仍然丢失关键信息

**示例**：
```python
effective_max_length = max(max_length, MEMORY_SUMMARY_MIN_EFFECTIVE_LIMIT)  # 至少 8KB
```

---

### 15. `MEMORY_SUMMARY_STDOUT_STDERR_SHELL` (8000 字符 / 8KB)

**含义**：在记忆摘要中显示 shell 命令的 stdout/stderr 限制。

**用途**：
- 用于在记忆摘要中显示 shell 命令的输出
- 比普通输出限制大，因为记忆摘要需要保留更多上下文

**使用位置**：
- `atloop/memory/summarizer.py` - 生成记忆摘要时显示工具执行结果

**影响**：
- ✅ **为什么需要 8KB**：记忆摘要需要保留足够的工具执行结果，以便 LLM 了解历史操作
- ✅ **太大**：浪费 token
- ✅ **太小**：可能丢失重要执行结果

---

### 16. `MEMORY_SUMMARY_STDOUT_STDERR_OTHER` (2000 字符 / 2KB)

**含义**：在记忆摘要中显示其他工具（非 shell）的输出限制。

**用途**：
- 用于在记忆摘要中显示非 shell 工具的输出
- 比 shell 命令小，因为其他工具的输出通常更短

**使用位置**：
- `atloop/memory/summarizer.py` - 生成记忆摘要时显示工具执行结果

**影响**：
- ✅ **为什么只需要 2KB**：非 shell 工具的输出通常是简单的确认消息
- ✅ **太大**：浪费 token
- ✅ **太小**：可能丢失重要错误信息

---

### 17. `MEMORY_SUMMARY_STDERR_TAIL` (2000 字符 / 2KB)

**含义**：在记忆摘要中显示最后错误的 stderr 尾部限制。

**用途**：
- 用于在记忆摘要中显示最后错误的 stderr 尾部
- 比 `STDERR_TAIL_LIMIT` 小，因为记忆摘要需要包含更多其他信息

**使用位置**：
- `atloop/memory/summarizer.py` - 生成记忆摘要时显示最后错误

**影响**：
- ✅ **为什么只需要 2KB**：记忆摘要需要包含很多其他信息，所以 stderr 尾部限制较小
- ✅ **太大**：占用过多记忆摘要空间
- ✅ **太小**：可能丢失关键错误信息

---

### 18. `MEMORY_SUMMARY_LAST_ERROR_STDOUT_STDERR_SHELL` (8000 字符 / 8KB)

**含义**：在记忆摘要中显示最后错误的完整输出限制（Shell 命令）。

**用途**：
- 用于在记忆摘要中显示最后错误的完整输出（shell 命令）
- 比普通输出限制大，因为最后错误通常是最重要的

**使用位置**：
- `atloop/memory/summarizer.py` - 生成记忆摘要时显示最后错误

**影响**：
- ✅ **为什么需要 8KB**：最后错误通常是最重要的，需要足够空间显示完整信息
- ✅ **太大**：占用过多记忆摘要空间
- ✅ **太小**：可能丢失关键错误信息

---

### 19. `MEMORY_SUMMARY_LAST_ERROR_STDOUT_STDERR_OTHER` (8000 字符 / 8KB)

**含义**：在记忆摘要中显示最后错误的完整输出限制（其他工具）。

**用途**：
- 用于在记忆摘要中显示最后错误的完整输出（非 shell 工具）
- 与 shell 命令相同，因为最后错误同样重要

**使用位置**：
- `atloop/memory/summarizer.py` - 生成记忆摘要时显示最后错误

**影响**：
- ✅ **为什么需要 8KB**：最后错误通常是最重要的，需要足够空间显示完整信息
- ✅ **太大**：占用过多记忆摘要空间
- ✅ **太小**：可能丢失关键错误信息

---

## 四、验证器（Verifier）限制

### 20. `VERIFIER_ERROR_SUMMARY_LIMIT` (8000 字符 / 8KB)

**含义**：从验证输出中提取错误摘要的最大长度。

**用途**：
- 用于从验证输出中提取错误摘要
- 需要足够大以包含完整的 ImportError traceback

**使用位置**：
- `atloop/orchestrator/verifier.py` - 提取验证错误时

**影响**：
- ✅ **为什么需要 8KB**：Python traceback 可能很长，需要足够空间
- ✅ **太大**：浪费 token
- ✅ **太小**：可能截断关键错误信息

---

### 21. `VERIFIER_ERROR_LINES_MAX` (30 行)

**含义**：从验证输出中提取错误相关的最大行数。

**用途**：
- 用于从验证输出中提取错误相关的行数
- 限制提取的行数，避免提取过多无关内容

**使用位置**：
- `atloop/orchestrator/verifier.py` - 提取错误行时

**影响**：
- ✅ **为什么需要 30 行**：通常错误信息在 traceback 的前 30 行内
- ✅ **太大**：可能包含过多无关内容
- ✅ **太小**：可能丢失关键错误行

---

### 22. `VERIFIER_ERROR_SIGNATURE_LINE_LIMIT` (200 字符)

**含义**：提取错误签名时的单行最大长度。

**用途**：
- 用于提取错误签名时的单行限制
- 错误签名通常是一行，但可能很长

**使用位置**：
- `atloop/orchestrator/verifier.py` - 提取错误签名时

**影响**：
- ✅ **为什么需要 200 字符**：错误签名可能包含长路径和函数名
- ✅ **太大**：浪费空间
- ✅ **太小**：可能截断错误签名

---

## 五、事件日志（Event Logger）限制

### 23. `EVENT_LOGGER_OUTPUT_LIMIT_NORMAL` (8000 字符 / 8KB)

**含义**：在事件日志中存储工具输出的最大长度。

**用途**：
- 用于在事件日志中存储工具输出
- 事件日志用于记录和调试，不需要完整输出

**使用位置**：
- `atloop/logging/event_logger.py` - 记录工具输出时

**影响**：
- ✅ **为什么需要 8KB**：需要足够空间记录关键输出，但不需要完整输出
- ✅ **太大**：事件日志文件会变得很大
- ✅ **太小**：可能丢失关键输出信息

---

### 24. `EVENT_LOGGER_PROMPT_PREVIEW_LIMIT` (2000 字符 / 2KB)

**含义**：在事件日志中存储 prompt 预览的最大长度。

**用途**：
- 用于在事件日志中存储 prompt 预览
- 只存储 prompt 的开头部分，用于调试

**使用位置**：
- `atloop/logging/event_logger.py` - 记录 prompt 预览时

**影响**：
- ✅ **为什么只需要 2KB**：prompt 预览只需要显示开头部分，用于调试
- ✅ **太大**：事件日志文件会变得很大
- ✅ **太小**：可能无法看到 prompt 的关键部分

---

## 六、报告生成（Report Generator）限制

### 25. `REPORT_DIFF_LIMIT` (5000 字符 / 5KB)

**含义**：在生成的报告中显示 diff 的最大长度。

**用途**：
- 用于在生成的报告中显示 diff
- 报告通常不需要完整的 diff，只需要关键变更

**使用位置**：
- `atloop/logging/report.py` - 生成报告时

**影响**：
- ✅ **为什么需要 5KB**：需要足够空间显示关键变更
- ✅ **太大**：报告会变得很长
- ✅ **太小**：可能丢失重要变更信息

---

### 26. `REPORT_TEST_RESULTS_LIMIT` (2000 字符 / 2KB)

**含义**：在生成的报告中显示测试结果的最大长度。

**用途**：
- 用于在生成的报告中显示测试结果
- 报告通常只需要测试结果的摘要

**使用位置**：
- `atloop/logging/report.py` - 生成报告时

**影响**：
- ✅ **为什么只需要 2KB**：报告只需要测试结果的摘要，不需要完整输出
- ✅ **太大**：报告会变得很长
- ✅ **太小**：可能丢失关键测试信息

---

### 27. `REPORT_STDERR_LIMIT` (1000 字符 / 1KB)

**含义**：在生成的报告中显示 stderr 的最大长度。

**用途**：
- 用于在生成的报告中显示 stderr
- 报告通常只需要 stderr 的摘要

**使用位置**：
- `atloop/logging/report.py` - 生成报告时

**影响**：
- ✅ **为什么只需要 1KB**：报告只需要 stderr 的摘要，不需要完整输出
- ✅ **太大**：报告会变得很长
- ✅ **太小**：可能丢失关键错误信息

---

## 七、其他配置限制

### 28. `LOG_FILE_MAX_SIZE_MB` (100 MB)

**含义**：日志文件的最大大小（MB），用于日志轮转。

**用途**：
- 用于日志轮转
- 当日志文件超过此大小时，会进行轮转

**使用位置**：
- 日志系统配置

**影响**：
- ✅ **为什么需要 100MB**：需要足够空间记录日志，但不会无限增长
- ✅ **太大**：日志文件会变得很大，难以查看
- ✅ **太小**：日志轮转过于频繁

---

## 配置关系图

```
工具执行输出
├── STDOUT_STDERR_LIMIT_NORMAL (5KB) - 普通命令
├── STDOUT_STDERR_LIMIT_FILE_VIEW (40KB) - 文件查看命令
└── STDOUT_STDERR_LIMIT_OTHER (2KB) - 其他工具

错误摘要
├── ERROR_SUMMARY_LIMIT_NORMAL (15KB) - 普通命令
├── ERROR_SUMMARY_LIMIT_FILE_VIEW (30KB) - 文件查看命令
└── STDERR_TAIL_LIMIT (5KB) - stderr 尾部

上下文包
├── RECENT_ERROR_LIMIT_NORMAL (10KB) - 普通错误
├── RECENT_ERROR_LIMIT_FILE_CONTENT (25KB) - 包含文件内容的错误
├── DIFF_LIMIT (5KB) - Diff 信息
├── TEST_RESULTS_LIMIT (8KB) - 测试结果（agent_loop）
├── TEST_RESULTS_LIMIT_CONTEXT (5KB) - 测试结果（context_pack）
└── CONTEXT_PACK_MAX_SIZE (100KB) - 上下文包总大小

记忆摘要
├── MEMORY_SUMMARY_DEFAULT_LIMIT (32KB) - 默认最大长度
├── MEMORY_SUMMARY_MIN_EFFECTIVE_LIMIT (8KB) - 最小有效长度
├── MEMORY_SUMMARY_STDOUT_STDERR_SHELL (8KB) - Shell 命令输出
├── MEMORY_SUMMARY_STDOUT_STDERR_OTHER (2KB) - 其他工具输出
├── MEMORY_SUMMARY_STDERR_TAIL (2KB) - stderr 尾部
├── MEMORY_SUMMARY_LAST_ERROR_STDOUT_STDERR_SHELL (8KB) - 最后错误（Shell）
└── MEMORY_SUMMARY_LAST_ERROR_STDOUT_STDERR_OTHER (8KB) - 最后错误（其他）

验证器
├── VERIFIER_ERROR_SUMMARY_LIMIT (8KB) - 错误摘要
├── VERIFIER_ERROR_LINES_MAX (30行) - 错误行数
└── VERIFIER_ERROR_SIGNATURE_LINE_LIMIT (200字符) - 错误签名

事件日志
├── EVENT_LOGGER_OUTPUT_LIMIT_NORMAL (8KB) - 工具输出
└── EVENT_LOGGER_PROMPT_PREVIEW_LIMIT (2KB) - Prompt 预览

报告生成
├── REPORT_DIFF_LIMIT (5KB) - Diff 信息
├── REPORT_TEST_RESULTS_LIMIT (2KB) - 测试结果
└── REPORT_STDERR_LIMIT (1KB) - stderr

其他
└── LOG_FILE_MAX_SIZE_MB (100MB) - 日志文件大小
```

---

## 调整建议

### 如果遇到 "prompt 太大" 错误

1. **减少 `MEMORY_SUMMARY_DEFAULT_LIMIT`**：从 32KB 减少到 24KB 或 16KB
2. **减少 `CONTEXT_PACK_MAX_SIZE`**：从 100KB 减少到 80KB
3. **减少 `MEMORY_SUMMARY_STDOUT_STDERR_SHELL`**：从 8KB 减少到 4KB

### 如果遇到 "丢失重要信息" 问题

1. **增加 `ERROR_SUMMARY_LIMIT_NORMAL`**：从 15KB 增加到 20KB
2. **增加 `MEMORY_SUMMARY_MIN_EFFECTIVE_LIMIT`**：从 8KB 增加到 10KB
3. **增加 `STDERR_TAIL_LIMIT`**：从 5KB 增加到 8KB

### 如果遇到 "token 使用过多" 问题

1. **减少所有限制**：按比例减少所有限制（如减少 20%）
2. **优先减少**：
   - `MEMORY_SUMMARY_DEFAULT_LIMIT`
   - `CONTEXT_PACK_MAX_SIZE`
   - `STDOUT_STDERR_LIMIT_FILE_VIEW`

---

## 总结

所有限制配置都有明确的用途和影响：

- ✅ **工具执行输出限制**：控制命令输出的截断
- ✅ **错误摘要限制**：控制错误信息的保留
- ✅ **上下文包限制**：控制传递给 LLM 的上下文大小
- ✅ **记忆摘要限制**：控制长期记忆的大小
- ✅ **验证器限制**：控制验证错误的提取
- ✅ **事件日志限制**：控制日志文件的大小
- ✅ **报告生成限制**：控制报告文件的大小

**关键原则**：
1. 文件查看命令需要更大的限制（40KB vs 5KB）
2. 错误信息需要更大的限制（15KB vs 5KB）
3. 记忆摘要需要最大的限制（32KB）
4. 报告和日志只需要较小的限制（1-5KB）
