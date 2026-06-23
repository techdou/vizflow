// API types matching contracts/openapi.yaml

export interface Dataset {
  dataset_id: string;
  name: string;
  mime: string;
  size_bytes: number;
  created_at: string;
}

export interface ChartNodePayload {
  type: 'chart';
  id: string;
  data: {
    chart_spec_id: string;
    dataset_id: string;
    vega_lite_spec: any;
    thumbnail_uri?: string;
    prompt?: string;
  };
}

export interface AnalysisNodePayload {
  type: 'analysis';
  id: string;
  data: {
    analysis_id: string;
    chart_spec_id: string;
    text: string;
    model_tag: string;
    created_at: string;
  };
}

export interface WorkflowElements {
  nodes: any[];
  edges: any[];
}

export interface WorkflowResponse {
  id: string;
  name: string;
  elements: any;
  created_at: string;
  updated_at: string;
}

export interface WorkflowExport {
  version: string;
  workflow: {
    id: string;
    name: string;
    created_at: string;
    updated_at: string;
  };
  elements: any;
  layout_meta?: any;
}

const API_BASE = '/api';

// ---- Shared fetch wrapper with AbortController support + friendly errors (fix #10/#11) ----

export class ApiError extends Error {
  status?: number;
  detail?: string;
  constructor(message: string, status?: number, detail?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function parseError(res: Response, defaultMessage: string): Promise<never> {
  // Try to extract backend {"detail": "..."} (fix #11)
  let detail = defaultMessage;
  try {
    const body = await res.json();
    if (body && typeof body.detail === 'string') detail = body.detail;
    else if (body && typeof body.error === 'string') detail = body.error;
  } catch {
    /* not JSON, keep default */
  }
  throw new ApiError(`${defaultMessage}: ${detail}`, res.status, detail);
}

function authHeaders(): Record<string, string> {
  // If the frontend has an API key configured (e.g. via localStorage), send it.
  const key = (typeof window !== 'undefined' && window.localStorage.getItem('vizflow_api_key')) || '';
  return key ? { 'X-API-Key': key } : {};
}

export async function uploadDataset(file: File, signal?: AbortSignal): Promise<{ dataset_id: string }> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/datasets`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
    signal,
  });

  if (!res.ok) return parseError(res, '上传失败');
  return res.json();
}

export async function listDatasets(signal?: AbortSignal): Promise<Dataset[]> {
  const res = await fetch(`${API_BASE}/datasets`, { signal });
  if (!res.ok) return parseError(res, '获取数据集列表失败');
  return res.json();
}

export async function generateChart(
  dataset_id: string,
  prompt?: string,
  policy_id?: string,
  signal?: AbortSignal
): Promise<{ chart_spec_id: string; node_payload: ChartNodePayload }> {
  const res = await fetch(`${API_BASE}/charts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ dataset_id, prompt, policy_id }),
    signal,
  });

  if (!res.ok) return parseError(res, '图表生成失败');
  return res.json();
}

export async function updateChart(
  chart_spec_id: string,
  dataset_id: string,
  options: {
    prompt?: string;
    spec_json?: any;
  },
  signal?: AbortSignal
): Promise<{ chart_spec_id: string; node_payload: ChartNodePayload }> {
  const res = await fetch(`${API_BASE}/charts/${chart_spec_id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      dataset_id,
      ...options
    }),
    signal,
  });

  if (!res.ok) return parseError(res, '图表更新失败');
  return res.json();
}

export async function analyzeChart(
  chart_spec_id: string,
  signal?: AbortSignal
): Promise<{ analysis_id: string; node_payload: AnalysisNodePayload }> {
  const res = await fetch(`${API_BASE}/analysis`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ chart_spec_id }),
    signal,
  });

  if (!res.ok) return parseError(res, '分析失败');
  return res.json();
}

export async function getAnalysis(
  analysis_id: string,
  signal?: AbortSignal
): Promise<AnalysisNodePayload> {
  const res = await fetch(`${API_BASE}/analysis/${analysis_id}`, { signal });
  if (!res.ok) return parseError(res, '获取分析失败');
  return res.json();
}

export async function updateAnalysis(
  analysis_id: string,
  text: string,
  signal?: AbortSignal
): Promise<AnalysisNodePayload> {
  const res = await fetch(`${API_BASE}/analysis/${analysis_id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
    signal,
  });

  if (!res.ok) return parseError(res, '更新分析失败');
  return res.json();
}

export async function saveWorkflow(
  workflow_id: string,
  elements: any,
  signal?: AbortSignal
): Promise<{ id: string; name: string; updated_at: string }> {
  const res = await fetch(`${API_BASE}/workflows/${workflow_id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ elements }),
    signal,
  });

  if (!res.ok) return parseError(res, '保存工作流失败');
  return res.json();
}

export async function loadWorkflow(workflow_id: string, signal?: AbortSignal): Promise<WorkflowResponse> {
  const res = await fetch(`${API_BASE}/workflows/${workflow_id}`, { signal });
  if (!res.ok) return parseError(res, '加载工作流失败');
  return res.json();
}

export async function exportWorkflow(workflow_id: string, signal?: AbortSignal): Promise<WorkflowExport> {
  const res = await fetch(`${API_BASE}/workflows/export/${workflow_id}`, {
    method: 'POST',
    signal,
  });
  if (!res.ok) return parseError(res, '导出工作流失败');
  return res.json();
}

export async function importWorkflow(data: WorkflowExport, signal?: AbortSignal): Promise<{ id: string; name: string }> {
  const res = await fetch(`${API_BASE}/workflows/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    signal,
  });
  if (!res.ok) return parseError(res, '导入工作流失败');
  return res.json();
}

export function getThumbnailUrl(chart_spec_id: string): string {
  return `${API_BASE}/thumbnails/${chart_spec_id}.png`;
}
