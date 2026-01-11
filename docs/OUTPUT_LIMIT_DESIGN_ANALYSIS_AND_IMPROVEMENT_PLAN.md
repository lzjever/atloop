# 工具输出限制设计分析与改进计划

## 📋 执行摘要

**问题确认**：
1. ✅ **read_file 工具确实会被截断**：使用 `STDOUT_STDERR_LIMIT_OTHER = 2000` (2KB) 限制，文件内容超过 2KB 会被截断
2. ✅ **当前修复是 workaround**：基于工具名称的特殊处理，不是结构化的解决方案
3. ✅ **设计缺陷**：基于工具名称决定限制，不够灵活，难以扩展，容易遗漏

**改进方向**：
- 从**基于工具名称**的设计改为**基于输出语义类型**的设计
- 建立统一的输出限制策略系统
- 工具可以声明其输出的语义类型，系统自动应用合适的限制

---

## 1. 问题确认

### 1.1 read_file 工具的输出限制问题

**当前状态**：
- `read_file` 工具返回文件内容在 `stdout` 中
- 在 `ToolResultFormatter._format_output` 中：
  ```python
  if tool == "run":
      # ...
  elif tool == "skill":
      max_size = STDOUT_STDERR_LIMIT_FILE_VIEW  # 60KB
  else:
      max_size = STDOUT_STDERR_LIMIT_OTHER  # 2KB ← read_file 使用这个！
  ```
- **结果**：如果文件内容超过 2KB，会被截断为前 1KB + 后 1KB

**影响**：
- ❌ 读取超过 2KB 的文件时，内容被严重截断
- ❌ LLM 无法看到完整的文件内容
- ❌ 可能导致 LLM 重复读取文件或无法正确理解文件内容

### 1.2 其他可能有问题的工具

**需要检查的工具**：
1. **read_skill_file** - 读取 skill 文件内容
   - 当前状态：未知（需要检查）
   - 可能问题：如果使用 `STDOUT_STDERR_LIMIT_OTHER` (2KB)，会被截断

2. **其他内容型工具** - 返回知识/内容而非执行结果的工具
   - 需要系统性地识别所有这类工具

### 1.3 当前修复的问题

**当前修复方式**：
```python
elif tool == "skill":
    max_size = STDOUT_STDERR_LIMIT_FILE_VIEW  # 60KB for skill
```

**问题**：
- ❌ **Workaround，不是结构化解决方案**
- ❌ 需要为每种特殊工具类型添加特殊处理
- ❌ 容易遗漏（如 read_file 就被遗漏了）
- ❌ 难以维护和扩展
- ❌ 不符合设计最佳实践

---

## 2. 根本设计问题分析

### 2.1 当前设计：基于工具名称

**设计模式**：
```python
if tool == "run":
    # 检查命令类型
elif tool == "skill":
    # 特殊处理
else:
    # 默认处理
```

**问题**：
1. **不够灵活**：需要为每种特殊工具类型添加特殊处理
2. **难以扩展**：新增工具类型需要修改多个地方
3. **容易遗漏**：read_file 就被遗漏了
4. **维护困难**：特殊处理逻辑分散在多个地方
5. **不符合开闭原则**：对扩展开放，对修改关闭

### 2.2 设计缺陷的具体表现

**分散的限制设置**：
1. **ToolResultFormatter._format_output** - 决定格式化时的限制
2. **MemorySummarizer.summarize** - 决定 Memory Summary 中的限制
3. **tool_results_history 显示** - 决定历史记录中的限制

**问题**：
- 每个地方都需要重复判断工具类型
- 逻辑不一致的风险
- 难以统一管理

### 2.3 语义类型缺失

**当前设计缺少的概念**：
- **输出语义类型**：工具输出的内容是什么类型的？
  - 知识内容（skill, read_file, read_skill_file）
  - 执行结果（run 命令的输出）
  - 状态信息（write_file, edit_file 的成功/失败消息）
  - 错误信息（stderr）

