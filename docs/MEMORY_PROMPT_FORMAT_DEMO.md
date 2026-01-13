# Memory Prompt 格式设计文档与示例

## 一、设计目标

本格式设计旨在为 LLM 提供清晰、高效的任务上下文，帮助 LLM：
1. **快速理解任务状态**：当前进度、已完成的工作、待完成的工作
2. **避免重复工作**：明确已创建的文件、已执行的步骤
3. **做出正确决策**：基于历史执行结果和当前状态
4. **高效执行任务**：清晰的指导，减少无效尝试

## 二、架构设计

### 2.1 Memory 模块职责

**Memory 模块负责**：
- ✅ 原始数据的存储和管理
- ✅ 各个条目的格式转换和控制输出（考虑约束：单条长度、字符串映射等）
- ✅ 提供统一的格式化接口，返回可直接注入 prompt 的字符串

**Memory 模块不负责**：
- ❌ 数据压缩（由独立的 CompressionPolicy 负责）
- ❌ 数据重要性评分（由独立的 Scorer 负责）

### 2.2 接口设计

```python
class Memory:
    """Memory 数据存储和管理"""
    
    def get_formatted_context(
        self,
        max_length: Optional[int] = None,
        constraints: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        获取格式化后的记忆上下文，可直接注入到 prompt 中。
        
        Args:
            max_length: 最大长度限制（可选）
            constraints: 输出约束（如单条长度、字符串映射等）
        
        Returns:
            格式化后的字符串，可直接用于 prompt 注入
        """
        pass
```

**使用方式**：
```python
# 在 prompt 模板中
user_message = f"""
{system_prompt}

## Task Context
{memory.get_formatted_context(max_length=64000)}

## Your Task
{task_goal}
...
"""
```

### 2.3 压缩策略设计

压缩作为独立的策略类，通过接口注入：

```python
class CompressionPolicy(ABC):
    """压缩策略接口"""
    
    @abstractmethod
    def compress(self, memory: Memory, target_size: int) -> Memory:
        """
        压缩 memory，返回压缩后的 memory。
        
        Args:
            memory: 原始 memory
            target_size: 目标大小（字符数）
        
        Returns:
            压缩后的 memory（可能是新实例或修改后的实例）
        """
        pass

class RuleBasedCompressionPolicy(CompressionPolicy):
    """基于规则的压缩策略"""
    pass

class ImportanceBasedCompressionPolicy(CompressionPolicy):
    """基于重要性的压缩策略"""
    pass

class LLMCompressionPolicy(CompressionPolicy):
    """基于 LLM 的压缩策略"""
    pass
```

**使用方式**：
```python
# 在需要压缩时
if memory_size > threshold:
    compression_policy = ImportanceBasedCompressionPolicy()
    memory = compression_policy.compress(memory, target_size=50000)
```

---

## 三、理想格式设计

### 3.1 格式结构

格式设计遵循以下原则：
1. **从重要到次要**：关键信息在前，细节在后
2. **从长期到短期**：长期记忆在前，近期活动在后
3. **指导性明确**：明确告诉 LLM 应该关注什么、下一步做什么
4. **信息密度高**：避免冗余，每个信息只出现一次

### 3.2 完整格式模板

```markdown
## Task Context

### ⚠️ Critical Warnings
[如果有已创建的文件，强烈警告不要重复创建]

### 📋 Task Overview
**Goal**: [任务目标]
**Status**: [进行中/已完成/已失败]
**Created Files**: [文件列表，如果有]

### 📝 Execution Plan
[当前执行计划，动态更新，标记已完成步骤]

### 🎯 Important Context
**Key Decisions**: [重要决策，Top 5]
**Milestones**: [重要里程碑，Top 5]
**Learnings**: [重要经验，Top 3]

### 📊 Recent Activity (Last 3 Steps)
**Steps**:
- Step N: [工具列表] → [stop_reason]
- Step N-1: [工具列表] → [stop_reason]
- Step N-2: [工具列表] → [stop_reason]

**Files Modified**:
- Step N: [文件列表]
- Step N-1: [文件列表]

### 🔧 Tool Execution Results (Last 5)
[工具执行结果，统一格式，包含成功/失败状态和关键输出]

### 📄 Modified Files Content
[最近修改的文件内容，如果有且重要]

### ⚠️ Current State
**Last Error**: [最近的错误，如果有]
**Current Diff**: [当前文件变更，如果有]
**Test Results**: [测试结果，如果有]

### 💡 Next Steps Guidance
[基于当前状态，明确指导下一步应该做什么]
```

