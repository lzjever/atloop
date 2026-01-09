# Memory 模块设计评审报告

## 执行摘要

作为 AI 专家，我对当前 memory 模块进行了全面评审。整体设计**基础扎实**，但存在**显著优化空间**。主要问题集中在：记忆压缩、重要性评估、检索机制、结构化存储等方面。

**评分**：7/10
- ✅ 优点：结构清晰、持久化完善、长期记忆支持
- ⚠️ 问题：缺少压缩机制、无重要性评分、无检索能力、plan 非结构化

---

## 一、当前设计分析

### 1.1 数据结构设计 ⭐⭐⭐⭐ (4/5)

**优点**：
- ✅ 清晰的短期/长期记忆分离
- ✅ 使用 dataclass，类型安全
- ✅ 支持序列化/反序列化
- ✅ 字段命名清晰

**问题**：
- ⚠️ `plan` 是字符串，无法跟踪步骤完成状态
- ⚠️ `attempts` 和 `decisions` 会无限增长（只有简单的 last N 限制）
- ⚠️ 缺少时间戳字段（无法判断记忆时效性）
- ⚠️ 缺少重要性评分字段

**建议**：
```python
@dataclass
class PlanStep:
    """结构化的计划步骤"""
    id: str
    description: str
    status: str  # "pending", "in_progress", "completed", "skipped"
    completed_at_step: Optional[int] = None
    dependencies: List[str] = field(default_factory=list)  # 依赖的其他步骤

@dataclass
class Memory:
    # ... existing fields ...
    plan: List[PlanStep] = field(default_factory=list)  # 结构化计划
    plan_version: int = 0  # 计划版本号，用于跟踪更新
    memory_compression_history: List[Dict] = field(default_factory=list)  # 压缩历史
```

### 1.2 持久化机制 ⭐⭐⭐⭐⭐ (5/5)

**优点**：
- ✅ JSON 格式，人类可读
- ✅ 自动保存和恢复
- ✅ 跨会话持久化

**评价**：这是设计最好的部分，无需改进。

### 1.3 摘要生成机制 ⭐⭐⭐ (3/5)

**优点**：
- ✅ 优先展示长期记忆
- ✅ 有截断保护机制

**问题**：
- ⚠️ **简单字符截断**：可能丢失关键信息
- ⚠️ **无重要性排序**：所有记忆平等对待
- ⚠️ **无压缩总结**：只是简单截断，不进行智能压缩
- ⚠️ **固定顺序**：总是按相同顺序展示，无法根据相关性调整

**业界最佳实践对比**：

| 特性 | 当前实现 | LangChain | AutoGPT | Claude Code |
|------|---------|-----------|---------|-------------|
| 记忆压缩 | ❌ 无 | ✅ LLM总结 | ✅ 重要性评分+压缩 | ✅ 对话历史压缩 |
| 重要性评分 | ❌ 无 | ✅ Embedding相似度 | ✅ 显式评分 | ✅ 隐式（通过压缩） |
| 检索机制 | ❌ 无 | ✅ Vector检索 | ✅ 关键词检索 | ✅ 时间窗口 |
| 结构化存储 | ⚠️ 部分 | ✅ 完整 | ✅ 完整 | ⚠️ 部分 |

### 1.4 记忆更新机制 ⭐⭐⭐ (3/5)

**优点**：
- ✅ MemoryManager 提供统一接口
- ✅ 自动限制列表长度

**问题**：
- ⚠️ **无去重机制**：可能存储重复信息
- ⚠️ **无重要性评估**：所有决策/里程碑都同等重要
- ⚠️ **无自动压缩**：长期运行会积累大量记忆

---

## 二、核心问题分析

### 2.1 问题1：记忆无限增长 ⚠️ **严重**

**现状**：
- `attempts` 列表会无限增长（虽然有 last 3 展示，但全部存储）
- `decisions` 列表会无限增长
- `important_decisions` 和 `milestones` 只有简单的 last 20 限制

**影响**：
- 状态文件会越来越大
- 恢复时间变长
- 内存占用增加