**为什么重要**：
- 不同类型的输出需要不同的限制策略
- 知识内容需要完整显示（或大限制）
- 执行结果需要适中限制
- 状态信息可以小限制

---

## 3. 结构化改进方案

### 3.1 核心设计理念

**从"基于工具名称"改为"基于输出语义类型"**

**设计原则**：
1. **工具声明语义类型**：工具可以声明其输出的语义类型
2. **统一策略系统**：建立统一的输出限制策略系统
3. **自动应用限制**：系统根据语义类型自动应用合适的限制
4. **易于扩展**：新增工具类型只需声明语义类型，无需修改核心逻辑

### 3.2 输出语义类型定义

**语义类型枚举**：

```python
class OutputSemanticType(Enum):
    """工具输出的语义类型"""
    
    # 知识内容 - 需要完整显示或大限制
    KNOWLEDGE_CONTENT = "knowledge_content"  # skill, read_file, read_skill_file
    
    # 文件内容 - 需要完整显示或大限制
    FILE_CONTENT = "file_content"  # read_file, read_skill_file
    
    # 执行结果 - 需要适中限制
    EXECUTION_RESULT = "execution_result"  # run 命令的输出
    
    # 文件查看结果 - 需要大限制
    FILE_VIEW_RESULT = "file_view_result"  # run("cat file.txt") 的输出
    
    # 状态信息 - 可以小限制
    STATUS_MESSAGE = "status_message"  # write_file, edit_file 的成功/失败消息
    
    # 错误信息 - 需要适中限制
    ERROR_MESSAGE = "error_message"  # stderr
```

### 3.3 工具元数据扩展

**BaseTool 扩展**：

```python
class BaseTool(ABC):
    """Base class for all tools."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description."""
        pass
    
    # ✅ 新增：输出语义类型
    @property
    def output_semantic_type(self) -> OutputSemanticType:
        """
        返回工具输出的语义类型。
        
        默认值：STATUS_MESSAGE（适用于大多数工具）
        子类可以覆盖此属性以声明其输出的语义类型。
        """
        return OutputSemanticType.STATUS_MESSAGE
    
    # ✅ 新增：stdout 的语义类型（可能不同于 stderr）
    @property
    def stdout_semantic_type(self) -> OutputSemanticType:
        """返回 stdout 的语义类型。"""
        return self.output_semantic_type
    
    @property
    def stderr_semantic_type(self) -> OutputSemanticType:
        """返回 stderr 的语义类型（通常是错误信息）。"""
        return OutputSemanticType.ERROR_MESSAGE
```

**工具实现示例**：

```python
class SkillTool(BaseTool):
    @property
    def output_semantic_type(self) -> OutputSemanticType:
        return OutputSemanticType.KNOWLEDGE_CONTENT

class ReadFileTool(BaseTool):
    @property
    def output_semantic_type(self) -> OutputSemanticType:
        return OutputSemanticType.FILE_CONTENT

class ReadSkillFileTool(BaseTool):
    @property
    def output_semantic_type(self) -> OutputSemanticType:
        return OutputSemanticType.FILE_CONTENT
```

### 3.4 统一输出限制策略系统

**OutputLimitStrategy 类**：

