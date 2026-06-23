# VizFlow

自然语言生成可视化工作流与节点编排 — MVP 演示版

## 快速开始

### 前置要求

- Python 3.11+
- Node.js 18+
- npm 或 yarn

### 启动（Windows PowerShell）

在项目根目录运行：

```powershell
.\scripts\dev.ps1
```

这会同时启动：
- 后端 FastAPI: http://localhost:8000
- 前端 Vite React: http://localhost:3000
- API 文档: http://localhost:8000/docs

### 手动启动

#### 后端

```powershell
cd backend
pip install -r requirements.txt
$env:PYTHONPATH="$PWD"
python -m uvicorn src.main:app --reload --port 8000
```

#### 前端

```powershell
cd frontend
npm install
npm run dev
```

## 项目结构

```
.
├── backend/              # Python FastAPI 后端
│   ├── src/
│   │   ├── api/         # API 路由 (datasets, charts, analysis, workflows)
│   │   ├── models/      # SQLAlchemy 数据模型
│   │   ├── services/    # LLM provider, thumbnails, validation
│   │   ├── schemas/     # Pydantic schemas
│   │   ├── storage/     # 文件存储适配器
│   │   ├── core/        # 配置、数据库、日志
│   │   └── main.py      # FastAPI 入口
│   └── requirements.txt
├── frontend/            # React + React Flow 前端
│   ├── src/
│   │   ├── components/
│   │   │   ├── nodes/   # DatasetNode, ChartNode, AnalysisNode
│   │   │   └── editors/ # 可视/JSON 双编辑器 (TODO)
│   │   ├── pages/       # FlowCanvas 主画布
│   │   ├── services/    # API 客户端
│   │   └── main.tsx
│   └── package.json
├── data/                # 运行时数据
│   ├── datasets/        # 上传的数据集
│   ├── thumbnails/      # 图表缩略图
│   └── db.sqlite3       # SQLite 数据库
└── specs/               # 规格与计划文档
    └── 001-number-1-shortname/
        ├── spec.md
        ├── plan.md
        ├── tasks.md
        ├── research.md
        ├── data-model.md
        └── contracts/openapi.yaml
```

## 当前功能（MVP Phase 3 完成 ✅）

- ✅ 上传数据集 (CSV/JSON) → 后端存储与去重
- ✅ **真实 LLM 集成** → DeepSeek API 生成 Vega-Lite spec
- ✅ 前端画布：React Flow + 节点/连线自动编排
- ✅ 节点组件：DatasetNode, ChartNode (带缩略图预览)
- ✅ 缓存与幂等 (hash-based)
- ⏳ 缩略图渲染（需安装 vl-convert-python）
- ⏳ 多模态分析（GLM-4.5v，Phase 4）
- ⏳ 图表可视/JSON 双编辑器（User Story 2）
- ⏳ 保存/导出与复现（User Story 3）

## 配置

创建 `backend/.env` 文件（可选）：

```env
DEMO_MODE=true
DB_URL=sqlite:///./data/db.sqlite3
DATASETS_DIR=./data/datasets
THUMBNAILS_DIR=./data/thumbnails

# LLM (optional)
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_MODEL=deepseek-chat

# Multimodal (optional)
GLM_API_KEY=your_key_here
GLM_MODEL=glm-4v
```

## 演示流程

1. 打开 http://localhost:3000
2. 点击"📤 上传数据"，选择 CSV 或 JSON 文件
3. （可选）输入自然语言 prompt，如"按月份汇总销售额并展示 Top5"
4. 点击"📊 生成图表"
5. 观察画布上出现 Dataset 节点与 Chart 节点，以及连线
6. 点击"🔄 自动布局"优化排版

## 开发进度

参见 `specs/001-number-1-shortname/tasks.md` 了解详细任务列表与依赖。

当前阶段：**Phase 3 - User Story 1 (P1 MVP)** 部分完成

## 文档

- [功能规格](specs/001-number-1-shortname/spec.md)
- [实现计划](specs/001-number-1-shortname/plan.md)
- [任务分解](specs/001-number-1-shortname/tasks.md)
- [技术决策](specs/001-number-1-shortname/research.md)
- [数据模型](specs/001-number-1-shortname/data-model.md)
- [API 契约](specs/001-number-1-shortname/contracts/openapi.yaml)

## License

MIT