---

## 四、详细示例

### 示例 1：任务早期阶段（简单场景）

**场景**：任务刚开始，只执行了环境检查

```markdown
## Task Context

### 📋 Task Overview
**Goal**: 模拟生成一只股票一个月的高开低收数据, 画成k线图给我.
**Status**: 进行中
**Created Files**: []

### 📝 Execution Plan
1. 检查当前目录和Python环境
2. 检查必要的Python库（如matplotlib, pandas）
3. 创建数据生成脚本
4. 创建绘图脚本
5. 运行脚本生成图表

### 🎯 Important Context
**Key Decisions**:
- ⭐⭐⭐ Step 2: Initial plan created (5 steps)

**Milestones**: (无)

**Learnings**: (无)

### 📊 Recent Activity (Last 3 Steps)
**Steps**:
- Step 3: [run, run] → continue
- Step 2: [plan] → continue

**Files Modified**:
- Step 3: []

### 🔧 Tool Execution Results (Last 5)
- Step 3: ✓ [run] `python3 --version && pip list | grep -E "matplotlib|pandas|numpy"`
  ```
  Python 3.10.12
  matplotlib                    3.10.8
  matplotlib-inline             0.2.1
  numpy                         2.2.6
  pandas                        2.3.3
  ```
  ✅ **Status**: Success - All required libraries are installed

- Step 3: ✓ [run] `ls -la`
  ```
  total 0
  drwxrwxrwx 2 root root 10 Jan 13 04:54 .
  drwxr-xr-x 1 root root 46 Jan 13 04:54 ..
  ```
  ✅ **Status**: Success - Directory is empty, ready for file creation

### ⚠️ Current State
**Last Error**: None
**Current Diff**: No changes
**Test Results**: No verification command available

### 💡 Next Steps Guidance
✅ **Environment Check Complete**: Python and required libraries are ready.
➡️ **Next Action**: Create the data generation script (`generate_data.py`) to generate OHLC data.
```

**设计要点**：
- ✅ 明确环境检查已完成，可以开始创建文件
- ✅ 工具执行结果包含关键信息（库版本、目录状态）
- ✅ 提供明确的下一步指导

### 示例 2：任务中期阶段（中等复杂度）

**场景**：已创建数据生成脚本，准备创建绘图脚本

```markdown
## Task Context

### ⚠️ Critical Warnings
🚨 **DO NOT recreate these files**:
- ✅ `generate_data.py` (created at Step 7)

### 📋 Task Overview
**Goal**: 模拟生成一只股票一个月的高开低收数据, 画成k线图给我.
**Status**: 进行中
**Created Files**: [generate_data.py]

### 📝 Execution Plan
1. ✅ 检查当前目录和Python环境
2. ✅ 检查必要的Python库（如matplotlib, pandas）
3. ✅ 创建数据生成脚本
4. 创建绘图脚本
5. 运行脚本生成图表

### 🎯 Important Context
**Key Decisions**:
- ⭐⭐⭐ Step 2: Initial plan created (5 steps)

**Milestones**:
- ⭐ Step 7: Created data generation script (`generate_data.py`)

**Learnings**: (无)

### 📊 Recent Activity (Last 3 Steps)
**Steps**:
- Step 7: [write_file] → continue
- Step 3: [run, run] → continue
- Step 2: [plan] → continue

**Files Modified**:
- Step 7: [generate_data.py]
- Step 3: []

### 🔧 Tool Execution Results (Last 5)
- Step 7: ✓ [write_file] `generate_data.py`
  ✅ **Status**: Success - File created (85 lines)
  📝 **Key Functions**:
    - `generate_stock_data(days=30, start_price=100.0)` - Generates OHLC data
    - `save_to_csv(df, filename='stock_data.csv')` - Saves to CSV

### 📄 Modified Files Content
**generate_data.py** (Step 7, 85 lines):
```python
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def generate_stock_data(days=30, start_price=100.0):
    """Generate OHLC (Open, High, Low, Close) data for a stock over a period."""
    # ... (implementation)
    