```python
class OutputLimitStrategy:
    """统一的输出限制策略系统"""
    
    # 语义类型到限制的映射
    SEMANTIC_TYPE_LIMITS = {
        OutputSemanticType.KNOWLEDGE_CONTENT: STDOUT_STDERR_LIMIT_FILE_VIEW,  # 60KB
        OutputSemanticType.FILE_CONTENT: STDOUT_STDERR_LIMIT_FILE_VIEW,  # 60KB
        OutputSemanticType.FILE_VIEW_RESULT: STDOUT_STDERR_LIMIT_FILE_VIEW,  # 60KB
        OutputSemanticType.EXECUTION_RESULT: STDOUT_STDERR_LIMIT_NORMAL,  # 8KB
        OutputSemanticType.STATUS_MESSAGE: STDOUT_STDERR_LIMIT_OTHER,  # 2KB
        OutputSemanticType.ERROR_MESSAGE: STDOUT_STDERR_LIMIT_NORMAL,  # 8KB
    }
    
    # Memory Summary 中的限制（通常比格式化时小）
    MEMORY_SUMMARY_LIMITS = {
        OutputSemanticType.KNOWLEDGE_CONTENT: MEMORY_SUMMARY_STDOUT_STDERR_SHELL,  # 12KB
        OutputSemanticType.FILE_CONTENT: MEMORY_SUMMARY_STDOUT_STDERR_SHELL,  # 12KB
        OutputSemanticType.FILE_VIEW_RESULT: MEMORY_SUMMARY_STDOUT_STDERR_SHELL,  # 12KB
        OutputSemanticType.EXECUTION_RESULT: MEMORY_SUMMARY_STDOUT_STDERR_SHELL,  # 12KB
        OutputSemanticType.STATUS_MESSAGE: MEMORY_SUMMARY_STDOUT_STDERR_OTHER,  # 4KB
        OutputSemanticType.ERROR_MESSAGE: MEMORY_SUMMARY_STDOUT_STDERR_SHELL,  # 12KB
    }
    
    @classmethod
    def get_limit_for_formatting(
        cls,
        tool: BaseTool,
        is_stderr: bool = False,
        args: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        获取格式化时的输出限制。
        
        Args:
            tool: 工具实例
            is_stderr: 是否是 stderr
            args: 工具参数（用于特殊判断，如 run 命令的文件查看）
        
        Returns:
            输出限制（字符数）
        """
        # 获取语义类型
        semantic_type = (
            tool.stderr_semantic_type if is_stderr
            else tool.stdout_semantic_type
        )
        
        # 特殊处理：run 命令的文件查看
        if tool.name == "run" and args:
            cmd = args.get("cmd", "")
            if is_file_view_command(cmd):
                return STDOUT_STDERR_LIMIT_FILE_VIEW
        
        # 返回对应限制
        return cls.SEMANTIC_TYPE_LIMITS.get(
            semantic_type,
            STDOUT_STDERR_LIMIT_OTHER  # 默认值
        )
    
    @classmethod
    def get_limit_for_memory_summary(
        cls,
        tool: BaseTool,
        is_stderr: bool = False
    ) -> int:
        """
        获取 Memory Summary 中的输出限制。
        
        Args:
            tool: 工具实例
            is_stderr: 是否是 stderr
        
        Returns:
            输出限制（字符数）
        """
        semantic_type = (
            tool.stderr_semantic_type if is_stderr
            else tool.stdout_semantic_type
        )
        
        return cls.MEMORY_SUMMARY_LIMITS.get(
            semantic_type,
            MEMORY_SUMMARY_STDOUT_STDERR_OTHER  # 默认值
        )
```

### 3.5 重构现有代码

**ToolResultFormatter 重构**：

```python
class ToolResultFormatter:
    """Formats tool execution results for LLM consumption."""
    
    @staticmethod
    def format_result_summary(
        tool: BaseTool,  # ✅ 改为接收工具实例，而非工具名称
        args: Dict[str, Any],
        result: Dict[str, Any]
    ) -> str:
        # ...
        stdout_preview = ToolResultFormatter._format_output(
            stdout,
            tool,  # ✅ 传递工具实例
            args,
            is_stderr=False
        )
        # ...
    
    @staticmethod
    def _format_output(
        output: str,
        tool: BaseTool,  # ✅ 改为接收工具实例
        args: Dict[str, Any],
        is_stderr: bool
    ) -> str:
        # ✅ 使用统一策略系统
        max_size = OutputLimitStrategy.get_limit_for_formatting(
            tool,
            is_stderr=is_stderr,
            args=args
        )
        
        if len(output) > max_size:
            # ... 截断逻辑
```

**MemorySummarizer 重构**：

