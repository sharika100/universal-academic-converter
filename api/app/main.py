import os
import uuid
import shutil
import tempfile
import zipfile
import logging
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.models.udm import UniversalDocumentModel
from app.models.template_spec import TemplateSpecification
from app.models.report import ConversionReport, CountComparison
from app.models.error_response import create_error_payload
from app.security.zip_guard import ZipGuard
from app.parsers.zip_utils import build_directory_tree, find_latex_entrypoint
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

app = FastAPI(title="Universal Academic Format Converter API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# Serve samples static directory
if os.path.exists(SAMPLES_DIR):
    app.mount("/samples", StaticFiles(directory=SAMPLES_DIR), name="samples")

from fastapi.responses import FileResponse, JSONResponse, HTMLResponse

INLINE_INDEX_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Universal Academic Format Converter</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <script type="module" crossorigin src="/assets/index-Df7Klhas.js"></script>
    <link rel="stylesheet" crossorigin href="/assets/index-DdlYOea-.css">
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>"""

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request

@app.get("/debug-vercel-path")
def debug_vercel_path(request: Request):
    return {
        "url_path": request.url.path,
        "scope_path": request.scope.get("path"),
        "raw_url": str(request.url),
        "headers": dict(request.headers)
    }

@app.get("")
@app.get("/")
@app.get("/backend/app/main.py")
@app.get("/backend/app/main.py/")
@app.get("/backend/app/main")
@app.get("/api/index.py")
@app.get("/api/index.py/")
def root_endpoint():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse(content=INLINE_INDEX_HTML, media_type="text/html")

@app.get("/api/health")
@app.get("/health")
@app.get("/backend/app/main.py/api/health")
@app.get("/backend/app/main.py/health")
@app.get("/api/index.py/api/health")
@app.get("/api/index.py/health")
def health_check():
    """Health check endpoint to verify backend API reachability."""
    return {
        "status": "ok",
        "service": "universal-academic-converter",
        "environment": "production"
    }

@app.get("/api/presets")
@app.get("/presets")
@app.get("/backend/app/main.py/api/presets")
@app.get("/backend/app/main.py/presets")
@app.get("/api/index.py/api/presets")
@app.get("/api/index.py/presets")
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
@app.post("/backend/app/main.py/api/analyze-source")
@app.post("/backend/app/main.py/analyze-source")
@app.post("/api/index.py/api/analyze-source")
@app.post("/api/index.py/analyze-source")
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
    
    # Read bytes asynchronously for Vercel ASGI serverless compatibility
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
    lower_filename = clean_filename.lower()
    
    logger.info(f"[{ref_id}] Analyzing Source Manuscript: {clean_filename} ({len(content)} bytes)")
    
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
            _, candidates, all_tex = find_latex_entrypoint(extract_dir)
            if all_tex:
                udm = LatexParser.parse_project(extract_dir, selected_entrypoint=selected_entrypoint)
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
            # Fallback format routing: attempt DOCX parser first, then text parser
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
        logger.error(f"[{ref_id}] Source analysis exception: {str(e)}")
        err_code = "DOCX_PARSE_ERROR" if lower_filename.endswith(".docx") else "LATEX_PARSE_ERROR"
        return JSONResponse(status_code=400, content=create_error_payload(
            stage="source_analysis",
            error_code=err_code,
            message=f"Unable to parse uploaded manuscript ({clean_filename}).",
            detail=str(e),
            ref_id=ref_id
        ))
        
    udm.warnings.extend(warnings)
    
    # Store UDM in job folder
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
        "udm": udm.model_dump()
    }

@app.post("/api/analyze-template")
@app.post("/analyze-template")
@app.post("/backend/app/main.py/api/analyze-template")
@app.post("/backend/app/main.py/analyze-template")
@app.post("/api/index.py/api/analyze-template")
@app.post("/api/index.py/analyze-template")
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
    
    # Read bytes asynchronously for Vercel ASGI serverless compatibility
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

@app.post("/api/convert")
@app.post("/convert")
@app.post("/backend/app/main.py/api/convert")
@app.post("/backend/app/main.py/convert")
@app.post("/api/index.py/api/convert")
@app.post("/api/index.py/convert")
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
    
    # Allow client to supply udm_json_str and spec_json_str to be 100% stateless across Vercel cold-starts
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
            error_code="STORAGE_ERROR",
            message="Failed to deserialize session conversion models.",
            detail=str(e),
            ref_id=ref_id
        ))
        
    logger.info(f"[{ref_id}] Executing Format Conversion: {udm.source_format} → {spec.format_type.upper()}")
    mapping_res = MappingEngine.map_and_evaluate(udm, spec)
    
    output_dir = os.path.join(job_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    
    created_files = []
    output_pdf_path = os.path.join(output_dir, "preview.pdf")
    
    if spec.format_type == "latex":
        output_zip_path = os.path.join(output_dir, "converted_project.zip")
        dest_template_dir = os.path.join(job_dir, "template", "extracted")
        
        # Ensure dest_template_dir exists across cold-starts
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
        
        entrypoint = "main.tex"
        compiled, sandbox_log = LatexSandbox.compile_project(
            project_dir=os.path.join(output_dir, "latex_proj"),
            entrypoint=entrypoint,
            udm=udm,
            output_pdf_path=output_pdf_path
        )
    else:
        # DOCX output
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

@app.get("/api/download/{job_id}/{file_kind}")
@app.get("/download/{job_id}/{file_kind}")
@app.get("/backend/app/main.py/api/download/{job_id}/{file_kind}")
@app.get("/backend/app/main.py/download/{job_id}/{file_kind}")
@app.get("/api/index.py/api/download/{job_id}/{file_kind}")
@app.get("/api/index.py/download/{job_id}/{file_kind}")
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

# Mount built frontend dist static files if present
@app.get("/{catchall:path}")
def serve_frontend(catchall: str):
    if catchall in ["health", "api/health", "backend/app/main.py/health"]:
        return health_check()
    file_path = os.path.join(STATIC_DIR, catchall)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse(content=INLINE_INDEX_HTML, media_type="text/html")
