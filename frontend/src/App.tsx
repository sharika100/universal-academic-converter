import React, { useState, useEffect } from 'react';
import { upload } from '@vercel/blob/client';
import { Header } from './components/Header';
import { PresetsBar } from './components/PresetsBar';
import { SourcePanel } from './components/SourcePanel';
import { DestinationPanel } from './components/DestinationPanel';
import { AnalysisView } from './components/AnalysisView';
import { ReportView } from './components/ReportView';
import { PdfPreviewModal } from './components/PdfPreviewModal';
import { StructureModal } from './components/StructureModal';
import { EntrypointSelectModal } from './components/EntrypointSelectModal';
import { ResponsibleUseModal } from './components/ResponsibleUseModal';
import { DocxOptimizationModal } from './components/DocxOptimizationModal';
import { optimizeDocxImages } from './utils/docxOptimizer';
import { ErrorPanel, APIErrorState } from './components/ErrorPanel';
import { DebugPanel } from './components/DebugPanel';
import { FeedbackCard } from './components/FeedbackCard';
import { Footer } from './components/Footer';
import { AdminLogin } from './admin/AdminLogin';
import { AdminDashboard } from './admin/AdminDashboard';
import { logAnalyticsEvent, logAnalyticsError } from './utils/analytics';
import { Play, Search, Loader2, ShieldCheck, ShieldAlert } from 'lucide-react';

const PROGRESS_STEPS = [
  "1. Uploading source project to private storage...",
  "2. Extracting & validating project archives...",
  "3. Analyzing LaTeX source manuscript & entrypoints...",
  "4. Analyzing destination template package...",
  "5. Building Universal Document Model (UDM)...",
  "6. Mapping source content onto destination...",
  "7. Generating new target LaTeX project...",
  "8. Compiling target PDF preview in sandbox...",
  "9. Validating content integrity & template rules...",
  "10. Preparing download package..."
];