**业界解决方案**：
1. **AutoGPT**: 使用重要性评分，只保留高分记忆
2. **LangChain**: 定期使用 LLM 总结压缩旧记忆
3. **Claude Code**: 使用滑动窗口，只保留最近 N 轮

**建议实现**：
```python
class MemoryCompressor:
    """记忆压缩器"""
    
    @staticmethod
    def compress_old_attempts(state: AgentState, keep_recent: int = 10) -> None:
        """压缩旧的 attempts，只保留最近的 N 个"""
        if len(state.memory.attempts) <= keep_recent:
            return
        
        # 保留最近的
        recent = state.memory.attempts[-keep_recent:]
        old = state.memory.attempts[:-keep_recent]
        
        # 使用 LLM 总结旧 attempts
        summary = summarize_attempts(old)  # 调用 LLM 总结
        state.memory.learnings.append(f"历史尝试总结: {summary}")
        
        # 替换为总结 + 最近的
        state.memory.attempts = [{"step": 0, "summary": summary, "compressed": True}] + recent
```

### 2.2 问题2：无重要性评估 ⚠️ **严重**

**现状**：
- 所有记忆都平等对待
- 无法区分关键记忆和普通记忆

**影响**：
- 重要信息可能被截断
- 无法优先保留关键记忆

**建议实现**：
```python
@dataclass
class MemoryItem:
    """带重要性评分的记忆项"""
    content: str
    importance_score: float  # 0.0-1.0
    timestamp: datetime
    step: int
    category: str  # "decision", "milestone", "learning", etc.
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "importance": self.importance_score,
            "timestamp": self.timestamp.isoformat(),
            "step": self.step,
            "category": self.category,
        }

class ImportanceScorer:
    """重要性评分器"""
    
    @staticmethod
    def score_decision(decision: Dict[str, Any]) -> float:
        """评估决策的重要性"""
        # 启发式规则：
        # - 涉及架构决策：+0.3
        # - 涉及技术选型：+0.2
        # - 影响多个文件：+0.2
        # - 解决关键错误：+0.3
        score = 0.5  # 基础分
        
        content = decision.get("content", "").lower()
        if any(keyword in content for keyword in ["架构", "设计", "结构"]):
            score += 0.3
        if any(keyword in content for keyword in ["技术", "框架", "库"]):
            score += 0.2
        if decision.get("context", {}).get("files_affected", 0) > 3:
            score += 0.2
        if "错误" in content or "bug" in content:
            score += 0.3
        
        return min(1.0, score)
```

### 2.3 问题3：无记忆检索机制 ⚠️ **中等**

**现状**：
- 所有记忆都线性展示
- 无法根据当前上下文检索相关记忆

**影响**：
- LLM 可能看不到相关的历史记忆
- 无法利用相似场景的经验

**建议实现**：
```python
class MemoryRetriever:
    """记忆检索器"""
    
    def __init__(self, use_embedding: bool = False):
        self.use_embedding = use_embedding
        if use_embedding:
            # 使用 embedding 进行语义检索
            from sentence_transformers import SentenceTransformer
            self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
            self.memory_embeddings = {}
    
    def retrieve_relevant(
        self,
        state: AgentState,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """检索与查询相关的记忆"""
        if self.use_embedding:
            return self._retrieve_with_embedding(state, query, top_k)
        else:
            return self._retrieve_with_keywords(state, query, top_k)
    
    def _retrieve_with_keywords(
        self,
        state: AgentState,
        query: str,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """基于关键词的检索"""
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        scored_items = []
        
        # 搜索所有记忆类型
        for decision in state.memory.important_decisions:
            content = decision.get("content", "").lower()
            score = len(query_words & set(content.split())) / len(query_words)
            if score > 0:
                scored_items.append((score, decision))
        
        for milestone in state.memory.milestones:
            content = milestone.get("content", "").lower()
            score = len(query_words & set(content.split())) / len(query_words)
            if score > 0:
                scored_items.append((score, milestone))
        
        # 按分数排序，返回 top_k
        scored_items.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_items[:top_k]]
```

