import React from 'react';
import { Zap, FileText, CheckCircle2, AlertTriangle, ShieldCheck, X, Loader2 } from 'lucide-react';

interface DocxOptimizationModalProps {
  isOpen: boolean;
  file: File | null;
  onConfirmOptimize: () => void;
  onProceedOriginal: () => void;
  onCancel: () => void;
  isOptimizing: boolean;
  optimizationProgress: { percent: number; statusText: string };
}

export const DocxOptimizationModal: React.FC<DocxOptimizationModalProps> = ({
  isOpen,
  file,
  onConfirmOptimize,
  onProceedOriginal,
  onCancel,
  isOptimizing,
  optimizationProgress
}) => {
  if (!isOpen || !file) return null;

  const originalSizeMb = (file.size / (1024 * 1024)).toFixed(1);
  const exceedsBlobLimit = file.size > 100 * 1024 * 1024;
  const estimatedOptimizedSizeMb = (file.size * 0.15 / (1024 * 1024)).toFixed(1);

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(15, 23, 42, 0.85)',
      backdropFilter: 'blur(6px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999,
      padding: '20px'
    }}>
      <div style={{
        backgroundColor: '#1E293B',
        border: '1px solid #334155',
        borderRadius: '16px',
        width: '100%',
        maxWidth: '560px',
        padding: '28px',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
        color: '#F8FAFC',
        position: 'relative'
      }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '44px',
              height: '44px',
              borderRadius: '12px',
              backgroundColor: 'rgba(59, 130, 246, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#3B82F6'
            }}>
              <Zap size={24} />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 700, color: '#F8FAFC' }}>
                Large Manuscript Detected ({originalSizeMb} MB)
              </h3>
              <span style={{ fontSize: '0.85rem', color: '#94A3B8' }}>
                Option B: Pre-Upload Document Image Optimization
              </span>
            </div>
          </div>
          {!isOptimizing && (
            <button
              onClick={onCancel}
              style={{ background: 'none', border: 'none', color: '#64748B', cursor: 'pointer', padding: '4px' }}
            >
              <X size={20} />
            </button>
          )}
        </div>

        {/* Content Body */}
        {isOptimizing ? (
          <div style={{ padding: '24px 0', textAlign: 'center' }}>
            <Loader2 size={40} className="animate-spin" style={{ color: '#3B82F6', margin: '0 auto 16px auto' }} />
            <h4 style={{ margin: '0 0 8px 0', fontSize: '1.05rem', color: '#F8FAFC' }}>
              Optimizing Manuscript Images...
            </h4>
            <p style={{ margin: '0 0 20px 0', fontSize: '0.88rem', color: '#94A3B8' }}>
              {optimizationProgress.statusText}
            </p>
            <div style={{ width: '100%', height: '8px', backgroundColor: '#0F172A', borderRadius: '4px', overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                width: `${optimizationProgress.percent}%`,
                backgroundColor: '#3B82F6',
                transition: 'width 0.3s ease'
              }} />
            </div>
          </div>
        ) : (
          <>
            {exceedsBlobLimit && (
              <div style={{
                backgroundColor: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                borderRadius: '10px',
                padding: '12px 16px',
                marginBottom: '20px',
                display: 'flex',
                alignItems: 'center',
                gap: '12px'
              }}>
                <AlertTriangle size={20} style={{ color: '#EF4444', flexShrink: 0 }} />
                <div style={{ fontSize: '0.85rem', color: '#FCA5A5' }}>
                  <strong>Upload Ceiling Exceeded:</strong> File size ({originalSizeMb} MB) exceeds Vercel storage's 100 MB limit. Optimization is required for successful upload.
                </div>
              </div>
            )}

            {/* Comparison Metrics Card */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '12px',
              backgroundColor: '#0F172A',
              padding: '16px',
              borderRadius: '12px',
              marginBottom: '20px'
            }}>
              <div>
                <span style={{ fontSize: '0.75rem', color: '#64748B', textTransform: 'uppercase', fontWeight: 600 }}>Original File Size</span>
                <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#EF4444' }}>{originalSizeMb} MB</div>
              </div>
              <div>
                <span style={{ fontSize: '0.75rem', color: '#64748B', textTransform: 'uppercase', fontWeight: 600 }}>Est. Optimized Size</span>
                <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#10B981' }}>~{estimatedOptimizedSizeMb} MB</div>
              </div>
            </div>

            {/* Preservations Checklist */}
            <div style={{ marginBottom: '24px' }}>
              <h4 style={{ margin: '0 0 12px 0', fontSize: '0.9rem', color: '#CBD5E1', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Strict Content & Format Guarantees
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 16px', fontSize: '0.85rem', color: '#94A3B8' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <CheckCircle2 size={15} style={{ color: '#10B981' }} /> 100% Text & Equations Intact
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <CheckCircle2 size={15} style={{ color: '#10B981' }} /> Captions & References Preserved
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <CheckCircle2 size={15} style={{ color: '#10B981' }} /> Dimensions & Aspect Ratio Kept
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <CheckCircle2 size={15} style={{ color: '#10B981' }} /> Tables & Layout Intact
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <button
                onClick={onConfirmOptimize}
                style={{
                  width: '100%',
                  padding: '14px',
                  backgroundColor: '#2563EB',
                  color: '#FFFFFF',
                  border: 'none',
                  borderRadius: '10px',
                  fontWeight: 600,
                  fontSize: '0.95rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  transition: 'background 0.2s ease'
                }}
              >
                <Zap size={18} />
                Optimize Images & Upload (~{estimatedOptimizedSizeMb} MB)
              </button>

              {!exceedsBlobLimit && (
                <button
                  onClick={onProceedOriginal}
                  style={{
                    width: '100%',
                    padding: '12px',
                    backgroundColor: 'transparent',
                    color: '#94A3B8',
                    border: '1px solid #334155',
                    borderRadius: '10px',
                    fontWeight: 500,
                    fontSize: '0.88rem',
                    cursor: 'pointer'
                  }}
                >
                  Upload Original Uncompressed ({originalSizeMb} MB)
                </button>
              )}

              <button
                onClick={onCancel}
                style={{
                  width: '100%',
                  padding: '10px',
                  backgroundColor: 'transparent',
                  color: '#64748B',
                  border: 'none',
                  fontSize: '0.85rem',
                  cursor: 'pointer'
                }}
              >
                Cancel Selection
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
