# Memory 模块重构开发计划

## 文档说明

本文档提供 Memory 模块重构的详细开发计划。开发团队必须严格按照此计划执行，每个阶段完成后必须通过测试才能进入下一阶段。

**参考文档**：
- 格式设计：`docs/MEMORY_PROMPT_FORMAT_DEMO.md`
- 架构设计：`docs/MEMORY_REFACTORING_PLAN.md`

**开发原则**：
1. 每个阶段必须通过测试才能进入下一阶段
2. 测试用例必须严格验证设计逻辑，不允许妥协
3. 删除不再需要的旧文件
4. 保持文件结构清晰，单个文件不超过 500 行
5. 模块职责单一，接口明确

---

## 阶段 0：准备阶段

### 0.1 创建测试基础设施

**目标**：建立测试框架，确保后续阶段可以验证功能

**步骤**：

1. **创建测试目录结构**
   ```
   atloop/tests/memory/
   ├── __init__.py
   ├── test_state.py
   ├── test_formatter.py
   ├── test_compression_policy.py
   ├── fixtures/
   │   ├── __init__.py
   │   ├── sample_state.py  # 提供测试用的 AgentState 实例
   │   └── sample_memory.py  # 提供测试用的 Memory 实例
   └── test_integration.py
   ```

2. **创建测试工具函数**
   - 文件：`atloop/tests/memory/fixtures/sample_state.py`
   - 内容：提供创建测试用 AgentState 的工厂函数
   - 要求：
     - 函数名：`create_sample_state(step: int, ...) -> AgentState`
     - 支持创建不同阶段的 state（早期、中期、后期）
     - 支持创建包含错误的 state
     - 支持创建包含文件修改的 state

3. **创建测试辅助函数**
   - 文件：`atloop/tests/memory/test_helpers.py`
   - 内容：提供测试辅助函数
   - 函数：
     - `assert_memory_format_valid(text: str)` - 验证格式是否符合设计
     - `extract_sections(text: str) -> Dict[str, str]` - 提取各个 section
     - `count_tool_results(text: str) -> int` - 统计工具结果数量

**验证标准**：
- [ ] 测试目录结构创建完成
- [ ] 可以成功导入所有测试模块
- [ ] 测试工具函数可以正常工作

**预计时间**：0.5 天

---

## 阶段 1：移除重复显示（高优先级）

### 1.1 目标

移除 `summarizer.py` 中工具执行结果的重复显示，只保留一个统一的显示位置。

### 1.2 具体步骤

#### 步骤 1.1：分析当前代码结构

**输入**：`atloop/atloop/memory/summarizer.py`

**任务**：
1. 标记需要删除的代码段：
   - Line 302-374: `## Recent Attempts` 中的工具执行详情部分
   - Line 616-674: 第二个 `## Recent Tool Execution Results` 部分
2. 标记需要保留的代码段：
   - Line 541-611: `## Recent Tool Execution Results (Enhanced Storage)` 部分
3. 记录依赖关系：
   - 哪些代码依赖 `attempts` 中的 `results` 字段
   - 哪些代码依赖 `tool_results_history`

**输出**：分析文档（Markdown 格式）

**验证标准**：
- [ ] 所有需要删除的代码段已标记
- [ ] 所有依赖关系已记录
- [ ] 分析文档已创建

**预计时间**：0.5 天

#### 步骤 1.2：创建工具结果格式化函数

**目标**：创建统一的工具结果格式化函数，避免代码重复

**文件**：`atloop/atloop/memory/formatter.py`（新建）

**内容**：

```python
"""Memory formatter for formatting memory data into prompt strings."""

from typing import Any, Dict, List, Optional
from atloop.memory.state import AgentState
from atloop.tools.base import BaseTool
from atloop.tools.output_limit_strategy import OutputLimitStrategy


class ToolResultFormatter:
    """格式化工具执行结果"""
    
    @staticmethod
    def format_single_result(
        tool_result: Dict[str, Any],
        tool_registry: Optional[Any] = None,
        include_full_output: bool = False
    ) -> str:
        """
        格式化单个工具执行结果。
        
        Args:
            tool_result: 工具执行结果字典，格式：
                {
                    "step": int,
                    "tool": str,
                    "args": Dict,
                    "placeholder": Optional[str],
                    "result": Dict
                }
            tool_registry: 工具注册表（用于获取输出限制策略）
            include_full_output: 是否包含完整输出
        
        Returns:
            格式化后的字符串，格式：
            - Step N: [状态] [工具] (参数信息)
              [输出内容]
        """
        # 实现逻辑：
        # 1. 提取基本信息（step, tool, args, result）
        # 2. 构建状态标记（✓ 成功，✗ 失败）
        # 3. 构建标题行（包含 placeholder 或关键参数）
        # 4. 格式化输出（使用 OutputLimitStrategy）
        # 5. 返回格式化字符串
        pass
    
    @staticmethod
    def format_results_list(
        tool_results: List[Dict[str, Any]],
        tool_registry: Optional[Any] = None,
        max_count: int = 5
    ) -> str:
        """
        格式化工具结果列表。
        
        Args:
            tool_results: 工具结果列表
            tool_registry: 工具注册表
            max_count: 最大显示数量
        
        Returns:
            格式化后的字符串，包含多个工具结果
        """
        # 实现逻辑：
        # 1. 取最后 max_count 个结果
        # 2. 对每个结果调用 format_single_result
        # 3. 拼接所有结果
        # 4. 返回完整字符串
        pass
```

