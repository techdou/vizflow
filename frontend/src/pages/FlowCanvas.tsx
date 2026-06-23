import { useCallback, useState, useRef, useEffect } from 'react';
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Edge,
  Node,
  ReactFlowProvider,
} from 'reactflow';
import dagre from 'dagre';
import 'reactflow/dist/style.css';

import DatasetNode from '../components/nodes/DatasetNode';
import ChartNode from '../components/nodes/ChartNode';
import AnalysisNode from '../components/nodes/AnalysisNode';
import { 
  uploadDataset, 
  generateChart,
  analyzeChart, 
  updateChart,
  updateAnalysis,
  saveWorkflow,
  loadWorkflow,
  exportWorkflow,
  importWorkflow,
} from '../services/api';

const nodeTypes = {
  datasetNode: DatasetNode,
  chartNode: ChartNode,
  analysisNode: AnalysisNode,
};

// Auto-layout with dagre
function getLayoutedElements(nodes: Node[], edges: Edge[]) {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ rankdir: 'LR', ranksep: 150, nodesep: 80 });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: 260, height: 200 });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - 130,
        y: nodeWithPosition.y - 100,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
}

function FlowCanvasInner() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [prompt, setPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [workflowId, setWorkflowId] = useState<string>(() => {
    // Get workflow ID from URL or generate new one
    const params = new URLSearchParams(window.location.search);
    return params.get('id') || `workflow-${Date.now()}`;
  });
  const [isSaving, setIsSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [isReadOnly, setIsReadOnly] = useState(false);
  const [toast, setToast] = useState<{ msg: string; kind: 'error' | 'info' } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const importFileRef = useRef<HTMLInputElement>(null);

  // Dirty flag + AbortController for in-flight LLM calls (fix #10/#12).
  // dirtyRef is set true on any node/edge change and cleared after a successful
  // save, so the 30s auto-save only fires when there are real changes.
  const dirtyRef = useRef(false);
  const llmAbortRef = useRef<AbortController | null>(null);

  // Non-blocking error/info toast instead of alert() (fix Low).
  const showToast = useCallback((msg: string, kind: 'error' | 'info' = 'error') => {
    setToast({ msg, kind });
    window.setTimeout(() => setToast(null), 5000);
  }, []);

  // Mark dirty whenever nodes/edges change (after the initial load).
  const firstLoadRef = useRef(true);
  useEffect(() => {
    if (firstLoadRef.current) {
      firstLoadRef.current = false;
      return;
    }
    dirtyRef.current = true;
  }, [nodes, edges]);

  // Load workflow on mount if ID exists in URL
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const id = params.get('id');
    if (id) {
      handleLoadWorkflow(id);
    }
  }, []);

  // Auto-save every 30 seconds, but only if there are unsaved changes (fix #12).
  useEffect(() => {
    if (nodes.length === 0) return;
    const interval = setInterval(() => {
      if (dirtyRef.current) {
        handleSaveWorkflow();
      }
    }, 30000);
    return () => clearInterval(interval);
  }, [nodes, edges]);

  const onConnect = useCallback(
    (params: Edge | Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  const handleChartUpdate = async (nodeId: string, newSpec: any) => {
    // Find the chart node
    const chartNode = nodes.find((n) => n.id === nodeId);
    if (!chartNode || chartNode.type !== 'chartNode') return;

    try {
      setIsGenerating(true);

      // Call update API
      const { node_payload } = await updateChart(
        chartNode.data.chart_spec_id,
        chartNode.data.dataset_id,
        { spec_json: newSpec }
      );

      // Update the node with new data
      setNodes((nds) =>
        nds.map((node) => {
          if (node.id === nodeId) {
            return {
              ...node,
              id: node_payload.id,  // Use new chart_spec_id
              data: {
                ...node_payload.data,
                onUpdate: handleChartUpdate,  // Preserve update handler
                onAnalyze: handleAnalyzeChart,  // Preserve analyze handler
              },
            };
          }
          return node;
        })
      );

      // Update edges if node id changed
      if (node_payload.id !== nodeId) {
        setEdges((eds) =>
          eds.map((edge) => {
            if (edge.target === nodeId) {
              return { ...edge, target: node_payload.id };
            }
            if (edge.source === nodeId) {
              return { ...edge, source: node_payload.id };
            }
            return edge;
          })
        );
      }

      console.log('Chart updated successfully:', node_payload.id);
    } catch (error) {
      console.error('Chart update failed:', error);
      showToast(`更新失败: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      setIsGenerating(true);
      const { dataset_id } = await uploadDataset(file);
      const datasetNode: Node = {
        id: dataset_id,
        type: 'datasetNode',
        position: { x: 50, y: 100 },
        data: {
          dataset_id,
          name: file.name,
          size_bytes: file.size,
          mime: file.type,
        },
      };

      setNodes((nds) => [...nds, datasetNode]);
    } catch (error) {
      console.error('Upload failed:', error);
      showToast(`上传失败: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsGenerating(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleGenerateChart = async () => {
    const datasetNode = nodes.find((n) => n.type === 'datasetNode');
    if (!datasetNode) {
      showToast('请先上传数据集');
      return;
    }

    // Abort any previous in-flight LLM request before starting a new one (fix #10).
    llmAbortRef.current?.abort();
    const ac = new AbortController();
    llmAbortRef.current = ac;

    try {
      setIsGenerating(true);
      console.log('[Chart] Starting generation, current nodes:', nodes.map(n => ({ id: n.id, type: n.type })));

      const { node_payload } = await generateChart(
        datasetNode.data.dataset_id,
        prompt || undefined,
        undefined,
        ac.signal
      );

      console.log('[Chart] API returned, current nodes:', nodes.map(n => ({ id: n.id, type: n.type })));

      const chartNode: Node = {
        id: node_payload.id,  // Use id from payload
        type: 'chartNode',
        position: { x: 350, y: 100 },
        data: {
          ...node_payload.data,
          onUpdate: handleChartUpdate,  // Pass update handler
          onAnalyze: handleAnalyzeChart,  // Pass analyze handler
        },
      };

      const edge: Edge = {
        id: `e-${datasetNode.id}-${node_payload.id}`,
        source: datasetNode.id,
        target: node_payload.id,
        animated: true,
      };

      // Create new nodes and edges arrays with the new items
      const newNodes = [...nodes, chartNode];
      const newEdges = [...edges, edge];

      // Apply auto-layout immediately on the new arrays
      const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
        newNodes,
        newEdges
      );

      setNodes(layoutedNodes);
      setEdges(layoutedEdges);
      dirtyRef.current = true;
    } catch (error: any) {
      if (error?.name === 'AbortError') {
        console.log('[Chart] generation aborted');
      } else {
        console.error('Chart generation failed:', error);
        showToast(`生成失败: ${error instanceof Error ? error.message : String(error)}`);
      }
    } finally {
      setIsGenerating(false);
    }
  };

  // Define handleAnalysisUpdate before handleAnalyzeChart so it can be used
  const handleAnalysisUpdate = useCallback(async (analysisId: string, newText: string) => {
    try {
      console.log('[Analysis Update] Updating analysis:', analysisId);
      
      // Call update API
      const node_payload = await updateAnalysis(analysisId, newText);
      
      console.log('[Analysis Update] Received updated payload:', node_payload);
      
      // Update the analysis node with new data - use functional update
      setNodes((nds) =>
        nds.map((node) => {
          if (node.id === analysisId && node.type === 'analysisNode') {
            return {
              ...node,
              data: {
                ...node_payload.data,
                onUpdate: handleAnalysisUpdate,  // Preserve update handler
              },
            };
          }
          return node;
        })
      );
      
      console.log('[Analysis Update] Node updated successfully');
      
    } catch (error) {
      console.error('[Analysis Update] Failed:', error);
      throw error;  // Re-throw to let component handle the error
    }
  }, []);  // Empty deps - function is stable

  const handleAnalyzeChart = useCallback(async (chartSpecId: string) => {
    // Abort any previous in-flight LLM request before starting a new one (fix #10).
    llmAbortRef.current?.abort();
    const ac = new AbortController();
    llmAbortRef.current = ac;

    try {
      setIsGenerating(true);

      console.log('[Analysis] Starting analysis for chart:', chartSpecId);

      const { node_payload } = await analyzeChart(chartSpecId, ac.signal);
      console.log('[Analysis] Received payload:', node_payload);

      // Single coordinated update: compute new nodes + edges from current state
      setNodes((currentNodes) => {
        setEdges((currentEdges) => {
          const chartNode = currentNodes.find(
            (n) => n.type === 'chartNode' && n.id === chartSpecId
          );

          if (!chartNode) {
            console.error('[Analysis] Chart node not found for chartSpecId:', chartSpecId);
            return currentEdges;
          }

          const analysisNode: Node = {
            id: node_payload.id,
            type: 'analysisNode',
            position: {
              x: chartNode.position.x + 350,
              y: chartNode.position.y,
            },
            data: {
              ...node_payload.data,
              onUpdate: handleAnalysisUpdate,
            },
          };

          const edge: Edge = {
            id: `e-${chartNode.id}-${node_payload.id}`,
            source: chartNode.id,
            target: node_payload.id,
            animated: true,
            style: { stroke: '#FF9800' },
          };

          const newNodes = [...currentNodes, analysisNode];
          const newEdges = [...currentEdges, edge];

          // Apply auto-layout to the combined set
          const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
            newNodes,
            newEdges
          );

          // Commit both updates together on the next tick to avoid nested-update warnings
          queueMicrotask(() => {
            setNodes(layoutedNodes);
            setEdges(layoutedEdges);
            dirtyRef.current = true;
          });

          return currentEdges;
        });

        return currentNodes;
      });

    } catch (error: any) {
      if (error?.name === 'AbortError') {
        console.log('[Analysis] aborted');
      } else {
        console.error('[Analysis] Chart analysis failed:', error);
        showToast(`分析失败: ${error instanceof Error ? error.message : String(error)}`);
      }
    } finally {
      setIsGenerating(false);
    }
  }, [showToast]);  // showToast is stable

  const handleAutoLayout = () => {
    const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(nodes, edges);
    setNodes(layoutedNodes);
    setEdges(layoutedEdges);
  };

  // Analyze the most recently created chart node (toolbar shortcut)
  const handleAnalyzeLatestChart = () => {
    // Find chart nodes in creation order (last one wins)
    const chartNodes = nodes.filter((n) => n.type === 'chartNode');
    if (chartNodes.length === 0) {
      showToast('请先生成图表，再进行分析', 'info');
      return;
    }
    const latest = chartNodes[chartNodes.length - 1];
    handleAnalyzeChart(latest.id);
  };

  const handleSaveWorkflow = async () => {
    try {
      setIsSaving(true);
      const elements = { nodes, edges };
      await saveWorkflow(workflowId, elements);
      setLastSaved(new Date());
      dirtyRef.current = false;  // clear dirty only after a successful save (fix #12)
      console.log('Workflow saved:', workflowId);
    } catch (error) {
      console.error('Save failed:', error);
      showToast(`保存失败: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleLoadWorkflow = async (id: string) => {
    try {
      setIsGenerating(true);
      const workflow = await loadWorkflow(id);
      
      // Restore nodes and edges
      if (workflow.elements) {
        const { nodes: loadedNodes, edges: loadedEdges } = workflow.elements;
        
        // Re-attach handlers to nodes
        const nodesWithHandlers = loadedNodes.map((node: Node) => {
          if (node.type === 'chartNode') {
            return {
              ...node,
              data: {
                ...node.data,
                onUpdate: handleChartUpdate,
                onAnalyze: handleAnalyzeChart,
              },
            };
          }
          if (node.type === 'analysisNode') {
            return {
              ...node,
              data: {
                ...node.data,
                onUpdate: handleAnalysisUpdate,
              },
            };
          }
          return node;
        });
        
        setNodes(nodesWithHandlers);
        setEdges(loadedEdges);
        setWorkflowId(id);
        
        // Update URL
        window.history.pushState({}, '', `?id=${id}`);
        console.log('Workflow loaded:', id);
      }
    } catch (error) {
      console.error('Load failed:', error);
      showToast(`加载失败: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleExportWorkflow = async () => {
    try {
      const exportData = await exportWorkflow(workflowId);
      
      // Download as JSON file
      const blob = new Blob([JSON.stringify(exportData, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `workflow-${workflowId}.json`;
      a.click();
      URL.revokeObjectURL(url);
      
      console.log('Workflow exported');
    } catch (error) {
      console.error('Export failed:', error);
      showToast(`导出失败: ${error instanceof Error ? error.message : String(error)}`);
    }
  };

  const handleImportFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      setIsGenerating(true);
      const text = await file.text();
      const data = JSON.parse(text);
      
      const result = await importWorkflow(data);
      
      // Load the imported workflow in read-only mode
      await handleLoadWorkflow(result.id);
      setIsReadOnly(true);
      
      showToast(`工作流已导入: ${result.name}`, 'info');
    } catch (error) {
      console.error('Import failed:', error);
      showToast(`导入失败: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsGenerating(false);
      if (importFileRef.current) importFileRef.current.value = '';
    }
  };

  return (
    <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Non-blocking toast (fix Low — replaces alert()) */}
      {toast && (
        <div style={{
          position: 'fixed', top: 16, right: 16, zIndex: 9999,
          padding: '12px 18px', borderRadius: 6, color: '#fff', fontSize: 14,
          backgroundColor: toast.kind === 'error' ? '#d32f2f' : '#1976d2',
          boxShadow: '0 4px 12px rgba(0,0,0,0.2)', maxWidth: 420,
        }}>
          {toast.msg}
        </div>
      )}
      {/* Top Toolbar */}
      <div style={{
        padding: '12px 16px',
        backgroundColor: '#fff',
        borderBottom: '1px solid #ddd',
        display: 'flex',
        gap: '12px',
        alignItems: 'center',
        boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
      }}>
        <h2 style={{ margin: 0, fontSize: '18px', color: '#333' }}>
          VizFlow
          {isReadOnly && <span style={{ color: '#ff9800', marginLeft: '8px', fontSize: '14px' }}>(只读模式)</span>}
        </h2>
        
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.json"
          onChange={handleFileUpload}
          style={{ display: 'none' }}
        />
        
        <input
          ref={importFileRef}
          type="file"
          accept=".json"
          onChange={handleImportFile}
          style={{ display: 'none' }}
        />
        
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={isGenerating || isReadOnly}
          style={{
            padding: '8px 16px',
            backgroundColor: '#4CAF50',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: (isGenerating || isReadOnly) ? 'not-allowed' : 'pointer',
            opacity: (isGenerating || isReadOnly) ? 0.6 : 1
          }}
        >
          📤 上传数据
        </button>

        <input
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="输入图表需求 (可选)"
          disabled={isReadOnly}
          style={{
            flex: 1,
            padding: '8px 12px',
            border: '1px solid #ddd',
            borderRadius: '4px',
            fontSize: '14px',
            opacity: isReadOnly ? 0.6 : 1
          }}
        />

        <button
          onClick={handleGenerateChart}
          disabled={isGenerating || nodes.length === 0 || isReadOnly}
          style={{
            padding: '8px 16px',
            backgroundColor: '#2196F3',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: (isGenerating || nodes.length === 0 || isReadOnly) ? 'not-allowed' : 'pointer',
            opacity: (isGenerating || nodes.length === 0 || isReadOnly) ? 0.6 : 1
          }}
        >
          {isGenerating ? '生成中...' : '📊 生成图表'}
        </button>

        <button
          onClick={handleAutoLayout}
          style={{
            padding: '8px 16px',
            backgroundColor: '#fff',
            color: '#333',
            border: '1px solid #ddd',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          🔄 自动布局
        </button>

        <button
          onClick={handleAnalyzeLatestChart}
          disabled={isGenerating || nodes.filter((n) => n.type === 'chartNode').length === 0 || isReadOnly}
          style={{
            padding: '8px 16px',
            backgroundColor: '#FF9800',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: (isGenerating || nodes.filter((n) => n.type === 'chartNode').length === 0 || isReadOnly) ? 'not-allowed' : 'pointer',
            opacity: (isGenerating || nodes.filter((n) => n.type === 'chartNode').length === 0 || isReadOnly) ? 0.6 : 1
          }}
        >
          💡 AI 分析
        </button>

        <div style={{ width: '1px', height: '24px', backgroundColor: '#ddd' }} />

        <button
          onClick={handleSaveWorkflow}
          disabled={isSaving || nodes.length === 0 || isReadOnly}
          style={{
            padding: '8px 16px',
            backgroundColor: '#9C27B0',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: (isSaving || nodes.length === 0 || isReadOnly) ? 'not-allowed' : 'pointer',
            opacity: (isSaving || nodes.length === 0 || isReadOnly) ? 0.6 : 1
          }}
        >
          {isSaving ? '保存中...' : '💾 保存'}
        </button>

        <button
          onClick={handleExportWorkflow}
          disabled={nodes.length === 0}
          style={{
            padding: '8px 16px',
            backgroundColor: '#FF9800',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: nodes.length === 0 ? 'not-allowed' : 'pointer',
            opacity: nodes.length === 0 ? 0.6 : 1
          }}
        >
          📥 导出
        </button>

        <button
          onClick={() => importFileRef.current?.click()}
          disabled={isGenerating}
          style={{
            padding: '8px 16px',
            backgroundColor: '#03A9F4',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: isGenerating ? 'not-allowed' : 'pointer',
            opacity: isGenerating ? 0.6 : 1
          }}
        >
          📤 导入
        </button>

        {lastSaved && (
          <span style={{ fontSize: '12px', color: '#666', marginLeft: 'auto' }}>
            最后保存: {lastSaved.toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* React Flow Canvas */}
      <div style={{ flex: 1 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          nodeTypes={nodeTypes}
          fitView
          minZoom={0.2}
          maxZoom={2}
        >
          <Controls />
          <MiniMap />
          <Background gap={12} size={1} />
        </ReactFlow>
      </div>
    </div>
  );
}

export default function FlowCanvas() {
  return (
    <ReactFlowProvider>
      <FlowCanvasInner />
    </ReactFlowProvider>
  );
}
