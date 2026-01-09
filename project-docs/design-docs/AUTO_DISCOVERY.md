# 工具自动发现机制

## 概述

工具注册机制已从手动注册改为基于 AST 的自动发现。这消除了手动注册时的错误，并确保所有工具都能自动被发现和注册。

## 工作原理

### 1. AST 扫描
- 自动扫描 `atloop/tools/` 目录下的所有 Python 文件
- 使用 AST 解析找到所有继承自 `BaseTool` 的类
- 跳过 `__init__.py`、`base.py`、`registry.py` 和测试文件

### 2. 自动导入
- 自动计算正确的模块路径
- 动态导入工具类
- 验证类确实是 `BaseTool` 的子类

### 3. 自动实例化
- 通过检查 `__init__` 签名自动确定需要的参数
- 根据参数名称自动传递 `sandbox` 或 `skill_loader`
- 处理不同的构造函数签名

### 4. 自动注册
- 自动实例化所有发现的工具
- 使用工具的名称属性注册到 registry
- 提供详细的注册统计信息

## 优势

### ✅ 消除手动错误
- **之前**：需要手动导入每个工具类
- **现在**：自动发现，不会遗漏工具

### ✅ 自动包含新工具
- **之前**：添加新工具需要修改 `registry.py`
- **现在**：只需创建工具类，自动被发现

### ✅ 提取完整信息
- 自动提取类名、模块路径、docstring
- 自动分析构造函数签名
- 可以扩展以提取更多元数据

### ✅ 向后兼容
- 保持 `ToolRegistry` 的 API 不变
- 现有代码无需修改
- 工具接口保持不变

## 使用方式

### 创建新工具

只需创建工具类，继承 `BaseTool`：

```python
# atloop/tools/my_category/my_tool.py
from atloop.tools.base import BaseTool, ToolResult
from atloop.runtime.sandbox_adapter import SandboxAdapter

class MyTool(BaseTool):
    """Tool for doing something."""
    
    def __init__(self, sandbox: SandboxAdapter):
        self.sandbox = sandbox
    
    @property
    def name(self) -> str:
        return "my_tool"
    
    @property
    def description(self) -> str:
        return "Tool description"
    
    def execute(self, args: Dict[str, Any]) -> ToolResult:
        # Implementation
        pass
```

**无需修改 `registry.py`**，工具会自动被发现和注册！

### 工具构造函数参数

自动发现机制支持以下参数：
- `sandbox: SandboxAdapter` - 自动传递
- `skill_loader` - 自动传递（如果提供）

如果工具需要其他参数，可以扩展 `instantiate_tool` 方法。

## 实现细节

### 文件结构

```
atloop/tools/
├── auto_discovery.py    # 自动发现逻辑
├── registry.py          # 注册表（使用自动发现）
├── base.py              # BaseTool 基类
├── filesystem/          # 文件系统工具
├── system/              # 系统工具
├── search/              # 搜索工具
└── interaction/          # 交互工具
```

### 核心类

#### `ToolDiscovery`
- `discover_tool_classes()` - 发现所有工具类
- `get_tool_info()` - 提取工具信息
- `instantiate_tool()` - 实例化工具

#### `auto_register_tools()`
- 自动发现和注册所有工具
- 返回注册统计信息

## 测试

运行测试验证自动发现功能：

```bash
uv run pytest tests/test_auto_tool_discovery.py -v
```

测试覆盖：
- ✅ 工具发现
- ✅ 模块路径提取
- ✅ 工具信息提取
- ✅ 工具实例化
- ✅ 自动注册
- ✅ 向后兼容性

## 日志

自动发现过程会记录详细日志：

```
[ToolRegistry] Auto-discovered 11 tools, registered 11, failed 0
[ToolRegistry] Registered tools: append_file, edit_file, glob, ...
```

## 故障排查

### 工具未被发现

1. **检查类是否继承 BaseTool**
   ```python
   class MyTool(BaseTool):  # ✅ 正确
   class MyTool:            # ❌ 错误
   ```

2. **检查文件位置**
   - 工具文件应在 `atloop/tools/` 或其子目录中
   - 文件名不应包含 "test"

3. **检查模块路径**
   - 确保模块可以正常导入
   - 检查是否有语法错误

### 工具实例化失败

1. **检查构造函数参数**
   - 工具应接受 `sandbox` 或 `skill_loader` 参数
   - 参数名称必须匹配

2. **查看日志**
   - 检查警告信息
   - 查看失败的工具名称

## 未来改进

### 可能的增强
1. **从 docstring 提取参数信息**
   - 自动解析 docstring 中的参数说明
   - 生成更详细的工具描述

2. **工具元数据**
   - 支持工具标签、分类
   - 支持工具依赖关系

3. **工具验证**
   - 验证工具接口完整性
   - 检查必需方法是否存在

## 迁移指南

### 从手动注册迁移

**之前**（手动注册）：
```python
def _register_builtin_tools(self):
    from atloop.tools.filesystem.write_file import WriteFileTool
    self.register(WriteFileTool(self.sandbox))
    # ... 更多手动注册
```

**现在**（自动发现）：
```python
def _register_builtin_tools(self):
    stats = auto_register_tools(
        registry=self,
        sandbox=self.sandbox,
        skill_loader=self.skill_loader
    )
    # 自动完成！
```

**无需其他修改**，所有现有工具都会自动被发现和注册。

## 总结

✅ **自动发现**：使用 AST 自动发现所有工具类
✅ **自动注册**：自动实例化和注册工具
✅ **向后兼容**：保持现有 API 不变
✅ **易于扩展**：添加新工具无需修改注册代码
✅ **完整测试**：所有功能都有测试覆盖