**要求**：
- 函数必须完全按照设计文档中的格式输出
- 必须使用 `OutputLimitStrategy` 进行输出截断
- 必须处理所有边界情况（None、空字符串、超长输出等）

**测试要求**：
- 文件：`atloop/tests/memory/test_formatter.py`
- 测试用例：
  1. `test_format_single_result_success()` - 测试成功结果的格式化
  2. `test_format_single_result_failure()` - 测试失败结果的格式化
  3. `test_format_single_result_with_placeholder()` - 测试包含占位符的结果
  4. `test_format_single_result_long_output()` - 测试长输出的截断
  5. `test_format_results_list()` - 测试列表格式化
  6. `test_format_results_list_max_count()` - 测试最大数量限制
  7. `test_format_results_empty()` - 测试空列表

**验证标准**：
- [ ] `ToolResultFormatter` 类创建完成
- [ ] 所有测试用例通过
- [ ] 输出格式完全符合 `MEMORY_PROMPT_FORMAT_DEMO.md` 中的格式
- [ ] 代码覆盖率 >= 90%

**预计时间**：1 天

#### 步骤 1.3：修改 summarizer.py，移除重复显示

**输入**：`atloop/atloop/memory/summarizer.py`

**任务**：

1. **修改 `## Recent Attempts` 部分**（Line 302-374）：
   - 保留文件修改统计
   - 移除 `Tool Execution Details` 部分
   - 修改后的代码：
   ```python
   if state.memory.attempts:
       parts.append("\n## Recent Attempts")
       for attempt in state.memory.attempts[-3:]:
           step = attempt.get("step", "?")
           files = attempt.get("files", [])
           success = attempt.get("success", False)
           status = "Success" if success else "Failed"
           parts.append(f"- Step {step}: Modified {len(files)} files: {status}")
           if files:
               parts.append(f"  Files: {', '.join(files[:5])}")
               if len(files) > 5:
                   parts.append(f"  ... (+{len(files) - 5} more)")
   ```

2. **删除第二个 `## Recent Tool Execution Results` 部分**（Line 616-674）：
   - 完全删除此部分代码
   - 确保没有其他代码依赖此部分

3. **修改 `## Recent Tool Execution Results (Enhanced Storage)` 部分**（Line 541-611）：
   - 重命名为 `## Recent Tool Execution Results`
   - 使用 `ToolResultFormatter.format_results_list()` 替换现有格式化逻辑
   - 修改后的代码：
   ```python
   if state.memory.tool_results_history:
       parts.append("\n## Recent Tool Execution Results")
       formatted = ToolResultFormatter.format_results_list(
           state.memory.tool_results_history,
           tool_registry=tool_registry,
           max_count=5
       )
       parts.append(formatted)
   ```

4. **添加导入**：
   ```python
   from atloop.memory.formatter import ToolResultFormatter
   ```

**验证标准**：
- [ ] 代码修改完成
- [ ] 所有现有测试用例通过（如果有）
- [ ] 运行完整测试套件，确保没有破坏现有功能
- [ ] 检查输出，确认没有重复显示

**预计时间**：1 天

#### 步骤 1.4：更新测试用例

**目标**：确保测试用例验证新的行为

**任务**：

1. **更新现有测试用例**（如果有）：
   - 修改期望的输出格式
   - 移除对重复显示的期望

2. **创建新的集成测试**：
   - 文件：`atloop/tests/memory/test_integration.py`
   - 测试用例：
     - `test_summarizer_no_duplicate_tool_results()` - 验证没有重复显示
     - `test_summarizer_recent_attempts_format()` - 验证 Recent Attempts 格式
     - `test_summarizer_tool_results_format()` - 验证 Tool Results 格式

**验证标准**：
- [ ] 所有测试用例通过
- [ ] 测试覆盖所有修改的代码路径
- [ ] 集成测试验证整体功能

**预计时间**：0.5 天

### 1.3 阶段 1 验收标准

- [ ] 工具执行结果只显示一次
- [ ] 输出格式符合设计文档
- [ ] 所有测试用例通过
- [ ] 代码覆盖率 >= 85%
- [ ] 没有破坏现有功能（运行完整测试套件）

### 1.4 阶段 1 预计时间

总计：3.5 天

---

## 阶段 2：重构数据存储结构

### 2.1 目标

统一使用 `tool_results_history` 作为工具执行结果的唯一数据源，移除 `attempts` 中的 `results` 字段。

### 2.2 具体步骤

#### 步骤 2.1：分析数据写入点

**目标**：找出所有写入 `attempts` 和 `tool_results_history` 的代码位置

**任务**：

1. **搜索代码库**：
   ```bash
   grep -r "attempts.append" atloop/
   grep -r "tool_results_history.append" atloop/
   grep -r "memory.attempts" atloop/
   grep -r "memory.tool_results_history" atloop/
   ```

2. **记录所有写入点**：
   - 文件位置
   - 写入的数据结构
   - 写入时机

3. **分析数据依赖**：
   - 哪些代码读取 `attempts[].results`
   - 哪些代码只读取 `attempts[].files`
   - 哪些代码读取 `tool_results_history`

**输出**：分析文档（Markdown 格式）

**验证标准**：
- [ ] 所有写入点已记录
- [ ] 所有读取点已记录
- [ ] 数据依赖关系已分析

**预计时间**：0.5 天

#### 步骤 2.2：修改 ActPhase，统一数据写入

**输入**：`atloop/atloop/orchestrator/phases/act.py`

**任务**：

1. **修改 `_update_memory_after_execution()` 方法**：
   - 保留 `attempts.append()`，但移除 `results` 字段
   - 确保 `tool_results_history.append()` 包含所有必要信息
   - 在 `tool_results_history` 中添加 `modified_files` 字段

