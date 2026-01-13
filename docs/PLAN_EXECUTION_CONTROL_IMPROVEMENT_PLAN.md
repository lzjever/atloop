# Plan Execution Control Improvement Plan

## 一、需求理解

### 1.1 核心需求

1. **严格顺序执行**：
   - LLM 每一轮只能输出与**当前计划步骤**（🔄标记的步骤）相关的 actions
   - **严禁**输出后面计划要做的事情（📋标记的步骤）
   - 只有当前步骤完成后，才能开始下一步

2. **步骤状态管理**：
   - ✅ **已完成**：步骤已完成，不能再执行相关 actions
   - 🔄 **进行中**：当前正在执行的步骤，只能执行这个步骤的 actions
   - 📋 **待开始**：尚未开始的步骤，不能执行相关 actions

3. **计划重新规划**：
   - 当 LLM 发现当前计划不可行时，允许重新规划**完整计划**
   - 重新规划时，需要智能合并已完成的工作：
     - 如果新计划中的步骤已经被之前的步骤覆盖，直接标记为 ✅
     - 从第一个未完成的步骤开始继续执行

### 1.2 示例场景

**场景 1：正常顺序执行**
```
初始计划: ["📋 Check env", "📋 Create script", "📋 Run script"]
Step 1: plan = ["🔄 Check env", "📋 Create script", "📋 Run script"]
        actions = [check_env_action]  ✅ 正确

Step 2: plan = ["✅ Check env", "🔄 Create script", "📋 Run script"]
        actions = [create_script_action]  ✅ 正确

Step 3: plan = ["✅ Check env", "✅ Create script", "🔄 Run script"]
        actions = [run_script_action]  ✅ 正确
```

**场景 2：错误示例（应该禁止）**
```
Step 1: plan = ["🔄 Check env", "📋 Create script", "📋 Run script"]
        actions = [check_env_action, create_script_action]  ❌ 错误！
        # 不能同时执行当前步骤和后续步骤
```

**场景 3：计划重新规划**
```
原计划: ["✅ Check env", "🔄 Create script", "📋 Run script"]
发现: 需要先安装依赖

新计划: ["✅ Check env", "✅ Install dependencies", "🔄 Create script", "📋 Run script"]
        # "Install dependencies" 虽然不在原计划中，但如果已经完成，标记为 ✅
        # 从第一个未完成的步骤（Create script）开始继续
```

## 二、修改计划

### 2.1 Prompt 修改（仅 Prompt，无需代码）

#### 修改点 1：强化 plan 字段说明
**位置**: `developer.txt` - "Important Notes on `plan` field" 部分

**修改内容**:
- 明确说明：**只能执行当前步骤（🔄标记）的 actions**
- 严禁执行后续步骤（📋标记）的 actions
- 只有当前步骤完成后，才能将下一步标记为 🔄

#### 修改点 2：添加执行约束说明
**位置**: `developer.txt` - "Important Notes" 部分

**修改内容**:
- 添加 **CRITICAL** 级别的约束：
  - 只能输出与当前步骤（🔄）相关的 actions
  - 严禁输出后续步骤（📋）的 actions
  - 当前步骤完成后，必须标记为 ✅，并将下一步标记为 🔄

#### 修改点 3：添加计划重新规划说明
**位置**: `developer.txt` - "Important Notes on `plan` field" 部分

**修改内容**:
- 说明何时可以重新规划：
  - 发现当前计划不可行
  - 需要调整步骤顺序
  - 需要添加/删除步骤
- 重新规划规则：
  - 必须提供**完整计划**（覆盖整个任务目标）
  - 智能合并已完成步骤：
    - 如果新计划中的步骤已经被之前的步骤覆盖，标记为 ✅
    - 从第一个未完成的步骤开始继续执行

#### 修改点 4：更新示例
**位置**: `developer.txt` - Examples 部分

**修改内容**:
- 更新所有示例，确保只包含当前步骤的 actions
- 添加"错误示例"，展示不应该做什么
- 添加"计划重新规划示例"

