# Memory 模块重构方案与理想 Prompt 格式设计

## 一、问题分析总结

### 1.1 重复显示问题（已在前一份报告详述）

**核心问题**：工具执行结果被重复显示 3 次
- `## Recent Attempts` (line 302-374)
- `## Recent Tool Execution Results (Enhanced Storage)` (line 541-611)  
- `## Recent Tool Execution Results` (line 616-674)

**影响**：
- Token 浪费：相同信息重复 3 次，每次 200-300 字符
- 信息混乱：LLM 需要在多个位置查找相同信息
- 维护困难：修改格式需要改多处代码

### 1.2 Memory 数据结构冗余

**问题 1：`attempts` 和 `tool_results_history` 职责重叠**

当前设计：
```python
# attempts: 按"文件修改尝试"组织
{
    "step": int,
    "files": List[str],  # 修改的文件列表
    "success": bool,
    "results": List[Dict]  # 工具执行结果（包含 stdout/stderr）
}

# tool_results_history: 按工具执行结果组织
{
    "step": int,
    "tool": str,
    "args": Dict,
    "placeholder": Optional[str],  # 占位符信息
    "result": Dict  # 工具执行结果（包含 stdout/stderr）
}
```

**问题**：
- 两者都存储工具执行结果（`results` vs `result`）
- `attempts` 按"文件修改"分组，但很多工具不涉及文件（如 `run`, `read_file`）
- `tool_results_history` 包含 placeholder 信息，但 `attempts` 中没有
- 数据写入时机相同（都在 ActPhase），导致重复存储

**问题 2：`attempts` 的语义不清晰**

- 名称暗示"尝试"，但实际存储的是"工具执行结果"
- 按"文件修改"分组，但很多工具执行不涉及文件
- 与 `tool_results_history` 的边界不清晰

### 1.3 Summarizer 代码冗余

**问题**：
- 三个地方生成工具执行结果的显示格式
- 格式逻辑重复（截断、预览、状态显示）
- 没有统一的格式化函数
- 去重逻辑缺失

### 1.4 压缩策略不完整

**当前压缩策略**：
- ✅ `attempts` 有压缩（基于规则）
- ✅ `decisions` 有压缩（基于规则 + LLM）
- ✅ `important_decisions`, `milestones`, `learnings` 有修剪
- ❌ `tool_results_history` **没有压缩策略**（可能无限增长）
- ❌ `modified_files_content` 压缩在外部处理

---

## 二、轻度重构方案

### 2.1 重构原则

1. **保持业务功能不变**：不改变现有功能，只优化结构
2. **渐进式重构**：分阶段实施，每阶段可独立验证
3. **向后兼容**：保持数据结构兼容，避免破坏现有代码

### 2.2 阶段 1：统一工具执行结果显示（高优先级）

**目标**：移除重复显示，只保留一个统一的工具执行结果部分

**方案**：
1. **移除 `## Recent Attempts` 中的工具执行详情**
   - 只保留文件修改统计（`Modified N files: Success/Failed`）
   - 移除 `Tool Execution Details` 部分

2. **移除第二个 `## Recent Tool Execution Results`**
   - 完全删除 line 616-674 的代码

3. **保留并增强 `## Recent Tool Execution Results (Enhanced Storage)`**
   - 重命名为 `## Recent Tool Execution Results`
   - 作为工具执行结果的唯一显示位置
   - 增强格式，包含所有必要信息

**代码变更**：
```python
# summarizer.py

# 1. 简化 Recent Attempts（只显示文件修改统计）
if state.memory.attempts:
    parts.append("\n## Recent Attempts")
    for attempt in state.memory.attempts[-3:]:
        files = attempt.get("files", [])
        success = attempt.get("success", False)
        status = "Success" if success else "Failed"
        parts.append(f"- Step {attempt.get('step', '?')}: Modified {len(files)} files: {status}")
        if files:
            parts.append(f"  Files: {', '.join(files[:5])}")
            if len(files) > 5:
                parts.append(f"  ... (+{len(files) - 5} more)")

# 2. 统一工具执行结果显示（从 tool_results_history）
if state.memory.tool_results_history:
    parts.append("\n## Recent Tool Execution Results")
    # ... 使用统一的格式化函数
```