2. **修改后的代码结构**：
   ```python
   def _update_memory_after_execution(
       self,
       state: Any,
       results: List[Dict[str, Any]],
       modified_files: List[str],
       success: bool,
   ) -> None:
       # 记录 attempt（只包含文件修改信息）
       state.memory.attempts.append({
           "step": state.step,
           "files": modified_files,
           "success": success,
           # 移除 results 字段
       })
       
       # 记录工具结果到 tool_results_history（包含所有信息）
       placeholder_info = getattr(state, "_act_phase_placeholder_info", [])
       for i, (result, placeholder_data) in enumerate(zip(results, placeholder_info)):
           tool = placeholder_data["tool"]
           placeholder = placeholder_data["placeholder"]
           args = placeholder_data["args"]
           
           tool_result_record = {
               "step": state.step,
               "tool": tool,
               "args": args if args is not None else {},
               "placeholder": placeholder,
               "result": result,
               "modified_files": modified_files if tool in ["write_file", "edit_file", "append_file"] else [],
           }
           state.memory.tool_results_history.append(tool_result_record)
   ```

**验证标准**：
- [ ] 代码修改完成
- [ ] `attempts` 不再包含 `results` 字段
- [ ] `tool_results_history` 包含所有必要信息
- [ ] 现有测试用例通过（如果有）

**预计时间**：1 天

#### 步骤 2.3：更新 summarizer.py，从 tool_results_history 提取文件修改信息

**输入**：`atloop/atloop/memory/summarizer.py`

**任务**：

1. **修改 `## Recent Attempts` 部分**：
   - 从 `tool_results_history` 提取文件修改信息
   - 按 step 分组
   - 显示每个 step 修改的文件

2. **修改后的代码**：
   ```python
   # 从 tool_results_history 提取文件修改信息
   if state.memory.tool_results_history:
       # 按 step 分组
       step_files = {}
       for tool_result in state.memory.tool_results_history:
           step = tool_result.get("step", 0)
           modified_files = tool_result.get("modified_files", [])
           if modified_files:
               if step not in step_files:
                   step_files[step] = []
               step_files[step].extend(modified_files)
       
       # 显示最近 3 个 step 的文件修改
       if step_files:
           parts.append("\n## Recent File Modifications")
           recent_steps = sorted(step_files.keys(), reverse=True)[:3]
           for step in recent_steps:
               files = list(set(step_files[step]))  # 去重
               parts.append(f"- Step {step}: Modified {len(files)} files")
               if files:
                   parts.append(f"  Files: {', '.join(files[:5])}")
                   if len(files) > 5:
                       parts.append(f"  ... (+{len(files) - 5} more)")
   ```

3. **保留 `attempts` 的向后兼容**（如果需要）：
   - 如果 `attempts` 存在且 `tool_results_history` 为空，使用 `attempts`
   - 添加警告日志

**验证标准**：
- [ ] 代码修改完成
- [ ] 文件修改信息正确提取
- [ ] 输出格式符合设计
- [ ] 测试用例通过

**预计时间**：1 天

#### 步骤 2.4：更新测试用例

**任务**：

1. **创建数据迁移测试**：
   - 文件：`atloop/tests/memory/test_data_migration.py`
   - 测试用例：
     - `test_act_phase_writes_to_tool_results_history()` - 验证写入 tool_results_history
     - `test_act_phase_attempts_no_results()` - 验证 attempts 不包含 results
     - `test_summarizer_extracts_files_from_tool_results()` - 验证从 tool_results_history 提取文件

2. **更新现有测试用例**：
   - 修改期望的数据结构
   - 更新测试数据

**验证标准**：
- [ ] 所有测试用例通过
- [ ] 数据迁移逻辑验证完成

**预计时间**：0.5 天

### 2.3 阶段 2 验收标准

- [ ] `attempts` 不再包含 `results` 字段
- [ ] `tool_results_history` 是工具执行结果的唯一数据源
- [ ] 文件修改信息可以从 `tool_results_history` 正确提取
- [ ] 所有测试用例通过
- [ ] 向后兼容性验证完成（如果有旧数据）

### 2.4 阶段 2 预计时间

总计：3 天

---

## 阶段 3：创建 MemoryFormatter 类

### 3.1 目标

创建 `MemoryFormatter` 类，负责格式化 Memory 数据为 prompt 字符串，按照设计文档中的格式。

### 3.2 具体步骤

#### 步骤 3.1：创建 MemoryFormatter 类结构

**文件**：`atloop/atloop/memory/formatter.py`（扩展现有文件）

**任务**：

1. **创建 `MemoryFormatter` 类**：
   ```python
   class MemoryFormatter:
       """格式化 Memory 数据为 prompt 字符串"""
       
       def __init__(self, tool_registry: Optional[Any] = None):
           self.tool_registry = tool_registry
           self.tool_result_formatter = ToolResultFormatter()
       
       def format(
           self,
           state: AgentState,
           format_options: Optional[Dict[str, Any]] = None
       ) -> str:
           """
           格式化 Memory 数据。
           
           Args:
               state: AgentState 实例
               format_options: 格式选项
                   - tool_results_count: int (默认 5)
                   - steps_summary_count: int (默认 3)
                   - include_file_content: bool (默认 True)
                   - max_file_content_length: int (默认 20000)
           
           Returns:
               格式化后的字符串，格式符合 MEMORY_PROMPT_FORMAT_DEMO.md
           """
           # 实现逻辑
           pass
   ```