### 2.2 代码修改（可选，但推荐）

#### 修改点 1：添加 Action 验证（推荐）
**位置**: `atloop/orchestrator/phases/plan.py` - PlanPhase.execute()

**功能**:
- 在 PlanPhase 中，解析 LLM 输出的 plan
- 识别当前步骤（🔄标记的步骤）
- 验证 actions 是否只针对当前步骤
- 如果发现 actions 针对后续步骤，记录警告/错误

**实现思路**:
```python
def validate_actions_against_current_step(
    actions: List[Dict],
    plan: List[str]
) -> Tuple[bool, Optional[str]]:
    """
    验证 actions 是否只针对当前步骤。
    
    Returns:
        (is_valid, error_message)
    """
    # 1. 找到当前步骤（🔄标记的）
    current_step_index = None
    for i, step in enumerate(plan):
        if "🔄" in step or step.strip().startswith("🔄"):
            current_step_index = i
            break
    
    if current_step_index is None:
        # 没有当前步骤，可能是所有步骤都完成了
        # 或者计划格式有问题
        return True, None  # 暂时允许，让 LLM 自己处理
    
    # 2. 解析当前步骤的内容（去除 emoji）
    current_step = plan[current_step_index].replace("🔄", "").strip()
    
    # 3. 验证 actions 是否与当前步骤相关
    # 这是一个启发式检查，不是严格的语义分析
    # 可以检查：
    # - 文件操作是否与当前步骤描述相关
    # - 命令是否与当前步骤描述相关
    # 注意：这个验证可能不够精确，主要是提示作用
    
    return True, None  # 暂时只做提示，不强制拒绝
```

#### 修改点 2：智能计划合并（推荐）
**位置**: `atloop/memory/plan.py` - PlanManager.update_plan_from_llm()

**功能**:
- 当 LLM 提供新计划时，智能合并已完成的工作
- 检查新计划中的步骤是否已经被之前的步骤覆盖
- 自动标记已完成步骤为 ✅

**实现思路**:
```python
def merge_plan_with_completed_steps(
    new_plan: List[str],
    old_plan: List[str],
    completed_files: List[str],
    completed_actions: List[Dict]
) -> List[str]:
    """
    智能合并新计划与已完成的工作。
    
    Args:
        new_plan: LLM 提供的新计划
        old_plan: 之前的计划
        completed_files: 已创建/修改的文件列表
        completed_actions: 已执行的 actions 列表
    
    Returns:
        合并后的计划，已完成步骤标记为 ✅
    """
    merged_plan = []
    
    for step in new_plan:
        step_clean = step.replace("✅", "").replace("🔄", "").replace("📋", "").strip()
        
        # 检查这个步骤是否已经完成
        # 启发式检查：
        # 1. 如果步骤描述的文件已经在 completed_files 中
        # 2. 如果步骤描述的操作已经在 completed_actions 中
        # 3. 如果步骤在 old_plan 中且标记为 ✅
        
        is_completed = False
        
        # 检查 1: 文件是否已创建
        for file in completed_files:
            if file in step_clean:
                is_completed = True
                break
        
        # 检查 2: 操作是否已执行（简化检查）
        # 这里可以根据实际需求扩展
        
        # 检查 3: 旧计划中是否已完成
        if old_plan:
            for old_step in old_plan:
                old_step_clean = old_step.replace("✅", "").replace("🔄", "").replace("📋", "").strip()
                if old_step_clean == step_clean and "✅" in old_step:
                    is_completed = True
                    break
        
        if is_completed:
            merged_plan.append(f"✅ {step_clean}")
        else:
            # 保持原样（可能是 🔄 或 📋）
            merged_plan.append(step)
    
    return merged_plan
```

#### 修改点 3：步骤完成检测（可选）
**位置**: `atloop/orchestrator/phases/act.py` - ActPhase.execute()

**功能**:
- 在 ACT 阶段完成后，检测当前步骤是否已完成
- 如果完成，自动更新 plan：将当前步骤标记为 ✅，下一步标记为 🔄