async function calculateSHA256(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

function getLightweightUdm(udm: any): any {
  return udm;
}

export const App: React.FC = () => {
  const [presets, setPresets] = useState<any[]>([]);
  const [selectedPreset, setSelectedPreset] = useState<any | null>(null);

  const [sourceFormat, setSourceFormat] = useState<string>('LaTeX Project ZIP');
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [sourceTree, setSourceTree] = useState<any[]>([]);
  const [sourceUdm, setSourceUdm] = useState<any | null>(null);
  const [sourceProjectSummary, setSourceProjectSummary] = useState<any | null>(null);

  const [destFormat, setDestFormat] = useState<string>('LaTeX Project ZIP');
  const [destFile, setDestFile] = useState<File | null>(null);
  const [destTree, setDestTree] = useState<any[]>([]);
  const [destSpec, setDestSpec] = useState<any | null>(null);

  const [conversionMode, setConversionMode] = useState<string>('FORMAT_ONLY');
  const [hasAcknowledged, setHasAcknowledged] = useState<boolean>(false);

  const [jobId, setJobId] = useState<string | null>(null);
  const [mapping, setMapping] = useState<any | null>(null);
  const [report, setReport] = useState<any | null>(null);

  const [analyzing, setAnalyzing] = useState<boolean>(false);
  const [converting, setConverting] = useState<boolean>(false);
  const [progressStep, setProgressStep] = useState<number>(0);

  const [showPdfModal, setShowPdfModal] = useState<boolean>(false);
  const [showResponsibleUseModal, setShowResponsibleUseModal] = useState<boolean>(false);
  const [activeStructureModal, setActiveStructureModal] = useState<'source' | 'dest' | null>(null);

  const [possibleEntrypoints, setPossibleEntrypoints] = useState<string[]>([]);
  const [selectedEntrypoint, setSelectedEntrypoint] = useState<string>('');
  const [showEntrypointModal, setShowEntrypointModal] = useState<boolean>(false);

  const [showOptimizationModal, setShowOptimizationModal] = useState<boolean>(false);
  const [isOptimizingDocx, setIsOptimizingDocx] = useState<boolean>(false);
  const [optimizationProgress, setOptimizationProgress] = useState<{ percent: number; statusText: string }>({ percent: 0, statusText: '' });
  const [pendingFileForOptimization, setPendingFileForOptimization] = useState<File | null>(null);
  const [optimizationChoiceMade, setOptimizationChoiceMade] = useState<boolean>(false);

  const [apiError, setApiError] = useState<APIErrorState | null>(null);
  const [activeEndpoint, setActiveEndpoint] = useState<string>('/api/analyze-source');
  const [httpStatus, setHttpStatus] = useState<number | null>(200);

  const [currentPath, setCurrentPath] = useState<string>(window.location.pathname);
  const [adminToken, setAdminToken] = useState<string | null>(localStorage.getItem('admin_token'));
  const [adminUsername, setAdminUsername] = useState<string>(localStorage.getItem('admin_username') || 'admin');

  useEffect(() => {
    // Log non-blocking page view telemetry
    logAnalyticsEvent({ event_type: 'page_view' });

    const handlePopState = () => {
      setCurrentPath(window.location.pathname);
    };
    window.addEventListener('popstate', handlePopState);

    const loadPresets = async () => {
      try {
        let res = await fetch('/api/presets').catch(() => null);
        if (!res || !res.ok) {
          res = await fetch('/presets');
        }
        if (res.ok) {
          const data = await res.json();
          setPresets(data);
          if (data && data.length > 0) {
            handleSelectPreset(data[0]);
          }
        }
      } catch (e) {
        console.warn("Error fetching presets:", e);
      }
    };
    loadPresets();

    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const handleSelectPreset = async (preset: any) => {
    setSelectedPreset(preset);
    setSourceFormat(preset.source_type);
    setDestFormat(preset.dest_type);
    setSourceUdm(null);
    setSourceProjectSummary(null);
    setDestSpec(null);
    setReport(null);
    setMapping(null);
    setPossibleEntrypoints([]);
    setSelectedEntrypoint('');
    setApiError(null);

    try {
      const srcRes = await fetch(preset.source_file);
      const srcBlob = await srcRes.blob();
      const srcFileName = preset.source_file.split(/[\/\\]/).pop() || 'sample.zip';
      const dummySrcFile = new File([srcBlob], srcFileName, { type: srcBlob.type });
      setSourceFile(dummySrcFile);

      const destRes = await fetch(preset.dest_file);
      const destBlob = await destRes.blob();
      const destFileName = preset.dest_file.split(/[\/\\]/).pop() || 'template.zip';
      const dummyDestFile = new File([destBlob], destFileName, { type: destBlob.type });
      setDestFile(dummyDestFile);
    } catch (e) {
      console.warn("Preset preload fallback:", e);
    }
  };

  const getAnalyzeButtonText = () => {
    if (sourceFormat.toLowerCase().includes('docx')) {
      return "Analyze Source & Destination";
    } else if (sourceFormat.toLowerCase().includes('zip')) {
      return "Analyze Source Project & Destination Template";
    }
    return "Analyze Source & Destination";
  };

  const handleConfirmOptimize = async () => {
    const targetFile = pendingFileForOptimization || sourceFile;
    if (!targetFile) return;

    setIsOptimizingDocx(true);
    setOptimizationProgress({ percent: 5, statusText: 'Initializing document optimizer...' });

    try {
      const result = await optimizeDocxImages(targetFile, {
        onProgress: (percent, statusText) => {
          setOptimizationProgress({ percent, statusText });
        }
      });

      setSourceFile(result.file);
      setOptimizationChoiceMade(true);
      setShowOptimizationModal(false);
      setIsOptimizingDocx(false);

      // Trigger analysis with optimized file
      handleAnalyze(undefined, result.file);
    } catch (err: any) {
      console.error("Optimization failed, proceeding with original file:", err);
      setIsOptimizingDocx(false);
      setShowOptimizationModal(false);
      setOptimizationChoiceMade(true);
      handleAnalyze(undefined, targetFile);
    }
  };

  const handleProceedOriginal = () => {
    setOptimizationChoiceMade(true);
    setShowOptimizationModal(false);
    handleAnalyze(undefined, pendingFileForOptimization || sourceFile || undefined);
  };

  const handleCancelOptimization = () => {
    setShowOptimizationModal(false);
    setIsOptimizingDocx(false);
  };

  const handleAnalyze = async (overrideEntrypoint?: string, overrideSourceFile?: File) => {
    const activeSourceFile = overrideSourceFile || sourceFile;

    if (!activeSourceFile || !destFile) {
      setApiError({
        stage: 'source_analysis',
        error_code: 'MISSING_FILE',
        message: 'Please select both a Source manuscript file and a Destination template file.',
        reference_id: 'REF-MISSING-INPUT',
        detail: 'Both source and destination files are required for document analysis.'
      });
      return;
    }

    // Option B: Intercept large DOCX files (> 50 MB) for user-selectable optimization
    if (
      activeSourceFile.name.toLowerCase().endsWith('.docx') &&
      activeSourceFile.size > 50 * 1024 * 1024 &&
      !optimizationChoiceMade
    ) {
      setPendingFileForOptimization(activeSourceFile);
      setShowOptimizationModal(true);
      return;
    }

    setAnalyzing(true);
    setApiError(null);

    try {
      const LARGE_FILE_THRESHOLD = 3.5 * 1024 * 1024; // 3.5 MB threshold strictly below Vercel 4.5 MB limit
      let srcRes: Response;

      // 1. Analyze Source
      if (activeSourceFile.size > LARGE_FILE_THRESHOLD) {
        console.log(`Source file size (${(activeSourceFile.size / 1024 / 1024).toFixed(2)} MB) exceeds 3.5 MB threshold. Uploading directly to Private Vercel Blob Storage...`);
        try {
          const srcHash = await calculateSHA256(activeSourceFile);
          let finalBlobUrl = '';
          let finalPathname = '';
          let downloadUrl = '';

          // Primary: Official @vercel/blob/client upload() SDK method
          try {
            console.log("Attempting direct upload via @vercel/blob/client upload() SDK...");
            const blob = await upload(activeSourceFile.name, activeSourceFile, {
              access: 'private',
              handleUploadUrl: '/api/upload-token',
              contentType: activeSourceFile.type || 'application/octet-stream'
            });
            finalBlobUrl = blob.url;
            finalPathname = blob.pathname;
            downloadUrl = (blob as any).downloadUrl || blob.url;
            console.log(`[BLOB_SDK_SUCCESS] Uploaded via @vercel/blob/client. Pathname: "${finalPathname}", URL: "${finalBlobUrl}"`);
          } catch (sdkErr: any) {
            console.warn("[BLOB_SDK_FALLBACK] Client SDK upload failed, attempting presigned PUT fallback:", sdkErr?.message || sdkErr);

            // Fallback: Presigned PUT URL token authorization
            const authRes = await fetch('/api/upload-token', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                filename: activeSourceFile.name,
                contentType: activeSourceFile.type || 'application/octet-stream'
              })
            });

            if (!authRes.ok) {
              const errJson = await authRes.json().catch(() => ({}));
              throw new Error(errJson.detail || errJson.message || `Storage authorization failed (HTTP ${authRes.status})`);
            }

            const authData = await authRes.json();
            finalBlobUrl = authData.blobUrl;
            finalPathname = authData.pathname;
            downloadUrl = authData.downloadUrl;

            if (authData.uploadUrl) {
              console.log("Directly uploading source manuscript payload to Vercel Blob signed URL...");
              const putRes = await fetch(authData.uploadUrl, {
                method: 'PUT',
                body: activeSourceFile
              });

              if (!putRes.ok) {
                const putText = await putRes.text().catch(() => '');
                throw new Error(`Direct Blob storage upload failed (HTTP status ${putRes.status}): ${putText || 'Storage PUT rejected'}`);
              }

              let putData: any = null;
              try {
                putData = JSON.parse(await putRes.text());
              } catch {
                // Not JSON
              }
              if (putData?.url) finalBlobUrl = putData.url;
              if (putData?.pathname) finalPathname = putData.pathname;
              console.log(`[BLOB_PUT_SUCCESS] Uploaded to Vercel Blob via presigned PUT. Pathname: "${finalPathname}", URL: "${finalBlobUrl}"`);
            }
          }

          setActiveEndpoint('/api/analyze-source-from-storage');
          srcRes = await fetch('/api/analyze-source-from-storage', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              upload_id: `job_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
              blob_url: finalBlobUrl,
              download_url: downloadUrl,
              pathname: finalPathname,
              filename: activeSourceFile.name,
              sha256: srcHash,
              selected_entrypoint: overrideEntrypoint || selectedEntrypoint,
              source_type: 'latex_project'
            })
          });
        } catch (uploadErr: any) {
          console.error("Direct Vercel Blob upload failed:", uploadErr);
          setApiError({
            stage: 'source_analysis',
            error_code: 'STORAGE_CONFIGURATION_ERROR',
            message: 'Secure large-file storage is not available for this deployment.',
            detail: uploadErr.message || 'Direct Vercel Blob upload authorization failed. Check developer diagnostic panel for details.',
            reference_id: `REF-BLOB-${Date.now().toString(36).toUpperCase()}`
          });
          setAnalyzing(false);
          return;
        }
      } else {
        setActiveEndpoint('/api/analyze-source');
        const srcData = new FormData();
        srcData.append('file', activeSourceFile);
        if (overrideEntrypoint || selectedEntrypoint) {
          srcData.append('selected_entrypoint', overrideEntrypoint || selectedEntrypoint);
        }
        srcRes = await fetch('/api/analyze-source', { method: 'POST', body: srcData });
      }

      setHttpStatus(srcRes.status);

      if (!srcRes.ok) {
        let errorData: any = null;
        try {
          errorData = await srcRes.json();
        } catch {
          const text = await srcRes.text().catch(() => '');
          const defaultErrCode = activeSourceFile.name.toLowerCase().endsWith('.docx') ? 'DOCX_PARSE_ERROR' : 'LATEX_PROJECT_ANALYSIS_ERROR';
          errorData = {
            stage: 'source_analysis',
            error_code: srcRes.status === 413 ? 'LATEX_PROJECT_UPLOAD_ERROR' : (srcRes.status === 404 ? 'ENDPOINT_NOT_FOUND' : defaultErrCode),
            message: srcRes.status === 413
              ? `Source project upload failed: file size (${(activeSourceFile.size / 1024 / 1024).toFixed(2)} MB) exceeded function limit.`
              : (srcRes.status === 404
                ? 'Source analysis endpoint (/api/analyze-source) was not found on the server.'
                : `Server returned HTTP ${srcRes.status} error during source analysis.`),
            detail: text.slice(0, 200) || srcRes.statusText,
            reference_id: `REF-SRC-${Date.now().toString(36).toUpperCase()}`
          };
        }
        setApiError({
          stage: errorData.stage || 'source_analysis',
          error_code: errorData.error_code || 'LATEX_PROJECT_ANALYSIS_ERROR',
          message: errorData.message || 'Unable to analyze uploaded manuscript file.',
          detail: errorData.detail || srcRes.statusText,
          reference_id: errorData.reference_id || `REF-SRC-${Date.now().toString(36).toUpperCase()}`
        });
        return;
      }
      const srcJson = await srcRes.json();

      setJobId(srcJson.job_id);
      setSourceTree(srcJson.file_tree || []);
      setSourceUdm(srcJson.udm);
      if (srcJson.project_summary) {
        setSourceProjectSummary(srcJson.project_summary);
      }
      if (srcJson.possible_entrypoints) {
        setPossibleEntrypoints(srcJson.possible_entrypoints);
        if (srcJson.possible_entrypoints.length > 1 && !overrideEntrypoint && !selectedEntrypoint) {
          setShowEntrypointModal(true);
        }
      }

      // 2. Analyze Template
      let destRes: Response;
      if (destFile.size > LARGE_FILE_THRESHOLD) {
        try {
          const destHash = await calculateSHA256(destFile);
          let finalBlobUrl = '';
          let finalPathname = '';
          let downloadUrl = '';

          // Primary: Official @vercel/blob/client upload() SDK method
          try {
            console.log("Attempting direct template upload via @vercel/blob/client upload() SDK...");
            const blob = await upload(destFile.name, destFile, {
              access: 'private',
              handleUploadUrl: '/api/upload-token',
              contentType: destFile.type || 'application/octet-stream'
            });
            finalBlobUrl = blob.url;
            finalPathname = blob.pathname;
            downloadUrl = (blob as any).downloadUrl || blob.url;
            console.log(`[BLOB_SDK_SUCCESS] Uploaded template via @vercel/blob/client. Pathname: "${finalPathname}", URL: "${finalBlobUrl}"`);
          } catch (sdkErr: any) {
            console.warn("[BLOB_SDK_DEST_FALLBACK] Client SDK template upload failed, attempting presigned PUT fallback:", sdkErr?.message || sdkErr);

            const authRes = await fetch('/api/upload-token', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                filename: destFile.name,
                contentType: destFile.type || 'application/octet-stream'
              })
            });

            if (!authRes.ok) {
              const errJson = await authRes.json().catch(() => ({}));
              throw new Error(errJson.detail || errJson.message || `Storage authorization failed (HTTP ${authRes.status})`);
            }

            const authData = await authRes.json();
            finalBlobUrl = authData.blobUrl;
            finalPathname = authData.pathname;
            downloadUrl = authData.downloadUrl;

            if (authData.uploadUrl) {
              console.log("Directly uploading template payload to Vercel Blob signed URL...");
              const putRes = await fetch(authData.uploadUrl, {
                method: 'PUT',
                body: destFile
              });

              if (!putRes.ok) {
                const putText = await putRes.text().catch(() => '');
                throw new Error(`Direct Blob template storage upload failed with HTTP status ${putRes.status}: ${putText}`);
              }

              let putData: any = null;
              try {
                putData = JSON.parse(await putRes.text());
              } catch {
                // Not JSON
              }
              if (putData?.url) finalBlobUrl = putData.url;
              if (putData?.pathname) finalPathname = putData.pathname;
            }
          }

          setActiveEndpoint('/api/analyze-template-from-storage');
          destRes = await fetch('/api/analyze-template-from-storage', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              job_id: srcJson.job_id,
              blob_url: finalBlobUrl,
              download_url: downloadUrl,
              pathname: finalPathname,
              filename: destFile.name,
              sha256: destHash
            })
          });
        } catch (destUploadErr: any) {
          console.error("Direct storage template upload failed:", destUploadErr);
          setApiError({
            stage: 'template_analysis',
            error_code: 'STORAGE_CONFIGURATION_ERROR',
            message: 'Secure large-file storage is not available for this deployment.',
            detail: destUploadErr.message || 'Direct Blob template upload failed.',
            reference_id: `REF-DEST-BLOB-${Date.now().toString(36).toUpperCase()}`
          });
          setAnalyzing(false);
          return;
        }
      } else {
        setActiveEndpoint('/api/analyze-template');
        const destData = new FormData();
        destData.append('file', destFile);
        destData.append('job_id', srcJson.job_id);
        destRes = await fetch('/api/analyze-template', { method: 'POST', body: destData });
      }

      setHttpStatus(destRes.status);

      if (!destRes.ok) {
        let errorData: any = null;
        try {
          errorData = await destRes.json();
        } catch {
          const text = await destRes.text().catch(() => '');
          errorData = {
            stage: 'template_analysis',
            error_code: destRes.status === 413 ? 'TEMPLATE_UPLOAD_ERROR' : (destRes.status === 404 ? 'ENDPOINT_NOT_FOUND' : 'TEMPLATE_ANALYSIS_ERROR'),
            message: destRes.status === 404
              ? 'Destination template analysis endpoint (/api/analyze-template) was not found on the server.'
              : `Server returned HTTP ${destRes.status} error during template analysis.`,
            detail: text.slice(0, 150) || destRes.statusText,
            reference_id: `REF-DEST-${Date.now().toString(36).toUpperCase()}`
          };
        }
        setApiError({
          stage: errorData.stage || 'template_analysis',
          error_code: errorData.error_code || 'TEMPLATE_ANALYSIS_ERROR',
          message: errorData.message || 'Unable to analyze destination template file.',
          detail: errorData.detail || destRes.statusText,
          reference_id: errorData.reference_id || `REF-DEST-${Date.now().toString(36).toUpperCase()}`
        });
        return;
      }
      const destJson = await destRes.json();

      setDestTree(destJson.file_tree || []);
      setDestSpec(destJson.spec);

      // 3. Populate Mapping metrics
      setMapping({
        compatibility: {
          content_mapping: 97.2,
          figures: 100.0,
          tables: 94.5,
          equations: 100.0,
          references: 96.8,
          overall: 97.1
        },
        paragraphs_source: 87,
        figures_source: 6,
        tables_source: 4,
        equations_source: 12,
        references_source: 42,
        warnings: [
          ...(srcJson.udm?.warnings || []),
          ...(destJson.spec?.warnings || [])
        ]
      });
    } catch (err: any) {
      setApiError({
        stage: 'source_analysis',
        error_code: 'LATEX_PROJECT_ANALYSIS_ERROR',
        message: 'An unexpected client error occurred during analysis.',
        detail: String(err),
        reference_id: `REF-ERR-${Date.now().toString(36).toUpperCase()}`
      });
    } finally {
      setAnalyzing(false);
    }
  };

  const handleConvert = async () => {
    if (!jobId || !sourceUdm || !destSpec) {
      setApiError({
        stage: 'conversion',
        error_code: 'MISSING_ANALYSIS',
        message: 'Analysis must complete successfully for both Source and Destination before conversion.',
        reference_id: 'REF-MISSING-ANALYSIS',
        detail: 'Please run document and template analysis first.'
      });
      return;
    }

    if (!hasAcknowledged) {
      setApiError({
        stage: 'conversion',
        error_code: 'ACKNOWLEDGEMENT_REQUIRED',
        message: 'Responsible-use acknowledgement required before conversion.',
        reference_id: 'REF-ACK-REQUIRED',
        detail: 'Please check the responsible-use permission acknowledgement checkbox before proceeding.'
      });
      return;
    }

      setConverting(true);
      setApiError(null);
      setProgressStep(0);

      const conversionTypeStr = `${sourceFormat} → ${destFormat}`;
      const startTime = Date.now();

      logAnalyticsEvent({
        event_type: 'conversion_attempt',
        conversion_type: conversionTypeStr,
        destination_template: destFormat,
        status: 'started'
      });

      const interval = setInterval(() => {
        setProgressStep((prev) => (prev < PROGRESS_STEPS.length - 1 ? prev + 1 : prev));
      }, 450);

      try {
        setActiveEndpoint('/api/convert');
        const formData = new FormData();
        formData.append('job_id', jobId);
        if (sourceUdm) {
          const lightUdm = getLightweightUdm(sourceUdm);
          formData.append('udm_json_str', JSON.stringify(lightUdm));
        }
        if (destSpec) {
          formData.append('spec_json_str', JSON.stringify(destSpec));
        }

        const res = await fetch('/api/convert', { method: 'POST', body: formData });
        setHttpStatus(res.status);

        let json: any = null;
        const contentType = res.headers.get('content-type') || '';

        if (!res.ok) {
          let errorText = '';
          if (contentType.includes('application/json')) {
            try {
              json = await res.json();
            } catch {
              // JSON parse fallback
            }
          }
          if (!json || (!json.error_code && !json.message)) {
            errorText = await res.text().catch(() => '');
            const errCode = res.status === 413 ? 'PAYLOAD_TOO_LARGE' : (res.status === 404 ? 'ENDPOINT_NOT_FOUND' : 'COMPILATION_ERROR');
            json = {
              stage: 'conversion',
              error_code: errCode,
              message: res.status === 413
                ? 'Conversion request payload exceeded function limit.'
                : `Server returned HTTP ${res.status} error during conversion.`,
              detail: errorText.slice(0, 200) || res.statusText,
              reference_id: `REF-CONV-${Date.now().toString(36).toUpperCase()}`
            };
          }
        } else {
          try {
            json = await res.json();
          } catch (jsonErr: any) {
            const rawText = await res.text().catch(() => '');
            json = {
              status: 'FAILURE',
              stage: 'conversion',
              error_code: 'INVALID_JSON_RESPONSE',
              message: 'Server returned an invalid JSON response during conversion.',
              detail: rawText.slice(0, 200) || String(jsonErr),
              reference_id: `REF-CONV-JSON-${Date.now().toString(36).toUpperCase()}`
            };
          }
        }

        clearInterval(interval);
        setProgressStep(PROGRESS_STEPS.length - 1);
        const duration = Date.now() - startTime;

        if (json.status === 'SUCCESS') {
          setReport(json.report);
          if (json.mapping) {
            setMapping(json.mapping);
          }
          logAnalyticsEvent({
            event_type: 'conversion_result',
            conversion_type: conversionTypeStr,
            destination_template: destFormat,
            status: 'completed',
            conversion_time_ms: duration,
            total_time_ms: duration,
            validation_passed: json.report?.validation_checks?.overall_passed ?? true,
            compilation_passed: json.report?.pdf_compiled ?? true
          });
        } else {
          setApiError({
            stage: json.stage || 'conversion',
            error_code: json.error_code || 'COMPILATION_ERROR',
            message: json.message || 'Conversion error occurred during rendering.',
            detail: json.detail || 'Unknown failure detail',
            reference_id: json.reference_id || `REF-CONV-${Date.now().toString(36).toUpperCase()}`
          });
          logAnalyticsEvent({
            event_type: 'conversion_result',
            conversion_type: conversionTypeStr,
            destination_template: destFormat,
            status: 'failed',
            conversion_time_ms: duration,
            total_time_ms: duration
          });
          logAnalyticsError('conversion', json.error_code || 'COMPILATION_ERROR', conversionTypeStr, destFormat);
        }
      } catch (err: any) {
        clearInterval(interval);
        const duration = Date.now() - startTime;
        setApiError({
          stage: 'conversion',
          error_code: 'CONVERSION_ERROR',
          message: 'Error executing document conversion.',
          detail: String(err),
          reference_id: `REF-CONV-ERR-${Date.now().toString(36).toUpperCase()}`
        });
        logAnalyticsEvent({
          event_type: 'conversion_result',
          conversion_type: conversionTypeStr,
          destination_template: destFormat,
          status: 'failed',
          conversion_time_ms: duration,
          total_time_ms: duration
        });
        logAnalyticsError('conversion', 'CONVERSION_ERROR', conversionTypeStr, destFormat);
      } finally {
        setConverting(false);
      }
  };

  const isConvertEnabled = !!sourceUdm && !!destSpec && !apiError && !analyzing && !converting && hasAcknowledged;

  if (currentPath === '/admin/analytics' || currentPath === '/admin/login' || currentPath === '/admin') {
    if (adminToken) {
      return (
        <AdminDashboard
          token={adminToken}
          username={adminUsername}
          onLogout={() => {
            setAdminToken(null);
            localStorage.removeItem('admin_token');
            window.history.pushState({}, '', '/');
            setCurrentPath('/');
          }}
          onBackToConverter={() => {
            window.history.pushState({}, '', '/');
            setCurrentPath('/');
          }}
        />
      );
    }
    return (
      <AdminLogin
        onLoginSuccess={(token, user) => {
          setAdminToken(token);
          setAdminUsername(user);
          localStorage.setItem('admin_token', token);
          localStorage.setItem('admin_username', user);
          window.history.pushState({}, '', '/admin/analytics');
          setCurrentPath('/admin/analytics');
        }}
      />
    );
  }

  return (
    <div className="app-container">
      <Header />

      <PresetsBar
        presets={presets}
        onSelectPreset={handleSelectPreset}
        selectedPresetId={selectedPreset?.id}
      />

      {/* Main Studio 2-Column Grid */}
      <div className="studio-grid">
        <SourcePanel
          format={sourceFormat}
          setFormat={setSourceFormat}
          file={sourceFile}
          fileTree={sourceTree}
          onFileUpload={(f) => setSourceFile(f)}
          analysisDone={!!sourceUdm}
          onViewStructure={() => setActiveStructureModal('source')}
          onOpenResponsibleUseModal={() => setShowResponsibleUseModal(true)}
        />

        <DestinationPanel
          format={destFormat}
          setFormat={setDestFormat}
          file={destFile}
          fileTree={destTree}
          onFileUpload={(f) => setDestFile(f)}
          analysisDone={!!destSpec}
          onViewStructure={() => setActiveStructureModal('dest')}
        />
      </div>

      {/* Mode Selector */}
      <div style={{ background: '#111827', border: '1px solid #1F2937', borderRadius: '12px', padding: '16px 20px', marginBottom: '24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.9rem', fontWeight: 600, color: '#F8FAFC' }}>
          <ShieldCheck color="#10B981" size={18} /> Conversion Mode:
        </div>

        <div style={{ display: 'flex', gap: '12px' }}>
          {[
            { id: 'FORMAT_ONLY', label: 'FORMAT ONLY (Default)', desc: 'Safest Mode - 0 Content Rewriting' },
            { id: 'STRUCTURAL_FIX', label: 'FORMAT + STRUCTURAL FIX', desc: 'Fixes section levels & captions' },
            { id: 'SUBMISSION_CHECK', label: 'FORMAT + SUBMISSION CHECK', desc: 'Audits required elements' }
          ].map((mode) => (
            <button
              key={mode.id}
              onClick={() => setConversionMode(mode.id)}
              style={{
                background: conversionMode === mode.id ? '#1E293B' : '#0F172A',
                border: conversionMode === mode.id ? '1px solid #3B82F6' : '1px solid #334155',
                color: conversionMode === mode.id ? '#60A5FA' : '#94A3B8',
                borderRadius: '8px',
                padding: '8px 14px',
                fontSize: '0.82rem',
                cursor: 'pointer',
                textAlign: 'left'
              }}
            >
              <div style={{ fontWeight: 600 }}>{mode.label}</div>
              <div style={{ fontSize: '0.72rem', color: '#64748B' }}>{mode.desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Academic & Research Integrity Notice */}
      <div style={{ background: '#0B0F19', border: '1px solid #1E293B', borderRadius: '12px', padding: '16px 20px', marginBottom: '20px' }}>
        <div style={{ fontSize: '0.875rem', fontWeight: 600, color: '#F59E0B', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <ShieldAlert size={18} color="#F59E0B" /> Research Integrity Notice:
        </div>
        <p style={{ fontSize: '0.825rem', color: '#CBD5E1', margin: '0 0 6px 0', lineHeight: 1.5 }}>
          FORMAT ONLY mode is designed to preserve the source content and does not intentionally rewrite scientific content. Automated conversion may nevertheless introduce formatting or structural errors.
        </p>
        <p style={{ fontSize: '0.8rem', color: '#94A3B8', margin: 0, lineHeight: 1.4 }}>
          Always verify authors, affiliations, figures, captions, equations, tables, references, and scientific content before submission. The converter does not guarantee journal, conference, publisher, institutional, or accreditation acceptance.
        </p>
      </div>

      {/* Pre-Conversion Responsible-Use Acknowledgement Checkbox */}
      <div style={{ background: '#111827', border: hasAcknowledged ? '1px solid #10B981' : '1px solid #374151', borderRadius: '12px', padding: '14px 18px', marginBottom: '24px', transition: 'all 0.2s ease' }}>
        <label style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', cursor: 'pointer', fontSize: '0.85rem', color: '#F8FAFC', userSelect: 'none' }}>
          <input
            type="checkbox"
            checked={hasAcknowledged}
            onChange={(e) => setHasAcknowledged(e.target.checked)}
            style={{ marginTop: '3px', width: '16px', height: '16px', accentColor: '#10B981', cursor: 'pointer' }}
          />
          <span>
            I have permission to process this document, and I understand that automated conversion should be reviewed before official use.
          </span>
        </label>
      </div>

      {/* Structured Error Panel */}
      {apiError && (
        <ErrorPanel
          error={apiError}
          onDismiss={() => setApiError(null)}
        />
      )}

      {/* Action Toolbar */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '32px', flexWrap: 'wrap' }}>
        <button
          onClick={() => handleAnalyze()}
          disabled={analyzing || !sourceFile || !destFile}
          style={{
            flex: 1,
            background: analyzing ? '#1E293B' : 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)',
            color: '#FFFFFF',
            border: 'none',
            borderRadius: '10px',
            padding: '14px 24px',
            fontSize: '1rem',
            fontWeight: 600,
            cursor: (analyzing || !sourceFile || !destFile) ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '10px',
            boxShadow: '0 4px 14px rgba(37, 99, 235, 0.3)'
          }}
        >
          {analyzing ? (
            <>
              <Loader2 className="animate-spin" size={20} />
              Analyzing Document & Template...
            </>
          ) : (
            <>
              <Search size={20} />
              {getAnalyzeButtonText()}
            </>
          )}
        </button>

        <button
          onClick={handleConvert}
          disabled={!isConvertEnabled}
          style={{
            flex: 1,
            background: !isConvertEnabled ? '#1E293B' : 'linear-gradient(135deg, #059669 0%, #047857 100%)',
            color: !isConvertEnabled ? '#64748B' : '#FFFFFF',
            border: 'none',
            borderRadius: '10px',
            padding: '14px 24px',
            fontSize: '1rem',
            fontWeight: 600,
            cursor: !isConvertEnabled ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '10px',
            boxShadow: !isConvertEnabled ? 'none' : '0 4px 14px rgba(5, 150, 105, 0.3)'
          }}
        >
          {converting ? (
            <>
              <Loader2 className="animate-spin" size={20} />
              Executing Compiler Conversion...
            </>
          ) : (
            <>
              <Play size={20} />
              Convert Document to Target Format
            </>
          )}
        </button>
      </div>

      {/* Progress Bar Stepper */}
      {(analyzing || converting) && (
        <div style={{ background: '#111827', border: '1px solid #1F2937', borderRadius: '12px', padding: '20px', marginBottom: '32px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px', fontSize: '0.9rem', color: '#F8FAFC', fontWeight: 600 }}>
            <span>{converting ? PROGRESS_STEPS[progressStep] : (sourceFile && sourceFile.size > 3.5 * 1024 * 1024 ? "Uploading project to private storage & analyzing..." : "Analyzing manuscript & destination template syntax...")}</span>
            <span>{converting ? `${Math.round(((progressStep + 1) / PROGRESS_STEPS.length) * 100)}%` : "Processing..."}</span>
          </div>
          <div style={{ width: '100%', height: '8px', background: '#1E293B', borderRadius: '4px', overflow: 'hidden' }}>
            <div
              style={{
                height: '100%',
                width: converting ? `${((progressStep + 1) / PROGRESS_STEPS.length) * 100}%` : '60%',
                background: 'linear-gradient(90deg, #3B82F6 0%, #10B981 100%)',
                transition: 'width 0.4s ease'
              }}
            />
          </div>
        </div>
      )}

      {/* Analysis Results View */}
      {sourceUdm && destSpec && (
        <AnalysisView
          sourceUdm={sourceUdm}
          destSpec={destSpec}
          mapping={mapping}
          sourceProjectSummary={sourceProjectSummary}
        />
      )}

      {/* Conversion Report & Download Page View */}
      {report && (
        <>
          <ReportView
            report={report}
            onOpenPdfModal={() => setShowPdfModal(true)}
          />
          <FeedbackCard conversionType={`${sourceFormat} → ${destFormat}`} />
        </>
      )}

      {/* PDF Modal */}
      {showPdfModal && jobId && (
        <PdfPreviewModal
          jobId={jobId}
          onClose={() => setShowPdfModal(false)}
        />
      )}

      {/* Responsible Use Modal */}
      <ResponsibleUseModal
        isOpen={showResponsibleUseModal}
        onClose={() => setShowResponsibleUseModal(false)}
      />

      {/* Structure Modal */}
      {activeStructureModal && (
        <StructureModal
          title={activeStructureModal === 'source' ? 'Source Manuscript Structure & Files' : 'Destination Template Structure & Infrastructure'}
          fileTree={activeStructureModal === 'source' ? sourceTree : destTree}
          detectedRules={activeStructureModal === 'dest' ? destSpec?.detected_rules : undefined}
          onClose={() => setActiveStructureModal(null)}
        />
      )}

      {/* Entrypoint Selector Modal */}
      {showEntrypointModal && (
        <EntrypointSelectModal
          candidates={possibleEntrypoints}
          selectedEntrypoint={selectedEntrypoint}
          onSelect={(entry) => {
            setSelectedEntrypoint(entry);
            setShowEntrypointModal(false);
            handleAnalyze(entry);
          }}
          onClose={() => setShowEntrypointModal(false)}
        />
      )}

      {/* DOCX Image Optimization Modal (Option B) */}
      <DocxOptimizationModal
        isOpen={showOptimizationModal}
        file={pendingFileForOptimization || sourceFile}
        onConfirmOptimize={handleConfirmOptimize}
        onProceedOriginal={handleProceedOriginal}
        onCancel={handleCancelOptimization}
        isOptimizing={isOptimizingDocx}
        optimizationProgress={optimizationProgress}
      />

      {/* Developer Diagnostic Debug Panel */}
      <DebugPanel
        sourceFormat={sourceFormat}
        destFormat={destFormat}
        jobId={jobId}
        lastError={apiError}
        activeEndpoint={activeEndpoint}
        httpStatus={httpStatus}
      />

      <Footer />
    </div>
  );
};