2. **创建各个格式化方法**：
   - `_format_critical_warnings()` - 格式化关键警告
   - `_format_task_overview()` - 格式化任务概览
   - `_format_execution_plan()` - 格式化执行计划
   - `_format_important_context()` - 格式化重要上下文
   - `_format_recent_activity()` - 格式化最近活动
   - `_format_tool_execution_results()` - 格式化工具执行结果
   - `_format_modified_files_content()` - 格式化修改的文件内容
   - `_format_current_state()` - 格式化当前状态
   - `_format_next_steps_guidance()` - 格式化下一步指导

**要求**：
- 每个方法必须完全按照设计文档中的格式输出
- 必须处理所有边界情况（None、空列表、超长内容等）
- 必须使用 `OutputLimitStrategy` 进行输出截断

**验证标准**：
- [ ] `MemoryFormatter` 类创建完成
- [ ] 所有格式化方法创建完成
- [ ] 代码可以编译（无语法错误）

**预计时间**：1 天

#### 步骤 3.2：实现各个格式化方法

**任务**：

按照 `MEMORY_PROMPT_FORMAT_DEMO.md` 中的格式，逐个实现各个方法。

**实现顺序**：

1. **`_format_critical_warnings()`**：
   - 输入：`state.memory.created_files`
   - 输出：符合设计文档的警告格式
   - 测试：`test_format_critical_warnings()`

2. **`_format_task_overview()`**：
   - 输入：`task_goal`, `state.memory.created_files`
   - 输出：符合设计文档的任务概览格式
   - 测试：`test_format_task_overview()`

3. **`_format_execution_plan()`**：
   - 输入：`state.memory.plan`
   - 输出：符合设计文档的执行计划格式
   - 测试：`test_format_execution_plan()`

4. **`_format_important_context()`**：
   - 输入：`state.memory.important_decisions`, `milestones`, `learnings`
   - 输出：符合设计文档的重要上下文格式
   - 测试：`test_format_important_context()`

5. **`_format_recent_activity()`**：
   - 输入：`state.memory.decisions`, `state.memory.tool_results_history`
   - 输出：符合设计文档的最近活动格式
   - 测试：`test_format_recent_activity()`

6. **`_format_tool_execution_results()`**：
   - 输入：`state.memory.tool_results_history`
   - 输出：符合设计文档的工具执行结果格式
   - 使用 `ToolResultFormatter.format_results_list()`
   - 测试：`test_format_tool_execution_results()`

7. **`_format_modified_files_content()`**：
   - 输入：`state.memory.modified_files_content`
   - 输出：符合设计文档的文件内容格式
   - 测试：`test_format_modified_files_content()`

8. **`_format_current_state()`**：
   - 输入：`state.last_error`, `state.artifacts.current_diff`, `state.artifacts.test_results`
   - 输出：符合设计文档的当前状态格式
   - 测试：`test_format_current_state()`

9. **`_format_next_steps_guidance()`**：
   - 输入：当前所有状态信息
   - 输出：符合设计文档的下一步指导格式
   - 测试：`test_format_next_steps_guidance()`

**每个方法的实现要求**：
- 必须完全按照设计文档中的格式
- 必须处理所有边界情况
- 必须添加类型注解
- 必须添加文档字符串

**验证标准**：
- [ ] 所有方法实现完成
- [ ] 每个方法都有对应的测试用例
- [ ] 所有测试用例通过
- [ ] 输出格式完全符合设计文档

**预计时间**：3 天

#### 步骤 3.3：实现主格式化方法

**任务**：

实现 `format()` 方法，调用所有子方法并拼接结果。

**要求**：
- 按照设计文档中的顺序拼接各个部分
- 处理 `format_options` 参数
- 应用长度限制（如果提供 `max_length`）
- 处理空部分（如果某个部分为空，不显示或显示 "(无)"）

**代码结构**：
```python
def format(
    self,
    state: AgentState,
    format_options: Optional[Dict[str, Any]] = None
) -> str:
    options = format_options or {}
    parts = []
    
    # 1. Critical Warnings
    warnings = self._format_critical_warnings(state)
    if warnings:
        parts.append(warnings)
    
    # 2. Task Overview
    parts.append(self._format_task_overview(state, task_goal))
    
    # 3. Execution Plan
    parts.append(self._format_execution_plan(state))
    
    # 4. Important Context
    parts.append(self._format_important_context(state))
    
    # 5. Recent Activity
    parts.append(self._format_recent_activity(state, options))
    
    # 6. Tool Execution Results
    parts.append(self._format_tool_execution_results(state, options))
    
    # 7. Modified Files Content
    if options.get("include_file_content", True):
        parts.append(self._format_modified_files_content(state, options))
    
    # 8. Current State
    parts.append(self._format_current_state(state))
    
    # 9. Next Steps Guidance
    parts.append(self._format_next_steps_guidance(state))
    
    # 拼接所有部分
    result = "\n\n".join(parts)
    
    # 应用长度限制
    max_length = options.get("max_length")
    if max_length and len(result) > max_length:
        result = self._apply_length_limit(result, max_length)
    
    return result
```

**验证标准**：
- [ ] `format()` 方法实现完成
- [ ] 所有部分按正确顺序拼接
- [ ] 长度限制正确应用
- [ ] 测试用例通过

**预计时间**：1 天

#### 步骤 3.4：创建完整测试套件

**任务**：

创建完整的测试套件，验证 `MemoryFormatter` 的所有功能。

**测试文件**：`atloop/tests/memory/test_formatter.py`（扩展现有文件）

**测试用例**：