**预期效果**：
- 减少 50-70% 的重复内容
- Token 节省：每个 step 节省 400-600 字符
- 信息更清晰：单一数据源，格式统一

### 2.3 阶段 2：重构数据存储结构（中优先级）

**目标**：明确 `attempts` 和 `tool_results_history` 的职责

**方案 A：保留两者，明确职责**

```python
# attempts: 仅用于"文件修改尝试"跟踪
{
    "step": int,
    "files": List[str],  # 修改的文件列表
    "success": bool,
    # 移除 results，改为引用 tool_results_history
    "tool_result_refs": List[int]  # tool_results_history 的索引
}

# tool_results_history: 作为工具执行结果的唯一来源
{
    "step": int,
    "tool": str,
    "args": Dict,
    "placeholder": Optional[str],
    "result": Dict,
    "index": int  # 自增索引，用于 attempts 引用
}
```

**方案 B：合并为单一数据结构（推荐）**

```python
# 移除 attempts，统一使用 tool_results_history
# 添加文件修改跟踪字段
{
    "step": int,
    "tool": str,
    "args": Dict,
    "placeholder": Optional[str],
    "result": Dict,
    "modified_files": List[str],  # 如果工具修改了文件
    "attempt_group": int  # 同一 step 的工具执行分组
}
```

**推荐方案 B**，原因：
- 更简单：单一数据源，减少维护成本
- 更灵活：不限制于"文件修改"场景
- 更清晰：所有工具执行结果统一管理

**实施步骤**：
1. 修改 `ActPhase._update_memory_after_execution()`：
   - 移除 `attempts.append()`
   - 在 `tool_results_history.append()` 中添加 `modified_files` 字段

2. 修改 `summarizer.py`：
   - 从 `tool_results_history` 提取文件修改信息
   - 移除对 `attempts` 的依赖

3. 修改 `compressor.py`：
   - 移除 `_compress_attempts()`
   - 添加 `_compress_tool_results_history()`

**向后兼容**：
- 保留 `attempts` 字段（标记为 deprecated）
- 提供迁移函数，从 `attempts` 迁移到 `tool_results_history`

### 2.4 阶段 3：代码精炼（低优先级）

**目标**：减少代码重复，提高可维护性

**方案**：创建统一的格式化函数

```python
class ToolResultFormatter:
    """统一格式化工具执行结果"""
    
    @staticmethod
    def format_tool_result(
        tool_result: Dict[str, Any],
        tool_registry: Optional[Any] = None,
        include_full_output: bool = False
    ) -> str:
        """
        格式化单个工具执行结果
        
        Args:
            tool_result: 工具执行结果字典
            tool_registry: 工具注册表（用于获取输出限制策略）
            include_full_output: 是否包含完整输出（用于错误场景）
        
        Returns:
            格式化后的字符串
        """
        step = tool_result.get("step", "?")
        tool_name = tool_result.get("tool", "unknown")
        placeholder = tool_result.get("placeholder")
        args = tool_result.get("args", {})
        result = tool_result.get("result", {})
        ok = result.get("ok", False)
        status = "✓" if ok else "✗"
        
        # 构建标题行
        title_parts = [f"Step {step}: {status} [{tool_name}]"]
        if placeholder:
            title_parts.append(f"({placeholder})")
        elif tool_name == "run" and "cmd" in args:
            cmd_preview = str(args["cmd"])[:50]
            title_parts.append(f"(cmd: {cmd_preview}...)")
        elif tool_name in ["write_file", "edit_file", "append_file"] and "path" in args:
            title_parts.append(f"(path: {args['path']})")
        
        lines = ["- " + " ".join(title_parts)]
        
        # 格式化输出（使用统一的截断策略）
        if result.get("stdout"):
            stdout_text = ToolResultFormatter._format_output(
                result.get("stdout", ""),
                tool_name,
                tool_registry,
                is_stderr=False,
                include_full=include_full_output
            )
            lines.append(f"  Stdout: {stdout_text}")
        
        if result.get("stderr"):
            stderr_text = ToolResultFormatter._format_output(
                result.get("stderr", ""),
                tool_name,
                tool_registry,
                is_stderr=True,
                include_full=include_full_output
            )
            lines.append(f"  Stderr: {stderr_text}")
        
        return "\n".join(lines)
    
    @staticmethod
    def _format_output(
        output: str,
        tool_name: str,
        tool_registry: Optional[Any],
        is_stderr: bool,
        include_full: bool
    ) -> str:
        """格式化输出内容（统一截断策略）"""
        # 使用 OutputLimitStrategy 获取限制
        # ... 实现统一的截断逻辑
        pass
```

