import React, { useState } from 'react';
import { Presentation, Upload, CheckCircle2, Download, AlertCircle, FileText, ArrowRight, RefreshCw, ShieldCheck, Lock, Info, ExternalLink } from 'lucide-react';
import { Header } from './Header';
import { Footer } from './Footer';

interface PptxConverterPageProps {
  onNavigate?: (path: string) => void;
}

const STEP_LABELS = [
  "Uploading",
  "Analyzing PowerPoint",
  "Analyzing Template",
  "Mapping Slides",
  "Extracting Images",
  "Generating LaTeX",
  "Compiling",
  "Creating ZIP"
];

export const PptxConverterPage: React.FC<PptxConverterPageProps> = ({ onNavigate }) => {
  const [pptxFile, setPptxFile] = useState<File | null>(null);
  const [tmplFile, setTmplFile] = useState<File | null>(null);

  const [analyzing, setAnalyzing] = useState<boolean>(false);
  const [converting, setConverting] = useState<boolean>(false);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [templateSpec, setTemplateSpec] = useState<any | null>(null);
  const [reportData, setReportData] = useState<any | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);

  const handlePptxUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const f = e.target.files[0];
      const ext = f.name.substring(f.name.lastIndexOf('.')).toLowerCase();
      if (ext !== '.pptx') {
        setErrorMessage(`Invalid PowerPoint file format '${ext}'. Please select a .pptx file.`);
        return;
      }
      setPptxFile(f);
      setErrorMessage(null);
    }
  };

  const handleTmplUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const f = e.target.files[0];
      const ext = f.name.substring(f.name.lastIndexOf('.')).toLowerCase();
      if (ext !== '.zip' && ext !== '.tex') {
        setErrorMessage(`Invalid template format '${ext}'. Please select a LaTeX template .zip archive or .tex file.`);
        return;
      }
      setTmplFile(f);
      setErrorMessage(null);
    }
  };

  const handleAnalyzeTemplate = async () => {
    if (!tmplFile) return;
    setAnalyzing(true);
    setErrorMessage(null);

    const fd = new FormData();
    fd.append('template_file', tmplFile);

    try {
      const res = await fetch('/api/pptx/analyze-template', { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Template analysis failed');
      setTemplateSpec(data.spec);
      alert(`Template Analyzed Successfully!\nClass: ${data.spec.document_class}\nBeamer: ${data.spec.is_beamer}\nTheme: ${data.spec.theme || 'Default'}\nSlide Environment: ${data.spec.slide_environment}`);
    } catch (err: any) {
      setErrorMessage(err.message || 'Error analyzing template');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleConvert = async () => {
    if (!pptxFile || !tmplFile) {
      setErrorMessage("Please select both a PowerPoint (.pptx) file and a LaTeX Template (.tex or .zip).");
      return;
    }

    setConverting(true);
    setErrorMessage(null);
    setReportData(null);
    setCurrentStep(0);

    // Animate stepped progression
    const timer1 = setTimeout(() => setCurrentStep(1), 500);
    const timer2 = setTimeout(() => setCurrentStep(2), 1200);
    const timer3 = setTimeout(() => setCurrentStep(3), 1800);
    const timer4 = setTimeout(() => setCurrentStep(4), 2400);
    const timer5 = setTimeout(() => setCurrentStep(5), 3000);
    const timer6 = setTimeout(() => setCurrentStep(6), 3600);

    const fd = new FormData();
    fd.append('pptx_file', pptxFile);
    fd.append('template_file', tmplFile);

    try {
      const res = await fetch('/api/pptx/convert', { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Conversion failed');

      setCurrentStep(7);
      setReportData(data);
      setJobId(data.job_id);
    } catch (err: any) {
      setErrorMessage(err.message || 'Conversion failed');
    } finally {
      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
      clearTimeout(timer4);
      clearTimeout(timer5);
      clearTimeout(timer6);
      setConverting(false);
    }
  };

  return (
    <div className="app-container">
      {/* Unified Navigation Header */}
      <Header currentPath="/pptx-to-latex" onNavigate={onNavigate} />

      {/* Main Container */}
      <main style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

        {/* Discovery & Back Link Banner */}
        <div className="panel" style={{ background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.12) 0%, rgba(17, 24, 39, 0.9) 100%)', borderColor: 'rgba(99, 102, 241, 0.3)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
            <div>
              <h2 style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Presentation style={{ width: '22px', height: '22px', color: 'var(--accent-primary)' }} />
                PPTX → LaTeX Beamer Converter
                <span className="panel-badge">Beamer Engine</span>
              </h2>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', lineHeight: '1.6', maxWidth: '800px', margin: 0 }}>
                Convert PowerPoint slides into customized LaTeX Beamer presentation projects.
                Extracts frame titles, bullet hierarchies, tables, high-resolution figures, and embedded OLE vector diagrams.
              </p>
            </div>
            <button
              onClick={() => onNavigate ? onNavigate('/') : (window.location.href = '/')}
              className="btn-secondary"
              style={{ fontSize: '0.85rem', padding: '8px 16px', display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <span>← Back to Universal Academic Format Converter</span>
            </button>
          </div>
        </div>

        {/* Academic Integrity & Responsibility Warning */}
        <aside className="integrity-card" aria-label="Academic Integrity & Responsibility" role="note" style={{
          background: 'rgba(245, 158, 11, 0.08)',
          border: '1px solid rgba(245, 158, 11, 0.35)',
          borderRadius: '8px',
          padding: '1rem 1.25rem',
          color: '#e2e8f0',
          lineHeight: 1.5
        }}>
          <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#fbbf24', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <span aria-hidden="true">⚠️</span> Academic Integrity &amp; Responsibility
          </div>
          <div style={{ fontSize: '0.815rem', color: '#cbd5e1', lineHeight: 1.45 }}>
            <p style={{ marginBottom: '0.5rem' }}>This tool converts and reformats user-provided academic content into LaTeX. It does not verify the originality, authorship, accuracy, research validity, citations, permissions, or ethical compliance of the submitted material.</p>
            <p style={{ marginBottom: '0.5rem' }}>Users are solely responsible for ensuring that their submitted content is original or properly attributed, that all figures, tables, images, datasets, and other materials are used with appropriate permission, and that the final document complies with the requirements and policies of the target journal, conference, institution, or publisher.</p>
            <p style={{ marginBottom: 0 }}>Formatting assistance does not constitute authorship, proofreading, peer review, plagiarism checking, or publication approval.</p>
          </div>
        </aside>

        {/* Error Alert Box */}
        {errorMessage && (
          <div className="panel" style={{ background: 'rgba(239, 68, 68, 0.1)', borderColor: 'rgba(239, 68, 68, 0.4)', padding: '16px', color: '#FCA5A5', display: 'flex', alignItems: 'center', gap: '12px' }}>
            <AlertCircle size={20} color="#EF4444" />
            <span style={{ fontSize: '0.875rem' }}>{errorMessage}</span>
          </div>
        )}

        {/* Upload Panels (Studio 2-Column Grid) */}
        <div className="studio-grid">

          {/* 1. PowerPoint Source Panel */}
          <div className="panel">
            <div className="panel-header">
              <div className="panel-title">
                <Presentation style={{ width: '20px', height: '20px', color: 'var(--accent-primary)' }} />
                <span>1. Source Presentation</span>
              </div>
              <span className="panel-badge">PPTX</span>
            </div>

            <label className="dropzone" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
              <Upload className="dropzone-icon" />
              <span className="dropzone-title">
                {pptxFile ? pptxFile.name : "Select PowerPoint Presentation"}
              </span>
              <span className="dropzone-sub" style={{ marginTop: '4px' }}>
                {pptxFile ? `${(pptxFile.size / 1024 / 1024).toFixed(2)} MB` : "Supports .pptx slide deck (up to 100 MB)"}
              </span>
              <input type="file" accept=".pptx" onChange={handlePptxUpload} style={{ display: 'none' }} />
            </label>
          </div>

          {/* 2. Destination Beamer Template Panel */}
          <div className="panel">
            <div className="panel-header">
              <div className="panel-title">
                <FileText style={{ width: '20px', height: '20px', color: 'var(--accent-primary)' }} />
                <span>2. LaTeX Beamer Template</span>
              </div>
              <span className="panel-badge">ZIP / TEX</span>
            </div>

            <label className="dropzone" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
              <Upload className="dropzone-icon" />
              <span className="dropzone-title">
                {tmplFile ? tmplFile.name : "Select LaTeX Template"}
              </span>
              <span className="dropzone-sub" style={{ marginTop: '4px' }}>
                {tmplFile ? `${(tmplFile.size / 1024 / 1024).toFixed(2)} MB` : "Supports Beamer template .zip or .tex"}
              </span>
              <input type="file" accept=".zip,.tex" onChange={handleTmplUpload} style={{ display: 'none' }} />
            </label>
          </div>
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
          <button
            onClick={handleAnalyzeTemplate}
            disabled={!tmplFile || analyzing || converting}
            className="btn-secondary"
            style={{ flex: 1, minWidth: '180px', padding: '12px 20px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', fontWeight: 600 }}
          >
            {analyzing ? <RefreshCw size={18} className="animate-spin" /> : null}
            <span>{analyzing ? "Analyzing Template..." : "Analyze Template"}</span>
          </button>

          <button
            onClick={handleConvert}
            disabled={!pptxFile || !tmplFile || converting}
            className="btn-primary"
            style={{ flex: 2, minWidth: '220px', padding: '12px 20px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', fontWeight: 600 }}
          >
            {converting ? <RefreshCw size={18} className="animate-spin" /> : <ArrowRight size={18} />}
            <span>{converting ? "Converting Presentation..." : "Convert Presentation"}</span>
          </button>
        </div>

        {/* Progress Pipeline */}
        {converting && (
          <div className="panel" style={{ padding: '20px' }}>
            <h4 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '16px' }}>Conversion Pipeline</h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '10px' }}>
              {STEP_LABELS.map((label, idx) => {
                const isActive = currentStep === idx;
                const isCompleted = currentStep > idx;
                return (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      fontSize: '0.8rem',
                      padding: '8px 10px',
                      borderRadius: '8px',
                      background: isCompleted ? 'rgba(16, 185, 129, 0.1)' : isActive ? 'rgba(99, 102, 241, 0.15)' : 'rgba(30, 41, 59, 0.5)',
                      border: isCompleted ? '1px solid rgba(16, 185, 129, 0.3)' : isActive ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent',
                      color: isCompleted ? '#34D399' : isActive ? '#A5B4FC' : '#64748B'
                    }}
                  >
                    <div style={{
                      width: '18px',
                      height: '18px',
                      borderRadius: '50%',
                      background: isCompleted ? '#10B981' : isActive ? '#6366F1' : '#334155',
                      color: '#FFFFFF',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '10px',
                      fontWeight: 700,
                      flexShrink: 0
                    }}>
                      {isCompleted ? "✓" : idx + 1}
                    </div>
                    <span style={{ fontWeight: isActive ? 600 : 400 }}>{label}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Conversion Results Card */}
        {reportData && (
          <div className="panel" style={{ padding: '24px', background: '#0F172A', borderColor: 'rgba(99, 102, 241, 0.3)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
                Conversion Summary
              </h3>
              <span
                style={{
                  display: 'inline-block',
                  padding: '4px 10px',
                  borderRadius: '6px',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  background: reportData.compilation?.pdf_generated ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                  color: reportData.compilation?.pdf_generated ? '#34D399' : '#FBBF24'
                }}
              >
                {reportData.compilation?.pdf_generated ? "PDF COMPILED" : "CONVERSION COMPLETED"}
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '14px', marginBottom: '20px' }}>
              <div style={{ background: '#1E293B', padding: '12px', borderRadius: '8px' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block' }}>PPT Slides</span>
                <strong style={{ fontSize: '1.05rem', color: 'var(--text-main)' }}>{reportData.summary.slide_count}</strong>
              </div>
              <div style={{ background: '#1E293B', padding: '12px', borderRadius: '8px' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block' }}>LaTeX Frames</span>
                <strong style={{ fontSize: '1.05rem', color: 'var(--text-main)' }}>{reportData.summary.generated_frames}</strong>
              </div>
              <div style={{ background: '#1E293B', padding: '12px', borderRadius: '8px' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block' }}>Extracted Images</span>
                <strong style={{ fontSize: '1.05rem', color: 'var(--text-main)' }}>{reportData.summary.extracted_images}</strong>
              </div>
              <div style={{ background: '#1E293B', padding: '12px', borderRadius: '8px' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block' }}>Converted Tables</span>
                <strong style={{ fontSize: '1.05rem', color: 'var(--text-main)' }}>{reportData.summary.converted_tables}</strong>
              </div>
              <div style={{ background: '#1E293B', padding: '12px', borderRadius: '8px' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block' }}>Template Class</span>
                <strong style={{ fontSize: '1.05rem', color: 'var(--text-main)' }}>{reportData.summary.template_class}</strong>
              </div>
              <div style={{ background: '#1E293B', padding: '12px', borderRadius: '8px' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block' }}>Compiler</span>
                <strong style={{ fontSize: '1.05rem', color: 'var(--text-main)' }}>{reportData.compilation?.compiler || "None"}</strong>
              </div>
            </div>

            <div style={{ fontSize: '0.85rem', color: '#94A3B8', marginBottom: '16px', lineHeight: 1.5 }}>
              {reportData.compilation?.pdf_generated
                ? "LaTeX compilation completed successfully."
                : "Conversion completed. LaTeX compilation could not be verified in the current environment."}
            </div>

            <a
              href={reportData.download_url}
              download
              className="btn-primary"
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                padding: '12px',
                borderRadius: '8px',
                textDecoration: 'none',
                fontWeight: 700,
                background: '#10B981',
                color: '#FFFFFF'
              }}
            >
              <Download size={18} />
              <span>Download LaTeX Project ZIP</span>
            </a>
          </div>
        )}

      </main>

      {/* Production UAFC Footer */}
      <Footer />
    </div>
  );
};
