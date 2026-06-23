# Prompt 优化说明 - 6步推理法

## 概述

采用结构化的 6 步推理流程来引导 DeepSeek LLM 生成高质量的 Vega-Lite 图表规范。

## 优化前后对比

### 优化前（简单模式）
```
User request: 哪一种电影最赚钱
Dataset: [JSON dump]

Generate Vega-Lite spec...
```

**问题**：
- LLM 缺乏明确的分析步骤
- 容易忽略关键操作（聚合、排序、筛选）
- 图表类型选择不够精准
- 缺少对字段类型的推断

### 优化后（6步推理法）

```markdown
### Instruction:
哪一种电影最赚钱

### Table Input:
Table Name: Movies
Table Header: title,genre,revenue,rating,year
Table Header Type: nominal,nominal,quantitative,quantitative,quantitative
Table Data Example:
Movie A,Action,500000000,8.5,2020
Movie B,Comedy,200000000,7.2,2021
...

### Response:
Follow the 6-step reasoning process:
Step 1. Select the columns
Step 2. Filter the data
Step 3. Add aggregate functions
Step 4. Choose chart type
Step 5. Select encodings
Step 6. Sort the data
```

## 6步推理详解

### Step 1: Select the columns（选择列）
- 从用户需求中识别需要的字段
- 示例："哪一种电影最赚钱" → 需要 `genre`（类型）和 `revenue`（收入）

### Step 2: Filter the data（筛选数据）
- 判断是否需要过滤条件
- 示例："前3名" → 需要 top 3 filter
- 示例："2020年后" → 需要 year >= 2020

### Step 3: Add aggregate functions（聚合函数）
- 确定聚合类型：sum, mean, count, max, min
- 示例："最赚钱" → 按 genre 分组，计算 sum(revenue)

### Step 4: Choose chart type（选择图表）
- 比较/排名 → bar chart
- 趋势 → line/area chart
- 分布 → histogram
- 占比 → arc/pie chart

### Step 5: Select encodings（映射编码）
- x轴：通常是维度（nominal/ordinal）
- y轴：通常是度量（quantitative）
- color：分组/分类
- size：数值大小

### Step 6: Sort the data（排序）
- 确定是否需要排序
- 示例："最赚钱" → sort by revenue descending (`sort: "-y"`)

## 实际示例

### 示例 1：哪一种电影最赚钱

**LLM 推理过程**：
```
Step 1: 选择 genre 和 revenue 列
Step 2: 不需要筛选，使用全部数据
Step 3: 按 genre 分组，计算 sum(revenue)
Step 4: 使用 bar chart 进行比较
Step 5: x = genre (nominal), y = sum(revenue) (quantitative)
Step 6: 按收入降序排列 (sort: "-y")
```

**生成的 Vega-Lite spec**：
```json
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": {"values": [...]},
  "mark": "bar",
  "encoding": {
    "x": {
      "field": "genre",
      "type": "nominal",
      "sort": "-y",
      "axis": {"title": "电影类型"}
    },
    "y": {
      "field": "revenue",
      "type": "quantitative",
      "aggregate": "sum",
      "axis": {"title": "总收入"}
    }
  }
}
```

### 示例 2：收入前3的电影

**LLM 推理过程**：
```
Step 1: 选择 title 和 revenue 列
Step 2: 筛选前3名 (使用 transform.window + filter)
Step 3: 不需要聚合，直接使用原始值
Step 4: 使用 bar chart 展示排名
Step 5: x = title (nominal), y = revenue (quantitative)
Step 6: 按收入降序排列
```

**生成的 Vega-Lite spec**：
```json
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": {"values": [...]},
  "transform": [
    {"window": [{"op": "rank", "as": "rank"}], "sort": [{"field": "revenue", "order": "descending"}]},
    {"filter": "datum.rank <= 3"}
  ],
  "mark": "bar",
  "encoding": {
    "x": {"field": "title", "type": "nominal", "sort": "-y"},
    "y": {"field": "revenue", "type": "quantitative"}
  }
}
```

## 技术实现

### 1. 列类型推断

```python
def _infer_column_types(self, columns, sample_data):
    """自动推断字段类型"""
    for col in columns:
        values = [row.get(col) for row in sample_data]
        
        # 尝试转换为数字
        try:
            numeric_values = [float(v) for v in values]
            → quantitative
        except:
            # 检查日期模式
            if contains_date_pattern(values[0]):
                → temporal
            else:
                → nominal
```

### 2. 结构化 Prompt 构建

```python
user_prompt = f"""
### Instruction:
{prompt}

### Table Input:
Table Name: {table_name}
Table Header: {','.join(columns)}
Table Header Type: {','.join(column_types)}
Table Data Example:
{sample_rows}

### Response:
Follow the 6-step reasoning process...
"""
```

### 3. 智能 JSON 提取

```python
# 支持多种格式：
# 1. Markdown code block: ```json ... ```
# 2. 纯 JSON 对象: { ... }
# 3. 带分析的混合格式: Analysis... ```json ... ```

if "```json" in content:
    extract_from_markdown_block()
elif "{" in content:
    extract_by_brace_matching()
```

## 配置参数

```python
# 降低 temperature 提高稳定性
temperature=0.2

# 增加 max_tokens 容纳完整分析
max_tokens=2500

# 使用 5 行样本数据提高类型推断准确性
sample_data[:5]

# 设置合理超时避免长时间等待
timeout=60
```

## 效果评估

### 质量指标
- ✅ 图表类型准确率（bar vs line vs arc）
- ✅ 聚合操作正确性（sum, mean, count）
- ✅ 排序逻辑合理性
- ✅ 字段类型匹配度
- ✅ Vega-Lite 规范有效性

### 测试方法
运行测试脚本：
```bash
cd backend
python test_prompt_quality.py
```

### 预期结果
- 成功率：> 90%
- 图表类型准确率：> 95%
- 聚合操作正确率：> 85%
- 规范有效性：100%

## 已知限制

1. **复杂多层分组**：当前对嵌套分组支持有限
2. **时间序列**：日期格式识别可能不够准确
3. **地理可视化**：不支持地图类型
4. **交互功能**：暂不生成 tooltip、selection 等交互

## 后续优化方向

1. **Few-shot learning**：添加更多高质量示例
2. **Schema validation**：实时校验 Vega-Lite 规范
3. **迭代优化**：支持用户反馈后重新生成
4. **多模型对比**：测试 GPT-4、Claude 等模型效果
5. **缓存优化**：相似 prompt 复用已有结果

## 参考资料

- [Vega-Lite Documentation](https://vega.github.io/vega-lite/)
- [DeepSeek API Documentation](https://platform.deepseek.com/docs)
- [Prompt Engineering Guide](https://www.promptingguide.ai/)
