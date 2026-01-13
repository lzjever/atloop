# 三部分交互式界面实现计划

## 概述

本计划旨在实现一个三部分交互式显示界面，用于在verbose模式下展示agent执行状态。界面分为：
1. **顶部固定区域**：显示状态统计（Files/Execution/Memory/Budget + Token数 + 运行时间）
2. **中间区域**：显示最近的thoughts和plan以及当前phase
3. **底部滚动区域**：显示LLM的原始输出历史

**当前状态**：单行表格显示已实现（Files/Execution/Memory/Budget在一行显示）

---

## 一、架构设计

### 1.1 界面布局结构

```
┌─────────────────────────────────────────────────────────────┐
│ 顶部固定区域 (Top Fixed Panel)                              │
│ - Files/Execution/Memory/Budget 单行表格                    │
│ - 累计Token数、运行时间等扩展信息                            │
├─────────────────────────────────────────────────────────────┤
│ 中间区域 (Middle Panel)                                     │
│ - 当前Phase                                                  │
│ - 最近的Thoughts (current_step_thoughts)                    │
│ - 当前的Plan                                                 │
├─────────────────────────────────────────────────────────────┤
│ 底部滚动区域 (Bottom Scrollable Panel)                      │
│ - LLM原始输出历史 (最近N条，滚动显示)                        │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 技术方案选择

**方案A：ANSI转义码 + 清屏重绘（推荐）**
- **优点**：固定位置显示，用户体验好
- **缺点**：需要处理终端兼容性问题
- **实现**：使用 `\033[H` 定位光标、`\033[J` 清屏、`\033[s`/`\033[u` 保存/恢复光标位置

**方案B：简单滚动缓冲区**
- **优点**：实现简单，兼容性好
- **缺点**：无法固定顶部区域
- **实现**：维护固定行数的输出缓冲区，每次更新时重绘

**推荐方案**：方案A（ANSI转义码），提供更好的用户体验。

---

## 二、数据结构扩展

### 2.1 扩展 `BudgetUsed` 类

**位置**：`atloop/memory/state.py`

**需要添加字段**：
```python
@dataclass
class BudgetUsed:
    llm_calls: int = 0
    tool_calls: int = 0
    wall_time_sec: int = 0
    # 新增字段
    total_tokens: int = 0  # 累计总token数
    input_tokens: int = 0  # 累计输入token数
    output_tokens: int = 0  # 累计输出token数
```

**修改点**：
- 在 `BudgetUsed` dataclass 中添加三个新字段
- 确保 `to_dict()` 和 `from_dict()` 方法包含新字段（如果存在）

### 2.2 Token累积机制

**位置**：`atloop/orchestrator/phases/plan.py`

**修改点**：在 `PlanPhase.execute()` 中，LLM调用返回 `usage_info` 后

**具体位置**：约 line 198，获取 `usage_info` 后

**代码示例**：
```python
# 在 line ~198 附近，获取usage_info后
action_json, error, usage, full_output, file_contents = (
    self.coordinator.llm_client.plan_and_act(...)
)

# 累积token使用量
if usage:
    state.budget_used.total_tokens += usage.get("total_tokens", 0)
    state.budget_used.input_tokens += usage.get("input_tokens", 0)
    state.budget_used.output_tokens += usage.get("output_tokens", 0)
```

**注意事项**：
- 确保 `usage` 不为 None
- 处理缺失字段的情况（使用 `.get()` 方法）
- 只在成功调用LLM后累积（避免重复计算）

---

## 三、显示模块设计

### 3.1 创建新的显示模块

**文件**：`atloop/orchestrator/interactive_display.py`

**主要类结构**：
```python
class InteractiveDisplay:
    """三部分交互式显示管理器"""
    
    def __init__(self, max_llm_output_lines: int = 20):
        self.max_llm_output_lines = max_llm_output_lines
        self.llm_output_buffer = []  # 存储LLM输出历史
        self.supports_ansi = self._check_ansi_support()  # 检测ANSI支持
        
    def render_top_panel(self, state: AgentState) -> str:
        """渲染顶部固定面板"""
        # 1. 调用 format_memory_stats 获取单行表格
        # 2. 添加扩展信息行（Token数、运行时间等）
        pass
        
    def render_middle_panel(self, state: AgentState) -> str:
        """渲染中间面板（thoughts + plan）"""
        # 1. 显示当前Phase
        # 2. 显示最近的Thoughts（截断）
        # 3. 显示当前Plan（截断）
        pass
        
    def render_bottom_panel(self) -> str:
        """渲染底部滚动面板（LLM输出）"""
        # 显示最近N条LLM输出
        pass
        
    def update_llm_output(self, llm_output: str, step: int):
        """更新LLM输出缓冲区"""
        # 添加到缓冲区，保持最大行数限制
        pass
        
    def render_full_display(self, state: AgentState) -> str:
        """渲染完整三部分界面"""
        # 组合三个面板
        pass
        
    def clear_screen(self):
        """清屏并重置光标位置（如果支持ANSI）"""
        pass
        
    def _check_ansi_support(self) -> bool:
        """检测终端是否支持ANSI转义码"""
        pass
```

### 3.2 顶部面板实现

**功能**：
1. **单行表格**：Files/Execution/Memory/Budget（已实现，调用 `format_memory_stats`）
2. **扩展信息行**：
   - 累计Token：`Total: {total_tokens} (In: {input_tokens}, Out: {output_tokens})`
   - 运行时间：`Runtime: {wall_time_sec}s`（已有）
   - 任务进度：`Progress: Step {step} / Phase: {phase}`

**数据来源**：
- `state.budget_used`（扩展后包含token信息）
- `state.step`, `state.phase`

**实现要点**：
- 复用现有的 `format_memory_stats()` 函数
- 在表格下方添加扩展信息行
- 格式化数字（如：1,234 tokens）

### 3.3 中间面板实现

**功能**：
1. **当前Phase**：显示当前阶段（DISCOVER/PLAN/ACT/VERIFY）
2. **最近的Thoughts**：
   - 来源：`state.memory.llm_responses[-1]["current_step_thoughts"]`
   - 如果没有，使用 `state.memory.decisions[-1]["current_step_thoughts"]`
   - 显示格式：截断到3-5行，过长时显示"..."
3. **当前Plan**：
   - 来源：`state.memory.plan`
   - 如果是list，显示前5项
   - 如果是string，显示前5行

**数据来源**：
- `state.phase`
- `state.memory.llm_responses[-1]` 或 `state.memory.decisions[-1]`
- `state.memory.plan`

**实现要点**：
- 处理空值情况（没有thoughts或plan时显示提示）
- 文本截断函数（见5.2节）
- 格式化显示（使用分隔线、缩进等）

### 3.4 底部面板实现

**功能**：
1. **滚动显示LLM原始输出历史**
2. **保留最近N条**（默认20条）
3. **每条显示**：
   - Step编号
   - 时间戳（可选）
   - 输出内容（截断到合理长度）

**数据来源**：
- `state.memory.llm_responses`（按step倒序取最近N条）
- 或维护独立的输出缓冲区

**实现要点**：
- 维护固定大小的缓冲区（FIFO队列）
- 每条输出显示格式：`[Step N] {truncated_output}...`
- 支持配置最大行数

---

## 四、集成点

### 4.1 修改 `Workflow._print_memory_stats()`

**位置**：`atloop/orchestrator/workflow/workflow.py`

**修改方案**：
```python
def _print_memory_stats(self, state: Any) -> None:
    """Print interactive three-panel display if verbose mode is enabled."""
    from atloop.orchestrator.interactive_display import InteractiveDisplay
    
    # 初始化display实例（如果不存在）
    if not hasattr(self, '_display'):
        self._display = InteractiveDisplay(max_llm_output_lines=20)
    
    # 更新LLM输出（如果有）
    if state.memory.llm_responses:
        latest = state.memory.llm_responses[-1]
        if latest.get("llm_output"):
            self._display.update_llm_output(
                latest["llm_output"], 
                latest["step"]
            )
    
    # 渲染并显示
    display_output = self._display.render_full_display(state)
    
    # 如果支持ANSI，使用清屏重绘；否则直接打印
    if self._display.supports_ansi:
        print(self._display.clear_screen(), end='')
    print(display_output)
```

**注意事项**：
- 检查 `verbose` 模式是否启用
- 延迟初始化 `_display` 实例
- 处理ANSI支持检测

### 4.2 在LLM调用后更新输出

**位置**：`atloop/orchestrator/phases/plan.py`

**修改点**：在获取 `full_output` 后（约 line 198）

**代码示例**：
```python
# 在获取full_output后
action_json, error, usage, full_output, file_contents = (
    self.coordinator.llm_client.plan_and_act(...)
)

# 累积token（见2.2节）
if usage:
    state.budget_used.total_tokens += usage.get("total_tokens", 0)
    state.budget_used.input_tokens += usage.get("input_tokens", 0)
    state.budget_used.output_tokens += usage.get("output_tokens", 0)

# 更新显示（如果verbose模式）
if self.coordinator.verbose and full_output:
    # 通过coordinator访问display实例
    if hasattr(self.coordinator, '_display'):
        self.coordinator._display.update_llm_output(full_output, state.step)
```

**注意事项**：
- 只在verbose模式下更新
- 确保coordinator有 `_display` 属性（在workflow中初始化）

---

## 五、实现细节

### 5.1 ANSI转义码使用

**常用ANSI转义码**：
```python
# 清屏并移动光标到顶部
CLEAR_SCREEN = "\033[2J\033[H"

# 保存/恢复光标位置
SAVE_CURSOR = "\033[s"
RESTORE_CURSOR = "\033[u"

# 移动光标到指定位置 (row, col)
def move_cursor(row: int, col: int) -> str:
    return f"\033[{row};{col}H"

# 隐藏/显示光标
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
```

**使用示例**：
```python
def clear_screen(self) -> str:
    """清屏并重置光标位置"""
    if self.supports_ansi:
        return CLEAR_SCREEN
    return "\n" * 50  # 回退方案：打印多行空行
```

### 5.2 文本截断和格式化

**截断函数**：
```python
def truncate_text(text: str, max_lines: int, max_chars_per_line: int = 80) -> str:
    """截断文本到指定行数和每行字符数"""
    if not text:
        return ""
    
    lines = text.split('\n')
    truncated = lines[:max_lines]
    
    # 如果超过最大行数，添加省略号
    if len(lines) > max_lines:
        truncated.append("...")
    
    # 截断每行长度
    result = []
    for line in truncated:
        if len(line) > max_chars_per_line:
            result.append(line[:max_chars_per_line-3] + "...")
        else:
            result.append(line)
    
    return '\n'.join(result)
```

**格式化函数**：
```python
def format_number(num: int) -> str:
    """格式化数字（添加千位分隔符）"""
    return f"{num:,}"

def format_time(seconds: int) -> str:
    """格式化时间（秒 -> 时:分:秒）"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"
```

### 5.3 兼容性处理

**ANSI支持检测**：
```python
def _check_ansi_support(self) -> bool:
    """检测终端是否支持ANSI转义码"""
    import os
    import sys
    
    # 检查环境变量
    term = os.getenv('TERM', '')
    if term in ('dumb', 'unknown'):
        return False
    
    # 检查是否在终端中
    if not sys.stdout.isatty():
        return False
    
    # 检查NO_COLOR环境变量
    if os.getenv('NO_COLOR'):
        return False
    
    return True
```

**回退方案**：
- 不支持ANSI时，使用简单的换行分隔
- 不进行清屏操作，直接追加输出
- 保持向后兼容性

---

## 六、配置选项

### 6.1 添加配置项

**位置**：`atloop/config/models.py` 或相关配置类

**配置结构**：
```python
@dataclass
class DisplayConfig:
    """显示配置"""
    interactive_display: bool = True  # 是否启用交互式显示
    max_llm_output_lines: int = 20  # 底部面板最大行数
    top_panel_always_visible: bool = True  # 顶部面板是否始终可见
    middle_panel_max_thought_lines: int = 5  # 中间面板thoughts最大行数
    middle_panel_max_plan_items: int = 5  # 中间面板plan最大项数
    use_ansi_escape: bool = True  # 是否使用ANSI转义码
```

**集成到主配置**：
- 在 `AtloopConfig` 中添加 `display: DisplayConfig` 字段
- 提供默认值
- 支持从YAML配置文件加载

---

## 七、测试计划

### 7.1 单元测试

**文件**：`tests/test_interactive_display.py`

**测试用例**：
1. **顶部面板测试**：
   - `test_render_top_panel_basic()` - 基础渲染
   - `test_render_top_panel_with_tokens()` - 包含token信息
   - `test_render_top_panel_empty_state()` - 空状态处理

2. **中间面板测试**：
   - `test_render_middle_panel_with_thoughts()` - 有thoughts的情况
   - `test_render_middle_panel_without_thoughts()` - 无thoughts的情况
   - `test_render_middle_panel_with_plan()` - 有plan的情况
   - `test_render_middle_panel_text_truncation()` - 文本截断

3. **底部面板测试**：
   - `test_render_bottom_panel_empty()` - 空缓冲区
   - `test_render_bottom_panel_with_outputs()` - 有输出
   - `test_render_bottom_panel_max_lines()` - 最大行数限制
   - `test_update_llm_output()` - 更新缓冲区

4. **ANSI支持测试**：
   - `test_ansi_support_detection()` - ANSI支持检测
   - `test_clear_screen_with_ansi()` - ANSI清屏
   - `test_clear_screen_without_ansi()` - 无ANSI回退

5. **文本处理测试**：
   - `test_truncate_text()` - 文本截断函数
   - `test_format_number()` - 数字格式化
   - `test_format_time()` - 时间格式化

### 7.2 集成测试

**文件**：`tests/test_interactive_display_integration.py`

**测试用例**：
1. **Workflow集成测试**：
   - `test_display_in_workflow_verbose_mode()` - 在workflow中显示
   - `test_token_accumulation()` - Token累积测试
   - `test_llm_output_updates()` - LLM输出更新测试

2. **多轮执行测试**：
   - `test_multiple_steps_display()` - 多步执行显示
   - `test_scrollable_output_buffer()` - 滚动缓冲区测试

### 7.3 手动测试清单

- [ ] 在支持ANSI的终端中测试（如：xterm, gnome-terminal）
- [ ] 在不支持ANSI的终端中测试（如：dumb terminal）
- [ ] 测试verbose模式开关
- [ ] 测试长时间运行（验证内存使用）
- [ ] 测试大量LLM输出（验证滚动性能）

---

## 八、实施步骤

### Phase 1：数据结构扩展（优先级：高）

**任务清单**：
- [ ] 扩展 `BudgetUsed` 类，添加token字段
- [ ] 更新 `to_dict()` 和 `from_dict()` 方法（如果存在）
- [ ] 在 `PlanPhase.execute()` 中添加token累积逻辑
- [ ] 编写单元测试验证token累积

**预计时间**：1-2小时

### Phase 2：显示模块基础（优先级：高）

**任务清单**：
- [ ] 创建 `InteractiveDisplay` 类
- [ ] 实现 `render_top_panel()` 方法
- [ ] 实现 `render_middle_panel()` 方法
- [ ] 实现 `render_bottom_panel()` 方法
- [ ] 实现 `render_full_display()` 方法
- [ ] 实现文本截断和格式化辅助函数
- [ ] 编写单元测试

**预计时间**：4-6小时

### Phase 3：集成到Workflow（优先级：高）

**任务清单**：
- [ ] 修改 `Workflow._print_memory_stats()` 方法
- [ ] 在 `PlanPhase` 中添加LLM输出更新逻辑
- [ ] 处理display实例的初始化
- [ ] 编写集成测试

**预计时间**：2-3小时

### Phase 4：ANSI优化（优先级：中）

**任务清单**：
- [ ] 实现ANSI支持检测
- [ ] 实现清屏和光标定位功能
- [ ] 添加回退方案（无ANSI支持时）
- [ ] 测试不同终端环境

**预计时间**：2-3小时

### Phase 5：配置和优化（优先级：低）

**任务清单**：
- [ ] 添加配置选项
- [ ] 性能优化（避免频繁重绘）
- [ ] 文档更新
- [ ] 最终测试

**预计时间**：2-3小时

**总预计时间**：11-17小时

---

## 九、注意事项

### 9.1 性能考虑

- **避免频繁清屏重绘**：可以设置最小更新间隔（如：每500ms最多更新一次）
- **限制缓冲区大小**：LLM输出缓冲区不要无限增长
- **延迟初始化**：只在verbose模式下初始化display实例

### 9.2 兼容性

- **终端检测**：检测终端类型，不支持ANSI时自动回退
- **环境变量**：尊重 `NO_COLOR` 等环境变量
- **向后兼容**：保留原有的 `format_memory_stats()` 作为fallback

### 9.3 可配置性

- **提供开关**：允许用户禁用交互式显示
- **可调参数**：最大行数、截断长度等可配置
- **配置优先级**：命令行参数 > 配置文件 > 默认值

### 9.4 错误处理

- **优雅降级**：ANSI失败时自动回退到简单模式
- **空值处理**：处理missing thoughts/plan的情况
- **异常捕获**：display相关异常不应影响主流程

---

## 十、文件清单

### 需要创建的文件

1. **`atloop/orchestrator/interactive_display.py`**
   - 主要显示模块
   - `InteractiveDisplay` 类
   - 所有渲染和格式化函数

2. **`tests/test_interactive_display.py`**
   - 单元测试
   - 覆盖所有主要功能

3. **`tests/test_interactive_display_integration.py`**
   - 集成测试
   - Workflow集成测试

### 需要修改的文件

1. **`atloop/memory/state.py`**
   - 扩展 `BudgetUsed` 类
   - 添加token字段

2. **`atloop/orchestrator/phases/plan.py`**
   - 添加token累积逻辑
   - 添加LLM输出更新逻辑

3. **`atloop/orchestrator/workflow/workflow.py`**
   - 修改 `_print_memory_stats()` 方法
   - 集成 `InteractiveDisplay`

4. **`atloop/config/models.py`**（可选）
   - 添加 `DisplayConfig` 类
   - 集成到主配置

### 文档更新

1. **`docs/VERBOSE_AND_BREAKPOINT.md`**（如果存在）
   - 更新verbose模式说明
   - 添加交互式显示说明

2. **README.md**（如果相关）
   - 添加新功能说明

---

## 十一、验收标准

### 功能验收

- [ ] 顶部面板正确显示Files/Execution/Memory/Budget单行表格
- [ ] 顶部面板正确显示累计Token数和运行时间
- [ ] 中间面板正确显示当前Phase
- [ ] 中间面板正确显示最近的Thoughts（截断）
- [ ] 中间面板正确显示当前Plan（截断）
- [ ] 底部面板正确显示LLM输出历史（滚动）
- [ ] Token数正确累积
- [ ] 支持ANSI的终端使用固定位置显示
- [ ] 不支持ANSI的终端使用回退方案

### 质量验收

- [ ] 所有单元测试通过
- [ ] 所有集成测试通过
- [ ] 代码通过lint检查
- [ ] 文档完整
- [ ] 性能可接受（无明显延迟）

### 兼容性验收

- [ ] 在支持ANSI的终端中正常工作
- [ ] 在不支持ANSI的终端中正常回退
- [ ] 向后兼容（不影响现有功能）
- [ ] 配置选项生效

---

## 十二、后续优化建议

### 短期优化

1. **性能优化**：
   - 实现增量更新（只更新变化的部分）
   - 使用线程安全的缓冲区

2. **用户体验**：
   - 添加颜色高亮（如果支持ANSI）
   - 添加进度条（如果适用）

### 长期优化

1. **功能扩展**：
   - 支持交互式操作（如：暂停、继续）
   - 支持导出显示内容

2. **架构改进**：
   - 考虑使用更现代的终端UI库（如：rich, textual）
   - 支持Web界面（如果未来有需求）

---

## 附录

### A. 相关文件参考

- `atloop/orchestrator/memory_stats.py` - 现有memory stats实现
- `atloop/memory/state.py` - 状态数据结构
- `atloop/orchestrator/workflow/workflow.py` - Workflow主循环
- `atloop/orchestrator/phases/plan.py` - Plan phase实现

### B. 外部依赖

- `prettytable` - 表格格式化（已存在）
- Python标准库：`os`, `sys` - 终端检测

### C. 参考资料

- ANSI转义码：https://en.wikipedia.org/wiki/ANSI_escape_code
- Terminal compatibility：https://no-color.org/

---

**文档版本**：1.0  
**创建日期**：2025-01-XX  
**最后更新**：2025-01-XX  
**维护者**：开发团队
