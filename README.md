<div align="center">

# VizFlow

**Turn natural language into working visualizations, end-to-end.**

*自然语言 → 可视化图表 + AI 洞察分析，三节点智能体工作流。*

[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org)
[![React](https://img.shields.io/badge/react-18-61dafb.svg)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Model: DeepSeek-V4](https://img.shields.io/badge/DeepSeek--V4-flash-blueviolet)](https://api-docs.deepseek.com)

A node-based workbench where a sentence becomes a chart, and a chart becomes a written insight.
Built on **DeepSeek-V4-Flash** for chart-spec synthesis and analysis, **FastAPI** for the
backend, **React Flow** for the canvas, and **Vega-Lite** as the chart description language.

</div>

---

## ✨ What it does

```
┌──────────┐  prompt  ┌──────────┐  spec  ┌────────────┐
│ Dataset  │ ───────► │  Chart   │ ─────► │  Analysis  │
│  node    │          │  node    │       │    node    │
└──────────┘          └──────────┘       └────────────┘
   ↑ CSV/JSON           Vega-Lite           Markdown
                         JSON spec            insight
```

| Step | What happens | Output |
|---|---|---|
| **1. Upload** | Drag a CSV / JSON / XLSX onto the canvas. Schema is inferred and persisted. | A green **Dataset** node |
| **2. Generate** | Type something like *"bar chart of sales by month, descending"*. The 6-step structured-reasoning prompt turns it into a Vega-Lite v5 spec. | A blue **Chart** node with a live, rendered visualization |
| **3. Analyze** | Click **💡 AI 分析**. The model receives the spec + computed statistics (min/max/mean/distribution) and returns structured Markdown. | An orange **Analysis** node with a 4-section insight |

Everything is persisted. Reload the page, share the URL, the workflow comes back.

---

## 🚀 Quick start

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** and **npm**
- A **DeepSeek API key** ([get one here](https://platform.deepseek.com))

### 1. Clone & configure

```bash
git clone https://github.com/techdou/vizflow.git
cd vizflow
```

Create `backend/.env` (this file is gitignored — **never commit it**):

```env
DEEPSEEK_API_KEY=sk-your-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-v4-flash

# Optional: enable X-API-Key auth on /api/charts and /api/analysis
# VIZFLOW_API_KEY=some-long-random-string

# Optional: cap concurrent in-flight LLM calls (default 3)
# MAX_CONCURRENT_LLM=3
```

### 2. Start the backend

```bash
cd backend
pip install -r requirements.txt
PYTHONPATH=. uvicorn src.main:app --reload --port 8001
```

> **Note:** The port 8000/8001 distinction is intentional — port 8000 is often
> claimed by Hyper-V on Windows. Change `--port` if 8001 is also taken.

API docs are at <http://localhost:8001/docs>.

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>.

### 4. Try it

1. Click **📤 上传数据**, pick a CSV (try `backend/sales_test.csv`).
2. Type a prompt, e.g. *"按月份展示销售趋势并标注最高月份"*.
3. Click **📊 生成图表** — wait a few seconds, a chart appears.
4. Click **💡 AI 分析** — the model writes a structured insight below the chart.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│ Browser (React + React Flow + Vega-Embed)                           │
│   · node-based canvas with dagre auto-layout                        │
│   · chart nodes render the live Vega-Lite spec via vega-embed       │
│   · analysis nodes render Markdown via react-markdown                │
└────────────────────┬────────────────────────────────────────────────┘
                     │ /api/* (REST + X-API-Key)
┌────────────────────▼────────────────────────────────────────────────┐
│ FastAPI backend                                                      │
│   · X-API-Key auth dependency (disabled if VIZFLOW_API_KEY unset)   │
│   · asyncio.Semaphore caps in-flight LLM calls (default 3)           │
│   · streams uploads, dedups by SHA-256, infers schema at upload      │
│   · chart cache keyed by (dataset_hash + prompt + policy + model)    │
│   · SQLite with WAL; background thumbnail tasks share the engine     │
└────────────────────┬────────────────────────────────────────────────┘
                     │ OpenAI-compatible Chat Completions
┌────────────────────▼────────────────────────────────────────────────┐
│ DeepSeek-V4-Flash (MoE 284B / 13B active, 1M context)               │
│   · chart generation: 6-step structured-reasoning prompt              │
│   · analysis: spec + computed stats (min/max/mean/distribution)     │
│   · JSON extraction is raw_decode-based → braces in strings survive  │
└─────────────────────────────────────────────────────────────────────┘
```

A printable architecture diagram is in `report/assets/fig_architecture.png`.

---

## 🧠 How chart generation works

The single most important design choice is the **6-step structured-reasoning prompt**.
Without it, the model happily returns a bar chart for "show trend" requests.

| Step | What the model is asked to do |
|---|---|
| 1. Select columns | Identify which fields from the table are needed |
| 2. Filter data | Top N, value range, category filter, etc. |
| 3. Aggregate | count / sum / mean / min / max |
| 4. Choose chart type | bar (compare) / line (trend) / arc (proportion) / ... |
| 5. Select encodings | x / y / color / size + field types + sort |
| 6. Sort | sort field and direction |

The model emits reasoning text **then** a `\`\`\`json` block. The backend
uses `json.JSONDecoder.raw_decode` to robustly extract the spec (even when
the reasoning contains braces), and injects the full dataset (capped at 500 rows
via deterministic stride sampling for big tables).

This is inspired by **Chain-of-Thought** (Wei et al., 2022) and **ReAct**
(Yao et al., 2023); see the `参考文献` section below.

---

## 📊 Case studies (also in `report/`)

| Case | Dataset | Prompt | Generated |
|---|---|---|---|
| 1 | sales_test.csv (12 rows) | 按月份展示销售趋势并标注最高月份 | Layered chart: line + rule + text annotation. Model correctly identifies **Dec = 350**. |
| 2 | sample_data.csv (20 rows) | 各类别销售额 Top5，降序 | Bar with aggregate=sum + window/filter for top-N. Electronics leads. |
| 3 | energy_production.csv (12 rows) | 各类能源总量占比，饼图 | Arc chart with `fold` transform. Coal dominates. |

---

## 🧪 Engineering highlights

This isn't just a weekend script — the codebase has been hardened against a
number of concrete failure modes:

- **No more data pollution between concurrent requests.** The LLM provider
  singleton no longer stores per-request state on `self`; everything is local.
  Previously, request B could overwrite request A's dataset mid-flight.
- **Cache key includes dataset content hash.** A re-uploaded file with the
  same name and prompt correctly invalidates the old chart instead of
  serving stale data.
- **`cache_key` is no longer a unique DB constraint.** Regenerating the same
  chart no longer triggers an `IntegrityError` on the second insert.
- **SQLite WAL + connection pool.** Background thumbnail tasks reuse the
  shared `SessionLocal` instead of opening a new engine per request.
- **Robust JSON extraction.** `JSONDecoder.raw_decode` walks every `{`
  position and asks the decoder how far the object extends — correctly
  handling strings that contain braces.
- **Cap on embedded rows.** Specs bigger than 500 rows are sampled
  deterministically, keeping both the spec and downstream analysis tractable.
- **`AbortController` on the frontend.** Starting a new chart cancels any
  in-flight LLM call from the previous click — no more stale responses
  overwriting fresh state.
- **`generation_runs` audit table.** Every LLM call (chart + analysis) is
  recorded with input, output, status, and latency in milliseconds.
- **Aborts and dirty-flag auto-save.** Auto-save only runs when there are
  pending changes; the 30-second loop is gated by a `dirtyRef`.

---

## 🗂️ Project structure

```
visflow/
├── backend/                  # FastAPI service
│   ├── src/
│   │   ├── api/              # datasets / charts / analysis / workflows
│   │   ├── core/             # config, database, logging, deps (auth+semaphore)
│   │   ├── models/           # SQLAlchemy ORM
│   │   ├── schemas/          # Pydantic request/response shapes
│   │   ├── services/         # LLM provider, thumbnails, dataset parsing
│   │   ├── storage/          # file storage
│   │   └── main.py           # FastAPI entry
│   ├── tests/                # pytest + smoke tests
│   ├── docs/                 # design notes
│   ├── requirements.txt
│   └── .env                  # NOT in git
│
├── frontend/                 # React + Vite + React Flow
│   ├── src/
│   │   ├── components/
│   │   │   ├── nodes/        # DatasetNode / ChartNode / AnalysisNode
│   │   │   └── editors/      # Visual + JSON chart editors
│   │   ├── pages/            # FlowCanvas (main view)
│   │   └── services/         # API client with AbortController
│   ├── public/               # static assets (report-only, gitignored)
│   ├── package.json
│   └── vite.config.ts
│
├── .gitignore                # excludes .env, node_modules, db.sqlite3, …
├── .env                       # NOT in git
└── README.md
```

---

## ⚙️ Configuration reference

`backend/.env` (all optional except `DEEPSEEK_API_KEY`):

| Key | Default | Notes |
|---|---|---|
| `DEEPSEEK_API_KEY` | — | **Required.** Get one at <https://platform.deepseek.com>. |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | OpenAI-compatible endpoint |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | Try `deepseek-v4-pro` for higher quality (slower, thinking mode on) |
| `VIZFLOW_API_KEY` | *(empty)* | If set, `/api/charts` and `/api/analysis` require `X-API-Key` header. **Never deploy publicly with this empty.** |
| `MAX_CONCURRENT_LLM` | `3` | Global asyncio.Semaphore on LLM calls |
| `DEMO_MODE` | `true` | Verbose error messages in responses |
| `CORS_ORIGINS` | `localhost:3000,127.0.0.1:3000` | Comma-separated |
| `MAX_UPLOAD_SIZE` | 25 MB | Streamed in 1 MB chunks |
| `MAX_ROWS` | 200000 | Datasets beyond this are rejected |
| `ANALYSIS_PROVIDER` | `text` | `text` = DeepSeek; `vision` = GLM-4.5v (requires `GLM_API_KEY`) |

Frontend reads `localStorage.vizflow_api_key` (if set) and sends it as
`X-API-Key`. The default Vite dev proxy points at `http://localhost:8001`.

---

## 🛠️ Development

```bash
# Backend
cd backend
pip install -r requirements.txt
PYTHONPATH=. uvicorn src.main:app --reload --port 8001

# Frontend
cd frontend
npm install
npm run dev
```

Useful endpoints:

| URL | What it is |
|---|---|
| <http://localhost:3000> | The app |
| <http://localhost:8001/docs> | Swagger UI for the API |
| <http://localhost:8001/health> | Liveness check |
| <http://localhost:8001/redoc> | ReDoc API reference |

### Running tests

```bash
cd backend
PYTHONPATH=. python -m pytest tests/ -v          # unit tests
PYTHONPATH=. python smoke_test.py                # smoke
PYTHONPATH=. python test_deepseek_llm.py         # live LLM test (needs key)
```

---

## 🚢 Deployment notes

- The default SQLite setup is fine for one-machine demos but won't scale beyond
  one process. For multi-worker production, switch `DB_URL` to PostgreSQL.
- If you set `VIZFLOW_API_KEY`, also set the same value in the frontend's
  `localStorage.vizflow_api_key` (or extend the API client to read it from
  another source).
- CORS is locked to `localhost:3000` by default; override `CORS_ORIGINS` for
  your deployment host.
- The thumbnail renderer (`vl-convert-python`) is optional; if missing, the
  frontend renders charts via vega-embed and analysis works regardless.

---

## 🤝 Contributing

Issues and PRs welcome. The honest constraints:

- **Hallucination is real.** Always have a human check numerical claims. The
  `generation_runs` table is your audit trail.
- **V4 is preview.** Latency is higher than the old `deepseek-chat` (~15-30s
  per chart) because of the 1M-context MoE architecture. Reduce `max_tokens`
  or disable thinking mode for latency-sensitive deployments.
- **The frontend is desktop-first.** Mobile canvas UX is not a target.

## 📄 License

[MIT](LICENSE) — see the file. You are free to use, modify, and distribute,
provided the copyright notice is preserved.

## 🙏 Acknowledgments

- [Vega-Lite](https://vega.github.io/vega-lite/) and the [Grammar of
  Graphics](https://www.cs.uic.edu/~wilkinson/TheGrammarOfGraphics/TheGrammarOfGraphics.pdf)
  for the declarative visualization model.
- [DeepSeek](https://api-docs.deepseek.com) for the V4-Flash API that makes
  this work.
- React Flow for the node-based canvas.
- The report in `report/` (一份中文项目实践报告) for the academic writeup.