def save_to_csv(df, filename='stock_data.csv'):
    """Save DataFrame to CSV file."""
    # ... (implementation)

if __name__ == "__main__":
    df = generate_stock_data(days=30, start_price=100.0)
    save_to_csv(df, 'stock_data.csv')
```

### ⚠️ Current State
**Last Error**: None
**Current Diff**: 
```
+++ generate_data.py
@@ -0,0 +1,85 @@
+import numpy as np
+...
```
**Test Results**: No verification command available

### 💡 Next Steps Guidance
✅ **Data Generation Script Created**: `generate_data.py` is ready.
➡️ **Next Action**: Create the plotting script (`plot_kline.py`) to visualize the OHLC data as candlestick chart.
📌 **Note**: The plotting script should read `stock_data.csv` (generated by `generate_data.py`).
```

**设计要点**：
- ✅ 明确警告不要重复创建已存在的文件
- ✅ 显示已创建文件的关键信息（函数、用途）
- ✅ 提供文件内容预览（帮助理解上下文）
- ✅ 明确下一步应该做什么，并给出注意事项

### 示例 3：任务后期阶段（包含错误处理）

**场景**：已创建两个脚本，运行数据生成脚本成功，准备运行绘图脚本

```markdown
## Task Context

### ⚠️ Critical Warnings
🚨 **DO NOT recreate these files**:
- ✅ `generate_data.py` (created at Step 7)
- ✅ `plot_kline.py` (created at Step 10)

### 📋 Task Overview
**Goal**: 模拟生成一只股票一个月的高开低收数据, 画成k线图给我.
**Status**: 进行中
**Created Files**: [generate_data.py, plot_kline.py]

### 📝 Execution Plan
1. ✅ 检查当前目录和Python环境
2. ✅ 检查必要的Python库（如matplotlib, pandas）
3. ✅ 创建数据生成脚本
4. ✅ 创建绘图脚本
5. 运行数据生成脚本生成 CSV
6. 运行绘图脚本生成图表
7. 验证图表文件已创建

### 🎯 Important Context
**Key Decisions**:
- ⭐⭐⭐ Step 2: Initial plan created (5 steps)
- ⭐ Step 10: Created plotting script with candlestick and volume charts

**Milestones**:
- ⭐ Step 7: Created data generation script
- ⭐ Step 10: Created plotting script

**Learnings**:
- ⭐ Step 11: Data generation script outputs `stock_data.csv` which is required by plotting script

### 📊 Recent Activity (Last 3 Steps)
**Steps**:
- Step 11: [run] → continue
- Step 10: [write_file] → continue
- Step 7: [write_file] → continue

**Files Modified**:
- Step 11: [] (generated stock_data.csv)
- Step 10: [plot_kline.py]
- Step 7: [generate_data.py]

### 🔧 Tool Execution Results (Last 5)
- Step 11: ✓ [run] `python3 generate_data.py`
  ```
  Data saved to stock_data.csv
  Generated 30 days of OHLC data
  
  First 5 rows:
        Date    Open    High     Low   Close
  0 2025-12-03  100.00  101.23   99.35  101.09
  1 2025-12-04  101.09  104.52  100.86  104.27
  ...
  
  Summary statistics:
             Open        High         Low       Close
  count   30.000000   30.000000   30.000000   30.000000
  mean   103.652000  105.129333  102.219333  103.708000
  ```
  ✅ **Status**: Success - CSV file `stock_data.csv` generated with 30 days of data

- Step 10: ✓ [write_file] `plot_kline.py`
  ✅ **Status**: Success - File created (218 lines)
  📝 **Key Functions**:
    - `plot_candlestick(df, ...)` - Creates candlestick chart
    - `plot_combined_chart(df, ...)` - Creates chart with volume

### 📄 Modified Files Content
**plot_kline.py** (Step 10, 218 lines, most recent):
```python
import pandas as pd
import matplotlib.pyplot as plt
...

def plot_candlestick(df, title='Stock Price Candlestick Chart (30 Days)', save_path='stock_kline.png'):
    """Plot candlestick chart (K-line chart) from OHLC data."""
    # ... (implementation)