```python
class MemorySummarizer:
    @staticmethod
    def summarize(state: AgentState, ...) -> str:
        # ...
        for result in results:
            tool_name = result.get("tool", "unknown")
            # ✅ 需要从 ToolRegistry 获取工具实例
            tool = tool_registry.get_tool(tool_name)
            
            # ✅ 使用统一策略系统
            max_stdout = OutputLimitStrategy.get_limit_for_memory_summary(
                tool,
                is_stderr=False
            )
            # ...
```

### 3.6 ToolRegistry 扩展

**需要支持的功能**：
1. **根据工具名称获取工具实例**
2. **支持工具实例的查询**

```python
class ToolRegistry:
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """
        根据工具名称获取工具实例。
        
        Args:
            tool_name: 工具名称
        
        Returns:
            工具实例，如果不存在返回 None
        """
        return self._tools.get(tool_name)
```

---

## 4. 实施计划

### 4.1 Phase 1: 定义语义类型和策略系统

**任务**：
1. ✅ 定义 `OutputSemanticType` 枚举
2. ✅ 创建 `OutputLimitStrategy` 类
3. ✅ 定义语义类型到限制的映射

**文件**：
- `atloop/tools/output_semantic_type.py` (新建)
- `atloop/tools/output_limit_strategy.py` (新建)

### 4.2 Phase 2: 扩展 BaseTool

**任务**：
1. ✅ 在 `BaseTool` 中添加 `output_semantic_type` 属性
2. ✅ 在 `BaseTool` 中添加 `stdout_semantic_type` 和 `stderr_semantic_type` 属性
3. ✅ 提供默认实现（STATUS_MESSAGE）

**文件**：
- `atloop/tools/base.py` (修改)

### 4.3 Phase 3: 更新工具实现

**任务**：
1. ✅ 更新 `ReadFileTool` 声明 `FILE_CONTENT`
2. ✅ 更新 `ReadSkillFileTool` 声明 `FILE_CONTENT`
3. ✅ 检查其他工具，必要时更新
4. ⏸️ **Note**: `SkillTool` will be replaced by new tools in Phase 9-14

**文件**：
- `atloop/tools/filesystem/read_file.py` (修改)
- `atloop/tools/filesystem/read_skill_file.py` (修改)

### 4.4 Phase 4: 重构 ToolResultFormatter

**任务**：
1. ✅ 修改 `format_result_summary` 接收工具实例
2. ✅ 修改 `_format_output` 使用 `OutputLimitStrategy`
3. ✅ 移除基于工具名称的特殊处理逻辑

**文件**：
- `atloop/orchestrator/phases/act_result_processor.py` (重构)

**依赖**：
- 需要从 `ActPhase` 传递工具实例，而非工具名称

### 4.5 Phase 5: 重构 MemorySummarizer

**任务**：
1. ✅ 修改 `summarize` 方法使用 `OutputLimitStrategy`
2. ✅ 从 `ToolRegistry` 获取工具实例
3. ✅ 移除基于工具名称的特殊处理逻辑

**文件**：
- `atloop/memory/summarizer.py` (重构)

**依赖**：
- 需要 `ToolRegistry` 实例（可能需要通过 `state` 或 `coordinator` 传递）

### 4.6 Phase 6: 扩展 ToolRegistry

**任务**：
1. ✅ 添加 `get_tool` 方法
2. ✅ 确保工具实例可以被查询

**文件**：
- `atloop/tools/registry.py` (修改)

### 4.7 Phase 7: 更新测试

**任务**：
1. ✅ 更新现有测试以使用新的设计
2. ✅ 删除不再有用的测试用例
3. ✅ 添加新的测试用例验证语义类型系统

**文件**：
- `tests/test_act_result_processor.py` (更新)
- `tests/test_memory_summarizer.py` (新建或更新)
- `tests/test_output_limit_strategy.py` (新建)

### 4.8 Phase 8: 文档更新

**任务**：
1. ✅ 更新设计文档
2. ✅ 更新工具开发指南
3. ✅ 更新限制配置文档

**文件**：
- `docs/TOOL_OUTPUT_LIMIT_DESIGN.md` (新建)
- `docs/TOOL_DEVELOPMENT_GUIDE.md` (更新)

