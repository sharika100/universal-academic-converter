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
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-600/20 text-indigo-400 rounded-lg border border-indigo-500/30">
              <BookOpen className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                Book Converter
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-mono">
                  Isolated Beta
                </span>
              </h1>
              <p className="text-xs text-slate-400">Universal Academic Format Converter Engine</p>
            </div>
          </div>
          <button
            onClick={() => window.location.href = '/'}
            className="text-xs text-slate-400 hover:text-white transition-colors"
          >
            ← Back to Main App
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-5xl mx-auto w-full px-6 py-10 space-y-8">
        
        {/* Banner */}
        <div className="p-6 rounded-2xl bg-gradient-to-r from-indigo-950/60 via-slate-900 to-slate-950 border border-indigo-500/20 space-y-2">
          <h2 className="text-2xl font-bold text-white flex items-center gap-3">
            Convert Academic Manuscript to Book Format
          </h2>
          <p className="text-sm text-slate-300 leading-relaxed max-w-3xl">
            Convert your academic manuscript into a book template while preserving your content and structure.
            Strictly enforces zero content rewriting, zero sample text leakage, and exact author metadata preservation.
          </p>
        </div>

        {/* Upload Panels */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          
          {/* 1. Source Panel */}
          <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                <FileText className="w-5 h-5 text-indigo-400" />
                1. Source Manuscript
              </h3>
              <span className="text-xs text-slate-400 font-mono">DOCX / ZIP</span>
            </div>

            <label className="flex flex-col items-center justify-center p-8 rounded-xl border-2 border-dashed border-slate-700 hover:border-indigo-500/50 bg-slate-950/50 cursor-pointer transition-colors group">
              <Upload className="w-8 h-8 text-slate-400 group-hover:text-indigo-400 transition-colors mb-2" />
              <span className="text-sm font-medium text-slate-200">
                {sourceFile ? sourceFile.name : "Select Manuscript File"}
              </span>
              <span className="text-xs text-slate-500 mt-1">
                {sourceFile ? `${(sourceFile.size / 1024 / 1024).toFixed(2)} MB` : "Supports .docx manuscript"}
              </span>
              <input type="file" accept=".docx,.zip" onChange={handleSourceUpload} className="hidden" />
            </label>
          </div>

          {/* 2. Destination Panel */}
          <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                <BookOpen className="w-5 h-5 text-indigo-400" />
                2. Target Book Template
              </h3>
              <span className="text-xs text-slate-400 font-mono">LaTeX ZIP</span>
            </div>

            <label className="flex flex-col items-center justify-center p-8 rounded-xl border-2 border-dashed border-slate-700 hover:border-indigo-500/50 bg-slate-950/50 cursor-pointer transition-colors group">
              <Upload className="w-8 h-8 text-slate-400 group-hover:text-indigo-400 transition-colors mb-2" />
              <span className="text-sm font-medium text-slate-200">
                {destFile ? destFile.name : "Select Book Template ZIP"}
              </span>
              <span className="text-xs text-slate-500 mt-1">
                {destFile ? `${(destFile.size / 1024 / 1024).toFixed(2)} MB` : "LaTeX Book Project (.zip)"}
              </span>
              <input type="file" accept=".zip,.docx" onChange={handleDestUpload} className="hidden" />
            </label>
          </div>

        </div>

        {/* Options & Action */}
        <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <ShieldCheck className="w-5 h-5 text-emerald-400 flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-slate-200">Mode: FORMAT ONLY (Default)</p>
              <p className="text-xs text-slate-400">Content is preserved without summarization or paraphrasing.</p>
            </div>
          </div>

          <button
            onClick={handleStartBookConversion}
            disabled={!sourceFile || !destFile || analyzing || converting}
            className="w-full md:w-auto px-8 py-3.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/30 transition-all"
          >
            {analyzing || converting ? (
              <>
                <RefreshCw className="w-5 h-5 animate-spin" />
                <span>{statusMessage || "Processing..."}</span>
              </>
            ) : (
              <>
                <span>Convert Book</span>
                <ArrowRight className="w-5 h-5" />
              </>
            )}
          </button>
        </div>

        {/* Error Message */}
        {errorMessage && (
          <div className="p-5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold">Book Conversion Warning</p>
              <p className="text-xs mt-1 leading-relaxed text-rose-200">{errorMessage}</p>
            </div>
          </div>
        )}

        {/* Output & Download Card */}
        {report && (
          <div className="p-8 rounded-2xl bg-slate-900 border border-emerald-500/30 space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="w-7 h-7 text-emerald-400" />
                <div>
                  <h3 className="text-lg font-bold text-white">Book Conversion Complete</h3>
                  <p className="text-xs text-slate-400">Generated target LaTeX book project ZIP</p>
                </div>
              </div>
              <button
                onClick={handleDownloadZip}
                className="px-6 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold flex items-center gap-2 shadow-lg shadow-emerald-600/20 transition-all"
              >
                <Download className="w-5 h-5" />
                Download Book ZIP
              </button>
            </div>

            {/* Validation Checklist */}
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Integrity Checks</h4>
              <ul className="space-y-1 text-xs font-mono">
                {report.validation_checks?.checks?.map((chk: string, idx: number) => (
                  <li key={idx} className={chk.startsWith('[FAIL]') ? 'text-rose-400' : 'text-emerald-400'}>
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
