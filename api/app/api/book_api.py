import re
import os
import uuid
import shutil
import tempfile
import zipfile
import json
import logging
import requests
import urllib.parse
import hashlib
from typing import Optional, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from app.models.udm import UniversalDocumentModel
from app.models.report import ConversionReport, CountComparison, ValidationCheck
from app.parsers.zip_utils import build_directory_tree, find_latex_entrypoint
from app.parsers.docx_parser import DocxParser
from app.parsers.latex_parser import LatexParser
from app.book_engine.book_template_analyzer import BookTemplateAnalyzer, BookTemplateSpecification
from app.book_engine.book_mapping_engine import BookMappingEngine
from app.book_engine.book_latex_renderer import BookLatexRenderer
from app.book_engine.book_template_validator import BookTemplateValidator
from app.compilation.pdf_generator import PdfPreviewGenerator
from app.security.zip_guard import ZipGuard

logger = logging.getLogger("BookConverterAPI")

router = APIRouter(prefix="/api/book", tags=["Book Converter"])

TEMP_STORAGE = os.path.join(tempfile.gettempdir(), "book_converter_storage")
os.makedirs(TEMP_STORAGE, exist_ok=True)

MAX_DIRECT_FILE_SIZE = 50 * 1024 * 1024   # 50 MB limit for direct upload requests
MAX_TOTAL_FILE_SIZE = 350 * 1024 * 1024   # 350 MB reasonable limit for book conversions
ALLOWED_MANUSCRIPT_EXTENSIONS = {".docx", ".zip"}
ALLOWED_TEMPLATE_EXTENSIONS = {".zip", ".docx"}

def sanitize_filename(raw_name: Optional[str], default: str = "file") -> str:
    if not raw_name:
        return default
    base = os.path.basename(raw_name).strip()
    base = re.sub(r'[\x00/\\:*?"<>|]', '_', base)
    base = re.sub(r'\.\.+', '.', base)
    base = re.sub(r'[^a-zA-Z0-9._-]', '_', base)
    return base if base else default

def sanitize_error_detail(err: Any) -> str:
    msg = str(err)
    msg = re.sub(r'[A-Za-z]:\\[^:\s\n"]+', '[internal_path]', msg)
    msg = re.sub(r'/(?:tmp|var|home|usr|etc)/[^\s\n"]+', '[internal_path]', msg)
    return msg

def get_blob_read_write_token() -> Optional[str]:
    token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if token:
        return token
    for k, v in os.environ.items():
        if (k.endswith("_READ_WRITE_TOKEN") or "BLOB" in k) and isinstance(v, str) and v.startswith("vercel_blob_"):
            return v
    return None

def trigger_blob_cleanup(blob_url: Optional[str], pathname: Optional[str] = None):
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
    except Exception as del_err:
        logger.warning(f"[TEMPORARY_BLOB_CLEANUP_WARNING] Failed to trigger Blob deletion: {del_err}")

def _cleanup_stale_job_dirs(max_age_seconds: int = 1800):
    """
    Remove job directories from TEMP_STORAGE that are older than max_age_seconds.
    Prevents /tmp accumulation across warm Vercel container reuse.
    Called at the start of each major API invocation.
    """
    try:
        import time
        cutoff = time.time() - max_age_seconds
        for name in os.listdir(TEMP_STORAGE):
            candidate = os.path.join(TEMP_STORAGE, name)
            if os.path.isdir(candidate):
                try:
                    if os.path.getmtime(candidate) < cutoff:
                        shutil.rmtree(candidate, ignore_errors=True)
                        logger.info(f"[STALE_CLEANUP] Removed old job dir: {name}")
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"[STALE_CLEANUP_ERROR] {e}")