---

## 9. Skill Loading Redesign (Phase 9-14)

### 9.1 Design Assessment

**User's Proposal**: Split skill loading into two tools:
1. **`load_skill`** - Load skill metadata and resource list (without content)
2. **`load_skill_resource`** - Incrementally load resource files into memory cache

**Assessment**: ✅ **GOOD DESIGN (8.5/10)**

**Advantages**:
- ✅ Follows lazy loading best practices
- ✅ Separation of concerns
- ✅ Incremental loading reduces token consumption
- ✅ Caching strategy for better performance

**See detailed analysis**: `docs/SKILL_LOADING_REDESIGN_ANALYSIS.md`

### 9.2 Phase 9: Add Memory Cache Structure

**Tasks**:
1. ✅ Add `skill_cache` field to `Memory` dataclass
2. ✅ Define cache structure format
3. ✅ Implement cache management helper methods

**Cache Structure**:
```python
skill_cache: Dict[str, Dict[str, Any]] = field(default_factory=dict)
# Format:
# {
#     "skill_name": {
#         "metadata": {
#             "name": str,
#             "description": str,
#             "body": str,  # SKILL.md body
#             "loaded_at_step": int
#         },
#         "resources": {
#             "scripts": Dict[str, Dict[str, Any]],  # {filename: {content, loaded_at_step}}
#             "references": Dict[str, Dict[str, Any]],
#             "assets": Dict[str, Dict[str, Any]]  # May not cache binary content
#         }
#     }
# }
```

**Files**:
- `atloop/memory/state.py` (modify)

### 9.3 Phase 10: Implement New Tools

**Tasks**:
1. ✅ Implement `LoadSkillTool` (replaces old `SkillTool`)
   - Load skill metadata and resource list
   - Return SKILL.md body + resource file names (no content)
   - Output semantic type: `KNOWLEDGE_CONTENT`
2. ✅ Implement `LoadSkillResourceTool`
   - Load specific resource file content
   - Cache content in `state.memory.skill_cache`
   - Return confirmation message (not full content to avoid duplication)
   - Output semantic type: `KNOWLEDGE_CONTENT`
3. ✅ Update skill loader to support resource file loading
   - Add method to load resource file content
   - Add method to list resources by type

**Tool Specifications**:

**`load_skill`**:
```python
# Input
{"name": "long-doc-writer"}

# Output
{
    "ok": True,
    "stdout": """
# Skill: long-doc-writer

## Description
Best practices for writing long documents.

## Main Content
[SKILL.md body content]

## Available Resources

### Scripts
- generate_doc.js
- format_doc.py

### References
- style_guide.md
- template_example.md

**Note**: Use `load_skill_resource` to load specific resource files.
""",
    "meta": {
        "skill_name": "long-doc-writer",
        "resources": {
            "scripts": ["generate_doc.js", "format_doc.py"],
            "references": ["style_guide.md", "template_example.md"],
            "assets": ["template.docx", "logo.png"]
        }
    }
}
```

**`load_skill_resource`**:
```python
# Input
{
    "skill_name": "long-doc-writer",
    "resource_type": "scripts",  # "scripts" | "references" | "assets"
    "resource_name": "generate_doc.js"
}

# Output
{
    "ok": True,
    "stdout": """
Resource loaded into skill cache.

**Skill**: long-doc-writer
**Resource Type**: scripts
**Resource Name**: generate_doc.js
**Content Length**: 1234 characters

**Note**: This resource is now cached in memory. It will be available in future memory summaries.
""",
    "meta": {
        "skill_name": "long-doc-writer",
        "resource_type": "scripts",
        "resource_name": "generate_doc.js",
        "content_length": 1234,
        "cached": True
    }
}
```

**Files**:
- `atloop/tools/interaction/load_skill.py` (new)
- `atloop/tools/interaction/load_skill_resource.py` (new)
- `atloop/skills/loader.py` (modify - add resource loading methods)

### 9.4 Phase 11: Update Memory Summary

