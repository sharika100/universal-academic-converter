import React from 'react';
import { X, Folder, FileCode, FileText, Image as ImageIcon, Database, Layers, CheckCircle } from 'lucide-react';

interface FileTreeItem {
  path: string;
  name: string;
  type: string;
  size: number;
}

interface StructureModalProps {
  title: string;
  fileTree: FileTreeItem[];
  detectedRules?: string[];
  onClose: () => void;
}

export const StructureModal: React.FC<StructureModalProps> = ({ title, fileTree, detectedRules, onClose }) => {
  const getIcon = (type: string) => {
    switch (type) {
      case 'code': return <FileCode size={15} color="#A5B4FC" />;
      case 'image': return <ImageIcon size={15} color="#34D399" />;
      case 'docx': return <FileText size={15} color="#60A5FA" />;
      default: return <FileText size={15} color="#94A3B8" />;
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '800px', height: '70vh' }}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '1.1rem', fontWeight: 600, color: '#F8FAFC' }}>
            <Folder color="#6366F1" size={20} /> {title} Structure Inspection
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#94A3B8', cursor: 'pointer' }}>
            <X size={22} />
          </button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '24px', background: '#090D16' }}>
          <div style={{ marginBottom: '20px', background: '#111827', border: '1px solid #1F2937', borderRadius: '10px', padding: '16px' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#94A3B8', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Layers size={16} color="#10B981" /> Extracted Files ({fileTree.length})
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.825rem', color: '#CBD5E1', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '8px' }}>
              {fileTree.map((item, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px', background: '#0B0F19', padding: '6px 10px', borderRadius: '6px', border: '1px solid #1E293B' }}>
                  {getIcon(item.type)}
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.path}</span>
                  <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: '#64748B' }}>{(item.size / 1024).toFixed(1)} KB</span>
                </div>
              ))}
            </div>
          </div>

          {detectedRules && detectedRules.length > 0 && (
            <div style={{ background: '#111827', border: '1px solid #1F2937', borderRadius: '10px', padding: '16px' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#94A3B8', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <CheckCircle size={16} color="#34D399" /> Template Analysis Rules Detected ({detectedRules.length})
              </div>
              <ul style={{ paddingLeft: '20px', fontSize: '0.85rem', color: '#CBD5E1', lineHeight: '1.7' }}>
                {detectedRules.map((rule, idx) => (
                  <li key={idx}>{rule}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