1. **单元测试**（每个格式化方法）：
   - `test_format_critical_warnings()` - 测试警告格式化
   - `test_format_task_overview()` - 测试任务概览格式化
   - `test_format_execution_plan()` - 测试执行计划格式化
   - `test_format_important_context()` - 测试重要上下文格式化
   - `test_format_recent_activity()` - 测试最近活动格式化
   - `test_format_tool_execution_results()` - 测试工具执行结果格式化
   - `test_format_modified_files_content()` - 测试文件内容格式化
   - `test_format_current_state()` - 测试当前状态格式化
   - `test_format_next_steps_guidance()` - 测试下一步指导格式化

2. **集成测试**：
   - `test_format_complete()` - 测试完整格式化
   - `test_format_with_options()` - 测试格式选项
   - `test_format_length_limit()` - 测试长度限制
   - `test_format_empty_memory()` - 测试空 memory
   - `test_format_early_stage()` - 测试早期阶段（对应示例 1）
   - `test_format_mid_stage()` - 测试中期阶段（对应示例 2）
   - `test_format_late_stage()` - 测试后期阶段（对应示例 3）
   - `test_format_with_errors()` - 测试包含错误（对应示例 4）

3. **格式验证测试**：
   - `test_format_matches_design_doc()` - 验证输出格式完全符合设计文档
   - `test_format_no_duplicate_content()` - 验证没有重复内容

**验证标准**：
- [ ] 所有测试用例创建完成
- [ ] 所有测试用例通过
- [ ] 代码覆盖率 >= 90%
- [ ] 输出格式完全符合设计文档

**预计时间**：2 天

### 3.3 阶段 3 验收标准

- [ ] `MemoryFormatter` 类完全实现
- [ ] 所有格式化方法实现完成
- [ ] 输出格式完全符合 `MEMORY_PROMPT_FORMAT_DEMO.md`
- [ ] 所有测试用例通过
- [ ] 代码覆盖率 >= 90%

### 3.4 阶段 3 预计时间

总计：7 天

---

## 阶段 4：在 Memory 类中添加 get_formatted_context() 方法

### 4.1 目标

在 `Memory` 类中添加 `get_formatted_context()` 方法，作为格式化输出的唯一接口。

### 4.2 具体步骤

#### 步骤 4.1：修改 Memory 类

**输入**：`atloop/atloop/memory/state.py`

**任务**：

1. **在 `Memory` 类中添加方法**：
   ```python
   def get_formatted_context(
       self,
       state: AgentState,  # 需要访问完整的 state
       task_goal: Optional[str] = None,
       max_length: Optional[int] = None,
       format_options: Optional[Dict[str, Any]] = None,
       tool_registry: Optional[Any] = None
   ) -> str:
       """
       获取格式化后的记忆上下文，可直接注入到 prompt 中。
       
       这是 Memory 模块的主要输出接口。
       
       Args:
           state: AgentState 实例（需要访问 memory, last_error, artifacts）
           task_goal: 任务目标（可选，用于任务概览）
           max_length: 最大长度限制（可选）
           format_options: 格式选项
               - tool_results_count: int (默认 5)
               - steps_summary_count: int (默认 3)
               - include_file_content: bool (默认 True)
               - max_file_content_length: int (默认 20000)
           tool_registry: 工具注册表（用于输出限制策略）
       
       Returns:
           格式化后的字符串，可直接用于 prompt 注入
           格式：符合 MEMORY_PROMPT_FORMAT_DEMO.md 中定义的格式
       """
       from atloop.memory.formatter import MemoryFormatter
       
       formatter = MemoryFormatter(tool_registry=tool_registry)
       
       # 合并 format_options 和 max_length
       options = format_options or {}
       if max_length:
           options["max_length"] = max_length
       
       return formatter.format(state, task_goal=task_goal, format_options=options)
   ```

**注意**：
- 方法需要访问完整的 `AgentState`，因为需要 `last_error` 和 `artifacts`
- 可以考虑将方法移到 `AgentState` 类中，但根据设计，应该在 `Memory` 类中

**验证标准**：
- [ ] 方法添加完成
- [ ] 方法签名正确
- [ ] 可以成功调用

**预计时间**：0.5 天

#### 步骤 4.2：创建测试用例

**任务**：

1. **创建测试用例**：
   - 文件：`atloop/tests/memory/test_state.py`（扩展现有文件）
   - 测试用例：
     - `test_get_formatted_context()` - 测试基本功能
     - `test_get_formatted_context_with_options()` - 测试格式选项
     - `test_get_formatted_context_length_limit()` - 测试长度限制
     - `test_get_formatted_context_empty()` - 测试空 memory

**验证标准**：
- [ ] 所有测试用例通过
- [ ] 输出格式正确

**预计时间**：0.5 天

### 4.3 阶段 4 验收标准

- [ ] `Memory.get_formatted_context()` 方法实现完成
- [ ] 方法可以正常工作
- [ ] 所有测试用例通过

### 4.4 阶段 4 预计时间

总计：1 天

---

## 阶段 5：创建 CompressionPolicy 接口和实现

### 5.1 目标

创建 `CompressionPolicy` 接口和实现类，将压缩逻辑从 `Memory` 模块中分离出来。

### 5.2 具体步骤

#### 步骤 5.1：创建 CompressionPolicy 接口

**文件**：`atloop/atloop/memory/compression_policy.py`（新建）

**任务**：

