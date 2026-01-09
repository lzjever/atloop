# Memory 模块增强功能

## 概述

为 memory 模块添加了长期记忆和动态更新功能，使系统能够更好地跟踪任务执行情况，避免重复工作，并保持执行一致性。

## 新增功能

### 1. 长期记忆字段

在 `Memory` 类中添加了以下长期记忆字段：

- **`plan`** (str): 当前执行计划，可以由 LLM 动态更新
- **`task_summary`** (str): 任务目标和约束的摘要
- **`important_decisions`** (List[Dict]): 重要决策列表，包含步骤、内容和上下文
- **`milestones`** (List[Dict]): 已达成里程碑列表
- **`learnings`** (List[str]): 重要经验总结

### 2. 动态更新机制

#### 2.1 自动捕获 Plan
- LLM 在 `plan` 字段中提供的计划会自动保存到长期记忆
- 计划可以动态更新：如果 LLM 在后续步骤中提供新计划，会自动替换旧计划
- 位置：`agent_loop.py` 中处理 `action_json.plan`

#### 2.2 自动初始化任务摘要
- 在第一步自动生成任务摘要（包含目标和约束）
- 位置：`agent_loop.py` 中第一步时初始化

#### 2.3 自动检测里程碑
- 当成功修改多个文件（≥3个）时，自动记录为里程碑
- 位置：`agent_loop.py` 中 `_phase_act` 完成后

### 3. MemoryManager 工具类

新增 `MemoryManager` 类，提供以下方法用于动态更新长期记忆：

- **`update_plan(state, plan, reason=None)`**: 更新执行计划
- **`add_important_decision(state, content, step=None, context=None)`**: 添加重要决策
- **`add_milestone(state, content, step=None, context=None)`**: 添加里程碑
- **`add_learning(state, learning, step=None)`**: 添加经验总结
- **`update_task_summary(state, summary)`**: 更新任务摘要
- **`get_long_term_memory_summary(state)`**: 获取长期记忆摘要

### 4. MemorySummarizer 增强

在记忆摘要中优先展示长期记忆：

1. **任务概览**：显示任务目标和约束
2. **当前执行计划**：显示最新的执行计划（可动态更新）
3. **重要决策**：显示最近的重要决策（最多5个）
4. **已达成里程碑**：显示最近的里程碑（最多5个）
5. **重要经验**：显示最近的经验总结（最多3个）

然后才显示短期记忆（已创建文件、最近尝试等）。

### 5. Memory 概况输出增强

在终端输出的 memory 概况中，也包含长期记忆的预览：
- 计划预览
- 重要决策数量
- 里程碑数量

## 使用方式

### LLM 如何提供计划

LLM 在 JSON 输出的 `plan` 字段中提供计划：

```json
{
  "actions": [...],
  "stop_reason": "continue",
  "plan": [
    "1. 创建项目结构",
    "2. 实现核心功能",
    "3. 编写测试",
    "4. 完善文档"
  ]
}
```

系统会自动保存这个计划到长期记忆，并在后续步骤中展示给 LLM。

### 动态更新计划

如果执行过程中需要调整计划，LLM 可以在下一轮的 `plan` 字段中提供新计划：

```json
{
  "actions": [...],
  "stop_reason": "continue",
  "plan": [
    "1. 创建项目结构（已完成）",
    "2. 实现核心功能（进行中）",
    "3. 优化性能（新增）",
    "4. 编写测试",
    "5. 完善文档"
  ]
}
```

系统会自动用新计划替换旧计划。

## 数据结构

### Important Decision
```python
{
    "step": 3,
    "content": "决定使用 Python 而不是 JavaScript",
    "context": {"reason": "性能要求", "alternatives": ["JavaScript", "Go"]}
}
```

### Milestone
```python
{
    "step": 5,
    "content": "成功创建核心模块：用户认证、数据存储、API 接口",
    "context": {"files": ["auth.py", "db.py", "api.py"]}
}
```

## 持久化

所有长期记忆字段都会：
- 保存到 `agent_state.json` 文件
- 在任务恢复时自动加载
- 跨步骤持久化

## 优势

1. **避免重复工作**：通过计划跟踪，LLM 可以知道哪些步骤已完成
2. **保持一致性**：重要决策被记住，避免前后矛盾
3. **进度可视化**：里程碑帮助了解任务进度
4. **经验积累**：经验总结帮助避免重复错误
5. **动态调整**：计划可以动态更新，适应执行过程中的变化

## 未来扩展

可以考虑添加：
- **计划步骤状态跟踪**：标记每个计划步骤的完成状态
- **决策影响分析**：分析重要决策对后续步骤的影响
- **经验自动提取**：从错误和成功中自动提取经验
- **计划依赖关系**：跟踪计划步骤之间的依赖关系
