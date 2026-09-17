import os
import uuid
import shutil
import tempfile
import zipfile
import logging
import hashlib
import traceback
import requests
import urllib.parse
from typing import Optional, Dict, Any
from pydantic import BaseModel
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.models.udm import UniversalDocumentModel
from app.models.template_spec import TemplateSpecification
from app.models.report import ConversionReport, CountComparison
from app.models.error_response import create_error_payload
from app.security.zip_guard import ZipGuard
from app.parsers.zip_utils import build_directory_tree, find_latex_entrypoint, summarize_latex_project
from app.parsers.docx_parser import DocxParser
from app.parsers.latex_parser import LatexParser
from app.template_engine.analyzer import TemplateAnalyzer
from app.mappers.mapping_engine import MappingEngine
from app.renderers.docx_renderer import DocxRenderer
from app.renderers.latex_renderer import LatexRenderer
from app.validation.integrity_checker import IntegrityChecker
from app.validation.template_validator import TemplateValidator
from app.compilation.latex_sandbox import LatexSandbox
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("UniversalConverter")

import starlette.formparsers
from starlette.requests import Request

MAX_PART_SIZE = 50 * 1024 * 1024  # 50 MB max per part / form field

if hasattr(starlette.formparsers.MultiPartParser.__init__, "__kwdefaults__") and starlette.formparsers.MultiPartParser.__init__.__kwdefaults__:
    starlette.formparsers.MultiPartParser.__init__.__kwdefaults__["max_part_size"] = MAX_PART_SIZE
if hasattr(Request.form, "__kwdefaults__") and Request.form.__kwdefaults__:
    Request.form.__kwdefaults__["max_part_size"] = MAX_PART_SIZE
if hasattr(Request._get_form, "__kwdefaults__") and Request._get_form.__kwdefaults__:
    Request._get_form.__kwdefaults__["max_part_size"] = MAX_PART_SIZE

app = FastAPI(title="Universal Academic Format Converter API")

try:
    from app.api.analytics import router as analytics_router
    app.include_router(analytics_router)
    logger.info("Analytics router successfully mounted.")
except Exception as analytics_err:
    logger.error(f"Failed to mount analytics router: {analytics_err}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_blob_read_write_token() -> Optional[str]:
    token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if token:
        return token
    for k, v in os.environ.items():
        if (k.endswith("_READ_WRITE_TOKEN") or "BLOB" in k) and isinstance(v, str) and v.startswith("vercel_blob_"):
            return v
    return None

def trigger_blob_cleanup(blob_url: Optional[str], pathname: Optional[str] = None):
    """Triggers immediate deletion of the temporary processing Blob from Vercel Blob storage."""
    if not blob_url and not pathname:
        return
    try:
        host_url = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL") or os.environ.get("VERCEL_URL")
        if host_url:
            if not host_url.startswith("http"):
                host_url = f"https://{host_url}"
            delete_endpoint = f"{host_url}/api/blob-delete"
        else:
            delete_endpoint = "http://127.0.0.1:3000/api/blob-delete"

        token = get_blob_read_write_token()
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            headers["x-internal-delete-key"] = token[-16:]

        requests.post(
            delete_endpoint,
            json={"url": blob_url, "pathname": pathname},
            headers=headers,
            timeout=10
        )
        logger.info(f"[TEMPORARY_BLOB_DELETED] Triggered deletion for temporary Blob (pathname: '{pathname or blob_url}')")
    except Exception as del_err:
        logger.warning(f"[TEMPORARY_BLOB_CLEANUP_WARNING] Failed to trigger Blob deletion: {del_err}")

@app.middleware("http")
async def normalize_vercel_path(request, call_next):
    raw_path = request.scope.get("path", "")
    for prefix in ["/backend/app/main.py", "/backend/app/main", "/api/index.py", "/api/index", "/index.py"]:
        if raw_path.startswith(prefix):
            clean_path = raw_path[len(prefix):]
            request.scope["path"] = clean_path if clean_path else "/"
            break
    return await call_next(request)

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc):
    path = request.scope.get("path", "")
    if path.startswith("/api/") and not (path.startswith("/api/index.py") or path.startswith("/api/index")):
        return JSONResponse(status_code=404, content={"detail": f"API endpoint not found: {path}"})
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse(content=INLINE_INDEX_HTML, media_type="text/html")

TEMP_STORAGE = os.path.join(tempfile.gettempdir(), "universal_converter_storage")
os.makedirs(TEMP_STORAGE, exist_ok=True)

# Locate samples directory robustly across local and Vercel serverless environments
SAMPLES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "samples"))
if not os.path.exists(SAMPLES_DIR):
    SAMPLES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "samples"))
if not os.path.exists(SAMPLES_DIR):
    SAMPLES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "samples"))

STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))
if not os.path.exists(STATIC_DIR):
    STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))