### 2.4 问题4：Plan 非结构化 ⚠️ **中等**

**现状**：
- `plan` 是字符串，无法跟踪步骤状态
- 无法知道哪些步骤已完成

**影响**：
- LLM 无法准确判断进度
- 可能重复执行已完成的步骤

**建议实现**：
```python
@dataclass
class PlanStep:
    """计划步骤"""
    id: str
    description: str
    status: str = "pending"  # "pending", "in_progress", "completed", "skipped", "failed"
    started_at_step: Optional[int] = None
    completed_at_step: Optional[int] = None
    dependencies: List[str] = field(default_factory=list)
    notes: str = ""

@dataclass
class Plan:
    """执行计划"""
    steps: List[PlanStep] = field(default_factory=list)
    version: int = 0
    created_at_step: int = 0
    last_updated_at_step: int = 0
    
    def get_progress(self) -> Dict[str, int]:
        """获取进度统计"""
        total = len(self.steps)
        completed = sum(1 for s in self.steps if s.status == "completed")
        in_progress = sum(1 for s in self.steps if s.status == "in_progress")
        pending = sum(1 for s in self.steps if s.status == "pending")
        
        return {
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "pending": pending,
            "completion_rate": completed / total if total > 0 else 0.0,
        }
```

### 2.5 问题5：截断策略简单 ⚠️ **中等**

**现状**：
- 只是简单的字符数截断
- 可能丢失关键信息

**建议实现**：
```python
class SmartTruncator:
    """智能截断器"""
    
    @staticmethod
    def truncate_with_priority(
        text: str,
        max_length: int,
        priority_sections: List[str],
    ) -> str:
        """优先保留重要部分的截断"""
        # 1. 先尝试保留所有 priority_sections
        # 2. 如果还是太长，压缩非优先部分
        # 3. 最后才截断
        
        # 实现细节...
        pass
```

---

## 三、优化建议（按优先级）

### 🔴 高优先级

#### 1. 实现记忆压缩机制
**目标**：防止记忆无限增长

**实现**：
- 定期压缩旧的 `attempts` 和 `decisions`
- 使用 LLM 总结旧记忆，保存到 `learnings`
- 只保留最近的 N 个详细记录

**代码位置**：`atloop/memory/compressor.py`

#### 2. 添加重要性评分
**目标**：优先保留重要记忆

**实现**：
- 为每个记忆项添加重要性评分
- 在截断时优先保留高分记忆
- 可以基于规则或 LLM 评分

**代码位置**：`atloop/memory/scorer.py`

#### 3. 结构化 Plan
**目标**：跟踪计划步骤状态

**实现**：
- 将 `plan` 从字符串改为 `List[PlanStep]`
- 跟踪每个步骤的状态（pending/in_progress/completed）
- 在摘要中显示进度

**代码位置**：修改 `atloop/memory/state.py`

### 🟡 中优先级

#### 4. 实现记忆检索
**目标**：根据上下文检索相关记忆

**实现**：
- 基于关键词的简单检索（初期）
- 可选：基于 embedding 的语义检索（后期）

**代码位置**：`atloop/memory/retriever.py`

#### 5. 智能截断
**目标**：避免丢失关键信息

**实现**：
- 识别关键部分（错误信息、重要决策等）
- 优先保留关键部分
- 压缩而非简单截断

**代码位置**：修改 `atloop/memory/summarizer.py`

#### 6. 记忆去重
**目标**：避免存储重复信息

**实现**：
- 检测相似的决策/里程碑
- 合并重复项
- 使用内容哈希或相似度计算

**代码位置**：`atloop/memory/deduplicator.py`

### 🟢 低优先级

#### 7. 记忆时效性
**目标**：区分新旧记忆的重要性

**实现**：
- 添加时间戳字段
- 旧记忆的重要性随时间衰减
- 在检索时考虑时效性

#### 8. 记忆分类和标签
**目标**：更好的记忆组织