**Tasks**:
1. ✅ Add skill cache display to Memory Summary
2. ✅ Show loaded skills with their cached resources
3. ✅ Show available but not loaded resources
4. ✅ Guide LLM to load needed resources

**Display Format**:
```markdown
## 📚 Loaded Skills (Cached in Memory)

### Skill: long-doc-writer (Loaded at Step 5)
[SKILL.md body content]

**Cached Resources:**
- Scripts: generate_doc.js (Step 10), format_doc.py (Step 12)
- References: style_guide.md (Step 15)

**Available but not loaded:**
- References: template_example.md
- Assets: template.docx, logo.png

**Note**: Use `load_skill_resource` to load additional resources when needed.
```

**Files**:
- `atloop/memory/summarizer.py` (modify)

### 9.5 Phase 12: Update Tool Descriptions

**Tasks**:
1. ✅ Write clear tool descriptions for `load_skill`
2. ✅ Write clear tool descriptions for `load_skill_resource`
3. ✅ Add examples and usage guidance

**Tool Descriptions**:

**`load_skill`**:
```
Load skill metadata and resource list. Returns the skill's main content (SKILL.md body) 
and a list of available resource files (scripts, references, assets) without their contents. 
Use this tool first to explore a skill's capabilities. Then use `load_skill_resource` to 
incrementally load specific resource files when needed.
```

**`load_skill_resource`**:
```
Load a specific resource file from a skill into memory cache. The resource content will 
be cached and available in future memory summaries. Use this tool after `load_skill` to 
load specific scripts, references, or assets that you need. The content is cached, so 
you don't need to reload it.
```

**Files**:
- `atloop/tools/interaction/load_skill.py` (modify)
- `atloop/tools/interaction/load_skill_resource.py` (modify)

### 9.6 Phase 13: Update LLM Prompts

**Tasks**:
1. ✅ Update system prompt with skill loading strategy
2. ✅ Update developer prompt with examples
3. ✅ Add workflow guidance

**System Prompt Addition**:
```
## Skill Loading Strategy

When you need to use a skill:

1. **First**: Use `load_skill` to get the skill's main content and see available resources
2. **Then**: Use `load_skill_resource` to load specific resources you need
3. **Note**: Loaded resources are cached in memory and will be available in future summaries

**Example workflow:**
- Step 1: `load_skill(name="long-doc-writer")` → Get main content + resource list
- Step 2: `load_skill_resource(skill_name="long-doc-writer", resource_type="scripts", resource_name="generate_doc.js")` → Load script
- Step 3: Use the cached content in your work
```

**Files**:
- `atloop/llm/prompts/en/system.txt` (modify)
- `atloop/llm/prompts/en/developer.txt` (modify)

### 9.7 Phase 14: Remove Old Tool and Update References

**Tasks**:
1. ✅ Remove old `SkillTool` (replaced by `LoadSkillTool` and `LoadSkillResourceTool`)
2. ✅ Update all references to old `skill` tool
3. ✅ Update tool registry
4. ✅ Update tests

**Files**:
- `atloop/tools/interaction/skill_tool.py` (delete)
- `atloop/tools/registry.py` (modify - remove old tool, add new tools)
- All files referencing `skill` tool (update)

### 9.8 Phase 15: Testing

**Tasks**:
1. ✅ Test skill loading workflow
2. ✅ Test resource caching
3. ✅ Test memory summary display
4. ✅ Test error handling (skill not found, resource not found, etc.)
5. ✅ Test idempotency (loading same resource twice)

**Files**:
- `tests/test_load_skill.py` (new)
- `tests/test_load_skill_resource.py` (new)
- `tests/test_skill_cache.py` (new)
- `tests/test_memory_summarizer.py` (modify - add skill cache tests)

---

## 5. 设计优势

### 5.1 结构化设计

**优势**：
1. ✅ **符合开闭原则**：对扩展开放，对修改关闭
2. ✅ **单一职责**：每个组件职责清晰
3. ✅ **易于维护**：逻辑集中，易于理解和修改
4. ✅ **易于扩展**：新增工具类型只需声明语义类型

