import React, { useRef } from 'react';
import { FileText, Upload, FolderArchive, CheckCircle, FileCode, Eye, ShieldAlert, Info } from 'lucide-react';

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
  onViewStructure: () => void;
  onOpenResponsibleUseModal: () => void;
}

export const SourcePanel: React.FC<SourcePanelProps> = ({
  format,
  setFormat,
  file,
  fileTree,
  onFileUpload,
  analysisDone,
  onViewStructure,
  onOpenResponsibleUseModal
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      onFileUpload(e.dataTransfer.files[0]);
    }
  };

  return (
    <div className="panel" style={{ display: 'flex', flexDirection: 'column' }}>
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
        {['LaTeX Project ZIP', 'DOCX', 'LaTeX'].map((fmt) => (
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
          {file ? file.name : `Upload Source ${format}`}
        </div>
        <div className="dropzone-sub">
          {file ? `${(file.size / 1024).toFixed(1)} KB — Click to replace` : 'Drag & Drop .zip or Browse Files'}
        </div>
      </div>

      {file && fileTree.length > 0 && (
        <div style={{ marginTop: '16px', background: '#0B0F19', border: '1px solid #1E293B', borderRadius: '10px', padding: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#34D399', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <CheckCircle size={14} /> Source Project Uploaded ({fileTree.length} items)
            </span>
            <button
              onClick={(e) => { e.stopPropagation(); onViewStructure(); }}
              style={{ background: '#1F2937', border: '1px solid #374151', borderRadius: '6px', color: '#A5B4FC', fontSize: '0.775rem', padding: '4px 10px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              <Eye size={12} /> View Project Structure
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

      {/* Compact Responsible Use Notice */}
      <div style={{ marginTop: 'auto', paddingTop: '16px' }}>
        <div style={{ background: '#0B0F19', border: '1px solid #1E293B', borderRadius: '10px', padding: '12px 14px', fontSize: '0.775rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontWeight: 600, color: '#A5B4FC', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <ShieldAlert size={14} color="#6366F1" /> Responsible Use & Privacy
            </span>
            <button
              type="button"
              onClick={onOpenResponsibleUseModal}
              style={{ background: 'transparent', border: 'none', color: '#38BDF8', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600, padding: 0, textDecoration: 'underline' }}
            >
              Learn more
            </button>
          </div>
          <p style={{ color: '#94A3B8', margin: '0 0 4px 0', lineHeight: 1.4 }}>
            Before uploading a document, make sure you have the right or permission to process it. Do not upload confidential, sensitive, personal, examination, proprietary, or unpublished material unless you are authorized to do so.
          </p>
          <p style={{ color: '#64748B', margin: 0, lineHeight: 1.4 }}>
            The converter is intended for document format and structural transformation. Always review the converted document before publication, submission, circulation, or official use.
          </p>
        </div>
      </div>
    </div>
  );
};
