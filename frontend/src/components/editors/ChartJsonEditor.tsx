import { useState, useEffect, useRef } from 'react';
import Editor from '@monaco-editor/react';

interface ChartJsonEditorProps {
  spec: any;
  onChange: (newSpec: any) => void;
  onValidationError: (error: string | null) => void;
}

export default function ChartJsonEditor({ 
  spec, 
  onChange, 
  onValidationError 
}: ChartJsonEditorProps) {
  const [editorValue, setEditorValue] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);
  const editorRef = useRef<any>(null);

  // Initialize editor value when spec changes
  useEffect(() => {
    setEditorValue(JSON.stringify(spec, null, 2));
  }, [spec]);

  const handleEditorChange = (value: string | undefined) => {
    if (!value) return;
    
    setEditorValue(value);
    
    // Validate JSON
    try {
      const parsed = JSON.parse(value);
      
      // Validate Vega-Lite schema
      const errors = validateVegaLiteSpec(parsed);
      
      if (errors.length > 0) {
        const errorMsg = errors.join('; ');
        setValidationError(errorMsg);
        onValidationError(errorMsg);
      } else {
        setValidationError(null);
        onValidationError(null);
        onChange(parsed);
      }
    } catch (e: any) {
      const errorMsg = `Invalid JSON: ${e.message}`;
      setValidationError(errorMsg);
      onValidationError(errorMsg);
    }
  };

  const validateVegaLiteSpec = (spec: any): string[] => {
    const errors: string[] = [];
    
    // Required fields
    if (!spec.$schema) {
      errors.push('Missing $schema field');
    }
    
    if (!spec.mark && !spec.layer) {
      errors.push('Missing mark or layer field');
    }
    
    if (!spec.data) {
      errors.push('Missing data field');
    }
    
    // Security check: forbid external URLs
    if (spec.data && spec.data.url) {
      errors.push('External data URLs are forbidden');
    }
    
    return errors;
  };

  const handleEditorMount = (editor: any) => {
    editorRef.current = editor;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {validationError && (
        <div style={{
          padding: '8px 12px',
          backgroundColor: '#fee',
          color: '#c00',
          borderBottom: '1px solid #fcc',
          fontSize: '12px'
        }}>
          ⚠️ {validationError}
        </div>
      )}
      
      <div style={{ flex: 1 }}>
        <Editor
          height="100%"
          defaultLanguage="json"
          value={editorValue}
          onChange={handleEditorChange}
          onMount={handleEditorMount}
          theme="vs-light"
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            lineNumbers: 'on',
            roundedSelection: false,
            scrollBeyondLastLine: false,
            automaticLayout: true,
            tabSize: 2,
            wordWrap: 'on',
          }}
        />
      </div>
      
      <div style={{
        padding: '8px 12px',
        backgroundColor: '#f5f5f5',
        borderTop: '1px solid #ddd',
        fontSize: '11px',
        color: '#666',
        display: 'flex',
        justifyContent: 'space-between'
      }}>
        <span>
          {validationError ? '❌ Invalid' : '✓ Valid Vega-Lite'}
        </span>
        <span>
          Ctrl+F: Find | Ctrl+H: Replace
        </span>
      </div>
    </div>
  );
}