### 5.2 避免遗漏

**优势**：
1. ✅ **自动应用**：系统根据语义类型自动应用限制
2. ✅ **不会遗漏**：工具声明语义类型后，所有地方自动使用正确限制
3. ✅ **一致性**：所有使用该工具的地方都使用相同的限制策略

### 5.3 灵活性

**优势**：
1. ✅ **可配置**：限制值集中在 `OutputLimitStrategy` 中
2. ✅ **可扩展**：可以轻松添加新的语义类型
3. ✅ **可测试**：策略系统可以独立测试

---

## 6. 迁移策略

### 6.1 向后兼容性

**注意**：用户明确表示**不考虑向后兼容**，可以直接重构。

**策略**：
1. ✅ 直接重构，不保留旧接口
2. ✅ 更新所有调用点
3. ✅ 删除不再有用的测试用例

### 6.2 渐进式实施

**建议**：
1. **Phase 1-3**：先建立基础设施（语义类型、策略系统、工具扩展）
2. **Phase 4-6**：重构核心逻辑（ToolResultFormatter, MemorySummarizer）
3. **Phase 7-8**：更新测试和文档

**好处**：
- 每个阶段都可以独立测试
- 降低风险
- 便于回滚

---

## 7. 风险评估

### 7.1 技术风险

**风险**：
1. **工具实例传递**：需要确保工具实例可以在各个组件间传递
2. **ToolRegistry 访问**：MemorySummarizer 需要访问 ToolRegistry

**缓解**：
1. 通过 `state` 或 `coordinator` 传递 ToolRegistry
2. 确保工具实例在需要的地方可用

### 7.2 测试风险

**风险**：
1. 现有测试可能需要大量更新
2. 新设计需要充分测试

**缓解**：
1. 用户明确表示可以删除过时的测试用例
2. 重点测试新设计的核心逻辑

---

## 10. Summary

### 10.1 Problem Confirmation

1. ✅ **read_file tool is truncated**: Uses 2KB limit
2. ✅ **Current fix is workaround**: Special handling based on tool name
3. ✅ **Design flaw**: Based on tool name, not flexible enough

### 10.2 Improvement Plan

**Core Improvements**:
- Change from **tool-name-based** to **output-semantic-type-based** design
- Establish unified output limit strategy system
- Tools declare semantic types, system automatically applies limits

**Additional Improvement**:
- **Skill loading redesign**: Split into two tools for lazy loading and caching
  - `load_skill`: Load metadata and resource list
  - `load_skill_resource`: Incrementally load resources into cache

### 10.3 Implementation Plan

**15 Phases**:

**Output Limit Redesign (Phase 1-8)**:
1. Define semantic types and strategy system
2. Extend BaseTool
3. Update tool implementations
4. Refactor ToolResultFormatter
5. Refactor MemorySummarizer
6. Extend ToolRegistry
7. Update tests
8. Update documentation

**Skill Loading Redesign (Phase 9-15)**:
9. Add memory cache structure
10. Implement new tools (`load_skill`, `load_skill_resource`)
11. Update Memory Summary
12. Update tool descriptions
13. Update LLM prompts
14. Remove old tool and update references
15. Testing

### 10.4 Expected Effects

**After Improvements**:
- ✅ All content-type tools (read_file, load_skill, load_skill_resource, read_skill_file) automatically use large limits
- ✅ No tools will be missed
- ✅ Easy to maintain and extend
- ✅ Follows design best practices
- ✅ Skill loading uses lazy loading pattern
- ✅ Resource caching reduces token consumption
- ✅ Better control over context size

### 10.5 Code and Comment Language

**Requirement**: All code and comments must be in English.

**Implementation**:
- ✅ All code written in English
- ✅ All comments written in English
- ✅ All docstrings written in English
- ✅ All variable/function/class names in English

---

**Report Completion Date**: 2026-01-11  
**Version**: 2.0 (with Skill Loading Redesign)
