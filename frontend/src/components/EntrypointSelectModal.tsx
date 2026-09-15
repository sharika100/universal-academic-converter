import React, { useState } from 'react';
import { X, FileCode, CheckCircle, HelpCircle } from 'lucide-react';

interface EntrypointSelectModalProps {
  candidates: string[];
  selectedEntrypoint: string;
  onSelect: (entrypoint: string) => void;
  onClose: () => void;
}

export const EntrypointSelectModal: React.FC<EntrypointSelectModalProps> = ({
  candidates,
  selectedEntrypoint,
  onSelect,
  onClose
}) => {
  const [current, setCurrent] = useState<string>(selectedEntrypoint || candidates[0]);

  const handleConfirm = () => {
    onSelect(current);
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '600px', height: 'auto', maxHeight: '80vh' }}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '1.1rem', fontWeight: 600, color: '#F8FAFC' }}>
            <HelpCircle color="#F59E0B" size={20} /> Multiple Entry Points Detected
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#94A3B8', cursor: 'pointer' }}>
            <X size={22} />
          </button>
        </div>

        <div style={{ padding: '24px', background: '#090D16' }}>
          <p style={{ color: '#CBD5E1', fontSize: '0.9rem', marginBottom: '16px', lineHeight: '1.5' }}>
            The uploaded source ZIP contains multiple candidate LaTeX files with <code>\documentclass</code>. Please select which file should be treated as the main manuscript entry point:
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '24px' }}>
            {candidates.map((file) => {
              const isSelected = current === file;
              return (
                <button
                  key={file}
                  onClick={() => setCurrent(file)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '12px 16px',
                    borderRadius: '8px',
                    background: isSelected ? 'rgba(99, 102, 241, 0.15)' : '#111827',
                    border: isSelected ? '1px solid #6366F1' : '1px solid #1F2937',
                    color: isSelected ? '#A5B4FC' : '#F8FAFC',
                    cursor: 'pointer',
                    fontSize: '0.9rem',
                    fontFamily: 'var(--font-mono)'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <FileCode size={16} color={isSelected ? '#6366F1' : '#94A3B8'} />
                    <span>{file}</span>
                  </div>
                  {isSelected && <CheckCircle size={16} color="#6366F1" />}
                </button>
              );
            })}
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
            <button className="btn-secondary" onClick={onClose}>Cancel</button>
            <button className="btn-primary" onClick={handleConfirm}>Confirm Entry Point</button>
          </div>
        </div>
      </div>
    </div>
  );
};
