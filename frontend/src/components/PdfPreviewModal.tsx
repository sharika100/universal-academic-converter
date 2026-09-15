import React from 'react';
import { X, ExternalLink, FileText } from 'lucide-react';

interface PdfPreviewModalProps {
  jobId: string;
  onClose: () => void;
}

export const PdfPreviewModal: React.FC<PdfPreviewModalProps> = ({ jobId, onClose }) => {
  const pdfUrl = `/api/download/${jobId}/pdf`;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '1.1rem', fontWeight: 600, color: '#F8FAFC' }}>
            <FileText color="#6366F1" size={20} /> Compiled PDF Manuscript Preview
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <a
              href={pdfUrl}
              target="_blank"
              rel="noreferrer"
              style={{ color: '#A5B4FC', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '4px', textDecoration: 'none' }}
            >
              Open in new tab <ExternalLink size={14} />
            </a>
            <button
              onClick={onClose}
              style={{ background: 'none', border: 'none', color: '#94A3B8', cursor: 'pointer', padding: '4px' }}
            >
              <X size={22} />
            </button>
          </div>
        </div>

        <div style={{ flex: 1, background: '#090D16' }}>
          <iframe
            src={pdfUrl}
            title="PDF Preview"
            style={{ width: '100%', height: '100%', border: 'none' }}
          />
        </div>
      </div>
    </div>
  );
};