1. **创建接口**：
   ```python
   from abc import ABC, abstractmethod
   from typing import Any, Optional
   from atloop.memory.state import Memory, AgentState
   
   class CompressionPolicy(ABC):
       """压缩策略接口"""
       
       @abstractmethod
       def compress(self, memory: Memory, target_size: int) -> Memory:
           """
           压缩 memory，返回压缩后的 memory。
           
           Args:
               memory: 原始 memory
               target_size: 目标大小（字符数，基于格式化后的字符串长度）
           
           Returns:
               压缩后的 memory（修改后的实例）
           
           Note:
               - 压缩策略应该修改 memory 的内部数据结构
               - 不应该修改 memory 的接口
           """
           pass
       
       @abstractmethod
       def estimate_size(self, memory: Memory, state: AgentState) -> int:
           """
           估算 memory 格式化后的大小。
           
           Args:
               memory: Memory 实例
               state: AgentState 实例（用于格式化）
           
           Returns:
               估算的字符数
           """
           pass
   ```

**验证标准**：
- [ ] 接口创建完成
- [ ] 接口定义清晰
- [ ] 可以成功导入

**预计时间**：0.5 天

#### 步骤 5.2：实现 RuleBasedCompressionPolicy

**文件**：`atloop/atloop/memory/compression_policy.py`（同一文件）

**任务**：

1. **实现 `RuleBasedCompressionPolicy` 类**：
   ```python
   class RuleBasedCompressionPolicy(CompressionPolicy):
       """基于规则的压缩策略"""
       
       def __init__(
           self,
           tool_results_keep_recent: int = 10,
           decisions_keep_recent: int = 5,
           important_decisions_keep: int = 20,
           milestones_keep: int = 20,
           learnings_keep: int = 10
       ):
           self.tool_results_keep_recent = tool_results_keep_recent
           self.decisions_keep_recent = decisions_keep_recent
           self.important_decisions_keep = important_decisions_keep
           self.milestones_keep = milestones_keep
           self.learnings_keep = learnings_keep
       
       def compress(self, memory: Memory, target_size: int) -> Memory:
           """基于规则的压缩"""
           # 1. 压缩 tool_results_history
           if len(memory.tool_results_history) > self.tool_results_keep_recent:
               self._compress_tool_results_history(memory)
           
           # 2. 压缩 decisions
           if len(memory.decisions) > self.decisions_keep_recent:
               self._compress_decisions(memory)
           
           # 3. 修剪其他字段
           if len(memory.important_decisions) > self.important_decisions_keep:
               memory.important_decisions = memory.important_decisions[-self.important_decisions_keep:]
           
           if len(memory.milestones) > self.milestones_keep:
               memory.milestones = memory.milestones[-self.milestones_keep:]
           
           if len(memory.learnings) > self.learnings_keep:
               memory.learnings = memory.learnings[-self.learnings_keep:]
           
           return memory
       
       def estimate_size(self, memory: Memory, state: AgentState) -> int:
           """估算大小"""
           # 使用 MemoryFormatter 估算
           from atloop.memory.formatter import MemoryFormatter
           formatter = MemoryFormatter()
           formatted = formatter.format(state)
           return len(formatted)
       
       def _compress_tool_results_history(self, memory: Memory) -> None:
           """压缩 tool_results_history"""
           # 实现逻辑（参考现有 compressor.py）
           pass
       
       def _compress_decisions(self, memory: Memory) -> None:
           """压缩 decisions"""
           # 实现逻辑（参考现有 compressor.py）
           pass
   ```

2. **迁移现有压缩逻辑**：
   - 从 `atloop/atloop/memory/compressor.py` 迁移相关代码
   - 保持逻辑一致

**验证标准**：
- [ ] `RuleBasedCompressionPolicy` 实现完成
- [ ] 压缩逻辑正确
- [ ] 测试用例通过

**预计时间**：2 天

#### 步骤 5.3：实现 ImportanceBasedCompressionPolicy

**文件**：`atloop/atloop/memory/compression_policy.py`（同一文件）

**任务**：

1. **实现 `ImportanceBasedCompressionPolicy` 类**：
   ```python
   class ImportanceBasedCompressionPolicy(CompressionPolicy):
       """基于重要性的压缩策略"""
       
       def __init__(
           self,
           scorer: Optional[Any] = None,
           importance_threshold: float = 0.3
       ):
           from atloop.memory.scorer import ImportanceScorer
           self.scorer = scorer or ImportanceScorer()
           self.importance_threshold = importance_threshold
       
       def compress(self, memory: Memory, target_size: int) -> Memory:
           """基于重要性的压缩"""
           # 1. 计算每个工具结果的重要性
           scored_results = []
           for result in memory.tool_results_history:
               score = self._calculate_importance(result, memory)
               scored_results.append((score, result))
           
           # 2. 排序
           scored_results.sort(key=lambda x: x[0], reverse=True)
           
           # 3. 保留重要的，压缩不重要的
           # ... 实现逻辑
           
           return memory
       
       def _calculate_importance(self, result: Dict[str, Any], memory: Memory) -> float:
           """计算工具结果的重要性"""
           # 实现逻辑（参考设计文档）
           pass
   ```

**验证标准**：
- [ ] `ImportanceBasedCompressionPolicy` 实现完成
- [ ] 重要性计算正确
- [ ] 测试用例通过

**预计时间**：2 天

#### 步骤 5.4：创建测试用例

**任务**：

1. **创建测试文件**：`atloop/tests/memory/test_compression_policy.py`

2. **测试用例**：
   - `test_rule_based_compression()` - 测试基于规则的压缩
   - `test_rule_based_compression_tool_results()` - 测试工具结果压缩
   - `test_rule_based_compression_decisions()` - 测试决策压缩
   - `test_importance_based_compression()` - 测试基于重要性的压缩
   - `test_compression_estimate_size()` - 测试大小估算
   - `test_compression_preserves_important_data()` - 测试保留重要数据

