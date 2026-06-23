# 前端手动测试步骤 (T014)

## 测试环境
- 后端: http://localhost:8000 (已运行)
- 前端: http://localhost:3000 (已运行)

## 测试步骤

### 1. 打开前端页面
访问 http://localhost:3000

### 2. 测试上传数据集
1. 点击"上传数据集"按钮
2. 选择 `backend/test_data.csv` 文件
3. **预期结果**: 
   - 画布上出现一个 DatasetNode 节点
   - 节点显示文件名 "test_data.csv"

### 3. 测试生成图表
1. 在 Prompt 输入框中输入: "创建一个柱状图显示每个类别的值"
2. 点击"生成图表"按钮
3. **预期结果**:
   - 画布上出现一个 ChartNode 节点
   - 两个节点之间有连线
   - ChartNode 显示 prompt 文本
   - 可能显示缩略图(如果 thumbnail 生成成功)或显示 "Preview unavailable"

### 4. 测试自动布局
1. 点击"自动布局"按钮
2. **预期结果**:
   - 节点自动排列整齐

### 5. 测试手动拖拽
1. 拖动节点到任意位置
2. **预期结果**:
   - 节点可以自由拖动
   - 连线跟随节点移动

## 已知问题
- 缩略图生成已禁用 (缺少 vl-convert-python 依赖)
- ChartNode 会显示 "Preview unavailable" 占位符

## T014 验收标准
✅ 前端页面加载成功
✅ 可以上传 CSV 文件并显示 DatasetNode
✅ 可以生成图表并显示 ChartNode + 连线
✅ 节点包含正确的数据 (prompt, dataset_id, vega_lite_spec)
