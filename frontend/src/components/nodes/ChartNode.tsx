import { memo, useState, useEffect, useRef } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import embed from 'vega-embed';
import ChartJsonEditor from '../editors/ChartJsonEditor';
import ChartVisualEditor from '../editors/ChartVisualEditor';

interface ChartNodeData {
  chart_spec_id: string;
  dataset_id: string;
  vega_lite_spec?: any;
  thumbnail_uri?: string;
  prompt?: string;
  onUpdate?: (nodeId: string, newSpec: any) => void;
  onAnalyze?: (chartSpecId: string) => void;
}

function ChartNode({ data, id }: NodeProps<ChartNodeData>) {
  const [showEditor, setShowEditor] = useState(false);
  const [editorMode, setEditorMode] = useState<'visual' | 'json'>('visual');
  const [renderError, setRenderError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [editedSpec, setEditedSpec] = useState<any>(null);
  const chartRef = useRef<HTMLDivElement>(null);

  // Render Vega-Lite chart when spec is available or edited
  useEffect(() => {
    const specToRender = editedSpec || data.vega_lite_spec;
    if (!specToRender || !chartRef.current || showEditor) return;

    const renderChart = async () => {
      try {
        setRenderError(null);
        
        // Clear previous chart
        chartRef.current!.innerHTML = '';
        
        // Embed Vega-Lite spec
        await embed(chartRef.current!, specToRender, {
          actions: false, // Hide vega actions menu
          renderer: 'svg',
          width: 200,
          height: 140,
        });
      } catch (error: any) {
        console.error('Vega-Lite rendering error:', error);
        setRenderError(error.message || 'Rendering failed');
      }
    };

    renderChart();
  }, [data.vega_lite_spec, editedSpec, showEditor]);

  const handleSpecChange = (newSpec: any) => {
    setEditedSpec(newSpec);
  };

  const handleValidationError = (error: string | null) => {
    setValidationError(error);
  };

  const handleApplyChanges = () => {
    if (editedSpec && !validationError) {
      // Call parent update handler if provided
      if (data.onUpdate && id) {
        data.onUpdate(id, editedSpec);
      }
      setShowEditor(false);
    }
  };

  const handleCancelEdit = () => {
    setEditedSpec(null);
    setValidationError(null);
    setShowEditor(false);
  };

  if (showEditor) {
    // Editor mode
    return (
      <div style={{
        padding: '12px',
        borderRadius: '8px',
        border: '2px solid #2196F3',
        backgroundColor: '#fff',
        width: '500px',
        height: '600px',
        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
        display: 'flex',
        flexDirection: 'column'
      }}>
        <Handle type="target" position={Position.Left} />
        <Handle type="source" position={Position.Right} />
        
        {/* Header */}
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          marginBottom: '12px'
        }}>
          <div style={{ fontWeight: 'bold', color: '#2196F3' }}>
            📈 Edit Chart
          </div>
          
          {/* Editor Mode Tabs */}
          <div style={{ display: 'flex', gap: '4px' }}>
            <button
              onClick={() => setEditorMode('visual')}
              style={{
                padding: '4px 12px',
                border: '1px solid #ddd',
                borderRadius: '4px',
                backgroundColor: editorMode === 'visual' ? '#2196F3' : '#fff',
                color: editorMode === 'visual' ? '#fff' : '#333',
                cursor: 'pointer',
                fontSize: '11px'
              }}
            >
              Visual
            </button>
            <button
              onClick={() => setEditorMode('json')}
              style={{
                padding: '4px 12px',
                border: '1px solid #ddd',
                borderRadius: '4px',
                backgroundColor: editorMode === 'json' ? '#2196F3' : '#fff',
                color: editorMode === 'json' ? '#fff' : '#333',
                cursor: 'pointer',
                fontSize: '11px'
              }}
            >
              JSON
            </button>
          </div>
        </div>
        
        {/* Editor Content */}
        <div style={{ flex: 1, overflow: 'hidden', border: '1px solid #ddd', borderRadius: '4px' }}>
          {editorMode === 'visual' ? (
            <ChartVisualEditor 
              spec={editedSpec || data.vega_lite_spec || {}}
              onChange={handleSpecChange}
            />
          ) : (
            <ChartJsonEditor 
              spec={editedSpec || data.vega_lite_spec || {}}
              onChange={handleSpecChange}
              onValidationError={handleValidationError}
            />
          )}
        </div>
        
        {/* Actions */}
        <div style={{ 
          display: 'flex', 
          gap: '8px', 
          marginTop: '12px',
          justifyContent: 'flex-end'
        }}>
          <button
            onClick={handleCancelEdit}
            style={{
              padding: '8px 16px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              backgroundColor: '#fff',
              cursor: 'pointer',
              fontSize: '13px'
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleApplyChanges}
            disabled={!!validationError}
            style={{
              padding: '8px 16px',
              border: 'none',
              borderRadius: '4px',
              backgroundColor: validationError ? '#ccc' : '#4CAF50',
              color: '#fff',
              cursor: validationError ? 'not-allowed' : 'pointer',
              fontSize: '13px',
              fontWeight: 'bold'
            }}
          >
            Apply & Regenerate
          </button>
        </div>
      </div>
    );
  }

  // Normal display mode
  return (
    <div style={{
      padding: '12px',
      borderRadius: '8px',
      border: '2px solid #2196F3',
      backgroundColor: '#fff',
      minWidth: '240px',
      boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
    }}>
      <Handle type="target" position={Position.Left} />
      <Handle type="source" position={Position.Right} />
      
      <div style={{ fontWeight: 'bold', marginBottom: '8px', color: '#2196F3' }}>
        📈 Chart
      </div>
      
      {data.prompt && (
        <div style={{ fontSize: '12px', color: '#666', marginBottom: '8px', fontStyle: 'italic' }}>
          "{data.prompt}"
        </div>
      )}
      
      {/* Vega-Lite Chart Container */}
      <div 
        ref={chartRef}
        style={{
          width: '216px',
          height: '160px',
          backgroundColor: '#f5f5f5',
          borderRadius: '4px',
          marginBottom: '8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden'
        }}
      >
        {!data.vega_lite_spec && (
          <div style={{ color: '#999', fontSize: '12px' }}>No chart spec</div>
        )}
        {renderError && (
          <div style={{ color: '#f44336', fontSize: '11px', padding: '8px', textAlign: 'center' }}>
            渲染失败: {renderError}
          </div>
        )}
      </div>
      
      <div style={{ display: 'flex', gap: '4px', fontSize: '11px' }}>
        <button 
          onClick={() => setShowEditor(!showEditor)}
          style={{
            padding: '4px 8px',
            border: '1px solid #2196F3',
            borderRadius: '4px',
            backgroundColor: '#fff',
            cursor: 'pointer'
          }}
        >
          {showEditor ? '收起' : '编辑'}
        </button>
        <button 
          onClick={() => data.onAnalyze?.(data.chart_spec_id)}
          disabled={!data.onAnalyze}
          style={{
            padding: '4px 8px',
            border: '1px solid #FF9800',
            borderRadius: '4px',
            backgroundColor: '#fff',
            cursor: data.onAnalyze ? 'pointer' : 'not-allowed',
            opacity: data.onAnalyze ? 1 : 0.5,
            color: '#FF9800'
          }}
        >
          🔍 分析
        </button>
      </div>
    </div>
  );
}

export default memo(ChartNode);