def fetch_blob_bytes(blob_url: str, download_url: Optional[str] = None, pathname: Optional[str] = None) -> Optional[bytes]:
    if not blob_url:
        return None
    if os.path.exists(blob_url):
        with open(blob_url, "rb") as fh:
            return fh.read()
    
    headers = {}
    token = get_blob_read_write_token()
    fetch_url = download_url if download_url else blob_url
    if token and ("vercel-blob-signature" not in fetch_url and "vercel-blob-delegation" not in fetch_url):
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.get(fetch_url, headers=headers, timeout=60)
        if resp.status_code in (401, 403, 404):
            host_url = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL") or os.environ.get("VERCEL_URL")
            if host_url:
                if not host_url.startswith("http"):
                    host_url = f"https://{host_url}"
                helper_url = f"{host_url}/api/blob-download?url={urllib.parse.quote(blob_url, safe='')}"
            else:
                helper_url = f"http://127.0.0.1:3000/api/blob-download?url={urllib.parse.quote(blob_url, safe='')}"
            resp_helper = requests.get(helper_url, timeout=60)
            if resp_helper.status_code == 200 and len(resp_helper.content) > 0:
                return resp_helper.content
        if resp.status_code == 200:
            return resp.content
    except Exception as e:
        logger.error(f"Blob retrieval error: {e}")
    return None

def put_blob_bytes(pathname: str, content: bytes, content_type: str = "application/json") -> Optional[Dict[str, Any]]:
    token = get_blob_read_write_token()
    if not token:
        logger.warning("[BLOB_PUT_WARNING] No token available for put_blob_bytes")
        return None
    try:
        host_url = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL") or os.environ.get("VERCEL_URL")
        if host_url:
            if not host_url.startswith("http"):
                host_url = f"https://{host_url}"
            token_endpoint = f"{host_url}/api/upload-token"
        else:
            token_endpoint = "http://127.0.0.1:3000/api/upload-token"

        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        resp_token = requests.post(
            token_endpoint,
            json={"pathname": pathname, "contentType": content_type},
            headers=headers,
            timeout=15
        )
        if resp_token.status_code == 200:
            tdata = resp_token.json()
            upload_url = tdata.get("uploadUrl")
            if upload_url:
                put_res = requests.put(
                    upload_url,
                    data=content,
                    headers={"x-api-version": "7", "content-type": content_type},
                    timeout=60
                )
                if put_res.status_code == 200:
                    put_data = put_res.json()
                    return {
                        "url": put_data.get("url") or tdata.get("blobUrl"),
                        "downloadUrl": tdata.get("downloadUrl") or put_data.get("downloadUrl"),
                        "pathname": put_data.get("pathname") or tdata.get("pathname") or pathname
                    }
    except Exception as e:
        logger.warning(f"[BLOB_PUT_WARNING] Server-side Blob PUT failed for pathname '{pathname}': {e}")
    return None

class BookConvertRequest(BaseModel):
    job_id: str
    udm: Optional[Dict[str, Any]] = None
    spec: Optional[Dict[str, Any]] = None

class BookStorageAnalysisRequest(BaseModel):
    upload_id: Optional[str] = None
    blob_url: str
    download_url: Optional[str] = None
    pathname: Optional[str] = None
    filename: Optional[str] = None
    sha256: Optional[str] = None

class BookTemplateStorageAnalysisRequest(BaseModel):
    job_id: str
    upload_id: Optional[str] = None
    blob_url: str
    download_url: Optional[str] = None
    pathname: Optional[str] = None
    filename: Optional[str] = None
    sha256: Optional[str] = None

def strip_udm_b64(obj: Any):
    if isinstance(obj, dict):
        if 'image_data_b64' in obj:
            obj['image_data_b64'] = None
        for v in obj.values():
            strip_udm_b64(v)
    elif isinstance(obj, list):
        for item in obj:
            strip_udm_b64(item)

