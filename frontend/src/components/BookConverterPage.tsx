import React, { useState } from 'react';
import { BookOpen, Upload, CheckCircle2, Download, AlertCircle, FileText, ArrowRight, RefreshCw, ShieldCheck } from 'lucide-react';

export const BookConverterPage: React.FC = () => {
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [destFile, setDestFile] = useState<File | null>(null);
  
  const [jobId, setJobId] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState<boolean>(false);
  const [converting, setConverting] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>('');
  
  const [sourceUdm, setSourceUdm] = useState<any | null>(null);
  const [destSpec, setDestSpec] = useState<any | null>(null);
  const [report, setReport] = useState<any | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [hasAcknowledged, setHasAcknowledged] = useState<boolean>(true);

  const handleSourceUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSourceFile(e.target.files[0]);
      setErrorMessage(null);
    }
  };

  const handleDestUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setDestFile(e.target.files[0]);
      setErrorMessage(null);
    }
  };

  const handleStartBookConversion = async () => {
    if (!sourceFile || !destFile) {
      setErrorMessage("Please select both a Source manuscript (.docx) and a Target Book Template (.zip).");
      return;
    }

    setAnalyzing(true);
    setErrorMessage(null);
    setStatusMessage("1/3 Analyzing source manuscript...");

    try {
      // 1. Analyze Source
      const srcData = new FormData();
      srcData.append('file', sourceFile);
      const srcRes = await fetch('/api/book/analyze-source', { method: 'POST', body: srcData });

      if (!srcRes.ok) {
        const errJson = await srcRes.json().catch(() => ({}));
        throw new Error(errJson.detail || `Source analysis failed (HTTP ${srcRes.status})`);
      }
      const srcJson = await srcRes.json();
      setJobId(srcJson.job_id);
      setSourceUdm(srcJson.udm);

      // 2. Analyze Template
      setStatusMessage("2/3 Analyzing target book template...");
      const tmplData = new FormData();
      tmplData.append('file', destFile);
      tmplData.append('job_id', srcJson.job_id);
      const tmplRes = await fetch('/api/book/analyze-template', { method: 'POST', body: tmplData });

      if (!tmplRes.ok) {
        const errJson = await tmplRes.json().catch(() => ({}));
        throw new Error(errJson.detail || `Book template analysis failed (HTTP ${tmplRes.status})`);
      }
      const tmplJson = await tmplRes.json();
      setDestSpec(tmplJson.spec);

      // 3. Convert Book
      setAnalyzing(false);
      setConverting(true);
      setStatusMessage("3/3 Rendering book project & compiling chapters...");

      const convData = new FormData();
      convData.append('job_id', srcJson.job_id);
      convData.append('udm_json_str', JSON.stringify(srcJson.udm));
      convData.append('spec_json_str', JSON.stringify(tmplJson.spec));

      const convRes = await fetch('/api/book/convert', { method: 'POST', body: convData });

      if (!convRes.ok) {
        const errJson = await convRes.json().catch(() => ({}));
        throw new Error(errJson.detail || `Book conversion failed (HTTP ${convRes.status})`);
      }

      const convJson = await convRes.json();
      setReport(convJson.report);
      setStatusMessage("Book Conversion Complete!");

    } catch (err: any) {
      console.error("Book conversion error:", err);
      setErrorMessage(err.message || "An unexpected error occurred during book conversion.");
    } finally {
      setAnalyzing(false);
      setConverting(false);
    }
  };

  const handleDownloadZip = () => {
    if (!jobId) return;
    window.location.href = `/api/book/download/${jobId}/zip`;
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', textAlign: 'left', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ padding: '8px', background: 'rgba(99, 102, 241, 0.15)', color: '#A5B4FC', borderRadius: '10px', border: '1px solid rgba(99, 102, 241, 0.3)' }}>
            <BookOpen style={{ width: '24px', height: '24px' }} />
          </div>
          <div>
            <h1 style={{ fontSize: '1.8rem', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: '10px' }}>
              Book Converter
              <span className="panel-badge">
                Isolated Beta
              </span>
            </h1>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: 0 }}>Universal Academic Format Converter Engine</p>
          </div>
        </div>
        <button
          onClick={() => window.location.href = '/'}
          className="btn-secondary"
          style={{ fontSize: '0.85rem', padding: '8px 16px' }}
        >
          ← Back to Main App
        </button>
      </header>

      {/* Main Container */}
      <main style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        
        {/* Banner */}
        <div className="panel" style={{ background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(17, 24, 39, 0.9) 100%)', borderColor: 'rgba(99, 102, 241, 0.3)' }}>
          <h2 style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            Convert Academic Manuscript to Book Format
          </h2>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', lineHeight: '1.6', maxWidth: '800px' }}>
            Convert your academic manuscript into a book template while preserving your content and structure.
            Strictly enforces zero content rewriting, zero sample text leakage, and exact author metadata preservation.
          </p>
        </div>

        {/* Upload Panels */}
        <div className="studio-grid">
          
          {/* 1. Source Panel */}
          <div className="panel">
            <div className="panel-header">
              <div className="panel-title">
                <FileText style={{ width: '20px', height: '20px', color: 'var(--accent-primary)' }} />
                <span>1. Source Manuscript</span>
              </div>
              <span className="panel-badge">DOCX / ZIP</span>
            </div>

            <label className="dropzone" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
              <Upload className="dropzone-icon" />
              <span className="dropzone-title">
                {sourceFile ? sourceFile.name : "Select Manuscript File"}
              </span>
              <span className="dropzone-sub" style={{ marginTop: '4px' }}>
                {sourceFile ? `${(sourceFile.size / 1024 / 1024).toFixed(2)} MB` : "Supports .docx manuscript"}
              </span>
              <input type="file" accept=".docx,.zip" onChange={handleSourceUpload} style={{ display: 'none' }} />
            </label>
          </div>

          {/* 2. Destination Panel */}
          <div className="panel">
            <div className="panel-header">
              <div className="panel-title">
                <BookOpen style={{ width: '20px', height: '20px', color: 'var(--accent-primary)' }} />
                <span>2. Target Book Template</span>
              </div>
              <span className="panel-badge">LaTeX ZIP</span>
            </div>

            <label className="dropzone" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
              <Upload className="dropzone-icon" />
              <span className="dropzone-title">
                {destFile ? destFile.name : "Select Book Template ZIP"}
              </span>
              <span className="dropzone-sub" style={{ marginTop: '4px' }}>
                {destFile ? `${(destFile.size / 1024 / 1024).toFixed(2)} MB` : "LaTeX Book Project (.zip)"}
              </span>
              <input type="file" accept=".zip,.docx" onChange={handleDestUpload} style={{ display: 'none' }} />
            </label>
          </div>

        </div>

        {/* Options & Action */}
        <div className="panel" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <ShieldCheck style={{ width: '20px', height: '20px', color: 'var(--accent-success)', flexShrink: 0 }} />
            <div>
              <p style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-main)' }}>Mode: FORMAT ONLY (Default)</p>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Content is preserved without summarization or paraphrasing.</p>
            </div>
          </div>

          <button
            onClick={handleStartBookConversion}
            disabled={!sourceFile || !destFile || analyzing || converting}
            className="btn-primary"
            style={{ padding: '12px 28px' }}
          >
            {analyzing || converting ? (
              <>
                <RefreshCw style={{ width: '20px', height: '20px', animation: 'spin 1s linear infinite' }} />
                <span>{statusMessage || "Processing..."}</span>
              </>
            ) : (
              <>
                <span>Convert Book</span>
                <ArrowRight style={{ width: '20px', height: '20px' }} />
              </>
            )}
          </button>
        </div>

        {/* Error Message */}
        {errorMessage && (
          <div className="warning-box" style={{ background: 'rgba(239, 68, 68, 0.12)', borderColor: 'rgba(239, 68, 68, 0.3)', color: '#FCA5A5', display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
            <AlertCircle style={{ width: '20px', height: '20px', color: '#EF4444', flexShrink: 0, marginTop: '2px' }} />
            <div>
              <p style={{ fontWeight: 600, fontSize: '0.9rem' }}>Book Conversion Warning</p>
              <p style={{ fontSize: '0.825rem', marginTop: '4px', lineHeight: '1.5' }}>{errorMessage}</p>
            </div>
          </div>
        )}

        {/* Output & Download Card */}
        {report && (
          <div className="report-section">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #1E293B', paddingBottom: '16px', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <CheckCircle2 style={{ width: '28px', height: '28px', color: 'var(--accent-success)' }} />
                <div>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main)' }}>Book Conversion Complete</h3>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Generated target LaTeX book project ZIP</p>
                </div>
              </div>
              <button
                onClick={handleDownloadZip}
                className="btn-primary"
                style={{ background: 'linear-gradient(135deg, #10B981 0%, #059669 100%)', padding: '10px 24px' }}
              >
                <Download style={{ width: '18px', height: '18px' }} />
                Download Book ZIP
              </button>
            </div>

            {/* Validation Checklist */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <h4 style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Integrity Checks</h4>
              <ul style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontFamily: 'var(--font-mono)', fontSize: '0.8rem', listStyle: 'none' }}>
                {report.validation_checks?.checks?.map((chk: string, idx: number) => (
                  <li key={idx} style={{ color: chk.startsWith('[FAIL]') ? '#EF4444' : '#10B981' }}>
                    {chk}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

      </main>
    </div>
  );
};
