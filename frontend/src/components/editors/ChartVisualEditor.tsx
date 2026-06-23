import { useState, useEffect } from 'react';

interface ChartVisualEditorProps {
  spec: any;
  onChange: (newSpec: any) => void;
}

export default function ChartVisualEditor({ spec, onChange }: ChartVisualEditorProps) {
  const [markType, setMarkType] = useState('bar');
  const [xField, setXField] = useState('');
  const [yField, setYField] = useState('');
  const [xType, setXType] = useState('nominal');
  const [yType, setYType] = useState('quantitative');
  const [aggregate, setAggregate] = useState('');
  const [sort, setSort] = useState('');
  const [topN, setTopN] = useState('');

  // Extract available fields from spec data
  const availableFields = spec?.data?.values?.[0] 
    ? Object.keys(spec.data.values[0]) 
    : [];

  // Initialize form from spec
  useEffect(() => {
    if (!spec) return;

    setMarkType(spec.mark || 'bar');
    
    const encoding = spec.encoding || {};
    
    // X axis
    if (encoding.x) {
      setXField(encoding.x.field || '');
      setXType(encoding.x.type || 'nominal');
      setSort(encoding.x.sort || '');
    }
    
    // Y axis
    if (encoding.y) {
      setYField(encoding.y.field || '');
      setYType(encoding.y.type || 'quantitative');
      setAggregate(encoding.y.aggregate || '');
    }
    
    // Top N from transform
    if (spec.transform) {
      const filterTransform = spec.transform.find((t: any) => t.filter);
      if (filterTransform) {
        const match = filterTransform.filter.match(/datum\.rank\s*<=\s*(\d+)/);
        if (match) {
          setTopN(match[1]);
        }
      }
    }
  }, [spec]);

  const handleApply = () => {
    // Build new spec
    const newSpec: any = {
      $schema: spec.$schema || 'https://vega.github.io/schema/vega-lite/v5.json',
      data: spec.data,
      mark: markType,
      encoding: {}
    };

    // Add encodings
    if (xField) {
      newSpec.encoding.x = {
        field: xField,
        type: xType,
      };
      
      if (sort) {
        newSpec.encoding.x.sort = sort;
      }
    }

    if (yField) {
      newSpec.encoding.y = {
        field: yField,
        type: yType,
      };
      
      if (aggregate) {
        newSpec.encoding.y.aggregate = aggregate;
      }
    }

    // Add Top N transform
    if (topN && parseInt(topN) > 0) {
      newSpec.transform = [
        {
          window: [{ op: 'rank', as: 'rank' }],
          sort: [{ field: yField, order: 'descending' }]
        },
        {
          filter: `datum.rank <= ${topN}`
        }
      ];
    }

    onChange(newSpec);
  };

  return (
    <div style={{ 
      padding: '16px', 
      display: 'flex', 
      flexDirection: 'column', 
      gap: '12px',
      height: '100%',
      overflow: 'auto'
    }}>
      <h3 style={{ margin: 0, fontSize: '14px', fontWeight: 'bold' }}>
        Visual Chart Editor
      </h3>

      {/* Chart Type */}
      <div>
        <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px', fontWeight: 'bold' }}>
          Chart Type
        </label>
        <select 
          value={markType} 
          onChange={(e) => setMarkType(e.target.value)}
          style={{ width: '100%', padding: '6px', fontSize: '13px' }}
        >
          <option value="bar">Bar Chart</option>
          <option value="line">Line Chart</option>
          <option value="area">Area Chart</option>
          <option value="point">Scatter Plot</option>
          <option value="arc">Pie Chart</option>
          <option value="tick">Tick Plot</option>
        </select>
      </div>

      {/* X Axis */}
      <div>
        <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px', fontWeight: 'bold' }}>
          X Axis (Dimension)
        </label>
        <select 
          value={xField} 
          onChange={(e) => setXField(e.target.value)}
          style={{ width: '100%', padding: '6px', fontSize: '13px', marginBottom: '4px' }}
        >
          <option value="">-- Select Field --</option>
          {availableFields.map(field => (
            <option key={field} value={field}>{field}</option>
          ))}
        </select>
        
        <select 
          value={xType} 
          onChange={(e) => setXType(e.target.value)}
          style={{ width: '100%', padding: '6px', fontSize: '13px' }}
        >
          <option value="nominal">Nominal (Category)</option>
          <option value="ordinal">Ordinal (Ordered)</option>
          <option value="quantitative">Quantitative (Number)</option>
          <option value="temporal">Temporal (Time)</option>
        </select>
      </div>

      {/* Y Axis */}
      <div>
        <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px', fontWeight: 'bold' }}>
          Y Axis (Measure)
        </label>
        <select 
          value={yField} 
          onChange={(e) => setYField(e.target.value)}
          style={{ width: '100%', padding: '6px', fontSize: '13px', marginBottom: '4px' }}
        >
          <option value="">-- Select Field --</option>
          {availableFields.map(field => (
            <option key={field} value={field}>{field}</option>
          ))}
        </select>
        
        <select 
          value={yType} 
          onChange={(e) => setYType(e.target.value)}
          style={{ width: '100%', padding: '6px', fontSize: '13px', marginBottom: '4px' }}
        >
          <option value="quantitative">Quantitative (Number)</option>
          <option value="nominal">Nominal (Category)</option>
          <option value="ordinal">Ordinal (Ordered)</option>
          <option value="temporal">Temporal (Time)</option>
        </select>
      </div>

      {/* Aggregation */}
      <div>
        <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px', fontWeight: 'bold' }}>
          Aggregation
        </label>
        <select 
          value={aggregate} 
          onChange={(e) => setAggregate(e.target.value)}
          style={{ width: '100%', padding: '6px', fontSize: '13px' }}
        >
          <option value="">None</option>
          <option value="count">Count</option>
          <option value="sum">Sum</option>
          <option value="mean">Mean</option>
          <option value="median">Median</option>
          <option value="min">Min</option>
          <option value="max">Max</option>
        </select>
      </div>

      {/* Sort */}
      <div>
        <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px', fontWeight: 'bold' }}>
          Sort Order
        </label>
        <select 
          value={sort} 
          onChange={(e) => setSort(e.target.value)}
          style={{ width: '100%', padding: '6px', fontSize: '13px' }}
        >
          <option value="">Default</option>
          <option value="-y">Descending (High to Low)</option>
          <option value="y">Ascending (Low to High)</option>
          <option value="-x">By X Descending</option>
          <option value="x">By X Ascending</option>
        </select>
      </div>

      {/* Top N */}
      <div>
        <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px', fontWeight: 'bold' }}>
          Top N (Optional)
        </label>
        <input 
          type="number" 
          value={topN} 
          onChange={(e) => setTopN(e.target.value)}
          placeholder="e.g., 10"
          min="1"
          style={{ width: '100%', padding: '6px', fontSize: '13px' }}
        />
      </div>

      {/* Apply Button */}
      <button
        onClick={handleApply}
        style={{
          padding: '10px 16px',
          backgroundColor: '#2196F3',
          color: '#fff',
          border: 'none',
          borderRadius: '4px',
          cursor: 'pointer',
          fontSize: '14px',
          fontWeight: 'bold',
          marginTop: 'auto'
        }}
      >
        Apply Changes
      </button>
    </div>
  );
}