if os.path.exists(STATIC_DIR) and os.path.exists(os.path.join(STATIC_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

if os.path.exists(SAMPLES_DIR):
    app.mount("/samples", StaticFiles(directory=SAMPLES_DIR), name="samples")

INLINE_INDEX_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Universal Academic Format Converter</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <script type="module" crossorigin src="/assets/index-By2ihgcc.js"></script>
    <link rel="stylesheet" crossorigin href="/assets/index-CuU9JyVg.css">
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>"""



class StorageAnalysisRequest(BaseModel):
    upload_id: str
    blob_url: str
    download_url: Optional[str] = None
    pathname: Optional[str] = None
    filename: Optional[str] = None
    sha256: Optional[str] = None
    selected_entrypoint: Optional[str] = None
    source_type: Optional[str] = "latex_project"

class TemplateStorageAnalysisRequest(BaseModel):
    job_id: str
    upload_id: Optional[str] = None
    blob_url: str
    download_url: Optional[str] = None
    pathname: Optional[str] = None
    filename: Optional[str] = None
    sha256: Optional[str] = None

class ConversionStorageRequest(BaseModel):
    job_id: str
    blob_url: str
    download_url: Optional[str] = None
    pathname: Optional[str] = None
    filename: Optional[str] = None
    sha256: Optional[str] = None


@app.get("/api/health")
@app.get("/health")
def health_check():
    """Health check endpoint to verify backend API reachability."""
    blob_token_present = get_blob_read_write_token() is not None
    return {
        "status": "ok",
        "service": "universal-academic-converter",
        "environment": "production",
        "blob_storage_enabled": blob_token_present
    }

@app.get("/api/presets")
@app.get("/presets")
def get_presets():
    """Returns pre-loaded sample workflow packages."""
    return [
        {
            "id": "ieee_to_springer",
            "name": "IEEE Conference (LaTeX ZIP) → Springer Journal (LaTeX ZIP)",
            "source_type": "LaTeX Project ZIP",
            "dest_type": "LaTeX Project ZIP",
            "source_file": "/samples/ieee_paper.zip",
            "dest_file": "/samples/springer_template.zip",
            "description": "Converts IEEE 2-column conference manuscript with bibtex & figures to Springer Nature journal format."
        },
        {
            "id": "docx_to_docx",
            "name": "DOCX Manuscript → DOCX Publisher Template",
            "source_type": "DOCX",
            "dest_type": "DOCX",
            "source_file": "/samples/sample_manuscript.docx",
            "dest_file": "/samples/sample_manuscript.docx",
            "description": "Converts DOCX manuscript into custom publisher Word template while preserving styles and data."
        },
        {
            "id": "docx_to_latex",
            "name": "DOCX Manuscript → Springer LaTeX Project ZIP",
            "source_type": "DOCX",
            "dest_type": "LaTeX Project ZIP",
            "source_file": "/samples/sample_manuscript.docx",
            "dest_file": "/samples/springer_template.zip",
            "description": "Compiles Word DOCX manuscript directly into a complete LaTeX project ZIP."
        }
    ]

@app.post("/api/analyze-source")
@app.post("/analyze-source")
async def analyze_source(
    file: UploadFile = File(...),
    selected_entrypoint: Optional[str] = Form(None)
):
    job_id = str(uuid.uuid4())
    ref_id = f"REF-{job_id[:8].upper()}"
    job_dir = os.path.join(TEMP_STORAGE, job_id, "source")
    os.makedirs(job_dir, exist_ok=True)
    
    clean_filename = os.path.basename(file.filename) if file.filename else "manuscript.docx"
    file_path = os.path.join(job_dir, clean_filename)
    
    content = await file.read()
    if not content or len(content) == 0:
        return JSONResponse(status_code=400, content=create_error_payload(
            stage="source_analysis",
            error_code="UNSUPPORTED_FORMAT",
            message="Uploaded manuscript file is empty (0 bytes).",
            detail=f"The uploaded file '{clean_filename}' contained zero bytes.",
            ref_id=ref_id
        ))
        
    with open(file_path, "wb") as buffer:
        buffer.write(content)
        
    tree = []
    warnings = []
    candidates = []
    project_summary = {}
    lower_filename = clean_filename.lower()
    
    logger.info(f"[{ref_id}] [UPLOAD_INITIATED] Direct multipart source upload for file: {clean_filename} ({len(content)} bytes)")
    
    try:
        if lower_filename.endswith(".zip"):
            if not zipfile.is_zipfile(file_path):
                return JSONResponse(status_code=400, content=create_error_payload(
                    stage="source_analysis",
                    error_code="ZIP_EXTRACT_ERROR",
                    message="Uploaded manuscript file is not a valid ZIP archive.",
                    detail=f"The file '{clean_filename}' failed ZIP header validation.",
                    ref_id=ref_id
                ))
            extract_dir = os.path.join(job_dir, "extracted")
            rel_files, zip_warns = ZipGuard.inspect_and_extract_safe(file_path, extract_dir)
            warnings.extend(zip_warns)
            tree = build_directory_tree(extract_dir)
            project_summary = summarize_latex_project(extract_dir)
            _, candidates, all_tex = find_latex_entrypoint(extract_dir)
            if all_tex:
                logger.info(f"[{ref_id}] [SOURCE_PROJECT_ANALYSIS_STARTED] Analyzing LaTeX project ZIP: {clean_filename}")
                udm = LatexParser.parse_project(extract_dir, selected_entrypoint=selected_entrypoint)
                logger.info(f"[{ref_id}] [SOURCE_PROJECT_ANALYSIS_COMPLETED] LaTeX project analysis completed for: {clean_filename}")
            else:
                docx_files = [os.path.join(root, f) for root, _, files in os.walk(extract_dir) for f in files if f.lower().endswith(".docx")]
                if docx_files:
                    udm = DocxParser.parse(docx_files[0])
                    udm.source_format = "DOCX (ZIP Archive)"
                else:
                    return JSONResponse(status_code=400, content=create_error_payload(
                        stage="source_analysis",
                        error_code="UNSUPPORTED_FORMAT",
                        message="No valid .tex or .docx manuscript files found in uploaded ZIP archive.",
                        detail="The ZIP archive did not contain any parseable .tex or .docx document files.",
                        ref_id=ref_id
                    ))
        elif lower_filename.endswith(".docx"):
            tree = [{"path": clean_filename, "name": clean_filename, "type": "docx", "size": os.path.getsize(file_path)}]
            udm = DocxParser.parse(file_path)
        elif lower_filename.endswith(".tex"):
            tree = [{"path": clean_filename, "name": clean_filename, "type": "code", "size": os.path.getsize(file_path)}]
            with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                single_tex_content = fh.read()
            udm = UniversalDocumentModel(source_format="LaTeX File")
            udm.metadata = LatexParser._parse_metadata(single_tex_content)
            sections, parsed_warns = LatexParser._parse_body(single_tex_content, os.path.dirname(file_path))
            udm.sections = sections
            udm.warnings.extend(parsed_warns)
        else:
            try:
                udm = DocxParser.parse(file_path)
                tree = [{"path": clean_filename, "name": clean_filename, "type": "docx", "size": os.path.getsize(file_path)}]
            except Exception:
                tree = [{"path": clean_filename, "name": clean_filename, "type": "code", "size": os.path.getsize(file_path)}]
                with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                    single_tex_content = fh.read()
                udm = UniversalDocumentModel(source_format="Manuscript File")
                udm.metadata = LatexParser._parse_metadata(single_tex_content)
                sections, parsed_warns = LatexParser._parse_body(single_tex_content, os.path.dirname(file_path))
                udm.sections = sections
                udm.warnings.extend(parsed_warns)
    except Exception as e:
        tb_str = traceback.format_exc()
        logger.error(f"[{ref_id}] Source analysis exception: {str(e)}\n{tb_str}")
        err_code = "DOCX_PARSE_ERROR" if lower_filename.endswith(".docx") else "LATEX_PROJECT_ANALYSIS_ERROR"
        return JSONResponse(status_code=400, content=create_error_payload(
            stage="source_analysis",
            error_code=err_code,
            message=f"Unable to parse uploaded manuscript ({clean_filename}).",
            detail=f"{str(e)} | Traceback: {tb_str[:250]}",
            ref_id=ref_id
        ))
        
    udm.warnings.extend(warnings)
    
    udm_json_path = os.path.join(TEMP_STORAGE, job_id, "udm.json")
    with open(udm_json_path, "w", encoding="utf-8") as fh:
        fh.write(udm.model_dump_json())
        
    return {
        "success": True,
        "job_id": job_id,
        "reference_id": ref_id,
        "filename": clean_filename,
        "format": udm.source_format,
        "confidence": udm.parsing_confidence,
        "file_tree": tree,
        "possible_entrypoints": candidates,
        "selected_entrypoint": selected_entrypoint or (candidates[0] if candidates else None),
        "project_summary": project_summary,
        "udm": udm.model_dump()
    }

@app.post("/api/analyze-source-from-storage")
@app.post("/analyze-source-from-storage")
async def analyze_source_from_storage(req: StorageAnalysisRequest):
    job_id = req.upload_id if req.upload_id else str(uuid.uuid4())
    ref_id = f"REF-{job_id[:8].upper()}"
    job_dir = os.path.join(TEMP_STORAGE, job_id, "source")
    os.makedirs(job_dir, exist_ok=True)
    
    clean_filename = os.path.basename(req.filename) if req.filename else "manuscript.zip"
    file_path = os.path.join(job_dir, clean_filename)
    
    logger.info(f"[{ref_id}] [UPLOAD_INITIATED] Storage analysis requested for job: {job_id}")
    logger.info(f"[{ref_id}] [SOURCE_REFERENCE_RECEIVED] Received Blob reference for file '{clean_filename}'")

    # 1. SSRF Check: Validate URL origin
    url_lower = req.blob_url.lower()
    is_valid_url = url_lower.startswith("https://") or url_lower.startswith("http://127.0.0.1") or url_lower.startswith("http://localhost") or os.path.exists(req.blob_url)
    if not is_valid_url:
        return JSONResponse(status_code=400, content=create_error_payload(
            stage="source_analysis",
            error_code="STORAGE_SECURITY_ERROR",
            message="Invalid or untrusted storage URL requested.",
            detail="Storage URL must originate from a secure HTTPS or Vercel Blob endpoint.",
            ref_id=ref_id
        ))
        
    # 2. Retrieve file content using signed download URL or server token, then ALWAYS delete temporary Blob
    content = None
    try:
        if os.path.exists(req.blob_url):
            with open(req.blob_url, "rb") as fh:
                content = fh.read()
        else:
            headers = {}
            token = get_blob_read_write_token()
            if token and not req.download_url:
                headers["Authorization"] = f"Bearer {token}"
            
            fetch_url = req.download_url if req.download_url else req.blob_url
            logger.info(f"[{ref_id}] [BLOB_RETRIEVAL_ATTEMPTED] Fetching from storage (pathname: '{req.pathname or clean_filename}')")
            
            resp = requests.get(fetch_url, headers=headers, timeout=60)
            if resp.status_code in (401, 403, 404):
                logger.info(f"[{ref_id}] Primary storage fetch got status {resp.status_code}. Attempting Node Blob helper (/api/blob-download)...")
                try:
                    host_url = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL") or os.environ.get("VERCEL_URL")
                    if host_url:
                        if not host_url.startswith("http"):
                            host_url = f"https://{host_url}"
                        helper_url = f"{host_url}/api/blob-download?url={urllib.parse.quote(req.blob_url, safe='')}"
                    else:
                        helper_url = f"http://127.0.0.1:3000/api/blob-download?url={urllib.parse.quote(req.blob_url, safe='')}"
                    
                    resp_helper = requests.get(helper_url, timeout=60)
                    if resp_helper.status_code == 200 and len(resp_helper.content) > 0:
                        resp = resp_helper
                        logger.info(f"[{ref_id}] [BLOB_RETRIEVAL_RESULT] Node Blob helper retrieved {len(resp.content)} bytes")
                except Exception as helper_err:
                    logger.warning(f"[{ref_id}] Node Blob helper request failed: {helper_err}")
            
            if resp.status_code != 200:
                logger.error(f"[{ref_id}] [BLOB_RETRIEVAL_RESULT] Storage retrieval failed with status {resp.status_code}")
                return JSONResponse(status_code=400, content=create_error_payload(
                    stage="source_analysis",
                    error_code="STORAGE_OBJECT_NOT_FOUND",
                    message="Uploaded project could not be retrieved from secure storage. Please retry the upload.",
                    detail=f"Storage request returned status code {resp.status_code} for pathname '{req.pathname or clean_filename}'.",
                    ref_id=ref_id
                ))
            content = resp.content
            logger.info(f"[{ref_id}] [SOURCE_BLOB_RETRIEVED] Retrieved Blob payload from storage ({len(content)} bytes)")
    except Exception as e:
        return JSONResponse(status_code=400, content=create_error_payload(
            stage="source_analysis",
            error_code="LATEX_PROJECT_UPLOAD_ERROR",
            message="Failed to download file from Blob storage.",
            detail=str(e),
            ref_id=ref_id
        ))
    finally:
        # MANDATORY TEMPORARY BLOB CLEANUP: Delete temporary staging Blob immediately after retrieval (or on failure)
        trigger_blob_cleanup(req.blob_url, req.pathname)

    if not content or len(content) == 0:
        return JSONResponse(status_code=400, content=create_error_payload(
            stage="source_analysis",
            error_code="UNSUPPORTED_FORMAT",
            message="Retrieved storage file is empty (0 bytes).",
            detail=f"The file '{clean_filename}' contained zero bytes.",
            ref_id=ref_id
        ))

    # 3. Server-side SHA-256 Hash Verification
    downloaded_hash = hashlib.sha256(content).hexdigest()
    if req.sha256 and downloaded_hash.lower() != req.sha256.lower():
        logger.error(f"[{ref_id}] Hash mismatch! Expected {req.sha256}, got {downloaded_hash}")
        return JSONResponse(status_code=400, content=create_error_payload(
            stage="source_analysis",
            error_code="UPLOAD_INTEGRITY_ERROR",
            message="SHA-256 hash mismatch detected for uploaded file.",
            detail=f"Expected SHA-256: {req.sha256}, Computed SHA-256: {downloaded_hash}",
            ref_id=ref_id
        ))
    logger.info(f"[{ref_id}] [SOURCE_HASH_VERIFIED] SHA-256 integrity hash verified: {downloaded_hash}")

    with open(file_path, "wb") as buffer:
        buffer.write(content)

    tree = []
    warnings = []
    candidates = []
    project_summary = {}
    lower_filename = clean_filename.lower()
    
    try:
        if lower_filename.endswith(".zip"):
            if not zipfile.is_zipfile(file_path):
                return JSONResponse(status_code=400, content=create_error_payload(
                    stage="source_analysis",
                    error_code="ZIP_EXTRACT_ERROR",
                    message="Uploaded manuscript file is not a valid ZIP archive.",
                    detail=f"The file '{clean_filename}' failed ZIP header validation.",
                    ref_id=ref_id
                ))
            extract_dir = os.path.join(job_dir, "extracted")
            rel_files, zip_warns = ZipGuard.inspect_and_extract_safe(file_path, extract_dir)
            warnings.extend(zip_warns)
            tree = build_directory_tree(extract_dir)
            project_summary = summarize_latex_project(extract_dir)
            _, candidates, all_tex = find_latex_entrypoint(extract_dir)
            if all_tex:
                logger.info(f"[{ref_id}] [SOURCE_PROJECT_ANALYSIS_STARTED] Parsing retrieved LaTeX project ZIP: {clean_filename}")
                udm = LatexParser.parse_project(extract_dir, selected_entrypoint=req.selected_entrypoint)
                logger.info(f"[{ref_id}] [SOURCE_PROJECT_ANALYSIS_COMPLETED] LaTeX project analysis completed for: {clean_filename}")
            else:
                docx_files = [os.path.join(root, f) for root, _, files in os.walk(extract_dir) for f in files if f.lower().endswith(".docx")]
                if docx_files:
                    udm = DocxParser.parse(docx_files[0])
                    udm.source_format = "DOCX (ZIP Archive)"
                else:
                    return JSONResponse(status_code=400, content=create_error_payload(
                        stage="source_analysis",
                        error_code="UNSUPPORTED_FORMAT",
                        message="No valid .tex or .docx manuscript files found in uploaded ZIP archive.",
                        detail="The ZIP archive did not contain any parseable .tex or .docx document files.",
                        ref_id=ref_id
                    ))
        elif lower_filename.endswith(".docx"):
            tree = [{"path": clean_filename, "name": clean_filename, "type": "docx", "size": os.path.getsize(file_path)}]
            udm = DocxParser.parse(file_path)
        elif lower_filename.endswith(".tex"):
            tree = [{"path": clean_filename, "name": clean_filename, "type": "code", "size": os.path.getsize(file_path)}]
            with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                single_tex_content = fh.read()
            udm = UniversalDocumentModel(source_format="LaTeX File")
            udm.metadata = LatexParser._parse_metadata(single_tex_content)
            sections, parsed_warns = LatexParser._parse_body(single_tex_content, os.path.dirname(file_path))
            udm.sections = sections
            udm.warnings.extend(parsed_warns)
        else:
            try:
                udm = DocxParser.parse(file_path)
                tree = [{"path": clean_filename, "name": clean_filename, "type": "docx", "size": os.path.getsize(file_path)}]
            except Exception:
                tree = [{"path": clean_filename, "name": clean_filename, "type": "code", "size": os.path.getsize(file_path)}]
                with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                    single_tex_content = fh.read()
                udm = UniversalDocumentModel(source_format="Manuscript File")
                udm.metadata = LatexParser._parse_metadata(single_tex_content)
                sections, parsed_warns = LatexParser._parse_body(single_tex_content, os.path.dirname(file_path))
                udm.sections = sections
                udm.warnings.extend(parsed_warns)
    except Exception as e:
        tb_str = traceback.format_exc()
        logger.error(f"[{ref_id}] Storage source analysis exception: {str(e)}\n{tb_str}")
        err_code = "DOCX_PARSE_ERROR" if lower_filename.endswith(".docx") else "LATEX_PROJECT_ANALYSIS_ERROR"
        return JSONResponse(status_code=400, content=create_error_payload(
            stage="source_analysis",
            error_code=err_code,
            message=f"Unable to parse manuscript from storage ({clean_filename}).",
            detail=f"{str(e)} | Traceback: {tb_str[:250]}",
            ref_id=ref_id
        ))

    udm.warnings.extend(warnings)

    udm_json_path = os.path.join(TEMP_STORAGE, job_id, "udm.json")
    with open(udm_json_path, "w", encoding="utf-8") as fh:
        fh.write(udm.model_dump_json())

    return {
        "success": True,
        "job_id": job_id,
        "reference_id": ref_id,
        "filename": clean_filename,
        "format": udm.source_format,
        "confidence": udm.parsing_confidence,
        "file_tree": tree,
        "possible_entrypoints": candidates,
        "selected_entrypoint": req.selected_entrypoint or (candidates[0] if candidates else None),
        "project_summary": project_summary,
        "udm": udm.model_dump()
    }

@app.post("/api/analyze-template")
@app.post("/analyze-template")
async def analyze_template(
    file: UploadFile = File(...),
    job_id: str = Form(...)
):
    ref_id = f"REF-{job_id[:8].upper()}"
    job_dir = os.path.join(TEMP_STORAGE, job_id, "template")
    os.makedirs(job_dir, exist_ok=True)
    
    clean_filename = os.path.basename(file.filename) if file.filename else "template.zip"
    file_path = os.path.join(job_dir, clean_filename)
    lower_filename = clean_filename.lower()
    
    content = await file.read()
    if not content or len(content) == 0:
        return JSONResponse(status_code=400, content=create_error_payload(
            stage="template_analysis",
            error_code="UNSUPPORTED_FORMAT",
            message="Uploaded template file is empty (0 bytes).",
            detail=f"The template file '{clean_filename}' contained zero bytes.",
            ref_id=ref_id
        ))
        
    with open(file_path, "wb") as buffer:
        buffer.write(content)
        
    tree = []
    target_extract_dir = job_dir
    logger.info(f"[{ref_id}] Analyzing Template: {clean_filename} ({len(content)} bytes)")
    
    try:
        if lower_filename.endswith(".zip"):
            if not zipfile.is_zipfile(file_path):
                return JSONResponse(status_code=400, content=create_error_payload(
                    stage="template_analysis",
                    error_code="ZIP_EXTRACT_ERROR",
                    message="Uploaded template file is not a valid ZIP archive.",
                    detail=f"The template file '{clean_filename}' failed ZIP validation.",
                    ref_id=ref_id
                ))
            target_extract_dir = os.path.join(job_dir, "extracted")
            _, zip_warns = ZipGuard.inspect_and_extract_safe(file_path, target_extract_dir)
            tree = build_directory_tree(target_extract_dir)
        else:
            tree = [{"path": clean_filename, "name": clean_filename, "type": "docx" if lower_filename.endswith(".docx") else "code", "size": os.path.getsize(file_path)}]
            
        spec = TemplateAnalyzer.analyze_destination_template(target_extract_dir if lower_filename.endswith(".zip") else file_path)
    except Exception as e:
        logger.error(f"[{ref_id}] Template analysis exception: {str(e)}")
        return JSONResponse(status_code=400, content=create_error_payload(
            stage="template_analysis",
            error_code="TEMPLATE_ANALYSIS_ERROR",
            message=f"Unable to analyze destination template ({clean_filename}).",
            detail=str(e),
            ref_id=ref_id
        ))
    
    spec_json_path = os.path.join(TEMP_STORAGE, job_id, "spec.json")
    with open(spec_json_path, "w", encoding="utf-8") as fh:
        fh.write(spec.model_dump_json())
        
    return {
        "success": True,
        "job_id": job_id,
        "reference_id": ref_id,
        "filename": clean_filename,
        "format": spec.format_type,
        "confidence": spec.template_confidence,
        "file_tree": tree,
        "spec": spec.model_dump()
    }

@app.post("/api/analyze-template-from-storage")
@app.post("/analyze-template-from-storage")
async def analyze_template_from_storage(req: TemplateStorageAnalysisRequest):
    job_id = req.job_id
    ref_id = f"REF-{job_id[:8].upper()}"
    job_dir = os.path.join(TEMP_STORAGE, job_id, "template")
    os.makedirs(job_dir, exist_ok=True)
    
    clean_filename = os.path.basename(req.filename) if req.filename else "template.zip"
    file_path = os.path.join(job_dir, clean_filename)
    lower_filename = clean_filename.lower()
    
    url_lower = req.blob_url.lower()
    is_valid_url = url_lower.startswith("https://") or url_lower.startswith("http://127.0.0.1") or url_lower.startswith("http://localhost") or os.path.exists(req.blob_url)
    if not is_valid_url:
        return JSONResponse(status_code=400, content=create_error_payload(
            stage="template_analysis",
            error_code="STORAGE_SECURITY_ERROR",
            message="Invalid or untrusted storage URL requested for template.",
            detail="Storage URL must originate from a secure HTTPS or Vercel Blob endpoint.",
            ref_id=ref_id
        ))

    try:
        if os.path.exists(req.blob_url):
            with open(req.blob_url, "rb") as fh:
                content = fh.read()
        else:
            headers = {}
            token = get_blob_read_write_token()
            if token and not req.download_url:
                headers["Authorization"] = f"Bearer {token}"
            
            fetch_url = req.download_url if req.download_url else req.blob_url
            logger.info(f"[{ref_id}] [BLOB_RETRIEVAL_ATTEMPTED] Fetching template from storage (pathname: '{req.pathname or clean_filename}')")
            
            resp = requests.get(fetch_url, headers=headers, timeout=60)
            if resp.status_code in (401, 403, 404):
                logger.info(f"[{ref_id}] Direct HTTP fetch got status {resp.status_code}. Attempting Node Blob helper (/api/blob-download)...")
                try:
                    host_url = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL") or os.environ.get("VERCEL_URL")
                    if host_url:
                        if not host_url.startswith("http"):
                            host_url = f"https://{host_url}"
                        helper_url = f"{host_url}/api/blob-download?url={urllib.parse.quote(req.blob_url, safe='')}"
                    else:
                        helper_url = f"http://127.0.0.1:3000/api/blob-download?url={urllib.parse.quote(req.blob_url, safe='')}"
                    
                    resp_helper = requests.get(helper_url, timeout=60)
                    if resp_helper.status_code == 200 and len(resp_helper.content) > 0:
                        resp = resp_helper
                        logger.info(f"[{ref_id}] [BLOB_RETRIEVAL_RESULT] Node Blob helper retrieved template ({len(resp.content)} bytes)")
                except Exception as helper_err:
                    logger.warning(f"[{ref_id}] Node Blob helper template request failed: {helper_err}")
            
            if resp.status_code != 200:
                logger.error(f"[{ref_id}] [BLOB_RETRIEVAL_RESULT] Template storage retrieval failed with status {resp.status_code}")
                return JSONResponse(status_code=400, content=create_error_payload(
                    stage="template_analysis",
                    error_code="STORAGE_OBJECT_NOT_FOUND",
                    message="Uploaded template could not be retrieved from secure storage. Please retry the upload.",
                    detail=f"Storage request returned status code {resp.status_code} for pathname '{req.pathname or clean_filename}'.",
                    ref_id=ref_id
                ))
            content = resp.content
    except Exception as e:
        return JSONResponse(status_code=400, content=create_error_payload(
            stage="template_analysis",
            error_code="TEMPLATE_ANALYSIS_ERROR",
            message="Failed to download template from Blob storage.",
            detail=str(e),
            ref_id=ref_id
        ))
    finally:
        # MANDATORY TEMPORARY BLOB CLEANUP: Delete temporary staging Blob immediately after retrieval (or on failure)
        trigger_blob_cleanup(req.blob_url, req.pathname)

    if not content or len(content) == 0:
        return JSONResponse(status_code=400, content=create_error_payload(
            stage="template_analysis",
            error_code="UNSUPPORTED_FORMAT",
            message="Retrieved template file is empty (0 bytes).",
            detail=f"The template file '{clean_filename}' contained zero bytes.",
            ref_id=ref_id
        ))

    downloaded_hash = hashlib.sha256(content).hexdigest()
    if req.sha256 and downloaded_hash.lower() != req.sha256.lower():
        return JSONResponse(status_code=400, content=create_error_payload(
            stage="template_analysis",
            error_code="UPLOAD_INTEGRITY_ERROR",
            message="SHA-256 hash mismatch detected for template file.",
            detail=f"Expected SHA-256: {req.sha256}, Computed SHA-256: {downloaded_hash}",
            ref_id=ref_id
        ))

    with open(file_path, "wb") as buffer:
        buffer.write(content)

    tree = []
    target_extract_dir = job_dir
    logger.info(f"[{ref_id}] Analyzing Template from Storage: {clean_filename} ({len(content)} bytes)")

    try:
        if lower_filename.endswith(".zip"):
            if not zipfile.is_zipfile(file_path):
                return JSONResponse(status_code=400, content=create_error_payload(
                    stage="template_analysis",
                    error_code="ZIP_EXTRACT_ERROR",
                    message="Uploaded template file is not a valid ZIP archive.",
                    detail=f"The template file '{clean_filename}' failed ZIP validation.",
                    ref_id=ref_id
                ))
            target_extract_dir = os.path.join(job_dir, "extracted")
            _, zip_warns = ZipGuard.inspect_and_extract_safe(file_path, target_extract_dir)
            tree = build_directory_tree(target_extract_dir)
        else:
            tree = [{"path": clean_filename, "name": clean_filename, "type": "docx" if lower_filename.endswith(".docx") else "code", "size": os.path.getsize(file_path)}]

        spec = TemplateAnalyzer.analyze_destination_template(target_extract_dir if lower_filename.endswith(".zip") else file_path)
    except Exception as e:
        logger.error(f"[{ref_id}] Template analysis exception: {str(e)}")
        return JSONResponse(status_code=400, content=create_error_payload(
            stage="template_analysis",
            error_code="TEMPLATE_ANALYSIS_ERROR",
            message=f"Unable to analyze destination template ({clean_filename}).",
            detail=str(e),
            ref_id=ref_id
        ))

    spec_json_path = os.path.join(TEMP_STORAGE, job_id, "spec.json")
    with open(spec_json_path, "w", encoding="utf-8") as fh:
        fh.write(spec.model_dump_json())

    return {
        "success": True,
        "job_id": job_id,
        "reference_id": ref_id,
        "filename": clean_filename,
        "format": spec.format_type,
        "confidence": spec.template_confidence,
        "file_tree": tree,
        "spec": spec.model_dump()
    }

def execute_conversion_pipeline(job_id: str, udm: UniversalDocumentModel, spec: TemplateSpecification, ref_id: str, job_dir: str):
    logger.info(f"[{ref_id}] Executing Format Conversion: {udm.source_format} → {spec.format_type.upper()}")
    mapping_res = MappingEngine.map_and_evaluate(udm, spec)
    
    output_dir = os.path.join(job_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    
    created_files = []
    output_pdf_path = os.path.join(output_dir, "preview.pdf")
    
    if spec.format_type == "latex":
        output_zip_path = os.path.join(output_dir, "converted_project.zip")
        dest_template_dir = os.path.join(job_dir, "template", "extracted")
        
        if not os.path.exists(dest_template_dir) or not os.listdir(dest_template_dir):
            sample_zip = os.path.join(SAMPLES_DIR, "springer_template.zip")
            if os.path.exists(sample_zip):
                ZipGuard.inspect_and_extract_safe(sample_zip, dest_template_dir)
            else:
                os.makedirs(dest_template_dir, exist_ok=True)
                
        created_files = LatexRenderer.render_project(
            udm=udm,
            spec=spec,
            dest_template_dir=dest_template_dir,
            output_dir=os.path.join(output_dir, "latex_proj"),
            output_zip_path=output_zip_path
        )

        is_valid_proj, val_errs = TemplateValidator.validate_rendered_project(
            output_dir=os.path.join(output_dir, "latex_proj"),
            udm=udm
        )
        if not is_valid_proj:
            logger.error(f"[{ref_id}] Rendered project validation failed: {val_errs}")
            return JSONResponse(status_code=400, content=create_error_payload(
                stage="conversion",
                error_code="CONVERSION_VALIDATION_ERROR",
                message="Rendered target project failed structural integrity validation.",
                detail="; ".join(val_errs),
                ref_id=ref_id
            ))
        
        entrypoint = "main.tex"
        compiled, sandbox_log = LatexSandbox.compile_project(
            project_dir=os.path.join(output_dir, "latex_proj"),
            entrypoint=entrypoint,
            udm=udm,
            output_pdf_path=output_pdf_path
        )
    else:
        output_docx_path = os.path.join(output_dir, "converted_document.docx")
        DocxRenderer.render(udm, spec, output_docx_path)
        created_files.append("converted_document.docx")
        
        compiled, sandbox_log = LatexSandbox.compile_project(
            project_dir=output_dir,
            entrypoint="",
            udm=udm,
            output_pdf_path=output_pdf_path
        )

    output_udm = udm
    integrity = IntegrityChecker.compare_integrity(udm, output_udm)
    validation_checks = TemplateValidator.validate_conformity(spec)
    
    report = ConversionReport(
        job_id=job_id,
        source_format=udm.source_format,
        destination_format=spec.format_type.upper(),
        source_confidence=udm.parsing_confidence,
        template_confidence=spec.template_confidence,
        conformity_estimate=mapping_res["compatibility"]["overall"],
        integrity=integrity,
        validation_checks=validation_checks,
        warnings=mapping_res["warnings"],
        converted_files=created_files,
        pdf_compiled=compiled,
        sandbox_log=sandbox_log
    )
    
    report_path = os.path.join(output_dir, "report.json")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(report.model_dump_json())
        
    return {
        "status": "SUCCESS",
        "job_id": job_id,
        "reference_id": ref_id,
        "report": report.model_dump(),
        "mapping": mapping_res
    }

@app.post("/api/convert")
@app.post("/convert")
async def convert_document(
    job_id: str = Form(...),
    udm_json_str: Optional[str] = Form(None),
    spec_json_str: Optional[str] = Form(None)
):
    ref_id = f"REF-{job_id[:8].upper()}"
    job_dir = os.path.join(TEMP_STORAGE, job_id)
    os.makedirs(job_dir, exist_ok=True)
    
    udm_json_path = os.path.join(job_dir, "udm.json")
    spec_json_path = os.path.join(job_dir, "spec.json")
    
    if udm_json_str:
        with open(udm_json_path, "w", encoding="utf-8") as fh:
            fh.write(udm_json_str)
    if spec_json_str:
        with open(spec_json_path, "w", encoding="utf-8") as fh:
            fh.write(spec_json_str)
            
    if not os.path.exists(udm_json_path) or not os.path.exists(spec_json_path):
        return JSONResponse(status_code=400, content=create_error_payload(
            stage="conversion",
            error_code="STORAGE_ERROR",
            message="Missing source UDM or template specification for this conversion job.",
            detail="The session data was not found on this serverless instance. Please re-run analysis.",
            ref_id=ref_id
        ))
        
    try:
        with open(udm_json_path, "r", encoding="utf-8") as fh:
            udm = UniversalDocumentModel.model_validate_json(fh.read())
        with open(spec_json_path, "r", encoding="utf-8") as fh:
            spec = TemplateSpecification.model_validate_json(fh.read())
    except Exception as e:
        return JSONResponse(status_code=400, content=create_error_payload(
            stage="conversion",
            error_code="CONVERSION_ERROR",
            message="Failed to deserialize session conversion models.",
            detail=str(e),
            ref_id=ref_id
        ))

    return execute_conversion_pipeline(job_id=job_id, udm=udm, spec=spec, ref_id=ref_id, job_dir=job_dir)

@app.post("/api/convert-from-storage")
@app.post("/convert-from-storage")
async def convert_document_from_storage(req: ConversionStorageRequest):
    job_id = req.job_id
    ref_id = f"REF-{job_id[:8].upper()}"
    job_dir = os.path.join(TEMP_STORAGE, job_id)
    os.makedirs(job_dir, exist_ok=True)
    
    url_lower = req.blob_url.lower()
    is_valid_url = url_lower.startswith("https://") or url_lower.startswith("http://127.0.0.1") or url_lower.startswith("http://localhost") or os.path.exists(req.blob_url)
    if not is_valid_url:
        return JSONResponse(status_code=400, content=create_error_payload(
            stage="conversion",
            error_code="STORAGE_SECURITY_ERROR",
            message="Invalid or untrusted storage URL requested for conversion.",
            detail="Storage URL must originate from a secure HTTPS or Vercel Blob endpoint.",
            ref_id=ref_id
        ))

    content = None
    try:
        if os.path.exists(req.blob_url):
            with open(req.blob_url, "rb") as fh:
                content = fh.read()
        else:
            headers = {}
            token = get_blob_read_write_token()
            if token and not req.download_url:
                headers["Authorization"] = f"Bearer {token}"
            
            fetch_url = req.download_url if req.download_url else req.blob_url
            logger.info(f"[{ref_id}] [BLOB_RETRIEVAL_ATTEMPTED] Fetching temporary conversion state from storage (pathname: '{req.pathname or 'conversion_state.json'}')")
            
            resp = requests.get(fetch_url, headers=headers, timeout=60)
            if resp.status_code in (401, 403, 404):
                try:
                    host_url = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL") or os.environ.get("VERCEL_URL")
                    if host_url:
                        if not host_url.startswith("http"):
                            host_url = f"https://{host_url}"
                        helper_url = f"{host_url}/api/blob-download?url={urllib.parse.quote(req.blob_url, safe='')}"
                    else:
                        helper_url = f"http://127.0.0.1:3000/api/blob-download?url={urllib.parse.quote(req.blob_url, safe='')}"
                    
                    resp_helper = requests.get(helper_url, timeout=60)
                    if resp_helper.status_code == 200 and len(resp_helper.content) > 0:
                        resp = resp_helper
                except Exception as helper_err:
                    logger.warning(f"[{ref_id}] Node Blob helper request failed for conversion state: {helper_err}")
            
            if resp.status_code != 200:
                return JSONResponse(status_code=400, content=create_error_payload(
                    stage="conversion",
                    error_code="STORAGE_OBJECT_NOT_FOUND",
                    message="Temporary conversion state payload could not be retrieved from secure storage.",
                    detail=f"Storage request returned status code {resp.status_code}.",
                    ref_id=ref_id
                ))
            content = resp.content
    except Exception as e:
        return JSONResponse(status_code=400, content=create_error_payload(
            stage="conversion",
            error_code="CONVERSION_ERROR",
            message="Failed to download conversion state from Blob storage.",
            detail=str(e),
            ref_id=ref_id
        ))
    finally:
        # Mandatory cleanup: delete temporary conversion state Blob post-processing
        trigger_blob_cleanup(req.blob_url, req.pathname)

    if not content or len(content) == 0:
        return JSONResponse(status_code=400, content=create_error_payload(
            stage="conversion",
            error_code="CONVERSION_ERROR",
            message="Retrieved temporary conversion state file is empty (0 bytes).",
            detail="The temporary conversion state payload was empty.",
            ref_id=ref_id
        ))

    import json as _json
    try:
        state_data = _json.loads(content.decode("utf-8"))
        udm_dict = state_data.get("udm")
        spec_dict = state_data.get("spec")
        
        udm = UniversalDocumentModel.model_validate(udm_dict)
        spec = TemplateSpecification.model_validate(spec_dict)
    except Exception as parse_err:
        return JSONResponse(status_code=400, content=create_error_payload(
            stage="conversion",
            error_code="CONVERSION_ERROR",
            message="Failed to parse temporary conversion state payload.",
            detail=str(parse_err),
            ref_id=ref_id
        ))

    udm_json_path = os.path.join(job_dir, "udm.json")
    spec_json_path = os.path.join(job_dir, "spec.json")
    with open(udm_json_path, "w", encoding="utf-8") as fh:
        fh.write(udm.model_dump_json())
    with open(spec_json_path, "w", encoding="utf-8") as fh:
        fh.write(spec.model_dump_json())

    return execute_conversion_pipeline(job_id=job_id, udm=udm, spec=spec, ref_id=ref_id, job_dir=job_dir)


@app.get("/api/download/{job_id}/{file_kind}")
@app.get("/download/{job_id}/{file_kind}")
def download_file(job_id: str, file_kind: str):
    output_dir = os.path.join(TEMP_STORAGE, job_id, "output")
    
    if file_kind == "zip":
        p = os.path.join(output_dir, "converted_project.zip")
        if os.path.exists(p):
            return FileResponse(p, filename="converted_academic_paper.zip", media_type="application/zip")
    elif file_kind == "docx":
        p = os.path.join(output_dir, "converted_document.docx")
        if os.path.exists(p):
            return FileResponse(p, filename="converted_academic_paper.docx", media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    elif file_kind == "pdf":
        p = os.path.join(output_dir, "preview.pdf")
        if os.path.exists(p):
            return FileResponse(p, filename="manuscript_preview.pdf", media_type="application/pdf")
    elif file_kind == "report":
        p = os.path.join(output_dir, "report.json")
        if os.path.exists(p):
            return FileResponse(p, filename="conversion_report.json", media_type="application/json")
            
    raise HTTPException(status_code=404, detail="Requested download file not found.")

@app.get("/{catchall:path}")
def serve_frontend(catchall: str):
    if catchall in ["health", "api/health"]:
        return health_check()
    file_path = os.path.join(STATIC_DIR, catchall)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse(content=INLINE_INDEX_HTML, media_type="text/html")
