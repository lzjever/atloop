# Memory Formatter 配置重构方案

## 问题分析

### 当前问题

1. **硬编码重复**：
   - `plan.py` line 63: `"steps_summary_count": 20`
   - `discover.py` line 59: `"steps_summary_count": 20`
   - `formatter.py` line 285: `options.get("steps_summary_count", 20)`
   - `formatter.py` line 500: `steps_count: int = 20`

2. **配置分散**：
   - 同样的值在 4 个地方定义
   - 修改需要同步更新多个文件
   - 容易产生不一致

3. **未使用现有配置系统**：
   - 已有 `MemoryConfig` 在 `config/models.py`
   - 但 `steps_summary_count` 等格式化选项未纳入配置系统
   - 其他类似配置项也有同样问题：
     - `tool_results_count` (默认 5)
     - `max_file_content_length` (默认 20000)

4. **违反设计原则**：
   - **DRY (Don't Repeat Yourself)**: 值重复定义
   - **Single Source of Truth**: 没有单一配置源
   - **Separation of Concerns**: 格式化配置应该集中在配置系统

## 改进方案

### 方案 1: 在 MemoryConfig 中添加格式化配置（推荐）

**优点**：
- 利用现有配置系统
- 单一数据源
- 可通过配置文件修改
- 类型安全

**实施步骤**：

1. **在 `MemoryConfig` 中添加格式化配置**：
```python
@dataclass(frozen=True)
class MemoryConfig:
    # ... existing fields ...
    
    # Formatting options
    steps_summary_count: int = field(
        default=20,
        metadata={"description": "Number of recent steps to show in Recent Activity"}
    )
    tool_results_count: int = field(
        default=5,
        metadata={"description": "Number of tool results to show in Tool Execution Results"}
    )
    max_file_content_length: int = field(
        default=20000,
        metadata={"description": "Maximum file content length in memory summary"}
    )
    include_file_content: bool = field(
        default=True,
        metadata={"description": "Whether to include file content in memory summary"}
    )
```

2. **在 `MemoryFormatter` 中从配置读取默认值**：
```python
class MemoryFormatter:
    def __init__(self, tool_registry: Optional[Any] = None):
        self.tool_registry = tool_registry
        self.tool_result_formatter = ToolResultFormatter()
        # Load default format options from config
        self._load_default_format_options()
    
    def _load_default_format_options(self):
        """Load default format options from config."""
        config = ConfigLoader.get()
        self.default_format_options = {
            "steps_summary_count": config.memory.steps_summary_count,
            "tool_results_count": config.memory.tool_results_count,
            "max_file_content_length": config.memory.max_file_content_length,
            "include_file_content": config.memory.include_file_content,
        }
    
    def format(self, state, task_goal=None, format_options=None):
        options = {**self.default_format_options, **(format_options or {})}
        # ... rest of the code
```

3. **在 `plan.py` 和 `discover.py` 中使用配置**：
```python
# In plan.py and discover.py
config = ConfigLoader.get()
memory_context = state.memory.get_formatted_context(
    state=state,
    task_goal=self.coordinator.task_spec.goal,
    max_length=memory_summary_max_length,
    format_options={
        "tool_results_count": config.memory.tool_results_count,
        "steps_summary_count": config.memory.steps_summary_count,
        "include_file_content": config.memory.include_file_content,
        "max_file_content_length": config.memory.max_file_content_length,
    },
    tool_registry=self.coordinator.tool_runtime.registry,
)
```

### 方案 2: 创建 FormatOptions 类（更灵活）

**优点**：
- 更清晰的配置结构
- 可以独立配置不同场景
- 更好的类型提示

**缺点**：
- 需要额外的配置类
- 可能过度设计

### 方案 3: 在 MemoryFormatter 中定义常量（简单但不够灵活）

**优点**：
- 实施简单
- 单一数据源（在 formatter 中）

**缺点**：
- 无法通过配置文件修改
- 不够灵活

## 推荐方案：方案 1

### 理由

1. **利用现有架构**：`MemoryConfig` 已经存在，应该充分利用
2. **单一数据源**：所有配置在 `config/models.py` 中定义
3. **可配置性**：用户可以通过配置文件修改
4. **一致性**：与其他 memory 配置保持一致
5. **类型安全**：dataclass 提供类型检查

### 实施细节

1. **配置定义**：在 `MemoryConfig` 中添加格式化选项
2. **默认值加载**：`MemoryFormatter` 从配置加载默认值
3. **调用方使用配置**：`plan.py` 和 `discover.py` 从配置读取
4. **向后兼容**：`format_options` 参数仍然可以覆盖配置值

## 其他改进建议

### 1. 统一所有格式化选项

不仅 `steps_summary_count`，其他格式化选项也应该统一：
- `tool_results_count`
- `max_file_content_length`
- `include_file_content`

### 2. 配置验证

在 `MemoryConfig` 中添加验证：
```python
def __post_init__(self):
    if self.steps_summary_count < 1:
        raise ValueError("steps_summary_count must be >= 1")
    if self.tool_results_count < 1:
        raise ValueError("tool_results_count must be >= 1")
```

### 3. 文档更新

更新相关文档，说明如何通过配置文件修改这些选项。

## 总结

当前设计确实存在冗余和结构问题：
- ✅ 你的观察是正确的
- ✅ 有明确的改进空间
- ✅ 应该遵循单一数据源原则
- ✅ 应该利用现有配置系统

推荐采用方案 1，将格式化选项纳入 `MemoryConfig`，实现配置的统一管理。