**实现**：
- 为记忆添加分类标签
- 支持按标签检索
- 便于记忆管理

---

## 四、推荐实现方案

### 方案A：渐进式改进（推荐）

**阶段1**：基础优化（1-2天）
1. ✅ 实现记忆压缩（压缩旧 attempts）
2. ✅ 添加重要性评分（基于规则）
3. ✅ 结构化 Plan

**阶段2**：检索和去重（2-3天）
4. ✅ 实现关键词检索
5. ✅ 实现记忆去重

**阶段3**：高级功能（可选）
6. ⚠️ Embedding 检索（需要额外依赖）
7. ⚠️ LLM 重要性评分（需要额外成本）

### 方案B：完整重构（不推荐）

完全重构 memory 模块，采用向量数据库等。**风险高，收益不确定**。

---

## 五、具体代码改进建议

### 5.1 添加记忆压缩

```python
# atloop/memory/compressor.py
class MemoryCompressor:
    """记忆压缩器"""
    
    ATTEMPTS_KEEP_RECENT = 10
    DECISIONS_KEEP_RECENT = 5
    
    @staticmethod
    def compress_if_needed(state: AgentState) -> bool:
        """如果需要，压缩记忆"""
        compressed = False
        
        # 压缩 attempts
        if len(state.memory.attempts) > MemoryCompressor.ATTEMPTS_KEEP_RECENT:
            MemoryCompressor._compress_attempts(state)
            compressed = True
        
        # 压缩 decisions
        if len(state.memory.decisions) > MemoryCompressor.DECISIONS_KEEP_RECENT:
            MemoryCompressor._compress_decisions(state)
            compressed = True
        
        return compressed
    
    @staticmethod
    def _compress_attempts(state: AgentState) -> None:
        """压缩旧的 attempts"""
        keep_recent = MemoryCompressor.ATTEMPTS_KEEP_RECENT
        if len(state.memory.attempts) <= keep_recent:
            return
        
        recent = state.memory.attempts[-keep_recent:]
        old = state.memory.attempts[:-keep_recent]
        
        # 生成总结
        summary = MemoryCompressor._summarize_attempts(old)
        
        # 创建压缩记录
        compressed_record = {
            "step": 0,
            "type": "compressed",
            "summary": summary,
            "original_count": len(old),
            "compressed_at_step": state.step,
        }
        
        # 替换
        state.memory.attempts = [compressed_record] + recent
        logger.info(f"[MemoryCompressor] 压缩了 {len(old)} 个旧 attempts")
    
    @staticmethod
    def _summarize_attempts(attempts: List[Dict]) -> str:
        """总结 attempts（可以使用 LLM 或简单规则）"""
        # 简单实现：统计信息
        total = len(attempts)
        successful = sum(1 for a in attempts if a.get("success", False))
        files_modified = set()
        for a in attempts:
            files_modified.update(a.get("files", []))
        
        return (
            f"历史 {total} 次尝试：成功 {successful} 次，"
            f"修改了 {len(files_modified)} 个文件"
        )
```

### 5.2 添加重要性评分

```python
# atloop/memory/scorer.py
class ImportanceScorer:
    """重要性评分器"""
    
    @staticmethod
    def score_decision(decision: Dict[str, Any]) -> float:
        """评估决策的重要性（0.0-1.0）"""
        score = 0.5  # 基础分
        
        content = decision.get("content", "").lower()
        context = decision.get("context", {})
        
        # 关键词加分
        important_keywords = [
            ("架构", 0.3), ("设计", 0.3), ("技术选型", 0.2),
            ("框架", 0.2), ("库", 0.2), ("错误", 0.3), ("bug", 0.3),
        ]
        for keyword, points in important_keywords:
            if keyword in content:
                score += points
        
        # 影响范围加分
        files_affected = context.get("files_affected", 0)
        if files_affected > 5:
            score += 0.2
        elif files_affected > 2:
            score += 0.1
        
        return min(1.0, score)
    
    @staticmethod
    def score_milestone(milestone: Dict[str, Any]) -> float:
        """评估里程碑的重要性"""
        # 里程碑通常都重要
        base_score = 0.7
        
        content = milestone.get("content", "").lower()
        if "完成" in content or "成功" in content:
            base_score += 0.2
        
        return min(1.0, base_score)
```

