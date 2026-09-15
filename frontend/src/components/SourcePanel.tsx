import React, { useRef } from 'react';
import { FileText, Upload, FolderArchive, CheckCircle, FileCode, ChevronRight } from 'lucide-react';

interface FileTreeItem {
  path: string;
  name: string;
  type: string;
  size: number;
}

interface SourcePanelProps {
  format: string;
  setFormat: (fmt: string) => void;
  file: File | null;
  fileTree: FileTreeItem[];
  onFileUpload: (file: File) => void;
  analysisDone: boolean;
}

export const SourcePanel: React.FC<SourcePanelProps> = ({
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
          <FileText color="#6366F1" size={22} />
          1. Source Manuscript
        </div>
        {analysisDone && (
          <span className="panel-badge" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#34D399', borderColor: 'rgba(16, 185, 129, 0.3)' }}>
            ✓ Parsed
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
        accept={format === 'LaTeX Project ZIP' ? '.zip' : (format === 'DOCX' ? '.docx' : '.tex,.zip')}
      />

      <div
        className={`dropzone ${file ? 'active' : ''}`}
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <Upload className="dropzone-icon" />
        <div className="dropzone-title">
          {file ? file.name : `Drag & Drop Source ${format}`}
        </div>
        <div className="dropzone-sub">
          {file ? `${(file.size / 1024).toFixed(1)} KB — Click to change` : 'or Browse Files'}
        </div>
      </div>

      {fileTree.length > 0 && (
        <div className="file-tree-container">
          <div className="file-tree-header">
            <span>EXTRACTED SOURCE STRUCTURE</span>
            <span>{fileTree.length} items</span>
          </div>
          {fileTree.map((item, idx) => (
            <div key={idx} className="file-tree-item">
              <ChevronRight size={12} color="#6366F1" />
              <CheckCircle size={13} color="#10B981" />
              <span>{item.path}</span>
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: '16px', fontSize: '0.825rem', color: '#64748B' }}>
        <strong>Source Template (Optional):</strong> Select if manuscript uses custom <code>.cls</code> or <code>.sty</code> package.
      </div>
    </div>
  );
};
