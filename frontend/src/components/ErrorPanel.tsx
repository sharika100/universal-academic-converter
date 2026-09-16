import React from 'react';
import { AlertTriangle, RefreshCw, HelpCircle } from 'lucide-react';

export interface APIErrorState {
  stage: string;
  error_code: string;
  message: string;
  detail?: string;
  reference_id: string;
  timestamp?: string;
}

interface ErrorPanelProps {
  error: APIErrorState;
  onDismiss: () => void;
}

export const ErrorPanel: React.FC<ErrorPanelProps> = ({ error, onDismiss }) => {
  const getStageTitle = (stage: string) => {
    switch (stage) {
      case 'source_analysis':
        return 'Source Document Analysis Failed';
      case 'template_analysis':
        return 'Destination Template Analysis Failed';
      case 'conversion':
        return 'Document Conversion Failed';
      default:
        return 'Operation Failed';
    }
  };

  return (
    <div style={{
      background: '#1E1B4B',
      border: '1px solid #6366F1',
      borderRadius: '12px',
      padding: '20px 24px',
      marginBottom: '24px',
      color: '#F8FAFC',
      boxShadow: '0 10px 25px -5px rgba(99, 102, 241, 0.2)'
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ background: '#312E81', padding: '8px', borderRadius: '8px', color: '#818CF8' }}>
            <AlertTriangle size={24} />
          </div>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600, color: '#F8FAFC' }}>
              {getStageTitle(error.stage)}
            </h3>
            <span style={{ fontSize: '0.8rem', color: '#94A3B8', fontFamily: 'monospace' }}>
              Reference ID: <strong style={{ color: '#A5B4FC' }}>{error.reference_id}</strong> | Code: <strong style={{ color: '#F43F5E' }}>{error.error_code}</strong>
            </span>
          </div>
        </div>

        <button
          onClick={onDismiss}
          style={{
            background: 'transparent',
            border: '1px solid #475569',
            color: '#94A3B8',
            borderRadius: '6px',
            padding: '6px 12px',
            fontSize: '0.85rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}
        >
          <RefreshCw size={14} /> Dismiss & Retry
        </button>
      </div>

      <div style={{ marginTop: '16px', background: '#0F172A', padding: '14px 18px', borderRadius: '8px', border: '1px solid #1E293B' }}>
        <p style={{ margin: 0, fontSize: '0.95rem', color: '#E2E8F0', fontWeight: 500 }}>
          {error.message}
        </p>
        {error.detail && (
          <div style={{ marginTop: '8px', fontSize: '0.85rem', color: '#94A3B8', fontFamily: 'monospace', wordBreak: 'break-all' }}>
            Technical Details: {error.detail}
          </div>
        )}
      </div>

      <div style={{ marginTop: '14px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', color: '#A5B4FC' }}>
        <HelpCircle size={15} />
        <span>
          {['STORAGE_OBJECT_NOT_FOUND', 'STORAGE_CONFIGURATION_ERROR', 'LATEX_PROJECT_UPLOAD_ERROR', 'STORAGE_SECURITY_ERROR'].includes(error.error_code)
            ? 'Suggested action: Secure storage could not retrieve the uploaded project. Please retry the upload. If the problem persists, contact support with the Reference ID.'
            : 'Suggested action: Verify your document format and file integrity, then re-upload.'}
        </span>
      </div>
    </div>
  );
};