**使用**：
```python
# summarizer.py
if state.memory.tool_results_history:
    parts.append("\n## Recent Tool Execution Results")
    for tool_result in state.memory.tool_results_history[-5:]:
        formatted = ToolResultFormatter.format_tool_result(
            tool_result,
            tool_registry=tool_registry,
            include_full_output=False
        )
        parts.append(formatted)
```

---

## 三、理想的 Memory 注入 Prompt 格式设计

### 3.1 设计原则

1. **层次清晰**：从抽象到具体，从长期到短期
2. **信息密度高**：避免冗余，每个信息只出现一次
3. **易于解析**：结构化格式，LLM 容易理解
4. **可扩展**：支持未来添加新字段

### 3.2 理想格式结构

```
## Memory and Context

### 1. Task Overview (Long-term)
**Goal**: [任务目标]
**Status**: [进行中/已完成/已失败]
**Created Files**: [文件列表，如果有]

### 2. Execution Plan (Long-term)
[当前执行计划，动态更新]

### 3. Important Context (Long-term)
**Decisions**: [重要决策，Top 5]
**Milestones**: [重要里程碑，Top 5]
**Learnings**: [重要经验，Top 3]

### 4. Recent Activity (Short-term)
**Steps Summary** (Last 3 steps):
- Step N: [工具列表] → [stop_reason]
- Step N-1: [工具列表] → [stop_reason]
- Step N-2: [工具列表] → [stop_reason]

**File Modifications** (Last 3 steps):
- Step N: Modified [文件列表]
- Step N-1: Modified [文件列表]

### 5. Tool Execution Results (Short-term)
[工具执行结果，Last 5，统一格式]

### 6. Current State
**Last Error**: [如果有]
**Current Diff**: [如果有]
**Test Results**: [如果有]
```

### 3.3 详细格式示例

#### 示例 1：简单任务（早期阶段）

```markdown
## Memory and Context

### 1. Task Overview
**Goal**: 模拟生成一只股票一个月的高开低收数据, 画成k线图给我.
**Status**: 进行中
**Created Files**: []

### 2. Execution Plan
1. 检查当前目录和Python环境
2. 检查必要的Python库（如matplotlib, pandas）
3. 创建数据生成脚本
4. 创建绘图脚本
5. 运行脚本生成图表

### 3. Important Context
**Decisions**:
- ⭐⭐⭐ Step 2: Initial plan (5 steps)

**Milestones**: (无)

**Learnings**: (无)

### 4. Recent Activity
**Steps Summary**:
- Step 3: [run, run] → continue
- Step 2: [plan] → continue

**File Modifications**:
- Step 3: Modified []

### 5. Tool Execution Results
- Step 3: ✓ [run] (cmd: python3 --version)
  Stdout: Python 3.10.12
  matplotlib 3.10.8
  numpy 2.2.6
  pandas 2.3.3

- Step 3: ✓ [run] (cmd: ls -la)
  Stdout: total 0
  drwxrwxrwx 2 root root 10 Jan 13 04:54 .

### 6. Current State
**Last Error**: None
**Current Diff**: No changes
**Test Results**: No verification command available
```

#### 示例 2：中等复杂度任务（中期阶段）

