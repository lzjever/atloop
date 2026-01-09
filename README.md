# TITAN Agent

**Tool-Integrated Task Automation Node** - 自动化代码修复和开发工具

## 简介

TITAN Agent 是一个能够在沙箱环境中自主检索、修改、运行、验证代码的自动化工具。它能够理解任务需求，分析代码问题，生成修复方案，并验证修复结果，最终产出可审计的改动（diff/patch）与结果报告。

## 核心特性

- ✅ **自动代码修复**: 自动识别并修复代码中的bug
- ✅ **自动功能实现**: 根据需求自动实现新功能
- ✅ **代码重构**: 在保持行为不变的前提下重构代码
- ✅ **智能检索**: 基于关键词和错误信息的智能代码检索
- ✅ **项目类型检测**: 自动识别Python、Node.js、Go等项目类型
- ✅ **事件日志**: 完整记录所有操作，支持回放和审计
- ✅ **报告生成**: 生成详细的执行报告（Markdown格式）
- ✅ **预算管理**: 支持LLM调用、工具调用和时间预算限制

## 文档

- **[架构设计](docs/ARCHITECTURE.md)** - 系统架构和设计原则
- **[功能文档](docs/FEATURES.md)** - 完整功能说明
- **[使用指南](docs/USAGE.md)** - CLI 和 API 使用说明

开发相关文档请查看 [project-docs/](project-docs/)。

## 快速开始

### 安装

#### 使用 uv (推荐)

```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装 TITAN
make dev-install
```

#### 使用 pip

```bash
pip install titan
```

#### 开发模式

```bash
# 使用 uv (推荐)
make dev-install

# 或使用 pip
pip install -e ".[dev]"
```

#### 本地依赖 (开发时)

如果使用本地版本的依赖 (varlord, lexilux, routilux, noxrunner)，需要设置 PYTHONPATH:

```bash
export PYTHONPATH=/path/to/varlord:/path/to/lexilux:/path/to/routilux:/path/to/noxrunner:$PYTHONPATH
```

### 配置

创建 `ai_infra_endpoints.json`:

```json
{
  "completion": {
    "model": "deepseek-chat",
    "api_base": "https://api.deepseek.com",
    "api_key": "your-api-key"
  },
  "embedding": {
    "model": "qwen3-embedding-0.6b",
    "api_base": "http://192.168.0.220:20553/v1",
    "api_key": "20552055"
  },
  "reranker": {
    "model": "qwen3-reranker-0.6b",
    "api_base": "http://192.168.0.220:20551/v1",
    "api_key": "20552055",
    "mode": "openai"
  }
}
```

### 基本使用

```python
from titan.config import load_config, load_task_spec
from titan.config.models import SandboxConfig
from titan.orchestrator import AgentLoop

# 加载配置
config = load_config("ai_infra_endpoints.json")

# 创建任务
task = load_task_spec(
    task_id="my_task",
    goal="修复test_add测试失败的问题",
    workspace_root="/path/to/workspace",
    task_type="bugfix",
)

# 配置沙箱
sandbox_config = SandboxConfig(
    base_url="http://127.0.0.1:8080",
    local_test=False,
)

# 运行Agent
loop = AgentLoop(task, config, sandbox_config)
report = loop.run()

# 查看结果
print(f"状态: {report['status']}")
if report["status"] == "success":
    print(f"Diff:\n{report.get('diff', '')}")
```

## 项目结构

```
titan/
├── titan/                    # 核心代码
│   ├── config/              # 配置管理
│   ├── runtime/             # 运行时层
│   ├── llm/                 # LLM客户端
│   ├── retrieval/           # 检索系统
│   ├── memory/              # 记忆系统
│   ├── orchestrator/        # 编排器
│   └── logging/             # 日志系统
├── tests/                    # 测试
├── examples/                # 示例
├── docs/                     # 文档
└── runs/                     # 运行日志
```

## 文档

### Sphinx 文档（推荐）

构建并查看完整的 Sphinx 文档：

```bash
cd docs && make html
# 打开 docs/build/html/index.html
```

### Markdown 参考文档

- [架构设计文档](docs/markdown/ARCHITECTURE.md) - 系统架构和设计
- [功能文档](docs/markdown/FEATURES.md) - 功能特性说明
- [API文档](docs/markdown/API.md) - API参考
- [用户使用手册](docs/markdown/USER_GUIDE.md) - 详细使用指南
- [设计文档](docs/markdown/DESIGN.md) - 设计决策和算法
- [快速开始](docs/markdown/QUICK_START.md) - 快速开始指南

## 功能模块

### 1. 配置系统 (config)

- 多源配置加载（文件、环境变量、CLI）
- 类型安全的配置模型
- 任务规范定义

### 2. 运行时层 (runtime)

- 沙箱适配器
- 工具运行时
- 统一的工具接口

### 3. LLM客户端 (llm)

- LLM调用封装
- Action JSON解析和验证
- Prompt模板管理

### 4. 检索系统 (retrieval)

- 工作区索引
- 项目类型检测
- 上下文打包

### 5. 记忆系统 (memory)

- Agent状态管理
- 记忆摘要
- 状态持久化

### 6. 编排器 (orchestrator)

- Agent主循环
- 状态机管理
- 预算管理
- 验证器

### 7. 日志系统 (logging)

- 事件日志记录
- 事件回放
- 报告生成

## 示例

### 修复失败的测试

```python
task = load_task_spec(
    task_id="fix_test",
    goal="修复test_add测试失败的问题",
    workspace_root="/path/to/project",
    task_type="bugfix",
    constraints=["必须通过pytest"],
)

loop = AgentLoop(task, config, sandbox_config)
report = loop.run()
```

### 实现新功能

```python
task = load_task_spec(
    task_id="add_feature",
    goal="实现用户登录功能并添加测试",
    workspace_root="/path/to/project",
    task_type="feature",
    definition_of_done=[
        "新增测试覆盖关键逻辑",
        "所有测试通过",
    ],
)
```

### 查看执行历史

```python
from titan.logging import EventReplay
from pathlib import Path

replay = EventReplay(Path("runs/task_id/events.jsonl"))
summary = replay.replay_to_step(10)
print(f"回放到step 10: {summary['total_events']}个事件")
```

### 生成报告

```python
from titan.logging import ReportGenerator

generator = ReportGenerator(Path("runs/task_id/events.jsonl"))
report = generator.generate_success_report("task_id", "goal")
markdown = generator.generate_markdown_report(report, Path("report.md"))
```

## 开发状态

### 已完成

- ✅ Milestone 1: 基础组件
- ✅ Milestone 2: Agent核心功能
- ✅ Milestone 3: 事件日志与回放

### 进行中

- 🔄 Milestone 4: 任务类型与质量门禁
- 🔄 Milestone 5: 工程化完善

## 测试

运行测试：

```bash
# 运行所有测试
pytest tests/

# 运行特定测试
pytest tests/test_e2e_agent.py

# 运行完整工作流测试
python tests/test_complete_workflow.py
```

## 贡献

欢迎贡献代码和提出建议！

## 许可证

[待定]

## 联系方式

[待定]