def plot_combined_chart(df, title='Stock Price with Volume'):
    """Plot candlestick chart with volume subplot."""
    # ... (implementation)

if __name__ == "__main__":
    df = load_stock_data('stock_data.csv')
    plot_candlestick(df)
    plot_combined_chart(df)
```

### ⚠️ Current State
**Last Error**: None
**Current Diff**: 
```
+++ plot_kline.py
@@ -0,0 +1,218 @@
+import pandas as pd
+...
```
**Test Results**: No verification command available

### 💡 Next Steps Guidance
✅ **Data Generated**: `stock_data.csv` is ready with 30 days of OHLC data.
✅ **Plotting Script Ready**: `plot_kline.py` is ready to visualize the data.
➡️ **Next Action**: Run `python3 plot_kline.py` to generate the candlestick charts.
📌 **Expected Output**: 
  - `stock_kline.png` (candlestick chart)
  - `stock_kline_with_volume.png` (chart with volume)
```

**设计要点**：
- ✅ 明确任务进度（已完成 4/7 步）
- ✅ 显示关键执行结果（CSV 生成成功）
- ✅ 提供明确的下一步指导和预期输出

### 示例 4：包含错误处理的场景

**场景**：运行绘图脚本时遇到错误

```markdown
## Task Context

### ⚠️ Critical Warnings
🚨 **DO NOT recreate these files**:
- ✅ `generate_data.py` (created at Step 7)
- ✅ `plot_kline.py` (created at Step 10)

### 📋 Task Overview
**Goal**: 模拟生成一只股票一个月的高开低收数据, 画成k线图给我.
**Status**: 进行中
**Created Files**: [generate_data.py, plot_kline.py]

### 📝 Execution Plan
1. ✅ 检查当前目录和Python环境
2. ✅ 检查必要的Python库
3. ✅ 创建数据生成脚本
4. ✅ 创建绘图脚本
5. ✅ 运行数据生成脚本生成 CSV
6. ⚠️ 运行绘图脚本生成图表 (遇到错误)
7. 修复错误并重新运行

### 🎯 Important Context
**Key Decisions**:
- ⭐⭐⭐ Step 2: Initial plan created
- ⭐ Step 10: Created plotting script

**Milestones**:
- ⭐ Step 7: Created data generation script
- ⭐ Step 10: Created plotting script
- ⭐ Step 11: Generated stock_data.csv

**Learnings**:
- ⭐ Step 12: `plot_kline.py` requires `stock_data.csv` to exist before running

### 📊 Recent Activity (Last 3 Steps)
**Steps**:
- Step 12: [run] → continue (error occurred)
- Step 11: [run] → continue
- Step 10: [write_file] → continue

**Files Modified**:
- Step 12: []
- Step 11: [] (generated stock_data.csv)
- Step 10: [plot_kline.py]

### 🔧 Tool Execution Results (Last 5)
- Step 12: ✗ [run] `python3 plot_kline.py`
  ```
  Traceback (most recent call last):
    File "plot_kline.py", line 1049, in <module>
      df = load_stock_data('stock_data.csv')
    File "plot_kline.py", line 867, in load_stock_data
      raise FileNotFoundError(f"Data file '{filename}' not found. Please run generate_data.py first.")
  FileNotFoundError: Data file 'stock_data.csv' not found. Please run generate_data.py first.
  ```
  ❌ **Status**: Failed - FileNotFoundError
  🔍 **Root Cause**: `stock_data.csv` was generated in a different directory
  💡 **Solution**: Check current directory and file location, or modify script to use absolute path

- Step 11: ✓ [run] `python3 generate_data.py`
  ```
  Data saved to stock_data.csv
  Generated 30 days of OHLC data
  ...
  ```
  ✅ **Status**: Success - CSV file generated

### ⚠️ Current State
**Last Error**: 
```
FileNotFoundError: Data file 'stock_data.csv' not found.
Location: plot_kline.py:867 in load_stock_data()
```
**Current Diff**: No new changes
**Test Results**: No verification command available

### 💡 Next Steps Guidance
❌ **Error Detected**: `stock_data.csv` not found when running plotting script.
🔍 **Investigation Needed**: 
  1. Check if `stock_data.csv` exists in current directory
  2. Verify the file was generated in the expected location
  3. Check if working directory changed between steps
➡️ **Next Action**: 
  - Option 1: Run `ls -la` to check current directory and file location
  - Option 2: Modify `plot_kline.py` to use absolute path or check file existence
  - Option 3: Re-run `generate_data.py` in the same directory as `plot_kline.py`
```