```markdown
## Memory and Context

### 1. Task Overview
**Goal**: 模拟生成一只股票一个月的高开低收数据, 画成k线图给我.
**Status**: 进行中
**Created Files**: [generate_data.py]

### 2. Execution Plan
1. ✅ 检查当前目录和Python环境
2. ✅ 检查必要的Python库
3. ✅ 创建数据生成脚本
4. 创建绘图脚本
5. 运行脚本生成图表

### 3. Important Context
**Decisions**:
- ⭐⭐⭐ Step 2: Initial plan (5 steps)

**Milestones**:
- ⭐ Step 7: Created data generation script (generate_data.py)

**Learnings**: (无)

### 4. Recent Activity
**Steps Summary**:
- Step 7: [write_file] → continue
- Step 3: [run, run] → continue
- Step 2: [plan] → continue

**File Modifications**:
- Step 7: Modified [generate_data.py]
- Step 3: Modified []

### 5. Tool Execution Results
- Step 7: ✓ [write_file] (path: generate_data.py)
  Result: File created successfully

- Step 3: ✓ [run] (cmd: python3 --version)
  Stdout: Python 3.10.12
  matplotlib 3.10.8
  numpy 2.2.6
  pandas 2.3.3

### 6. Current State
**Last Error**: None
**Current Diff**: 
+++ generate_data.py
@@ -0,0 +1,85 @@
+import numpy as np
+...

**Test Results**: No verification command available
```

#### 示例 3：复杂任务（后期阶段，包含错误）

```markdown
## Memory and Context

### 1. Task Overview
**Goal**: 模拟生成一只股票一个月的高开低收数据, 画成k线图给我.
**Status**: 进行中
**Created Files**: [generate_data.py, plot_kline.py]

### 2. Execution Plan
1. ✅ 检查当前目录和Python环境
2. ✅ 检查必要的Python库
3. ✅ 创建数据生成脚本
4. ✅ 创建绘图脚本
5. 运行脚本生成图表
6. 验证图表生成

### 3. Important Context
**Decisions**:
- ⭐⭐⭐ Step 2: Initial plan (5 steps)
- ⭐ Step 10: Created plotting script

**Milestones**:
- ⭐ Step 7: Created data generation script
- ⭐ Step 10: Created plotting script

**Learnings**:
- ⭐ Step 11: Data generation script requires CSV output for plotting script

### 4. Recent Activity
**Steps Summary**:
- Step 11: [write_file, run] → continue
- Step 10: [write_file] → continue
- Step 7: [write_file] → continue

**File Modifications**:
- Step 11: Modified [plot_kline.py]
- Step 10: Modified [plot_kline.py]
- Step 7: Modified [generate_data.py]

### 5. Tool Execution Results
- Step 11: ✓ [run] (cmd: python3 generate_data.py)
  Stdout: Data saved to stock_data.csv
  Generated 30 days of OHLC data
  ...
  Summary statistics:
  [统计数据]

- Step 11: ✓ [write_file] (path: plot_kline.py)
  Result: File created successfully

- Step 10: ✓ [write_file] (path: plot_kline.py)
  Result: File created successfully

### 6. Current State
**Last Error**: None
**Current Diff**: 
+++ plot_kline.py
@@ -0,0 +1,218 @@
+import pandas as pd
+...

**Test Results**: ✅ Tests Passed
```

### 3.4 字段说明

#### 必需字段

1. **Task Overview**
   - `Goal`: 任务目标（必需）
   - `Status`: 任务状态（进行中/已完成/已失败）
   - `Created Files`: 已创建文件列表（用于防止重复创建）

2. **Execution Plan**
   - 当前执行计划（动态更新）
   - 支持标记已完成步骤（✅）

3. **Recent Activity**
   - `Steps Summary`: 最近 3 步的摘要（工具列表 + stop_reason）
   - `File Modifications`: 最近 3 步的文件修改（如果有）

4. **Tool Execution Results**
   - 最近 5 个工具执行结果
   - 统一格式：Step + Tool + Args + Result

#### 可选字段

1. **Important Context**（如果有）
   - `Decisions`: Top 5 重要决策
   - `Milestones`: Top 5 重要里程碑
   - `Learnings`: Top 3 重要经验

2. **Current State**（如果有）
   - `Last Error`: 最近的错误信息
   - `Current Diff`: 当前文件变更
   - `Test Results`: 测试结果

3. **Modified Files Content**（如果有且重要）
   - 最近修改的文件内容（自动读取）
   - 限制：最多 5 个文件，总共 20KB

### 3.5 格式优势

