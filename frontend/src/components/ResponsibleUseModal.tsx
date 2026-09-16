import React, { useEffect } from 'react';
import { ShieldAlert, X, Lock, FileCheck, Info, CheckCircle2, AlertTriangle } from 'lucide-react';

interface ResponsibleUseModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ResponsibleUseModal: React.FC<ResponsibleUseModalProps> = ({ isOpen, onClose }) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="modal-overlay"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="responsible-use-title"
    >
      <div
        className="modal-content"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: '750px', maxHeight: '85vh', display: 'flex', flexDirection: 'column' }}
      >
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '1.15rem', fontWeight: 600, color: '#F8FAFC' }}>
            <ShieldAlert color="#6366F1" size={22} />
            <span id="responsible-use-title">Responsible Use, Privacy & Academic Integrity</span>
          </div>
          <button
            onClick={onClose}
            aria-label="Close modal"
            style={{ background: 'none', border: 'none', color: '#94A3B8', cursor: 'pointer', padding: '4px' }}
          >
            <X size={22} />
          </button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '24px', background: '#090D16', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          {/* Section A: Purpose */}
          <div style={{ background: '#111827', border: '1px solid #1F2937', borderRadius: '10px', padding: '16px' }}>
            <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#A5B4FC', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Info size={18} color="#6366F1" /> A. Purpose & Function
            </div>
            <p style={{ fontSize: '0.85rem', color: '#CBD5E1', lineHeight: 1.6, margin: 0 }}>
              The Universal Academic Format Converter transforms document formatting and structural elements between supported source and destination formats (such as DOCX and LaTeX). It is designed to assist researchers with publisher template layout compliance.
            </p>
          </div>

          {/* Section B: User Responsibility */}
          <div style={{ background: '#111827', border: '1px solid #1F2937', borderRadius: '10px', padding: '16px' }}>
            <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#A5B4FC', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <CheckCircle2 size={18} color="#10B981" /> B. User Responsibility
            </div>
            <p style={{ fontSize: '0.85rem', color: '#CBD5E1', lineHeight: 1.6, margin: 0 }}>
              Users are strictly responsible for ensuring that they have the appropriate copyright, IP rights, and institutional permissions to process uploaded manuscripts and destination template packages using this tool.
            </p>
          </div>

          {/* Section C & H: Confidentiality & Institutional Documents */}
          <div style={{ background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.25)', borderRadius: '10px', padding: '16px' }}>
            <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#F87171', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Lock size={18} color="#F87171" /> C. Confidentiality & Restricted Documents
            </div>
            <p style={{ fontSize: '0.85rem', color: '#FCA5A5', lineHeight: 1.6, margin: 0 }}>
              Do not upload institutional, student, examination, administrative, personal, confidential, proprietary, or other restricted documents unless you are authorized to process them using this service. Always review your institution's governance policies before processing unpublished or confidential research.
            </p>
          </div>

          {/* Section D & E: Academic Integrity & Content Preservation */}
          <div style={{ background: '#111827', border: '1px solid #1F2937', borderRadius: '10px', padding: '16px' }}>
            <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#A5B4FC', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <FileCheck size={18} color="#34D399" /> D. Academic & Content Integrity
            </div>
            <p style={{ fontSize: '0.85rem', color: '#CBD5E1', lineHeight: 1.6, margin: 0 }}>
              <strong>FORMAT ONLY</strong> mode preserves source text as the conversion target allows without paraphrasing, summarizing, or AI-generating scientific text. However, automated conversions may introduce formatting, layout, or structural errors. Users must inspect all authors, affiliations, figures, captions, tables, math equations, and citations prior to official submission.
            </p>
          </div>

          {/* Section F: Submission Disclaimer */}
          <div style={{ background: '#111827', border: '1px solid #1F2937', borderRadius: '10px', padding: '16px' }}>
            <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#A5B4FC', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertTriangle size={18} color="#F59E0B" /> E. Submission Disclaimer
            </div>
            <p style={{ fontSize: '0.85rem', color: '#CBD5E1', lineHeight: 1.6, margin: 0 }}>
              Successful document conversion or template compilation does not guarantee acceptance by any journal, conference, publisher, academic institution, or accreditation body.
            </p>
          </div>

          {/* Section G: Privacy Behavior */}
          <div style={{ background: '#111827', border: '1px solid #1F2937', borderRadius: '10px', padding: '16px' }}>
            <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#A5B4FC', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Lock size={18} color="#38BDF8" /> F. Verified Privacy Policy
            </div>
            <p style={{ fontSize: '0.85rem', color: '#CBD5E1', lineHeight: 1.6, margin: 0 }}>
              Please do not upload confidential or sensitive documents unless you are authorized to process them. Review your institution's policies before using the service for restricted documents. Uploaded manuscripts are processed in instance temporary storage to execute parsing and format conversion. Files are not analyzed for advertising or shared with third-party tracking services.
            </p>
          </div>

        </div>

        <div style={{ padding: '16px 24px', background: '#0F172A', borderTop: '1px solid #1E293B', display: 'flex', justifyContent: 'flex-end' }}>
          <button
            className="btn-primary"
            onClick={onClose}
            style={{ padding: '8px 20px', fontSize: '0.875rem' }}
          >
            I Understand
          </button>
        </div>
      </div>
    </div>
  );
};