**实现思路**:
```python
def auto_update_plan_after_step_completion(
    state: AgentState,
    actions: List[Dict],
    results: List[Dict]
) -> None:
    """
    在步骤完成后自动更新 plan。
    
    这是一个可选功能，可以让系统自动管理步骤状态，
    而不是完全依赖 LLM 手动更新。
    """
    if not state.memory.plan:
        return
    
    # 检查当前步骤（🔄标记的）
    current_step_index = None
    for i, step in enumerate(state.memory.plan):
        if "🔄" in step:
            current_step_index = i
            break
    
    if current_step_index is None:
        return
    
    # 检查 actions 是否成功执行
    all_success = all(r.get("ok", False) for r in results)
    
    if all_success:
        # 标记当前步骤为完成
        current_step = state.memory.plan[current_step_index]
        state.memory.plan[current_step_index] = current_step.replace("🔄", "✅")
        
        # 如果有下一步，标记为进行中
        if current_step_index + 1 < len(state.memory.plan):
            next_step = state.memory.plan[current_step_index + 1]
            if "📋" in next_step or (not "✅" in next_step and not "🔄" in next_step):
                state.memory.plan[current_step_index + 1] = next_step.replace("📋", "🔄").replace(next_step.strip(), f"🔄 {next_step.strip()}")
```

## 三、实施优先级

### 3.1 第一阶段：Prompt 修改（必须）
- ✅ 修改 plan 字段说明
- ✅ 添加执行约束说明
- ✅ 添加计划重新规划说明
- ✅ 更新示例

**影响**: 仅影响 LLM 行为，无需代码修改，风险低

### 3.2 第二阶段：代码验证（推荐）
- ✅ 添加 Action 验证（PlanPhase）
- ✅ 智能计划合并（PlanManager）

**影响**: 增加系统健壮性，可以检测和提示 LLM 的错误行为

### 3.3 第三阶段：自动管理（可选）
- ⚠️ 步骤完成检测和自动更新

**影响**: 可能过于自动化，可能与 LLM 的手动更新冲突，需要谨慎设计

## 四、风险评估

### 4.1 Prompt 修改风险
- **低风险**: 只影响 LLM 行为，不改变系统逻辑
- **可能问题**: LLM 可能不完全遵循约束（需要多次迭代优化 prompt）

### 4.2 代码验证风险
- **中等风险**: 需要准确识别"当前步骤"和"步骤相关性"
- **可能问题**: 
  - 步骤相关性检查可能不够精确（语义理解困难）
  - 可能误判，导致合法 actions 被拒绝

### 4.3 自动管理风险
- **高风险**: 可能与 LLM 的手动更新冲突
- **可能问题**: 
  - 系统自动更新 vs LLM 手动更新，可能产生不一致
  - 步骤完成检测可能不够准确

## 五、建议

### 5.1 立即实施
1. **Prompt 修改**（第一阶段）
   - 风险低，收益高
   - 可以立即改善 LLM 行为

### 5.2 后续考虑
2. **代码验证**（第二阶段）
   - 建议先实施 Prompt 修改，观察效果
   - 如果 LLM 仍然不遵循约束，再添加代码验证
   - 验证逻辑应该以"提示/警告"为主，不要过于严格拒绝

### 5.3 谨慎实施
3. **自动管理**（第三阶段）
   - 建议先观察前两阶段的效果
   - 如果 LLM 能够很好地手动管理步骤状态，可能不需要自动管理
   - 如果实施，应该提供配置选项，允许禁用

## 六、测试计划

### 6.1 Prompt 修改测试
- 使用现有测试用例，观察 LLM 是否遵循新约束
- 创建专门测试用例，验证：
  - LLM 是否只执行当前步骤的 actions
  - LLM 是否正确更新步骤状态
  - LLM 是否能够正确重新规划

### 6.2 代码验证测试
- 单元测试：验证步骤识别和相关性检查
- 集成测试：验证完整流程中的验证逻辑

### 6.3 端到端测试
- 使用真实任务，验证整个改进是否达到预期效果