1. **层次清晰**：从长期到短期，从抽象到具体
2. **信息密度高**：每个信息只出现一次
3. **易于解析**：结构化 Markdown，LLM 容易理解
4. **可扩展**：支持添加新字段而不破坏现有格式

---

## 四、架构重新设计（基于用户建议）

### 4.1 Memory 模块职责重新定义

**Memory 模块负责**：
- ✅ 原始数据的存储和管理（`state.memory`）
- ✅ 各个条目的格式转换和控制输出
  - 考虑约束：单条长度、字符串映射等
  - 提供统一的格式化接口
- ✅ 提供简易接口，返回可直接注入 prompt 的字符串

**Memory 模块不负责**：
- ❌ 数据压缩（由独立的 CompressionPolicy 负责）
- ❌ 数据重要性评分（由独立的 Scorer 负责，如果使用）

### 4.2 Memory 接口设计

```python
class Memory:
    """Memory 数据存储和管理"""
    
    def get_formatted_context(
        self,
        max_length: Optional[int] = None,
        format_options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        获取格式化后的记忆上下文，可直接注入到 prompt 中。
        
        这是 Memory 模块的主要输出接口，返回格式化的字符串。
        
        Args:
            max_length: 最大长度限制（可选，用于控制输出大小）
            format_options: 格式选项
                - include_file_content: bool (是否包含文件内容)
                - max_file_content_length: int (文件内容最大长度)
                - tool_results_count: int (工具结果数量，默认 5)
                - steps_summary_count: int (步骤摘要数量，默认 3)
                - string_mappings: Dict[str, str] (字符串映射规则)
        
        Returns:
            格式化后的字符串，可直接用于 prompt 注入
            格式：符合 MEMORY_PROMPT_FORMAT_DEMO.md 中定义的格式
        """
        # 实现格式化逻辑
        # 1. 格式化各个部分（Task Overview, Execution Plan, etc.）
        # 2. 应用约束（长度限制、字符串映射等）
        # 3. 拼接所有部分
        # 4. 返回最终字符串
        pass
```

**使用方式**：
```python
# 在 prompt 模板中（developer.txt）
## Task Context
{memory_context}

# 在代码中
memory_context = state.memory.get_formatted_context(
    max_length=64000,
    format_options={
        "tool_results_count": 5,
        "steps_summary_count": 3,
        "include_file_content": True,
        "max_file_content_length": 20000
    }
)

user_message = llm_client.build_user_message(
    goal=task_spec.goal,
    memory_context=memory_context,  # 直接注入
    ...
)
```

### 4.3 压缩策略作为独立类

压缩作为独立的策略类，通过接口注入到 Memory 中：

```python
from abc import ABC, abstractmethod

class CompressionPolicy(ABC):
    """压缩策略接口"""
    
    @abstractmethod
    def compress(self, memory: Memory, target_size: int) -> Memory:
        """
        压缩 memory，返回压缩后的 memory。
        
        Args:
            memory: 原始 memory（可能是 AgentState.memory）
            target_size: 目标大小（字符数，基于格式化后的字符串长度）
        
        Returns:
            压缩后的 memory（可能是新实例或修改后的实例）
        
        Note:
            - 压缩策略应该修改 memory 的内部数据结构
            - 不应该修改 memory 的接口
            - 压缩后的 memory 仍然可以通过 get_formatted_context() 获取格式化输出
        """
        pass
    
    @abstractmethod
    def estimate_size(self, memory: Memory) -> int:
        """
        估算 memory 格式化后的大小。
        
        Args:
            memory: Memory 实例
        
        Returns:
            估算的字符数
        """
        pass

class RuleBasedCompressionPolicy(CompressionPolicy):
    """基于规则的压缩策略"""
    
    def compress(self, memory: Memory, target_size: int) -> Memory:
        """
        基于规则的压缩：
        - 保留最近 N 个工具结果
        - 保留最近 N 个决策
        - 压缩旧的为摘要
        """
        # 实现压缩逻辑
        pass

class ImportanceBasedCompressionPolicy(CompressionPolicy):
    """基于重要性的压缩策略"""
    
    def __init__(self, scorer: Optional[ImportanceScorer] = None):
        self.scorer = scorer or ImportanceScorer()
    
    def compress(self, memory: Memory, target_size: int) -> Memory:
        """
        基于重要性的压缩：
        - 计算每个条目的重要性分数
        - 保留重要的，压缩不重要的
        """
        # 实现压缩逻辑
        pass

class LLMCompressionPolicy(CompressionPolicy):
    """基于 LLM 的压缩策略"""
    
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
    
    def compress(self, memory: Memory, target_size: int) -> Memory:
        """
        使用 LLM 压缩：
        - 选择要压缩的内容
        - 调用 LLM 生成摘要
        - 替换原始内容
        """
        # 实现压缩逻辑
        pass
```

