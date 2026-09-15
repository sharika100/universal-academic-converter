import React, { useRef } from 'react';
import { LayoutTemplate, Upload, FolderArchive, CheckCircle, FileCode, ChevronRight } from 'lucide-react';

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
}

export const DestinationPanel: React.FC<DestinationPanelProps> = ({
  format,
  setFormat,
  file,
  fileTree,
  onFileUpload,
  analysisDone
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
        {['DOCX', 'LaTeX', 'LaTeX Project ZIP'].map((fmt) => (
          <button
            key={fmt}
            className={`format-btn ${format === fmt ? 'active' : ''}`}
            onClick={() => setFormat(fmt)}
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
        accept={format === 'LaTeX Project ZIP' ? '.zip' : (format === 'DOCX' ? '.docx' : '.tex,.cls,.zip')}
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
          {file ? `${(file.size / 1024).toFixed(1)} KB — Click to change` : 'Accepts complete template ZIP packages (.cls, .sty, .bst, sample.tex)'}
        </div>
      </div>

      {fileTree.length > 0 && (
        <div className="file-tree-container">
          <div className="file-tree-header">
            <span>TARGET TEMPLATE INFRASTRUCTURE</span>
            <span>{fileTree.length} items</span>
          </div>
          {fileTree.map((item, idx) => (
            <div key={idx} className="file-tree-item">
              <ChevronRight size={12} color="#10B981" />
              <CheckCircle size={13} color="#34D399" />
              <span>{item.path}</span>
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: '16px', fontSize: '0.825rem', color: '#64748B' }}>
        <strong>Optional Guidelines:</strong> Upload PDF/DOCX author guidelines or sample paper for target rule extraction.
      </div>
    </div>
  );
};
