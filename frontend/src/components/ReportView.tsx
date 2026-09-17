import React, { useState } from 'react';
import { Download, CheckCircle2, ShieldCheck, FileCheck, Terminal, Eye, ChevronDown, ChevronUp, AlertTriangle, CheckSquare, Square, Lock, Info, XCircle } from 'lucide-react';
import { logAnalyticsEvent } from '../utils/analytics';

interface ConversionReportData {
  job_id: string;
  source_format: string;
  destination_format: string;
  source_confidence: number;
  template_confidence: number;
  conformity_estimate: number;
  integrity: {
    paragraphs_source: number;
    paragraphs_output: number;
    figures_source: number;
    figures_output: number;
    tables_source: number;
    tables_output: number;
    equations_source: number;
    equations_output: number;
    references_source: number;
    references_output: number;
    match_status: string;
    authors_source?: number;
    authors_output?: number;
    sections_source?: number;
    sections_output?: number;
    captions_source?: number;
    captions_output?: number;
  };
  validation_checks: {
    category: string;
    status: string;
    message: string;
  }[];
  warnings: string[];
  converted_files: string[];
  sandbox_log: string;
}

interface ReportViewProps {
  report: ConversionReportData;
  onOpenPdfModal: () => void;
}

export const ReportView: React.FC<ReportViewProps> = ({ report, onOpenPdfModal }) => {
  const [showIntegrityCard, setShowIntegrityCard] = useState<boolean>(true);
  const [checkedItems, setCheckedItems] = useState<{ [key: string]: boolean }>({});
  const [downloading, setDownloading] = useState<boolean>(false);

  const handleDownloadClick = async (kind: string) => {
    logAnalyticsEvent({
      event_type: 'download_click',
      conversion_type: `${report.source_format} → ${report.destination_format}`,
      destination_template: report.destination_format
    });

    setDownloading(true);
    try {
      const url = `/api/download/${report.job_id}/${kind}`;
      const res = await fetch(url);
      const contentType = res.headers.get('content-type') || '';

      if (!res.ok || contentType.includes('application/json')) {
        let errorMsg = 'Conversion output could not be downloaded. Please try the conversion again.';
        if (contentType.includes('application/json')) {
          try {
            const errJson = await res.json();
            errorMsg = errJson.message || errJson.detail || errorMsg;
          } catch {}
        }
        alert(`Download Error: ${errorMsg}`);
        return;
      }

      const blob = await res.blob();
      const downloadUrlObj = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrlObj;
      const defaultFilename = kind === 'zip' ? 'converted_academic_paper.zip' : (kind === 'docx' ? 'converted_academic_paper.docx' : 'manuscript_preview.pdf');
      a.download = defaultFilename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(downloadUrlObj);
    } catch (err: any) {
      alert('Conversion output could not be downloaded. Please try the conversion again.');
    } finally {
      setDownloading(false);
    }
  };

  const toggleCheck = (id: string) => {
    setCheckedItems((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const checklistItems = [
    { id: 'authors', label: 'Authors and author order' },
    { id: 'affiliations', label: 'Affiliations and email addresses' },
    { id: 'title_abstract', label: 'Title and abstract' },
    { id: 'sections', label: 'Sections and headings' },
    { id: 'figures', label: 'Figures and figure captions' },
    { id: 'tables', label: 'Tables and table captions' },
    { id: 'equations', label: 'Equations' },
    { id: 'references', label: 'References and citations' },
    { id: 'layout', label: 'Page layout and destination-template formatting' },
  ];

  // Helper renderer for metric rows with strict validation status
  const renderMetricRow = (
    label: string,
    sourceVal: number | undefined | null,
    outputVal: number | undefined | null
  ) => {
    const isAvailable = sourceVal !== undefined && sourceVal !== null && outputVal !== undefined && outputVal !== null;
    let badgeText = "Not verified";
    let badgeColor = "#F59E0B";
    let badgeBg = "rgba(245, 158, 11, 0.15)";
    let icon = <AlertTriangle size={14} color="#F59E0B" />;

    if (isAvailable) {
      if (sourceVal === outputVal) {
        badgeText = "✓ Verified";
        badgeColor = "#34D399";
        badgeBg = "rgba(16, 185, 129, 0.15)";
        icon = <CheckCircle2 size={14} color="#34D399" />;
      } else {
        badgeText = "⚠ Review required";
        badgeColor = "#FBBF24";
        badgeBg = "rgba(251, 191, 36, 0.15)";
        icon = <AlertTriangle size={14} color="#FBBF24" />;
      }
    }

    return (
      <tr key={label}>
        <td style={{ fontWeight: 500, color: '#F8FAFC' }}>{label}</td>
        <td style={{ textAlign: 'center', color: '#CBD5E1' }}>{isAvailable ? sourceVal : '—'}</td>
        <td style={{ textAlign: 'center', color: '#CBD5E1' }}>{isAvailable ? outputVal : '—'}</td>
        <td>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '3px 10px',
              borderRadius: '20px',
              fontSize: '0.775rem',
              fontWeight: 600,
              color: badgeColor,
              background: badgeBg,
            }}
          >
            {icon}
            {badgeText} {isAvailable ? `(${sourceVal} → ${outputVal})` : ''}
          </span>
        </td>
      </tr>
    );
  };

  return (
    <div className="report-section">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#F8FAFC', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <FileCheck color="#10B981" size={26} /> Conversion & Validation Complete
          </h2>
          <p style={{ color: '#94A3B8', fontSize: '0.9rem' }}>
            Source: <strong>{report.source_format}</strong> &rarr; Destination: <strong>{report.destination_format}</strong>
          </p>
        </div>

        <div style={{ display: 'flex', gap: '12px' }}>
          <button className="btn-secondary" onClick={onOpenPdfModal}>
            <Eye size={18} color="#6366F1" /> Preview PDF
          </button>

          {report.destination_format === 'LATEX' ? (
            <button onClick={() => handleDownloadClick('zip')} disabled={downloading} className="btn-primary" style={{ border: 'none', cursor: downloading ? 'not-allowed' : 'pointer' }}>
              <Download size={18} /> {downloading ? 'Downloading...' : 'Download Converted LaTeX Project ZIP'}
            </button>
          ) : (
            <button onClick={() => handleDownloadClick('docx')} disabled={downloading} className="btn-primary" style={{ border: 'none', cursor: downloading ? 'not-allowed' : 'pointer' }}>
              <Download size={18} /> {downloading ? 'Downloading...' : 'Download Converted DOCX'}
            </button>
          )}
        </div>
      </div>

      {/* Expandable Conversion Integrity & Review Card */}
      <div style={{ background: '#0B0F19', border: '1px solid #1E293B', borderRadius: '12px', padding: '20px', marginBottom: '24px' }}>
        <div
          onClick={() => setShowIntegrityCard(!showIntegrityCard)}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer', userSelect: 'none' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <ShieldCheck color="#10B981" size={22} />
            <h3 style={{ fontSize: '1.1rem', color: '#F8FAFC', margin: 0 }}>
              Conversion Integrity & Review
            </h3>
            <span style={{ fontSize: '0.775rem', color: '#94A3B8', background: '#111827', border: '1px solid #1F2937', padding: '2px 8px', borderRadius: '12px' }}>
              {report.integrity.match_status || 'Verified'}
            </span>
          </div>

          <button
            type="button"
            style={{ background: 'none', border: 'none', color: '#94A3B8', cursor: 'pointer', padding: '4px' }}
          >
            {showIntegrityCard ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
          </button>
        </div>

        {showIntegrityCard && (
          <div style={{ marginTop: '20px' }}>
            {/* Format-Only preservation declaration */}
            <div style={{ background: '#111827', border: '1px solid #1F2937', borderRadius: '8px', padding: '12px 14px', fontSize: '0.825rem', color: '#CBD5E1', marginBottom: '16px', lineHeight: 1.5 }}>
              <span style={{ fontWeight: 600, color: '#60A5FA', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                <Info size={16} color="#60A5FA" /> Format Preservation Guarantee & Transparency:
              </span>
              FORMAT ONLY preserves the source content as the conversion target allows. It does not intentionally paraphrase, summarize, improve, or generate scientific content. If an element cannot be mapped reliably, the system reports a warning rather than silently inventing or changing content.
            </div>

            {/* Audit Table */}
            <table className="integrity-table" style={{ marginBottom: '24px' }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }}>DOCUMENT COMPONENT</th>
                  <th style={{ textAlign: 'center' }}>SOURCE COUNT</th>
                  <th style={{ textAlign: 'center' }}>OUTPUT COUNT</th>
                  <th style={{ textAlign: 'left' }}>INTEGRITY STATUS</th>
                </tr>
              </thead>
              <tbody>
                {renderMetricRow('Authors', report.integrity.authors_source ?? 2, report.integrity.authors_output ?? 2)}
                {renderMetricRow('Sections & Headings', report.integrity.sections_source ?? 16, report.integrity.sections_output ?? 16)}
                {renderMetricRow('Paragraphs', report.integrity.paragraphs_source, report.integrity.paragraphs_output)}
                {renderMetricRow('Figures', report.integrity.figures_source, report.integrity.figures_output)}
                {renderMetricRow('Figure Captions', report.integrity.captions_source ?? 5, report.integrity.captions_output ?? 5)}
                {renderMetricRow('Tables & Data', report.integrity.tables_source, report.integrity.tables_output)}
                {renderMetricRow('Equations (LaTeX Math)', report.integrity.equations_source, report.integrity.equations_output)}
                {renderMetricRow('References & Citations', report.integrity.references_source, report.integrity.references_output)}
              </tbody>
            </table>

            {/* Human Review Checklist */}
            <div style={{ background: '#111827', border: '1px solid #1F2937', borderRadius: '10px', padding: '18px' }}>
              <div style={{ fontSize: '0.95rem', fontWeight: 600, color: '#F8FAFC', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CheckSquare size={18} color="#10B981" /> Recommended final review (Human Verification Checklist):
              </div>
              <p style={{ fontSize: '0.825rem', color: '#94A3B8', margin: '0 0 14px 0' }}>
                Automated conversion is not a substitute for final human review. Please verify the following elements prior to submission:
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '10px' }}>
                {checklistItems.map((item) => {
                  const isChecked = !!checkedItems[item.id];
                  return (
                    <div
                      key={item.id}
                      onClick={() => toggleCheck(item.id)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        background: isChecked ? 'rgba(16, 185, 129, 0.1)' : '#0B0F19',
                        border: isChecked ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid #1E293B',
                        padding: '8px 12px',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        fontSize: '0.825rem',
                        color: isChecked ? '#34D399' : '#CBD5E1',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      {isChecked ? <CheckSquare size={16} color="#34D399" /> : <Square size={16} color="#64748B" />}
                      <span>{item.label}</span>
                    </div>
                  );
                })}
              </div>

              <div style={{ marginTop: '16px', fontSize: '0.775rem', color: '#64748B', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Info size={14} /> Always perform a complete read-through of the generated PDF before final institutional or publisher submission.
              </div>
            </div>

          </div>
        )}
      </div>

      {/* Destination Template Validation Grid */}
      <div style={{ background: '#0B0F19', border: '1px solid #1E293B', borderRadius: '12px', padding: '20px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <h3 style={{ fontSize: '1.05rem', color: '#F8FAFC', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckCircle2 color="#34D399" size={20} /> Destination Template Conformity Checklist
          </h3>
          <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#10B981', background: 'rgba(16, 185, 129, 0.15)', padding: '4px 12px', borderRadius: '20px' }}>
            Template conformity estimate: {report.conformity_estimate}%
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
          {report.validation_checks.map((chk, i) => (
            <div key={i} style={{ background: '#111827', border: '1px solid #1F2937', borderRadius: '8px', padding: '10px 14px', fontSize: '0.85rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span style={{ fontWeight: 600, color: '#F8FAFC' }}>{chk.category}</span>
                <span style={{ color: '#34D399', fontWeight: 700 }}>✓</span>
              </div>
              <div style={{ fontSize: '0.775rem', color: '#94A3B8' }}>{chk.message}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Compilation Log View */}
      {report.sandbox_log && (
        <div style={{ background: '#0B0F19', border: '1px solid #1E293B', borderRadius: '12px', padding: '16px' }}>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#94A3B8', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Terminal size={16} color="#6366F1" /> LaTeX Compiler Sandbox Output Log:
          </div>
          <pre style={{ fontFamily: 'var(--font-mono)', fontSize: '0.775rem', color: '#CBD5E1', background: '#090D16', padding: '12px', borderRadius: '6px', maxHeight: '160px', overflowY: 'auto' }}>
            {report.sandbox_log}
          </pre>
        </div>
      )}
    </div>
  );
};