**使用方式**：
```python
# 在需要压缩时（例如在 PlanPhase 之前）
memory = state.memory

# 估算当前大小
compression_policy = ImportanceBasedCompressionPolicy()
current_size = compression_policy.estimate_size(memory)

# 如果超过阈值，执行压缩
if current_size > threshold:
    memory = compression_policy.compress(memory, target_size=50000)
    state.memory = memory  # 更新 state

# 获取格式化输出（压缩后的）
memory_context = memory.get_formatted_context(max_length=64000)
```

### 4.4 压缩时机和优先级

### 4.5 压缩优先级

**优先级 1（最高）：长期记忆**
- `task_summary`: 不压缩，始终保留
- `plan`: 不压缩，始终保留
- `important_decisions`: 保留 Top N（默认 20）
- `milestones`: 保留 Top N（默认 20）
- `learnings`: 保留 Top N（默认 10）

**优先级 2（高）：当前状态**
- `last_error`: 不压缩，始终保留
- `created_files`: 不压缩，始终保留（防止重复创建）
- `current_diff`: 不压缩，始终保留

**优先级 3（中）：短期记忆**
- `tool_results_history`: 保留最近 N 个（默认 10）
- `decisions`: 保留最近 N 个（默认 5），旧的压缩为摘要
- `modified_files_content`: 保留最近 N 个（默认 5），按重要性排序

**优先级 4（低）：调试信息**
- `llm_responses`: 不压缩，但可以完全删除（仅用于调试）

### 4.3 压缩策略

#### 策略 1：基于规则的压缩（当前已有）

```python
# 保留最近 N 个，压缩旧的为摘要
def compress_tool_results_history(state, keep_recent=10):
    if len(state.memory.tool_results_history) <= keep_recent:
        return
    
    recent = state.memory.tool_results_history[-keep_recent:]
    old = state.memory.tool_results_history[:-keep_recent]
    
    # 生成摘要
    summary = summarize_tool_results(old)
    
    # 创建压缩记录
    compressed = {
        "type": "compressed",
        "summary": summary,
        "original_count": len(old),
        "compressed_at_step": state.step
    }
    
    # 替换
    state.memory.tool_results_history = [compressed] + recent
```

#### 策略 2：基于重要性的压缩（推荐）

```python
# 根据重要性评分，保留重要的，压缩不重要的
def compress_by_importance(state, target_size):
    # 计算每个工具结果的重要性
    scored_results = []
    for result in state.memory.tool_results_history:
        score = calculate_importance(result)
        scored_results.append((score, result))
    
    # 排序
    scored_results.sort(key=lambda x: x[0], reverse=True)
    
    # 保留重要的
    important = [r for _, r in scored_results[:target_size]]
    
    # 压缩不重要的
    less_important = [r for _, r in scored_results[target_size:]]
    summary = summarize_tool_results(less_important)
    
    compressed = {
        "type": "compressed",
        "summary": summary,
        "original_count": len(less_important)
    }
    
    state.memory.tool_results_history = [compressed] + important

def calculate_importance(result):
    """计算工具结果的重要性"""
    score = 0.0
    
    # 1. 错误结果更重要
    if not result.get("result", {}).get("ok", True):
        score += 1.0
    
    # 2. 文件修改更重要
    if result.get("tool") in ["write_file", "edit_file", "append_file"]:
        score += 0.5
    
    # 3. 最近的更重要
    step = result.get("step", 0)
    current_step = state.step
    recency = max(0, 1.0 - (current_step - step) / 10.0)
    score += recency * 0.3
    
    # 4. 有占位符的更重要（表示是文件内容）
    if result.get("placeholder"):
        score += 0.2
    
    return score
```

