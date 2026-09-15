import React, { useRef } from 'react';
import { LayoutTemplate, Upload, FolderArchive, CheckCircle, FileCode, ChevronRight, Eye } from 'lucide-react';

interface FileTreeItem {
  path: string;
  name: string;
  type: string;
  size: number;
}

interface DestinationPanelProps {
  format: string;
  setFormat: (fmt: string) => void;
  file: File | null;
  fileTree: FileTreeItem[];
  onFileUpload: (file: File) => void;
  analysisDone: boolean;
  onViewStructure: () => void;
}

export const DestinationPanel: React.FC<DestinationPanelProps> = ({
  format,
  setFormat,
  file,
  fileTree,
  onFileUpload,
  analysisDone,
  onViewStructure
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      onFileUpload(e.dataTransfer.files[0]);
    }
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <div className="panel-title">
          <LayoutTemplate color="#10B981" size={22} />
          2. Destination Template
        </div>
        {analysisDone && (
          <span className="panel-badge" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#34D399', borderColor: 'rgba(16, 185, 129, 0.3)' }}>
            ✓ Target Analyzed
          </span>
        )}
      </div>

      <div className="format-selector">
        {['LaTeX Template ZIP', 'DOCX Template', 'LaTeX Template'].map((fmt) => (
          <button
            key={fmt}
            className={`format-btn ${format.includes('ZIP') && fmt.includes('ZIP') ? 'active' : (format === fmt ? 'active' : '')}`}
            onClick={() => setFormat(fmt.includes('ZIP') ? 'LaTeX Project ZIP' : (fmt.includes('DOCX') ? 'DOCX' : 'LaTeX'))}
          >
            {fmt.includes('ZIP') ? <FolderArchive size={15} /> : <FileCode size={15} />}
            {fmt}
          </button>
        ))}
      </div>

      <input
        type="file"
        ref={fileInputRef}
        style={{ display: 'none' }}
        onChange={(e) => {
          if (e.target.files && e.target.files[0]) {
            onFileUpload(e.target.files[0]);
          }
        }}
        accept={format.includes('ZIP') ? '.zip' : (format.includes('DOCX') ? '.docx' : '.tex,.cls,.zip')}
      />

      <div
        className={`dropzone ${file ? 'active' : ''}`}
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <Upload className="dropzone-icon" style={{ color: '#34D399' }} />
        <div className="dropzone-title">
          {file ? file.name : `Upload Destination Template (${format})`}
        </div>
        <div className="dropzone-sub">
          {file ? `${(file.size / 1024).toFixed(1)} KB — Click to replace` : 'Accepts complete template ZIP packages (.cls, .sty, .bst, sample.tex)'}
        </div>
      </div>

      {file && fileTree.length > 0 && (
        <div style={{ marginTop: '16px', background: '#0B0F19', border: '1px solid #1E293B', borderRadius: '10px', padding: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#34D399', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <CheckCircle size={14} /> Destination Template Uploaded ({fileTree.length} items)
            </span>
            <button
              onClick={(e) => { e.stopPropagation(); onViewStructure(); }}
              style={{ background: '#1F2937', border: '1px solid #374151', borderRadius: '6px', color: '#A5B4FC', fontSize: '0.775rem', padding: '4px 10px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              <Eye size={12} /> View Template Structure
            </button>
          </div>

          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.775rem', color: '#CBD5E1', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {fileTree.slice(0, 5).map((item, idx) => (
              <span key={idx} style={{ background: '#111827', padding: '2px 8px', borderRadius: '4px', border: '1px solid #1F2937' }}>
                ✓ {item.name}
              </span>
            ))}
            {fileTree.length > 5 && (
              <span style={{ color: '#64748B', fontSize: '0.75rem', alignSelf: 'center' }}>+{fileTree.length - 5} more</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
