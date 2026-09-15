import React, { useState } from 'react';
import { Terminal, ChevronDown, ChevronUp, Cpu, Server, Activity } from 'lucide-react';
import { APIErrorState } from './ErrorPanel';

interface DebugPanelProps {
  sourceFormat: string;
  destFormat: string;
  jobId: string | null;
  lastError: APIErrorState | null;
  activeEndpoint?: string;
  httpStatus?: number | null;
}

export const DebugPanel: React.FC<DebugPanelProps> = ({
  sourceFormat,
  destFormat,
  jobId,
  lastError,
  activeEndpoint = '/api/analyze-source',
  httpStatus = 200
}) => {
  const [open, setOpen] = useState(false);

  return (
    <div style={{
      background: '#0B0F19',
      border: '1px solid #1E293B',
      borderRadius: '10px',
      marginTop: '32px',
      marginBottom: '16px',
      overflow: 'hidden',
      fontSize: '0.85rem'
    }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: '100%',
          background: '#0F172A',
          border: 'none',
          padding: '12px 18px',
          color: '#94A3B8',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
          fontWeight: 600
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Terminal size={16} color="#38BDF8" />
          <span>Developer Diagnostic Debug Panel</span>
          <span style={{
            background: '#1E293B',
            color: '#38BDF8',
            fontSize: '0.75rem',
            padding: '2px 8px',
            borderRadius: '4px',
            fontFamily: 'monospace'
          }}>
            Vercel Python 3.12 / ASGI
          </span>
        </div>
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>

      {open && (
        <div style={{ padding: '16px 20px', color: '#CBD5E1', fontFamily: 'monospace' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
            <div>
              <span style={{ color: '#64748B' }}>Source Format:</span>
              <div style={{ color: '#38BDF8', fontWeight: 'bold' }}>{sourceFormat}</div>
            </div>

            <div>
              <span style={{ color: '#64748B' }}>Destination Format:</span>
              <div style={{ color: '#38BDF8', fontWeight: 'bold' }}>{destFormat}</div>
            </div>

            <div>
              <span style={{ color: '#64748B' }}>Job Reference ID:</span>
              <div style={{ color: '#A855F7' }}>{jobId || 'N/A (Pending)'}</div>
            </div>

            <div>
              <span style={{ color: '#64748B' }}>Active API Route:</span>
              <div style={{ color: '#E2E8F0' }}>{activeEndpoint}</div>
            </div>

            <div>
              <span style={{ color: '#64748B' }}>HTTP Status:</span>
              <div style={{ color: httpStatus === 200 ? '#10B981' : '#F43F5E', fontWeight: 'bold' }}>
                {httpStatus ? `${httpStatus} OK` : 'None'}
              </div>
            </div>

            <div>
              <span style={{ color: '#64748B' }}>Last Error Code:</span>
              <div style={{ color: lastError ? '#F43F5E' : '#10B981' }}>
                {lastError ? lastError.error_code : 'CLEAN_NONE'}
              </div>
            </div>
          </div>

          {lastError && (
            <div style={{ marginTop: '14px', background: '#020617', padding: '10px 14px', borderRadius: '6px', border: '1px solid #1E293B' }}>
              <div style={{ color: '#F43F5E', fontWeight: 'bold', marginBottom: '4px' }}>
                Last Failure Stage: {lastError.stage} ({lastError.reference_id})
              </div>
              <div style={{ color: '#94A3B8' }}>{lastError.message}</div>
              {lastError.detail && <div style={{ color: '#64748B', marginTop: '4px' }}>Detail: {lastError.detail}</div>}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