### 5.3 结构化 Plan

```python
# atloop/memory/plan.py
@dataclass
class PlanStep:
    """计划步骤"""
    id: str
    description: str
    status: str = "pending"  # "pending", "in_progress", "completed", "skipped"
    started_at_step: Optional[int] = None
    completed_at_step: Optional[int] = None
    dependencies: List[str] = field(default_factory=list)
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status,
            "started_at_step": self.started_at_step,
            "completed_at_step": self.completed_at_step,
            "dependencies": self.dependencies,
            "notes": self.notes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanStep":
        return cls(
            id=data["id"],
            description=data["description"],
            status=data.get("status", "pending"),
            started_at_step=data.get("started_at_step"),
            completed_at_step=data.get("completed_at_step"),
            dependencies=data.get("dependencies", []),
            notes=data.get("notes", ""),
        )

class PlanManager:
    """计划管理器"""
    
    @staticmethod
    def update_plan_from_llm(
        state: AgentState,
        plan_text: str,
    ) -> None:
        """从 LLM 的 plan 文本更新结构化计划"""
        # 解析 plan_text（可能是列表或字符串）
        if isinstance(plan_text, list):
            steps_text = plan_text
        else:
            # 尝试解析字符串格式的计划
            steps_text = [line.strip() for line in plan_text.split("\n") if line.strip()]
        
        # 创建或更新步骤
        new_steps = []
        for i, step_text in enumerate(steps_text):
            step_id = f"step_{i+1}"
            
            # 检查是否已存在
            existing = next((s for s in state.memory.plan if s.id == step_id), None)
            if existing:
                # 更新描述，保持状态
                existing.description = step_text
                new_steps.append(existing)
            else:
                # 新步骤
                new_steps.append(PlanStep(
                    id=step_id,
                    description=step_text,
                    status="pending",
                ))
        
        state.memory.plan = new_steps
    
    @staticmethod
    def mark_step_completed(
        state: AgentState,
        step_id: str,
    ) -> None:
        """标记步骤为已完成"""
        step = next((s for s in state.memory.plan if s.id == step_id), None)
        if step:
            step.status = "completed"
            step.completed_at_step = state.step
```

---

## 六、总结

### 当前设计评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 数据结构 | ⭐⭐⭐⭐ | 清晰但可优化 |
| 持久化 | ⭐⭐⭐⭐⭐ | 完善 |
| 摘要生成 | ⭐⭐⭐ | 基础功能，缺少智能 |
| 更新机制 | ⭐⭐⭐ | 基础功能，缺少压缩 |
| **总体** | **⭐⭐⭐ (7/10)** | **基础扎实，有优化空间** |

### 关键改进点

1. **记忆压缩**：防止无限增长 ⚠️ **必须**
2. **重要性评分**：优先保留关键记忆 ⚠️ **重要**
3. **结构化 Plan**：跟踪步骤状态 ⚠️ **重要**
4. **记忆检索**：根据上下文检索 ⚠️ **有用**
5. **智能截断**：避免丢失关键信息 ⚠️ **有用**

### 实施建议

**立即实施**（高优先级）：
1. 记忆压缩机制
2. 重要性评分
3. 结构化 Plan

**后续优化**（中优先级）：
4. 记忆检索
5. 智能截断
6. 记忆去重

**可选增强**（低优先级）：
7. Embedding 检索
8. LLM 重要性评分
9. 记忆时效性

---

## 七、参考实现

可以参考以下项目的 memory 实现：
- **LangChain**: `langchain.memory` 模块
- **AutoGPT**: 重要性评分 + 记忆压缩
- **Claude Code**: 对话历史压缩
- **Gemini CLI**: Session summary + auto-compact