**验证标准**：
- [ ] 所有测试用例通过
- [ ] 压缩逻辑验证完成

**预计时间**：1 天

### 5.3 阶段 5 验收标准

- [ ] `CompressionPolicy` 接口创建完成
- [ ] `RuleBasedCompressionPolicy` 实现完成
- [ ] `ImportanceBasedCompressionPolicy` 实现完成
- [ ] 所有测试用例通过
- [ ] 压缩逻辑正确

### 5.4 阶段 5 预计时间

总计：5.5 天

---

## 阶段 6：更新 PlanPhase 使用新接口

### 6.1 目标

更新 `PlanPhase` 使用新的 `Memory.get_formatted_context()` 接口，替换现有的 `MemorySummarizer.summarize()` 调用。

### 6.2 具体步骤

#### 步骤 6.1：修改 PlanPhase

**输入**：`atloop/atloop/orchestrator/phases/plan.py`

**任务**：

1. **找到 `MemorySummarizer.summarize()` 调用**（约 Line 57）：
   ```python
   memory_summary = MemorySummarizer.summarize(
       state,
       max_length=memory_summary_max_length,
       task_goal=self.coordinator.task_spec.goal,
       tool_registry=self.coordinator.tool_runtime.registry,
   )
   ```

2. **替换为新的接口**：
   ```python
   memory_context = state.memory.get_formatted_context(
       state=state,
       task_goal=self.coordinator.task_spec.goal,
       max_length=memory_summary_max_length,
       format_options={
           "tool_results_count": 5,
           "steps_summary_count": 3,
           "include_file_content": True,
           "max_file_content_length": 20000
       },
       tool_registry=self.coordinator.tool_runtime.registry
   )
   ```

3. **更新变量名**：
   - 将所有 `memory_summary` 替换为 `memory_context`
   - 更新 `build_user_message()` 调用中的参数名

4. **更新 `build_user_message()` 方法**（如果需要）：
   - 文件：`atloop/atloop/llm/client.py`
   - 将 `state_summary` 参数改为 `memory_context`

**验证标准**：
- [ ] 代码修改完成
- [ ] 所有变量名更新完成
- [ ] 可以成功编译

**预计时间**：1 天

#### 步骤 6.2：更新 prompt 模板

**输入**：`atloop/atloop/llm/prompts/en/developer.txt`

**任务**：

1. **找到 `{STATE_SUMMARY}` 占位符**：
   - 搜索 `{STATE_SUMMARY}` 或 `state_summary`

2. **替换为新的格式**：
   ```markdown
   ## Task Context
   {memory_context}
   ```

3. **移除旧的格式说明**（如果有）

**验证标准**：
- [ ] Prompt 模板更新完成
- [ ] 占位符正确替换

**预计时间**：0.5 天

#### 步骤 6.3：更新测试用例

**任务**：

1. **更新现有测试用例**：
   - 修改期望的输出格式
   - 更新测试数据

2. **创建集成测试**：
   - 文件：`atloop/tests/orchestrator/phases/test_plan_phase_memory.py`
   - 测试用例：
     - `test_plan_phase_uses_new_memory_interface()` - 验证使用新接口
     - `test_plan_phase_memory_format()` - 验证 memory 格式

**验证标准**：
- [ ] 所有测试用例通过
- [ ] 集成测试验证完成

**预计时间**：1 天

### 6.3 阶段 6 验收标准

- [ ] `PlanPhase` 使用新接口
- [ ] Prompt 模板更新完成
- [ ] 所有测试用例通过
- [ ] 功能正常工作

### 6.4 阶段 6 预计时间

总计：2.5 天

---

## 阶段 7：清理和优化

### 7.1 目标

删除不再需要的旧代码，优化文件结构，确保代码质量。

### 7.2 具体步骤

#### 步骤 7.1：删除旧代码

**任务**：

1. **删除 `MemorySummarizer.summarize()` 方法**（如果不再使用）：
   - 文件：`atloop/atloop/memory/summarizer.py`
   - 检查是否有其他代码依赖此方法
   - 如果没有，删除整个方法

2. **保留 `MemorySummarizer.get_memory_overview()`**（如果仍在使用）：
   - 检查是否有其他代码使用
   - 如果使用，保留；如果不使用，删除

3. **删除 `MemoryCompressor` 类**（如果不再使用）：
   - 文件：`atloop/atloop/memory/compressor.py`
   - 检查是否有其他代码依赖
   - 如果没有，删除整个文件

4. **清理导入**：
   - 删除不再使用的导入
   - 更新所有文件的导入语句

**验证标准**：
- [ ] 旧代码删除完成
- [ ] 没有破坏性更改
- [ ] 所有测试用例通过

**预计时间**：1 天

#### 步骤 7.2：优化文件结构

**任务**：

1. **检查文件长度**：
   - 如果任何文件超过 500 行，考虑拆分
   - 目标：每个文件不超过 500 行

2. **优化模块结构**：
   - 确保每个模块职责单一
   - 确保接口清晰

3. **更新文档字符串**：
   - 确保所有公共方法都有文档字符串
   - 确保文档字符串准确

**验证标准**：
- [ ] 文件结构优化完成
- [ ] 所有文件长度合理
- [ ] 文档字符串完整

**预计时间**：1 天

#### 步骤 7.3：代码审查和优化

**任务**：

