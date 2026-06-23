import { memo, useState } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface AnalysisNodeData {
  analysis_id: string;
  chart_spec_id: string;
  text: string;
  model_tag?: string;
  created_at?: string;
  onUpdate?: (analysisId: string, newText: string) => void;
}

function AnalysisNode({ data, selected }: NodeProps<AnalysisNodeData>) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedText, setEditedText] = useState(data.text);
  const [isSaving, setIsSaving] = useState(false);

  // Format timestamp
  const formattedTime = data.created_at 
    ? new Date(data.created_at).toLocaleString('zh-CN', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    : '';

  const handleEdit = () => {
    setEditedText(data.text);
    setIsEditing(true);
  };

  const handleSave = async () => {
    if (!data.onUpdate) {
      alert('无法保存：缺少更新回调函数');
      return;
    }

    try {
      setIsSaving(true);
      await data.onUpdate(data.analysis_id, editedText);
      setIsEditing(false);
    } catch (error) {
      console.error('Failed to save analysis:', error);
      alert(`保存失败: ${error}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setEditedText(data.text);
    setIsEditing(false);
  };

  return (
    <div style={{
      padding: '12px 16px',
      borderRadius: '8px',
      border: selected ? '2px solid #FF9800' : '2px solid #FFE0B2',
      backgroundColor: '#fff',
      minWidth: '320px',
      maxWidth: '500px',
      boxShadow: selected 
        ? '0 4px 12px rgba(255, 152, 0, 0.3)' 
        : '0 2px 8px rgba(0,0,0,0.1)',
      transition: 'all 0.2s ease'
    }}>
      <Handle type="target" position={Position.Left} />
      
      {/* Header */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        marginBottom: '12px'
      }}>
        <div style={{ 
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <div style={{ fontWeight: 'bold', color: '#FF9800', fontSize: '14px' }}>
            💡 AI Analysis
          </div>
          {data.model_tag && (
            <div style={{ 
              fontSize: '10px', 
              color: '#999',
              backgroundColor: '#f5f5f5',
              padding: '2px 6px',
              borderRadius: '3px'
            }}>
              {data.model_tag}
            </div>
          )}
        </div>
        
        {/* Edit button */}
        {!isEditing && data.onUpdate && (
          <button
            onClick={handleEdit}
            style={{
              padding: '4px 10px',
              fontSize: '12px',
              border: '1px solid #FF9800',
              borderRadius: '4px',
              backgroundColor: '#fff',
              color: '#FF9800',
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#FFF3E0';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = '#fff';
            }}
          >
            ✏️ 编辑
          </button>
        )}
      </div>
      
      {/* Content area */}
      {isEditing ? (
        <div>
          <textarea
            value={editedText}
            onChange={(e) => setEditedText(e.target.value)}
            style={{
              width: '100%',
              minHeight: '200px',
              padding: '8px',
              fontSize: '13px',
              lineHeight: '1.6',
              border: '1px solid #ddd',
              borderRadius: '4px',
              fontFamily: 'inherit',
              resize: 'vertical'
            }}
            placeholder="输入分析内容（支持 Markdown）..."
          />
          
          {/* Action buttons */}
          <div style={{
            display: 'flex',
            gap: '8px',
            marginTop: '8px',
            justifyContent: 'flex-end'
          }}>
            <button
              onClick={handleCancel}
              disabled={isSaving}
              style={{
                padding: '6px 12px',
                fontSize: '12px',
                border: '1px solid #ddd',
                borderRadius: '4px',
                backgroundColor: '#fff',
                color: '#666',
                cursor: isSaving ? 'not-allowed' : 'pointer',
                opacity: isSaving ? 0.6 : 1
              }}
            >
              取消
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving}
              style={{
                padding: '6px 12px',
                fontSize: '12px',
                border: 'none',
                borderRadius: '4px',
                backgroundColor: '#FF9800',
                color: '#fff',
                cursor: isSaving ? 'not-allowed' : 'pointer',
                opacity: isSaving ? 0.6 : 1
              }}
            >
              {isSaving ? '保存中...' : '💾 保存'}
            </button>
          </div>
        </div>
      ) : (
        <div 
          className="markdown-content"
          style={{
            fontSize: '13px',
            lineHeight: '1.7',
            color: '#333',
            maxHeight: '400px',
            overflowY: 'auto',
            paddingRight: '4px'
          }}
        >
          <ReactMarkdown 
            remarkPlugins={[remarkGfm]}
            components={{
              h1: ({node, ...props}) => <h1 style={{ fontSize: '18px', marginTop: '12px', marginBottom: '8px', color: '#FF9800' }} {...props} />,
              h2: ({node, ...props}) => <h2 style={{ fontSize: '16px', marginTop: '10px', marginBottom: '6px', color: '#FF9800' }} {...props} />,
              h3: ({node, ...props}) => <h3 style={{ fontSize: '14px', marginTop: '8px', marginBottom: '4px', color: '#FFA726' }} {...props} />,
              p: ({node, ...props}) => <p style={{ marginBottom: '8px' }} {...props} />,
              ul: ({node, ...props}) => <ul style={{ marginLeft: '20px', marginBottom: '8px' }} {...props} />,
              ol: ({node, ...props}) => <ol style={{ marginLeft: '20px', marginBottom: '8px' }} {...props} />,
              li: ({node, ...props}) => <li style={{ marginBottom: '4px' }} {...props} />,
              code: ({node, inline, ...props}: any) => 
                inline 
                  ? <code style={{ backgroundColor: '#f5f5f5', padding: '2px 4px', borderRadius: '3px', fontSize: '12px' }} {...props} />
                  : <code style={{ display: 'block', backgroundColor: '#f5f5f5', padding: '8px', borderRadius: '4px', fontSize: '12px', overflowX: 'auto' }} {...props} />,
              strong: ({node, ...props}) => <strong style={{ color: '#FF9800', fontWeight: 600 }} {...props} />,
              blockquote: ({node, ...props}) => <blockquote style={{ borderLeft: '3px solid #FF9800', paddingLeft: '12px', margin: '8px 0', color: '#666' }} {...props} />,
            }}
          >
            {data.text || '分析中...'}
          </ReactMarkdown>
        </div>
      )}
      
      {/* Footer with timestamp */}
      {formattedTime && !isEditing && (
        <div style={{
          marginTop: '12px',
          paddingTop: '8px',
          borderTop: '1px solid #eee',
          fontSize: '11px',
          color: '#999',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <span>🕐 {formattedTime}</span>
          <span style={{ fontSize: '10px', color: '#bbb' }}>
            Markdown 支持
          </span>
        </div>
      )}
    </div>
  );
}

export default memo(AnalysisNode);