#### 策略 3：LLM 压缩（可选，用于复杂场景）

```python
# 使用 LLM 压缩旧的记忆
def compress_with_llm(state, llm_client, target_size):
    # 选择要压缩的内容
    to_compress = state.memory.tool_results_history[:-target_size]
    
    # 构建压缩提示
    prompt = f"""请将以下工具执行历史压缩为简洁摘要：

{format_tool_results_for_compression(to_compress)}

要求：
1. 保留关键信息：错误、重要输出、文件修改
2. 移除冗余和重复
3. 摘要长度控制在 {target_size // 2} 字符以内
4. 使用结构化格式（Markdown）
"""
    
    # 调用 LLM
    compressed_summary = llm_client.compress(prompt)
    
    # 创建压缩记录
    compressed = {
        "type": "llm_compressed",
        "summary": compressed_summary,
        "original_count": len(to_compress)
    }
    
    # 替换
    recent = state.memory.tool_results_history[-target_size:]
    state.memory.tool_results_history = [compressed] + recent
```

### 4.4 压缩配置

```python
@dataclass
class MemoryCompressionConfig:
    # 基于规则的压缩
    tool_results_keep_recent: int = 10
    decisions_keep_recent: int = 5
    important_decisions_keep: int = 20
    milestones_keep: int = 20
    learnings_keep: int = 10
    
    # 基于重要性的压缩
    importance_compression_enabled: bool = True
    importance_threshold: float = 0.3  # 低于此分数将被压缩
    
    # LLM 压缩
    llm_compression_enabled: bool = False
    llm_compression_threshold: int = 100000  # 超过此大小触发 LLM 压缩
    llm_compression_target: int = 50000  # 压缩目标大小
    
    # 去重
    deduplication_enabled: bool = True
    deduplication_similarity_threshold: float = 0.8
```

### 4.5 压缩流程

```
1. 在 PlanPhase 之前，检查 memory 大小
   ↓
2. 使用 CompressionPolicy.estimate_size() 估算大小
   ↓
3. 如果超过阈值，选择压缩策略并执行压缩
   ↓
4. 压缩策略内部按优先级处理：
   a. 长期记忆：修剪到 Top N（不压缩）
   b. 短期记忆：保留最近 N 个，压缩旧的为摘要
   c. 调试信息：可选删除
   ↓
5. 压缩策略返回修改后的 memory
   ↓
6. 使用 memory.get_formatted_context() 获取格式化输出
   ↓
7. 验证格式化后的字符串大小
```

### 4.6 压缩策略配置

```python
@dataclass
class CompressionConfig:
    """压缩配置"""
    
    # 压缩策略选择
    policy_type: str = "importance_based"  # "rule_based" | "importance_based" | "llm"
    
    # 压缩阈值
    compression_threshold: int = 80000  # 超过此大小触发压缩
    target_size: int = 50000  # 压缩目标大小
    
    # 基于规则的压缩参数
    rule_based_keep_recent: Dict[str, int] = field(default_factory=lambda: {
        "tool_results": 10,
        "decisions": 5,
        "important_decisions": 20,
        "milestones": 20,
        "learnings": 10
    })
    
    # 基于重要性的压缩参数
    importance_threshold: float = 0.3  # 低于此分数将被压缩
    
    # LLM 压缩参数
    llm_compression_enabled: bool = False
    llm_client: Optional[Any] = None
```

### 4.7 架构优势

**分离关注点的优势**：
1. **Memory 模块职责单一**：只负责数据管理和格式化
2. **压缩策略可插拔**：可以轻松切换不同的压缩策略
3. **易于测试**：Memory 和 CompressionPolicy 可以独立测试
4. **易于扩展**：添加新的压缩策略不需要修改 Memory 模块
5. **清晰的接口**：`get_formatted_context()` 是唯一的输出接口

---

## 五、实施计划

### 阶段 1：统一工具执行结果显示（1-2 天）
- [ ] 修改 `summarizer.py`，移除重复显示
- [ ] 测试验证，确保功能正常
- [ ] 测量 Token 节省效果

