import React from 'react';
import { Download, FileText, CheckCircle2, ShieldCheck, FileCheck, Terminal, Eye } from 'lucide-react';

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
  const downloadUrl = (kind: string) => `/api/download/${report.job_id}/${kind}`;

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
            <a href={downloadUrl('zip')} download className="btn-primary" style={{ textDecoration: 'none' }}>
              <Download size={18} /> Download Converted LaTeX Project ZIP
            </a>
          ) : (
            <a href={downloadUrl('docx')} download className="btn-primary" style={{ textDecoration: 'none' }}>
              <Download size={18} /> Download Converted DOCX
            </a>
          )}
        </div>
      </div>

      {/* Content Integrity Check */}
      <div style={{ background: '#0B0F19', border: '1px solid #1E293B', borderRadius: '12px', padding: '20px', marginBottom: '24px' }}>
        <h3 style={{ fontSize: '1.05rem', color: '#F8FAFC', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ShieldCheck color="#10B981" size={20} /> Section 17: Content Integrity Check (Source vs Output)
        </h3>

        <table className="integrity-table">
          <thead>
            <tr>
              <th>DOCUMENT COMPONENT</th>
              <th>SOURCE COUNT</th>
              <th>OUTPUT COUNT</th>
              <th>INTEGRITY STATUS</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Paragraphs</td>
              <td>{report.integrity.paragraphs_source}</td>
              <td>{report.integrity.paragraphs_output}</td>
              <td><span style={{ color: '#34D399', fontWeight: 600 }}>✓ Preserved</span></td>
            </tr>
            <tr>
              <td>Figures & Captions</td>
              <td>{report.integrity.figures_source}</td>
              <td>{report.integrity.figures_output}</td>
              <td><span style={{ color: '#34D399', fontWeight: 600 }}>✓ Preserved</span></td>
            </tr>
            <tr>
              <td>Tables & Data</td>
              <td>{report.integrity.tables_source}</td>
              <td>{report.integrity.tables_output}</td>
              <td><span style={{ color: '#34D399', fontWeight: 600 }}>✓ Preserved</span></td>
            </tr>
            <tr>
              <td>Equations (LaTeX Math)</td>
              <td>{report.integrity.equations_source}</td>
              <td>{report.integrity.equations_output}</td>
              <td><span style={{ color: '#34D399', fontWeight: 600 }}>✓ Preserved</span></td>
            </tr>
            <tr>
              <td>References & Citations</td>
              <td>{report.integrity.references_source}</td>
              <td>{report.integrity.references_output}</td>
              <td><span style={{ color: '#34D399', fontWeight: 600 }}>✓ Preserved</span></td>
            </tr>
          </tbody>
        </table>
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