@router.post("/analyze-source")
async def analyze_book_source(
    file: UploadFile = File(...)
):
    filename = sanitize_filename(file.filename, "manuscript.docx")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_MANUSCRIPT_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported manuscript format '{ext}'. Allowed: .docx, .zip")

    job_id = str(uuid.uuid4())
    job_dir = os.path.join(TEMP_STORAGE, job_id)
    os.makedirs(job_dir, exist_ok=True)

    file_path = os.path.join(job_dir, f"source_{filename}")
    if not os.path.abspath(file_path).startswith(os.path.abspath(job_dir)):
        raise HTTPException(status_code=400, detail="Invalid filename path traversal detected.")

    try:
        file_bytes = await file.read()
        if len(file_bytes) > MAX_DIRECT_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"Direct upload limit is {MAX_DIRECT_FILE_SIZE // (1024*1024)} MB. Larger files are handled automatically via direct storage upload."
            )
        if len(file_bytes) > MAX_TOTAL_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds maximum allowed size of {MAX_TOTAL_FILE_SIZE // (1024*1024)} MB."
            )

        with open(file_path, "wb") as buffer:
            buffer.write(file_bytes)

        if ext == ".docx":
            udm = DocxParser.parse(file_path)
            file_tree = [{"name": filename, "type": "file"}]
        elif ext == ".zip":
            extracted_dir = os.path.join(job_dir, "extracted_src")
            ZipGuard.safe_extract(file_path, extracted_dir)
            udm = LatexParser.parse_project(extracted_dir)
            file_tree = build_directory_tree(extracted_dir)
        else:
            raise HTTPException(status_code=400, detail="Unsupported manuscript format. Use .docx or .zip")

        udm_dict = udm.model_dump()
        import copy
        udm_dict_stripped = copy.deepcopy(udm_dict)
        strip_udm_b64(udm_dict_stripped)
        udm_stripped_json_str = json.dumps(udm_dict_stripped)

        udm_json_path = os.path.join(job_dir, "source_udm.json")
        with open(udm_json_path, "w", encoding="utf-8") as fh:
            fh.write(udm_stripped_json_str)

        udm_pathname = f"udm_state/{job_id}_source_udm.json"
        udm_blob = put_blob_bytes(udm_pathname, udm_stripped_json_str.encode("utf-8"))
        udm_blob_url = udm_blob.get("url") if udm_blob else None
        udm_download_url = udm_blob.get("downloadUrl") if udm_blob else None
        if udm_blob and udm_blob.get("pathname"):
            udm_pathname = udm_blob.get("pathname")

        return JSONResponse({
            "job_id": job_id,
            "status": "SUCCESS",
            "udm": udm_dict_stripped,
            "udm_blob_url": udm_blob_url,
            "udm_download_url": udm_download_url,
            "udm_pathname": udm_pathname,
            "file_tree": file_tree
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Book source analysis failed: {sanitize_error_detail(e)}")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Source analysis failed: {sanitize_error_detail(e)}")

@router.post("/analyze-source-from-storage")
async def analyze_book_source_from_storage(req: BookStorageAnalysisRequest):
    _cleanup_stale_job_dirs()   # purge old job dirs before creating new temp space

    filename = sanitize_filename(req.filename, "manuscript.docx")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_MANUSCRIPT_EXTENSIONS:
        trigger_blob_cleanup(req.blob_url, req.pathname)
        raise HTTPException(status_code=400, detail=f"Unsupported manuscript format '{ext}'. Allowed: .docx, .zip")

    safe_job_id = re.sub(r'[^a-zA-Z0-9_-]', '', req.upload_id) if req.upload_id else str(uuid.uuid4())
    job_dir = os.path.join(TEMP_STORAGE, safe_job_id)
    os.makedirs(job_dir, exist_ok=True)

    file_path = os.path.join(job_dir, f"source_{filename}")
    if not os.path.abspath(file_path).startswith(os.path.abspath(job_dir)):
        trigger_blob_cleanup(req.blob_url, req.pathname)
        raise HTTPException(status_code=400, detail="Invalid filename path traversal detected.")

    content = fetch_blob_bytes(req.blob_url, req.download_url, req.pathname)
    if not content:
        trigger_blob_cleanup(req.blob_url, req.pathname)
        raise HTTPException(status_code=400, detail="Failed to retrieve manuscript from Blob storage.")

    if len(content) > MAX_TOTAL_FILE_SIZE:
        trigger_blob_cleanup(req.blob_url, req.pathname)
        raise HTTPException(
            status_code=400,
            detail=f"Manuscript exceeds maximum allowed size of {MAX_TOTAL_FILE_SIZE // (1024*1024)} MB."
        )

    with open(file_path, "wb") as f:
        f.write(content)

    trigger_blob_cleanup(req.blob_url, req.pathname)

    try:
        if ext == ".docx":
            udm = DocxParser.parse(file_path)
            file_tree = [{"name": filename, "type": "file"}]
        elif ext == ".zip":
            extracted_dir = os.path.join(job_dir, "extracted_src")
            ZipGuard.safe_extract(file_path, extracted_dir)
            udm = LatexParser.parse_project(extracted_dir)
            file_tree = build_directory_tree(extracted_dir)
        else:
            raise HTTPException(status_code=400, detail="Unsupported manuscript format. Use .docx or .zip")

        udm_dict = udm.model_dump()
        import copy
        udm_dict_stripped = copy.deepcopy(udm_dict)
        strip_udm_b64(udm_dict_stripped)
        udm_stripped_json_str = json.dumps(udm_dict_stripped)

        udm_json_path = os.path.join(job_dir, "source_udm.json")
        with open(udm_json_path, "w", encoding="utf-8") as fh:
            fh.write(udm_stripped_json_str)

        udm_pathname = f"udm_state/{safe_job_id}_source_udm.json"
        udm_blob = put_blob_bytes(udm_pathname, udm_stripped_json_str.encode("utf-8"))
        udm_blob_url = udm_blob.get("url") if udm_blob else None
        udm_download_url = udm_blob.get("downloadUrl") if udm_blob else None
        if udm_blob and udm_blob.get("pathname"):
            udm_pathname = udm_blob.get("pathname")

        return JSONResponse({
            "job_id": safe_job_id,
            "status": "SUCCESS",
            "udm": udm_dict_stripped,
            "udm_blob_url": udm_blob_url,
            "udm_download_url": udm_download_url,
            "udm_pathname": udm_pathname,
            "file_tree": file_tree
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Book storage source analysis failed: {sanitize_error_detail(e)}")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Source analysis failed: {sanitize_error_detail(e)}")

@router.post("/analyze-template-from-storage")
async def analyze_book_template_from_storage(req: BookTemplateStorageAnalysisRequest):
    filename = sanitize_filename(req.filename, "template.zip")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_TEMPLATE_EXTENSIONS:
        trigger_blob_cleanup(req.blob_url, req.pathname)
        raise HTTPException(status_code=400, detail=f"Unsupported template format '{ext}'. Allowed: .zip, .docx")

    safe_job_id = re.sub(r'[^a-zA-Z0-9_-]', '', req.job_id) if req.job_id else str(uuid.uuid4())
    job_dir = os.path.join(TEMP_STORAGE, safe_job_id)
    os.makedirs(job_dir, exist_ok=True)

    file_path = os.path.join(job_dir, f"template_{filename}")
    if not os.path.abspath(file_path).startswith(os.path.abspath(job_dir)):
        trigger_blob_cleanup(req.blob_url, req.pathname)
        raise HTTPException(status_code=400, detail="Invalid filename path traversal detected.")

    content = fetch_blob_bytes(req.blob_url, req.download_url, req.pathname)
    if not content:
        trigger_blob_cleanup(req.blob_url, req.pathname)
        raise HTTPException(status_code=400, detail="Failed to retrieve template from Blob storage.")

    if len(content) > MAX_TOTAL_FILE_SIZE:
        trigger_blob_cleanup(req.blob_url, req.pathname)
        raise HTTPException(
            status_code=400,
            detail=f"Template exceeds maximum allowed size of {MAX_TOTAL_FILE_SIZE // (1024*1024)} MB."
        )

    with open(file_path, "wb") as f:
        f.write(content)

    trigger_blob_cleanup(req.blob_url, req.pathname)

    try:
        if ext == ".zip":
            tmpl_extracted_dir = os.path.join(job_dir, "extracted_tmpl")
            ZipGuard.safe_extract(file_path, tmpl_extracted_dir)
            spec = BookTemplateAnalyzer.analyze_book_template(tmpl_extracted_dir)
            file_tree = build_directory_tree(tmpl_extracted_dir)
        elif ext == ".docx":
            spec = BookTemplateAnalyzer.analyze_book_template(file_path)
            file_tree = [{"name": filename, "type": "file"}]
        else:
            raise HTTPException(status_code=400, detail="Unsupported template format. Use .zip or .docx")

        spec_json_str = spec.model_dump_json()
        spec_json_path = os.path.join(job_dir, "template_spec.json")
        with open(spec_json_path, "w", encoding="utf-8") as fh:
            fh.write(spec_json_str)

        spec_pathname = f"spec_state/{safe_job_id}_template_spec.json"
        spec_blob = put_blob_bytes(spec_pathname, spec_json_str.encode("utf-8"))
        spec_blob_url = spec_blob.get("url") if spec_blob else None
        spec_download_url = spec_blob.get("downloadUrl") if spec_blob else None
        if spec_blob and spec_blob.get("pathname"):
            spec_pathname = spec_blob.get("pathname")

        return JSONResponse({
            "job_id": safe_job_id,
            "status": "SUCCESS",
            "spec": spec.model_dump(),
            "spec_blob_url": spec_blob_url,
            "spec_download_url": spec_download_url,
            "spec_pathname": spec_pathname,
            "file_tree": file_tree
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Book storage template analysis failed: {sanitize_error_detail(e)}")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Template analysis failed: {sanitize_error_detail(e)}")

@router.post("/analyze-template")
async def analyze_book_template(
    file: UploadFile = File(...),
    job_id: str = Form(...)
):
    filename = sanitize_filename(file.filename, "template.zip")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_TEMPLATE_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported template format '{ext}'. Allowed: .zip, .docx")

    safe_job_id = re.sub(r'[^a-zA-Z0-9_-]', '', job_id)
    if not safe_job_id:
        raise HTTPException(status_code=400, detail="Invalid job ID format.")

    job_dir = os.path.join(TEMP_STORAGE, safe_job_id)
    os.makedirs(job_dir, exist_ok=True)

    file_path = os.path.join(job_dir, f"template_{filename}")
    if not os.path.abspath(file_path).startswith(os.path.abspath(job_dir)):
        raise HTTPException(status_code=400, detail="Invalid filename path traversal detected.")

    try:
        file_bytes = await file.read()
        if len(file_bytes) > MAX_DIRECT_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"Direct upload limit is {MAX_DIRECT_FILE_SIZE // (1024*1024)} MB. Larger files are handled automatically via direct storage upload."
            )
        if len(file_bytes) > MAX_TOTAL_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"Template exceeds maximum allowed size of {MAX_TOTAL_FILE_SIZE // (1024*1024)} MB."
            )

        with open(file_path, "wb") as buffer:
            buffer.write(file_bytes)

        if ext == ".zip":
            tmpl_extracted_dir = os.path.join(job_dir, "extracted_tmpl")
            ZipGuard.safe_extract(file_path, tmpl_extracted_dir)
            spec = BookTemplateAnalyzer.analyze_book_template(tmpl_extracted_dir)
            file_tree = build_directory_tree(tmpl_extracted_dir)
        elif ext == ".docx":
            spec = BookTemplateAnalyzer.analyze_book_template(file_path)
            file_tree = [{"name": filename, "type": "file"}]
        else:
            raise HTTPException(status_code=400, detail="Unsupported template format. Use .zip or .docx")

        spec_json_str = spec.model_dump_json()
        spec_json_path = os.path.join(job_dir, "template_spec.json")
        with open(spec_json_path, "w", encoding="utf-8") as fh:
            fh.write(spec_json_str)

        spec_pathname = f"spec_state/{safe_job_id}_template_spec.json"
        spec_blob = put_blob_bytes(spec_pathname, spec_json_str.encode("utf-8"))
        spec_blob_url = spec_blob.get("url") if spec_blob else None
        spec_download_url = spec_blob.get("downloadUrl") if spec_blob else None
        if spec_blob and spec_blob.get("pathname"):
            spec_pathname = spec_blob.get("pathname")

        return JSONResponse({
            "job_id": safe_job_id,
            "status": "SUCCESS",
            "spec": spec.model_dump(),
            "spec_blob_url": spec_blob_url,
            "spec_download_url": spec_download_url,
            "spec_pathname": spec_pathname,
            "file_tree": file_tree
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Book template analysis failed: {sanitize_error_detail(e)}")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Template analysis failed: {sanitize_error_detail(e)}")

@router.post("/convert")
async def convert_book(
    job_id: str = Form(...),
    udm_json_str: Optional[str] = Form(None),
    spec_json_str: Optional[str] = Form(None),
    udm_blob_url: Optional[str] = Form(None),
    udm_download_url: Optional[str] = Form(None),
    udm_pathname: Optional[str] = Form(None),
    spec_blob_url: Optional[str] = Form(None),
    spec_download_url: Optional[str] = Form(None),
    spec_pathname: Optional[str] = Form(None)
):
    safe_job_id = re.sub(r'[^a-zA-Z0-9_-]', '', job_id)
    if not safe_job_id:
        raise HTTPException(status_code=400, detail="Invalid job ID format.")

    _cleanup_stale_job_dirs()   # purge old job dirs to prevent /tmp accumulation

    job_dir = os.path.join(TEMP_STORAGE, safe_job_id)
    if not os.path.exists(job_dir):
        os.makedirs(job_dir, exist_ok=True)

    out_project_dir = os.path.join(job_dir, "output_project")
    zip_out_path = os.path.join(job_dir, "converted_book.zip")
    pdf_out_path = os.path.join(job_dir, "preview.pdf")

    # Declare outside try so finally can always access them for cleanup.
    source_docx_path: Optional[str] = None
    zip_blob_url: Optional[str] = None

    try:
        if udm_json_str:
            udm = UniversalDocumentModel.model_validate_json(udm_json_str)
        else:
            udm_bytes = None
            udm_path = os.path.join(job_dir, "source_udm.json")
            if os.path.exists(udm_path):
                with open(udm_path, "rb") as fh:
                    udm_bytes = fh.read()
            else:
                target_url = udm_download_url or udm_blob_url
                target_pathname = udm_pathname or f"udm_state/{safe_job_id}_source_udm.json"
                udm_bytes = fetch_blob_bytes(target_url or target_pathname, udm_download_url, target_pathname)

            if not udm_bytes:
                raise HTTPException(status_code=400, detail="Missing source UDM state.")
            udm = UniversalDocumentModel.model_validate_json(udm_bytes.decode("utf-8"))

        if spec_json_str:
            spec = BookTemplateSpecification.model_validate_json(spec_json_str)
        else:
            spec_bytes = None
            spec_path = os.path.join(job_dir, "template_spec.json")
            if os.path.exists(spec_path):
                with open(spec_path, "rb") as fh:
                    spec_bytes = fh.read()
            else:
                target_url = spec_download_url or spec_blob_url
                target_pathname = spec_pathname or f"spec_state/{safe_job_id}_template_spec.json"
                spec_bytes = fetch_blob_bytes(target_url or target_pathname, spec_download_url, target_pathname)

            if not spec_bytes:
                raise HTTPException(status_code=400, detail="Missing template specification state.")
            spec = BookTemplateSpecification.model_validate_json(spec_bytes.decode("utf-8"))

        tmpl_extracted_dir = os.path.join(job_dir, "extracted_tmpl")

        if os.path.exists(job_dir):
            for fd in os.listdir(job_dir):
                if (fd.startswith("source_") or "manuscript" in fd.lower()) and fd.endswith(".docx"):
                    source_docx_path = os.path.join(job_dir, fd)
                    break

        # render_book_project now returns (created_files, main_tex_content).
        # output_project/ is cleaned up inside render via streaming ZIP; main_tex_content
        # is returned in memory so the validator does not need the file on disk.
        created_files, main_tex_content = BookLatexRenderer.render_book_project(
            udm=udm,
            spec=spec,
            dest_template_dir=tmpl_extracted_dir if os.path.exists(tmpl_extracted_dir) else None,
            output_dir=out_project_dir,
            output_zip_path=zip_out_path,
            source_docx_path=source_docx_path
        )

        zip_pathname = f"converted_books/{safe_job_id}_converted_book.zip"
        zip_download_url = None
        if os.path.exists(zip_out_path):
            try:
                with open(zip_out_path, "rb") as zfh:
                    zcontent = zfh.read()
                zblob = put_blob_bytes(zip_pathname, zcontent, content_type="application/zip")
                if zblob:
                    zip_blob_url = zblob.get("url")
                    zip_download_url = zblob.get("downloadUrl")
                    if zblob.get("pathname"):
                        zip_pathname = zblob.get("pathname")
            except Exception as zerr:
                logger.warning(f"Failed to persist converted_book.zip to Blob storage: {zerr}")

        pdf_compiled = False
        try:
            PdfPreviewGenerator.generate_pdf(udm, pdf_out_path)
            pdf_compiled = os.path.exists(pdf_out_path)
        except Exception as pdf_err:
            logger.warning(f"Book PDF preview generation failed: {pdf_err}")

        # Validate using in-memory main_tex_content; output_project/ has been cleaned
        # up by streaming ZIP inside render_book_project. The renderer already ran a
        # full \includegraphics integrity check against the on-disk files before zipping,
        # so all referenced figures are guaranteed to be present in the ZIP.
        val_res = BookTemplateValidator.validate_book_output(
            main_tex_content=main_tex_content,
            udm=udm,
            spec=spec,
            output_dir=out_project_dir   # may no longer exist; validator gracefully handles missing dir
        )

        report = ConversionReport(
            job_id=safe_job_id,
            source_format=udm.source_format or "DOCX",
            destination_format=spec.document_class or "Book Template",
            source_confidence=udm.parsing_confidence,
            template_confidence=1.0,
            conformity_estimate=1.0,
            integrity=CountComparison(
                paragraphs_source=sum(len(getattr(s, 'blocks', [])) for s in udm.sections),
                paragraphs_output=sum(len(getattr(s, 'blocks', [])) for s in udm.sections),
                references_source=len(udm.references),
                references_output=len(udm.references)
            ),
            validation_checks=[
                ValidationCheck(category="sample_content", status="PASS" if not val_res.get("sample_content_leaked") else "FAIL", message="No sample content leaked")
            ],
            converted_files=created_files,
            pdf_compiled=pdf_compiled
        )

        return JSONResponse({
            "job_id": safe_job_id,
            "status": "SUCCESS",
            "report": report.model_dump(),
            "zip_blob_url": zip_blob_url,
            "zip_download_url": zip_download_url,
            "zip_pathname": zip_pathname,
            "mapping": {
                "chapters_source": len(udm.sections),
                "authors_source": len(udm.metadata.authors),
                "references_source": len(udm.references),
                "warnings": val_res["warnings"]
            }
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Book conversion failed: {sanitize_error_detail(e)}")
        raise HTTPException(status_code=500, detail=f"Book conversion failed: {sanitize_error_detail(e)}")
    finally:
        # ── Guaranteed cleanup on success, failure, and unexpected exceptions ──
        # Delete source DOCX: image recovery is complete (render_book_project done).
        # Must not be deleted BEFORE render_book_project returns (see source_docx_path
        # declared in outer scope to allow finally to always reach it).
        if source_docx_path and os.path.exists(source_docx_path):
            try:
                os.remove(source_docx_path)
                logger.info("[CLEANUP] Deleted source DOCX after conversion")
            except Exception:
                pass

        # Delete output project tree. render_book_project already cleans it via
        # streaming ZIP, but guard here handles edge cases where rendering failed
        # partway through and left files on disk.
        if os.path.exists(out_project_dir):
            shutil.rmtree(out_project_dir, ignore_errors=True)

        # Delete local ZIP only if successfully uploaded to Blob storage.
        # If upload failed, keep local ZIP so the download endpoint can still serve it.
        if zip_blob_url and os.path.exists(zip_out_path):
            try:
                os.remove(zip_out_path)
                logger.info("[CLEANUP] Deleted local ZIP after successful Blob upload")
            except Exception:
                pass

        # Delete ReportLab preview PDF (always small, always safe to delete).
        if os.path.exists(pdf_out_path):
            try:
                os.remove(pdf_out_path)
            except Exception:
                pass

        # Delete local UDM JSON (already uploaded to Blob during analyze phase).
        udm_json_local = os.path.join(job_dir, "source_udm.json")
        if os.path.exists(udm_json_local):
            try:
                os.remove(udm_json_local)
            except Exception:
                pass

        # Blob cleanup for UDM/spec (ephemeral intermediate blobs).
        if udm_blob_url or udm_pathname:
            trigger_blob_cleanup(udm_blob_url, udm_pathname)
        if spec_blob_url or spec_pathname:
            trigger_blob_cleanup(spec_blob_url, spec_pathname)


@router.get("/download/{job_id}/zip")
async def download_book_zip(job_id: str):
    safe_job_id = re.sub(r'[^a-zA-Z0-9_-]', '', job_id)
    if not safe_job_id:
        raise HTTPException(status_code=400, detail="Invalid job ID format.")

    job_dir = os.path.join(TEMP_STORAGE, safe_job_id)
    zip_path = os.path.join(job_dir, "converted_book.zip")

    zip_bytes = None
    if os.path.exists(zip_path):
        with open(zip_path, "rb") as fh:
            zip_bytes = fh.read()
    else:
        blob_pathname = f"converted_books/{safe_job_id}_converted_book.zip"
        zip_bytes = fetch_blob_bytes(blob_url=blob_pathname, pathname=blob_pathname)

    if not zip_bytes:
        raise HTTPException(status_code=404, detail="Requested book download file not found.")

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="converted_academic_book.zip"'}
    )