### 阶段 2：重构架构（3-5 天）
- [ ] 重构 `Memory` 类，添加 `get_formatted_context()` 接口
- [ ] 创建 `MemoryFormatter` 类，负责格式化各个部分
- [ ] 创建 `CompressionPolicy` 接口和实现类
- [ ] 将现有压缩逻辑迁移到 `CompressionPolicy` 实现
- [ ] 修改 `ActPhase`，统一使用 `tool_results_history`
- [ ] 添加向后兼容层
- [ ] 测试验证

### 阶段 3：代码精炼（2-3 天）
- [ ] 创建 `ToolResultFormatter` 类
- [ ] 重构 `summarizer.py`，使用统一格式化函数
- [ ] 测试验证

### 阶段 4：实现理想格式（3-5 天）
- [ ] 实现新的 prompt 格式
- [ ] 添加配置选项，支持新旧格式切换
- [ ] 测试验证
- [ ] 逐步迁移到新格式

### 阶段 5：完善压缩策略（2-3 天）
- [ ] 实现 `ImportanceBasedCompressionPolicy`
- [ ] 实现 `LLMCompressionPolicy`（可选）
- [ ] 添加压缩策略配置
- [ ] 测试验证压缩效果

**总预计时间**：11-18 天

### 阶段 6：迁移到新格式（2-3 天）
- [ ] 实现新的 prompt 格式（参考 `MEMORY_PROMPT_FORMAT_DEMO.md`）
- [ ] 更新 `MemoryFormatter` 使用新格式
- [ ] 更新 prompt 模板使用新接口
- [ ] 测试验证新格式效果
- [ ] 逐步迁移到新格式

**总预计时间**：13-21 天

---

## 六、风险评估与缓解

### 风险 1：破坏现有功能
**缓解**：
- 保持向后兼容
- 分阶段实施，每阶段充分测试
- 添加配置选项，支持回滚

### 风险 2：性能影响
**缓解**：
- 压缩策略可配置，默认使用轻量级策略
- LLM 压缩可选，默认关闭
- 监控压缩耗时

### 风险 3：信息丢失
**缓解**：
- 压缩时保留摘要，不直接删除
- 重要信息（错误、文件修改）始终保留
- 提供压缩日志，便于调试

---

## 七、成功指标

1. **Token 节省**：减少 30-50% 的 memory prompt 大小
2. **代码质量**：减少 40-60% 的重复代码
3. **维护性**：单一数据源，修改一处即可
4. **性能**：压缩耗时 < 100ms（基于规则的压缩）
5. **功能完整性**：所有现有功能正常工作

---

## 八、总结

本重构方案旨在：
1. **消除重复**：统一工具执行结果显示，减少 Token 浪费
2. **明确职责**：重构数据存储结构，明确各字段职责
3. **分离关注点**：Memory 负责数据管理和格式化，Compression 作为独立策略
4. **简化接口**：提供单一接口 `get_formatted_context()` 获取格式化输出
5. **优化格式**：设计理想的 prompt 格式，提高 LLM 理解效率（详见 `MEMORY_PROMPT_FORMAT_DEMO.md`）
6. **可扩展压缩**：通过 CompressionPolicy 接口支持不同的压缩策略

### 8.1 关键改进点

**架构改进**：
- ✅ Memory 模块职责单一：只负责数据管理和格式化
- ✅ 压缩作为独立策略：通过接口注入，支持不同策略
- ✅ 单一输出接口：`get_formatted_context()` 是唯一的格式化输出接口

**格式改进**：
- ✅ 层次清晰：从重要到次要，从长期到短期
- ✅ 指导性强：明确告诉 LLM 下一步应该做什么
- ✅ 信息密度高：避免冗余，每个信息只出现一次

**代码改进**：
- ✅ 减少重复：统一格式化逻辑
- ✅ 易于维护：清晰的职责划分
- ✅ 易于扩展：支持新的压缩策略和格式选项

通过分阶段实施，可以在保持业务功能不变的前提下，显著提升代码质量和系统性能。

### 8.2 相关文档

- **格式设计文档**：`MEMORY_PROMPT_FORMAT_DEMO.md` - 包含详细的格式设计和示例
- **本重构方案**：`MEMORY_REFACTORING_PLAN.md` - 包含重构计划和架构设计
