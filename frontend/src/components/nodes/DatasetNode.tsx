import { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';

interface DatasetNodeData {
  dataset_id: string;
  name: string;
  size_bytes: number;
  mime: string;
}

function DatasetNode({ data }: NodeProps<DatasetNodeData>) {
  return (
    <div style={{
      padding: '12px 16px',
      borderRadius: '8px',
      border: '2px solid #4CAF50',
      backgroundColor: '#fff',
      minWidth: '200px',
      boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
    }}>
      <Handle type="source" position={Position.Right} />
      
      <div style={{ fontWeight: 'bold', marginBottom: '8px', color: '#4CAF50' }}>
        📊 Dataset
      </div>
      
      <div style={{ fontSize: '14px', marginBottom: '4px' }}>
        {data.name}
      </div>
      
      <div style={{ fontSize: '12px', color: '#666' }}>
        {data.mime} • {(data.size_bytes / 1024).toFixed(1)} KB
      </div>
    </div>
  );
}

export default memo(DatasetNode);
