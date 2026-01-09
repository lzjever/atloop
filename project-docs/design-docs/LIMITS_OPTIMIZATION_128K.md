# Limits 配置优化报告 - 128k+8k Token 上下文

## 优化概述

根据 **128k token 输入 + 8k token 输出 = 136k token 总上下文**，对 limits 配置进行了全面优化。

## 上下文分配策略

### 总上下文：136k tokens ≈ 544k 字符（按 1 token ≈ 4 字符估算）

主要组件大小估算：
1. **系统 prompt + 工具描述**：~20-30k 字符（4-6%）
2. **记忆摘要（长期记忆）**：~64k 字符（12.5%）
3. **上下文包（错误、diff、测试结果等）**：~200k 字符（39%）
4. **工具输出（当前执行）**：~60k 字符（12%）
5. **历史对话等**：~200k 字符（39%）

## 优化详情

### 1. 工具执行输出限制

| 配置项 | 原值 | 优化值 | 变化 | 原因 |
|--------|------|--------|------|------|
| `STDOUT_STDERR_LIMIT_NORMAL` | 5KB | **8KB** | +60% | 可以保留更多命令输出 |
| `STDOUT_STDERR_LIMIT_FILE_VIEW` | 40KB | **60KB** | +50% | 可以查看更大的文件 |
| `STDOUT_STDERR_LIMIT_OTHER` | 2KB | 2KB | - | 其他工具输出通常很短 |
| `ERROR_SUMMARY_LIMIT_NORMAL` | 15KB | **25KB** | +67% | 确保完整错误信息（包括长 traceback） |
| `ERROR_SUMMARY_LIMIT_FILE_VIEW` | 30KB | **50KB** | +67% | 文件查看错误可能包含大量文件内容 |
| `STDERR_TAIL_LIMIT` | 5KB | **10KB** | +100% | 错误信息通常在尾部 |

### 2. 上下文包限制

| 配置项 | 原值 | 优化值 | 变化 | 原因 |
|--------|------|--------|------|------|
| `RECENT_ERROR_LIMIT_NORMAL` | 10KB | **20KB** | +100% | 可以包含更多错误上下文 |
| `RECENT_ERROR_LIMIT_FILE_CONTENT` | 25KB | **40KB** | +60% | 文件内容错误需要更多空间 |
| `DIFF_LIMIT` | 5KB | **10KB** | +100% | 可以显示更多文件变更 |
| `TEST_RESULTS_LIMIT` | 8KB | **15KB** | +88% | 测试输出可能很长 |
| `TEST_RESULTS_LIMIT_CONTEXT` | 5KB | **10KB** | +100% | 与 agent_loop 保持一致 |
| `CONTEXT_PACK_MAX_SIZE` | 100KB | **200KB** | +100% | 充分利用上下文空间 |

### 3. 验证器限制

| 配置项 | 原值 | 优化值 | 变化 | 原因 |
|--------|------|--------|------|------|
| `VERIFIER_ERROR_SUMMARY_LIMIT` | 8KB | **15KB** | +88% | 确保完整 traceback |
| `VERIFIER_ERROR_LINES_MAX` | 30行 | 30行 | - | 通常足够 |
| `VERIFIER_ERROR_SIGNATURE_LINE_LIMIT` | 200字符 | 200字符 | - | 通常足够 |

### 4. 记忆摘要限制（最重要）

| 配置项 | 原值 | 优化值 | 变化 | 原因 |
|--------|------|--------|------|------|
| `MEMORY_SUMMARY_DEFAULT_LIMIT` | 32KB | **64KB** | +100% | 充分利用长期记忆能力（12.5% 的输入上下文） |
| `MEMORY_SUMMARY_MIN_EFFECTIVE_LIMIT` | 8KB | **16KB** | +100% | 确保至少保留足够的关键信息 |
| `MEMORY_SUMMARY_STDOUT_STDERR_SHELL` | 8KB | **12KB** | +50% | 记忆摘要需要保留更多历史操作 |
| `MEMORY_SUMMARY_STDOUT_STDERR_OTHER` | 2KB | **4KB** | +100% | 其他工具的输出也需要更多空间 |
| `MEMORY_SUMMARY_STDERR_TAIL` | 2KB | **5KB** | +150% | 最后错误很重要 |
| `MEMORY_SUMMARY_LAST_ERROR_STDOUT_STDERR_SHELL` | 8KB | **15KB** | +88% | 最后错误需要完整信息 |
| `MEMORY_SUMMARY_LAST_ERROR_STDOUT_STDERR_OTHER` | 8KB | **15KB** | +88% | 最后错误需要完整信息 |