1. **运行代码质量工具**：
   - `ruff check`
   - `mypy`
   - `pylint`（如果使用）

2. **修复所有问题**：
   - 修复类型错误
   - 修复代码风格问题
   - 修复潜在 bug

3. **运行完整测试套件**：
   - 确保所有测试通过
   - 确保代码覆盖率 >= 85%

**验证标准**：
- [ ] 所有代码质量检查通过
- [ ] 所有测试用例通过
- [ ] 代码覆盖率 >= 85%

**预计时间**：1 天

### 7.3 阶段 7 验收标准

- [ ] 旧代码删除完成
- [ ] 文件结构优化完成
- [ ] 代码质量检查通过
- [ ] 所有测试用例通过
- [ ] 代码覆盖率 >= 85%

### 7.4 阶段 7 预计时间

总计：3 天

---

## 阶段 8：最终验收

### 8.1 目标

进行最终验收，确保所有功能正常工作，符合设计文档。

### 8.2 具体步骤

#### 步骤 8.1：功能验收

**任务**：

1. **运行完整测试套件**：
   ```bash
   uv run pytest atloop/tests/memory/ -v
   uv run pytest atloop/tests/orchestrator/phases/ -v
   ```

2. **运行集成测试**：
   - 使用真实数据测试完整流程
   - 验证输出格式符合设计文档

3. **性能测试**：
   - 测试格式化性能
   - 测试压缩性能
   - 确保性能可接受

**验证标准**：
- [ ] 所有测试用例通过
- [ ] 集成测试通过
- [ ] 性能可接受

**预计时间**：1 天

#### 步骤 8.2：文档验收

**任务**：

1. **检查代码文档**：
   - 所有公共方法都有文档字符串
   - 文档字符串准确

2. **检查设计文档一致性**：
   - 代码实现符合设计文档
   - 输出格式符合设计文档

3. **更新 README**（如果需要）：
   - 更新使用说明
   - 更新架构说明

**验证标准**：
- [ ] 代码文档完整
- [ ] 实现符合设计文档
- [ ] README 更新完成

**预计时间**：0.5 天

#### 步骤 8.3：最终审查

**任务**：

1. **代码审查**：
   - 审查所有修改的代码
   - 确保代码质量

2. **架构审查**：
   - 确保架构符合设计
   - 确保接口清晰

3. **测试审查**：
   - 确保测试覆盖充分
   - 确保测试质量

**验证标准**：
- [ ] 代码审查通过
- [ ] 架构审查通过
- [ ] 测试审查通过

**预计时间**：0.5 天

### 8.3 阶段 8 验收标准

- [ ] 所有功能正常工作
- [ ] 所有测试用例通过
- [ ] 代码质量符合标准
- [ ] 实现符合设计文档
- [ ] 文档完整

### 8.4 阶段 8 预计时间

总计：2 天

---

## 总结

### 总预计时间

- 阶段 0：0.5 天
- 阶段 1：3.5 天
- 阶段 2：3 天
- 阶段 3：7 天
- 阶段 4：1 天
- 阶段 5：5.5 天
- 阶段 6：2.5 天
- 阶段 7：3 天
- 阶段 8：2 天

**总计：28 天**

### 关键里程碑

1. **阶段 1 完成**：移除重复显示，减少 Token 浪费
2. **阶段 3 完成**：`MemoryFormatter` 实现完成，输出格式符合设计
3. **阶段 4 完成**：`Memory.get_formatted_context()` 接口可用
4. **阶段 6 完成**：系统使用新接口，功能完整
5. **阶段 8 完成**：最终验收通过，可以发布

### 风险控制

1. **每个阶段必须通过测试才能进入下一阶段**
2. **不允许为了通过测试而妥协测试用例**
3. **如果遇到问题，必须修复后再继续**
4. **定期审查代码质量，确保符合标准**

### 开发规范

1. **代码规范**：
   - 使用类型注解
   - 添加文档字符串
   - 遵循 PEP 8

2. **测试规范**：
   - 每个功能都要有测试用例
   - 测试覆盖率 >= 85%
   - 测试用例必须验证设计逻辑

3. **文档规范**：
   - 所有公共方法都要有文档字符串
   - 复杂逻辑要有注释
   - 更新相关文档

---

## 附录：文件结构

### 最终文件结构

```
atloop/atloop/memory/
├── __init__.py
├── state.py                    # Memory 数据结构和 get_formatted_context()
├── formatter.py                # MemoryFormatter 和 ToolResultFormatter
├── compression_policy.py        # CompressionPolicy 接口和实现
├── scorer.py                   # ImportanceScorer（已存在）
├── memory_manager.py           # MemoryManager（已存在）
├── plan.py                     # PlanManager（已存在）
└── progress_tracker.py         # ProgressTracker（已存在）

atloop/tests/memory/
├── __init__.py
├── test_state.py               # 测试 Memory 类
├── test_formatter.py           # 测试 MemoryFormatter
├── test_compression_policy.py  # 测试 CompressionPolicy
├── test_integration.py         # 集成测试
├── fixtures/
│   ├── __init__.py
│   ├── sample_state.py         # 测试用的 AgentState 工厂
│   └── sample_memory.py        # 测试用的 Memory 工厂
└── test_helpers.py             # 测试辅助函数
```

### 删除的文件

- `atloop/atloop/memory/summarizer.py`（如果 `get_memory_overview()` 不再使用）
- `atloop/atloop/memory/compressor.py`（压缩逻辑迁移到 `compression_policy.py`）

---

**开发团队必须严格按照此计划执行，每个阶段完成后必须通过验收才能进入下一阶段。**
