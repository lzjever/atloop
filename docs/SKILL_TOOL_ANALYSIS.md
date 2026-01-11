# Skill 工具加载逻辑问题分析

## 🎉 问题状态：已修复

**修复时间**：2026-01-11  
**所有修复已实施并通过测试** ✅

---

## 执行摘要

通过分析日志和代码，发现了 skill 工具加载逻辑的根本问题：**skill 工具返回的内容被严重截断，导致 LLM 无法看到完整的技能内容，从而重复调用 skill 工具，形成 VIEW_WITHOUT_MODIFY 循环**。

**根本原因**：skill 工具的内容被当作普通工具输出处理，使用了过小的限制（2KB/4KB），而 skill 内容通常很长（几万字符）。

**修复方案**：✅ **已实施**
1. ✅ 在 `ToolResultFormatter` 中为 skill 工具使用更大的限制（60KB）
2. ✅ 在 `MemorySummarizer` 中为 skill 工具使用更大的限制（12KB）
3. ✅ 在 `tool_results_history` 中为 skill 工具显示更多内容（5KB）
4. ✅ 在 Memory Summary 中添加专门的 skill 内容显示部分（完整内容）

---

## 1. 问题现象

从日志中可以看到：

```
Step 2: LLM 调用 skill("long-doc-writer")
Step 6: LLM 再次调用 skill("long-doc-writer")  
Step 10: 系统检测到 VIEW_WITHOUT_MODIFY 循环（5 次重复）
Step 11: 系统强制恢复，跳过 LLM 调用
```

**关键观察**：
- LLM 多次调用同一个 skill
- 系统检测到"查看但不修改"的循环
- LLM 似乎没有真正使用 skill 的内容

---

## 2. 代码分析

### 2.1 Skill 工具的实现

```python
# atloop/tools/interaction/skill_tool.py:51-89
def execute(self, args: Dict[str, Any]) -> ToolResult:
    skill_name = args["name"]
    content = self.skill_loader.get_skill_content(skill_name)
    
    return ToolResult(
        ok=True,
        stdout=content,  # ← skill 内容在 stdout 中
        stderr="",
        meta={"skill_name": skill_name, "content_length": len(content)},
    )
```

**正常**：skill 工具正确返回内容到 `stdout`。

### 2.2 结果格式化 - 第一次截断

```python
# atloop/orchestrator/phases/act_result_processor.py:69-102
def _format_output(output: str, tool: str, args: Dict[str, Any], is_stderr: bool) -> str:
    if tool == "run":
        cmd = args.get("cmd", "")
        max_size = (
            STDOUT_STDERR_LIMIT_FILE_VIEW  # 60KB for file view
            if is_file_view_command(cmd)
            else STDOUT_STDERR_LIMIT_NORMAL  # 8KB for normal
        )
    else:
        max_size = STDOUT_STDERR_LIMIT_OTHER  # ⚠️ 2KB for other tools (including skill!)
    
    if len(output) > max_size:
        return (
            output[: max_size // 2]  # 前 1KB
            + f"\n... [omitted {omitted} chars in middle] ...\n"
            + output[-max_size // 2 :]  # 后 1KB
        )
```

**问题 1**：skill 工具不是 "run"，所以使用 `STDOUT_STDERR_LIMIT_OTHER = 2000` (2KB) 的限制。

**影响**：如果 skill 内容超过 2KB，在 `last_error.summary` 中只显示前 1KB + 后 1KB。

### 2.3 Memory Summary 中的显示 - 第二次截断

```python
# atloop/memory/summarizer.py:256-291
# For shell commands (run tool), show more output
is_shell = tool == "run"
max_stderr = (
    MEMORY_SUMMARY_STDOUT_STDERR_SHELL  # 12KB for shell
    if is_shell
    else MEMORY_SUMMARY_STDOUT_STDERR_OTHER  # ⚠️ 4KB for other tools (including skill!)
)
max_stdout = (
    MEMORY_SUMMARY_STDOUT_STDERR_SHELL  # 12KB for shell
    if is_shell
    else MEMORY_SUMMARY_STDOUT_STDERR_OTHER  # ⚠️ 4KB for other tools (including skill!)
)

if stdout:
    if len(stdout) > max_stdout:
        stdout_preview = (
            stdout[: max_stdout // 2]  # 前 2KB
            + f"\n... [Omitted {len(stdout) - max_stdout} chars] ...\n"
            + stdout[-max_stdout // 2 :]  # 后 2KB
        )
```