**设计要点**：
- ✅ 明确错误信息和根本原因
- ✅ 提供错误分析和解决方案建议
- ✅ 给出多个可行的修复选项

---

## 五、格式优化建议

### 5.1 对 LLM 的指导性

**当前格式的优势**：
- ✅ 层次清晰，从重要到次要
- ✅ 信息完整，包含必要的上下文
- ✅ 格式统一，易于解析

**可以改进的地方**：
1. **更明确的指导语言**：
   - 使用 "➡️ Next Action" 明确下一步
   - 使用 "📌 Note" 提供重要提示
   - 使用 "⚠️ Warning" 强调关键警告

2. **更清晰的状态标记**：
   - ✅ 成功
   - ❌ 失败
   - ⚠️ 警告
   - ➡️ 下一步

3. **更结构化的工具结果**：
   - 统一格式：`[状态] [工具] [命令/路径]`
   - 关键输出用代码块包裹
   - 状态和根因分析明确标注

### 5.2 信息密度优化

**当前可能冗余的地方**：
1. "Recent Activity" 和 "Tool Execution Results" 可能有重叠
   - **建议**：Recent Activity 只显示步骤摘要，详细结果在 Tool Execution Results

2. "Modified Files Content" 可能过长
   - **建议**：只显示关键部分（函数签名、主要逻辑），完整内容通过 `read_file` 获取

3. "Execution Plan" 可能包含已完成步骤的详细信息
   - **建议**：已完成步骤只显示 ✅ 标记，不显示详细内容

### 5.3 可扩展性

**支持未来扩展**：
1. **技能加载信息**：如果有加载的技能，可以添加 "Loaded Skills" 部分
2. **相关文件**：如果有识别的相关文件，可以添加 "Relevant Files" 部分
3. **进度指标**：如果有循环检测等指标，可以添加 "Progress Metrics" 部分

---

## 六、实现建议

### 6.1 Memory 模块接口

```python
class Memory:
    """Memory 数据存储和管理"""
    
    def get_formatted_context(
        self,
        max_length: Optional[int] = None,
        format_options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        获取格式化后的记忆上下文。
        
        Args:
            max_length: 最大长度限制
            format_options: 格式选项
                - include_file_content: bool (是否包含文件内容)
                - max_file_content_length: int (文件内容最大长度)
                - tool_results_count: int (工具结果数量)
                - steps_summary_count: int (步骤摘要数量)
        
        Returns:
            格式化后的字符串
        """
        # 实现格式化逻辑
        pass
```

### 6.2 格式化器设计

```python
class MemoryFormatter:
    """Memory 格式化器"""
    
    def format_task_overview(self, memory: Memory) -> str:
        """格式化任务概览"""
        pass
    
    def format_execution_plan(self, memory: Memory) -> str:
        """格式化执行计划"""
        pass
    
    def format_tool_results(
        self, 
        memory: Memory, 
        count: int = 5,
        max_output_length: int = 1000
    ) -> str:
        """格式化工具执行结果"""
        pass
    
    # ... 其他格式化方法
```

### 6.3 约束处理

```python
class OutputConstraints:
    """输出约束管理"""
    
    def __init__(self):
        self.max_single_item_length = 5000  # 单条最大长度
        self.max_total_length = 64000  # 总最大长度
        self.string_mappings = {
            # 字符串映射规则
        }
    
    def apply_constraints(self, text: str) -> str:
        """应用约束"""
        # 截断、映射等处理
        pass
```

---

## 七、总结

本格式设计旨在：
1. **提供清晰的上下文**：LLM 可以快速理解任务状态
2. **避免重复工作**：明确已创建的文件和已执行的步骤
3. **指导正确决策**：基于历史结果和当前状态
4. **高效执行任务**：明确的下一步指导和预期输出

通过分离关注点（Memory 负责格式化，Compression 作为独立策略），可以：
- 保持代码清晰和可维护
- 支持不同的压缩策略
- 易于扩展和定制