### 5. 事件日志限制

| 配置项 | 原值 | 优化值 | 变化 | 原因 |
|--------|------|--------|------|------|
| `EVENT_LOGGER_OUTPUT_LIMIT_NORMAL` | 8KB | **12KB** | +50% | 事件日志需要记录更多信息 |
| `EVENT_LOGGER_PROMPT_PREVIEW_LIMIT` | 2KB | **4KB** | +100% | 可以预览更多 prompt 内容 |

### 6. 报告生成限制

| 配置项 | 原值 | 优化值 | 变化 | 原因 |
|--------|------|--------|------|------|
| `REPORT_DIFF_LIMIT` | 5KB | **10KB** | +100% | 报告需要显示更多变更 |
| `REPORT_TEST_RESULTS_LIMIT` | 2KB | **5KB** | +150% | 报告需要显示更多测试信息 |
| `REPORT_STDERR_LIMIT` | 1KB | **3KB** | +200% | 报告需要显示更多错误信息 |

## 关键优化点

### 1. 记忆摘要大幅增加（最重要）

- **MEMORY_SUMMARY_DEFAULT_LIMIT**: 32KB → **64KB**（+100%）
  - 这是最重要的优化，充分利用 128k token 的长期记忆能力
  - 64KB 约占总输入上下文的 12.5%，是合理的比例

### 2. 上下文包大幅增加

- **CONTEXT_PACK_MAX_SIZE**: 100KB → **200KB**（+100%）
  - 可以包含更多错误信息、diff、测试结果等
  - 约占总输入上下文的 39%，充分利用上下文空间

### 3. 错误信息限制增加

- 所有错误相关的限制都增加了 50-100%
  - 确保完整错误信息（包括长 traceback）
  - 文件查看错误的限制增加到 50KB

### 4. 工具输出限制适度增加

- 文件查看命令：40KB → **60KB**
- 普通命令：5KB → **8KB**
- 可以查看更大的文件和保留更多输出

## 预期效果

### 优势

1. ✅ **更好的长期记忆**：64KB 的记忆摘要可以保留更多历史操作和决策
2. ✅ **更完整的错误信息**：增加的错误限制可以保留完整的 traceback
3. ✅ **更大的文件处理能力**：60KB 的文件查看限制可以处理更大的文件
4. ✅ **更丰富的上下文**：200KB 的上下文包可以包含更多相关信息

### 注意事项

1. ⚠️ **Prompt 大小监控**：虽然优化了限制，但仍需监控实际 prompt 大小
2. ⚠️ **400 错误处理**：如果遇到 400 错误，系统会自动减少 memory summary 大小
3. ⚠️ **Token 使用**：虽然上下文很大，但仍需注意 token 使用效率

## 调整建议

### 如果仍然遇到 "prompt 太大" 错误

1. **减少 `MEMORY_SUMMARY_DEFAULT_LIMIT`**：从 64KB 减少到 48KB
2. **减少 `CONTEXT_PACK_MAX_SIZE`**：从 200KB 减少到 150KB
3. **减少 `STDOUT_STDERR_LIMIT_FILE_VIEW`**：从 60KB 减少到 50KB

### 如果遇到 "丢失重要信息" 问题

1. **检查实际使用情况**：查看日志中的实际 prompt 大小
2. **适当增加限制**：如果确实需要更多信息，可以进一步增加
3. **优化压缩策略**：确保 memory 压缩机制正常工作

## 总结

所有配置已针对 **128k+8k token 上下文**进行了优化：

- ✅ **记忆摘要**：从 32KB 增加到 **64KB**（最重要）
- ✅ **上下文包**：从 100KB 增加到 **200KB**
- ✅ **错误信息**：所有错误限制增加 50-100%
- ✅ **工具输出**：文件查看从 40KB 增加到 **60KB**
- ✅ **其他限制**：适度增加以充分利用上下文空间

这些优化应该能够充分利用 128k token 的上下文能力，同时保持合理的 token 使用效率。