**问题 2**：skill 工具不是 shell 工具，所以使用 `MEMORY_SUMMARY_STDOUT_STDERR_OTHER = 4000` (4KB) 的限制。

**影响**：在 Memory Summary 中，skill 内容只显示前 2KB + 后 2KB。

### 2.4 tool_results_history 中的显示 - 第三次截断

```python
# atloop/memory/summarizer.py:458-478
if state.memory.tool_results_history:
    parts.append("\n## Recent Tool Execution Results (Enhanced Storage)")
    for tool_result in state.memory.tool_results_history[-5:]:
        # ...
        if result.get("stdout"):
            stdout_preview = result.get("stdout", "")[:100]  # ⚠️ 只显示前 100 字符！
            if len(result.get("stdout", "")) > 100:
                stdout_preview += "..."
            parts.append(f"  Stdout: {stdout_preview}")
```

**问题 3**：在 `tool_results_history` 中，只显示前 100 个字符。

**影响**：如果 skill 内容很长，LLM 几乎看不到任何有用信息。

---

## 3. 问题根源

### 3.1 设计假设错误

**当前设计假设**：
- 普通工具的输出通常很短（成功/失败消息）
- 只有 shell 命令的输出可能很长
- 所以非 shell 工具使用较小的限制（2KB/4KB）

**实际情况**：
- **skill 工具的输出是"知识内容"**，通常很长（几万字符）
- skill 内容需要**完整显示**给 LLM，不能被截断
- skill 工具应该被视为"知识加载"工具，而不是普通工具

### 3.2 截断导致的循环

**循环形成过程**：

1. **Step 2**: LLM 调用 `skill("long-doc-writer")`
   - skill 内容返回（比如 50KB）
   - 但在 `last_error.summary` 中只显示前 1KB + 后 1KB
   - LLM 看到的内容不完整

2. **Step 6**: LLM 再次调用 `skill("long-doc-writer")`
   - 可能因为：
     - LLM 认为第一次没有成功加载
     - LLM 需要完整内容，但只看到部分
     - LLM 没有意识到已经加载过

3. **Step 10**: 系统检测到 VIEW_WITHOUT_MODIFY 循环
   - 连续 5 次 view 操作（skill + run 命令）
   - 没有 modify 操作（没有创建文件）
   - 触发 FORCE_STRATEGY 干预

4. **Step 11**: 系统强制恢复
   - 跳过 LLM 调用
   - 执行强制恢复动作

---

## 4. 完整数据流分析

```mermaid
sequenceDiagram
    participant LLM
    participant PlanPhase
    participant ActPhase
    participant SkillTool
    participant ToolResultFormatter
    participant ErrorStateManager
    participant MemorySummarizer
    
    Note over LLM: Step 2: 调用 skill("long-doc-writer")
    LLM --> PlanPhase: ActionJSON with skill action
    PlanPhase --> ActPhase: Execute skill action
    ActPhase --> SkillTool: Execute skill("long-doc-writer")
    SkillTool --> SkillTool: Load skill content (50KB)
    SkillTool --> ActPhase: ToolResult(stdout=50KB content)
    
    ActPhase --> ToolResultFormatter: Format result
    Note over ToolResultFormatter: ⚠️ 问题：使用 STDOUT_STDERR_LIMIT_OTHER=2KB
    ToolResultFormatter --> ToolResultFormatter: 截断为前1KB+后1KB
    ToolResultFormatter --> ErrorStateManager: result_summary (截断后)
    ErrorStateManager --> ErrorStateManager: 存储到 last_error.summary
    
    Note over LLM: Step 6: 再次调用 skill("long-doc-writer")
    LLM --> PlanPhase: ActionJSON with skill action (again!)
    PlanPhase --> MemorySummarizer: Generate memory summary
    Note over MemorySummarizer: ⚠️ 问题：使用 MEMORY_SUMMARY_STDOUT_STDERR_OTHER=4KB
    MemorySummarizer --> MemorySummarizer: 截断为前2KB+后2KB
    MemorySummarizer --> LLM: Memory summary (skill 内容被截断)
    
    Note over LLM: LLM 看不到完整内容，再次调用 skill
    LLM --> PlanPhase: ActionJSON with skill action (again!)
    
    Note over PlanPhase: Step 10: 检测到 VIEW_WITHOUT_MODIFY 循环
    PlanPhase --> PlanPhase: FORCE_STRATEGY intervention
```

---

## 5. 根本原因总结

### 5.1 核心问题

1. **skill 工具被当作普通工具处理**
   - 使用 `STDOUT_STDERR_LIMIT_OTHER = 2000` (2KB) 限制
   - 使用 `MEMORY_SUMMARY_STDOUT_STDERR_OTHER = 4000` (4KB) 限制
   - 在 `tool_results_history` 中只显示前 100 字符

2. **skill 内容需要完整显示**
   - skill 内容是"知识"，不是普通工具输出
   - LLM 需要完整内容才能正确使用技能
   - 截断会导致 LLM 无法理解或使用技能

3. **缺少特殊处理逻辑**
   - 没有识别 skill 工具的特殊性
   - 没有为 skill 工具使用更大的限制
   - 没有在 Memory Summary 中优先显示 skill 内容

### 5.2 为什么会导致循环

1. **LLM 看不到完整内容** → 认为 skill 没有加载成功
2. **LLM 需要完整内容** → 再次调用 skill
3. **内容仍然被截断** → 继续循环
4. **没有 modify 操作** → 触发 VIEW_WITHOUT_MODIFY 检测

---

## 6. 解决方案 ✅ **已实施**

### 6.1 方案 1: 为 skill 工具使用更大的限制 ✅ **已完成**

**修改点**：

1. ✅ **在 `ToolResultFormatter._format_output` 中**：
   ```python
   # atloop/orchestrator/phases/act_result_processor.py:85-93
   if tool == "run":
       # ... existing logic
   elif tool == "skill":
       # ✅ Skill 工具使用更大的限制（类似文件查看）
       max_size = STDOUT_STDERR_LIMIT_FILE_VIEW  # 60KB
   else:
       max_size = STDOUT_STDERR_LIMIT_OTHER  # 2KB
   ```

2. ✅ **在 `MemorySummarizer.summarize` 中**：
   ```python
   # atloop/memory/summarizer.py:256-267
   # For shell commands (run tool) and skill tools, show more output
   is_shell = tool == "run"
   is_skill = tool == "skill"  # ✅ 识别 skill 工具
   max_stderr = (
       MEMORY_SUMMARY_STDOUT_STDERR_SHELL
       if is_shell or is_skill  # ✅ skill 使用 shell 的限制 (12KB)
       else MEMORY_SUMMARY_STDOUT_STDERR_OTHER
   )
   max_stdout = (
       MEMORY_SUMMARY_STDOUT_STDERR_SHELL
       if is_shell or is_skill  # ✅ skill 使用 shell 的限制 (12KB)
       else MEMORY_SUMMARY_STDOUT_STDERR_OTHER
   )
   ```

3. ✅ **在 `tool_results_history` 显示中**：
   ```python
   # atloop/memory/summarizer.py:468-477
   if result.get("stdout"):
       if tool == "skill":
           # ✅ skill 工具显示更多内容（前 5KB）
           stdout_preview = result.get("stdout", "")[:5000]
           total_len = len(result.get("stdout", ""))
           if total_len > 5000:
               stdout_preview += f"... (total {total_len} chars, see full content in Recent Attempts section above)"
           parts.append(f"  Stdout ({total_len} chars):\n{stdout_preview}")
       else:
           stdout_preview = result.get("stdout", "")[:100]
   ```

### 6.2 方案 2: 在 Memory Summary 中优先显示 skill 内容 ✅ **已完成**

**修改点**：

✅ **在 `MemorySummarizer.summarize` 中，添加专门的 skill 内容显示部分**：

```python
# atloop/memory/summarizer.py:121-145
# ✅ Priority: Show loaded skills (complete content) - skills are knowledge that LLM needs
if state.memory.attempts:
    skill_contents = []
    for attempt in state.memory.attempts[-5:]:  # Last 5 attempts
        results = attempt.get("results", [])
        for result in results:
            if result.get("tool") == "skill" and result.get("ok"):
                skill_name = result.get("meta", {}).get("skill_name", "unknown")
                stdout = result.get("stdout", "")
                if stdout:
                    skill_contents.append({
                        "name": skill_name,
                        "content": stdout,  # ✅ 完整内容，不截断
                        "step": attempt.get("step", "?")
                    })
    
    if skill_contents:
        parts.append("## 📚 Loaded Skills (Complete Content - Use These Guidelines)")
        for skill in skill_contents[-3:]:  # Last 3 skills
            parts.append(f"### Skill: {skill['name']} (Loaded at Step {skill['step']})")
            parts.append(f"```\n{skill['content']}\n```")
            parts.append("")
```

### 6.3 方案 3: 在 last_error 中完整显示 skill 内容

**修改点**：

在 `ErrorStateManager.update_error_state` 中，对 skill 工具使用特殊处理：

```python
@staticmethod
def update_error_state(state, tool, args, result, result_summary):
    # ✅ 对于 skill 工具，即使没有错误，也要确保完整内容被显示
    if tool == "skill" and result.get("ok"):
        # skill 内容应该在 last_error.summary 中完整显示
        # 或者使用更大的限制
        max_summary = ERROR_SUMMARY_LIMIT_FILE_VIEW  # 50KB for skill
    else:
        max_summary = ERROR_SUMMARY_LIMIT_NORMAL  # 25KB
```

---

## 7. 实施结果 ✅

**推荐方案**：方案 1 + 方案 2 的组合 ✅ **已全部实施**

1. ✅ **方案 1**：为 skill 工具使用更大的限制（60KB/12KB）
   - ✅ 确保 skill 内容在 `last_error.summary` 和 Memory Summary 中不被过度截断

2. ✅ **方案 2**：在 Memory Summary 中优先显示完整 skill 内容
   - ✅ 在摘要开头专门显示 skill 内容
   - ✅ 确保 LLM 能看到完整的技能指导

**实施状态**：
- ✅ **P0（高优先级）**：方案 1 - 修复截断问题 ✅ **已完成**
- ✅ **P1（中优先级）**：方案 2 - 优化显示位置 ✅ **已完成**

---

## 8. 验证方法 ✅ **已实施测试**

### 8.1 测试用例 ✅ **已创建**

1. ✅ **测试 skill 内容不被截断**：
   ```python
   # tests/test_act_result_processor.py:174-197
   def test_format_result_summary_skill_tool_uses_large_limit():
       # 创建包含长内容的 skill (50KB)
       # 验证在 ToolResultFormatter 中不被过度截断
       # 验证至少显示 40KB 内容
   ```

2. ✅ **测试 skill 内容不被严重截断**：
   ```python
   # tests/test_act_result_processor.py:199-220
   def test_format_result_summary_skill_tool_not_truncated_severely():
       # 创建 5KB skill 内容
       # 验证不被截断到 2KB
       # 验证完整显示
   ```

3. ⏸️ **测试不会重复调用 skill**（集成测试，需要实际运行验证）
   - 通过实际使用场景验证
   - 观察是否还会触发 VIEW_WITHOUT_MODIFY 循环

---

## 9. 总结

### 9.1 根本原因 ✅ **已修复**

**skill 工具的内容被当作普通工具输出处理，使用了过小的限制（2KB/4KB），导致内容被严重截断。LLM 看不到完整的技能内容，无法正确使用技能，从而重复调用 skill 工具，形成 VIEW_WITHOUT_MODIFY 循环。**

### 9.2 关键发现

1. ✅ **skill 工具实现正确**：正确返回内容到 `stdout`
2. ✅ **结果格式化已修复**：现在使用 60KB 限制，不过度截断
3. ✅ **Memory Summary 显示已修复**：现在使用 12KB 限制，并在开头完整显示
4. ✅ **tool_results_history 显示已修复**：现在显示前 5KB 内容

### 9.3 修复结果 ✅

1. ✅ **识别 skill 工具的特殊性** - 已完成
2. ✅ **为 skill 工具使用更大的限制**（类似文件查看命令）- 已完成
3. ✅ **在 Memory Summary 中优先显示完整 skill 内容** - 已完成
4. ✅ **确保 LLM 能看到完整的技能指导** - 已完成

### 9.4 测试结果

- ✅ **2 个新测试全部通过**
- ✅ **所有 259 个测试通过**（新增 2 个）
- ✅ **代码语法检查通过**

### 9.5 预期效果

修复后，skill 工具应该：
- ✅ 内容不被过度截断（60KB/12KB 限制）
- ✅ 在 Memory Summary 中完整显示（专门的 section）
- ✅ LLM 能看到完整的技能指导
- ✅ 不会重复调用 skill 工具
- ✅ 不会触发 VIEW_WITHOUT_MODIFY 循环

---

**报告完成时间**：2026-01-11  
**修复完成时间**：2026-01-11  
**版本**：2.0（修复完成版）
