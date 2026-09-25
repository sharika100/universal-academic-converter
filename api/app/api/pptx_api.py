import os
import re
import uuid
import shutil
import zipfile
import tempfile
import time
import logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, FileResponse

from app.security.zip_guard import ZipGuard
from app.pptx_engine.parser.pptx_parser import PptxParser
from app.pptx_engine.analyzer.template_analyzer import TemplateAnalyzer
from app.pptx_engine.renderer.latex_renderer import LatexRenderer
from app.pptx_engine.compiler.latex_compiler import LatexCompiler

logger = logging.getLogger("pptx_api")

router = APIRouter(prefix="/api/pptx", tags=["PPTX Converter"])

TEMP_JOBS_DIR = os.path.join(tempfile.gettempdir(), "pptx_converter_jobs")
os.makedirs(TEMP_JOBS_DIR, exist_ok=True)

def sanitize_filename(name: str, fallback: str = "file") -> str:
    clean = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', os.path.basename(name or fallback))
    return clean or fallback

def _cleanup_stale_job_dirs(max_age_seconds: int = 1800):
    try:
        cutoff = time.time() - max_age_seconds
        for item in os.listdir(TEMP_JOBS_DIR):
            item_path = os.path.join(TEMP_JOBS_DIR, item)
            if os.path.isdir(item_path):
                try:
                    if os.path.getmtime(item_path) < cutoff:
                        shutil.rmtree(item_path, ignore_errors=True)
                except Exception:
                    pass
    except Exception as cleanup_err:
        logger.warning(f"Error cleaning stale pptx job dirs: {cleanup_err}")

@router.get("/health")
def pptx_health():
    compiler = LatexCompiler.get_available_compiler()
    return {
        "status": "healthy",
        "service": "pptx-latex-template-converter",
        "compiler_available": compiler is not None,
        "compiler": compiler
    }

@router.post("/analyze-template")
async def analyze_template(template_file: UploadFile = File(...)):
    _cleanup_stale_job_dirs()
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(TEMP_JOBS_DIR, job_id, "template")
    os.makedirs(job_dir, exist_ok=True)

    filename = sanitize_filename(template_file.filename or "template.tex")
    ext = os.path.splitext(filename)[1].lower()

    if ext not in [".tex", ".zip"]:
        raise HTTPException(status_code=400, detail=f"Unsupported template format '{ext}'. Must be .tex or .zip")

    dest_file = os.path.join(job_dir, filename)
    content = await template_file.read()
    with open(dest_file, "wb") as f:
        f.write(content)

    try:
        if ext == ".zip":
            extract_dir = os.path.join(job_dir, "extracted")
            ZipGuard.inspect_and_extract_safe(dest_file, extract_dir)
            spec = TemplateAnalyzer.analyze_template(extract_dir)
        else:
            spec = TemplateAnalyzer.analyze_template(dest_file)

        return {
            "success": True,
            "job_id": job_id,
            "filename": filename,
            "spec": spec.model_dump()
        }
    except Exception as e:
        logger.error(f"Template analysis failed: {e}")
        raise HTTPException(status_code=400, detail=f"Template analysis failed: {str(e)}")

@router.post("/convert")
async def convert(
    pptx_file: UploadFile = File(...),
    template_file: UploadFile = File(...)
):
    _cleanup_stale_job_dirs()
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(TEMP_JOBS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    # 1. Validate PPTX extension
    pptx_name = sanitize_filename(pptx_file.filename or "presentation.pptx")
    if not pptx_name.lower().endswith(".pptx"):
        raise HTTPException(status_code=400, detail="PowerPoint file must have a .pptx extension.")

    # 2. Validate Template extension
    tmpl_name = sanitize_filename(template_file.filename or "template.tex")
    tmpl_ext = os.path.splitext(tmpl_name)[1].lower()
    if tmpl_ext not in [".tex", ".zip"]:
        raise HTTPException(status_code=400, detail="Template file must be .tex or .zip.")

    # Save uploaded files
    local_pptx = os.path.join(job_dir, pptx_name)
    with open(local_pptx, "wb") as f:
        f.write(await pptx_file.read())

    local_tmpl = os.path.join(job_dir, tmpl_name)
    with open(local_tmpl, "wb") as f:
        f.write(await template_file.read())

    # 3. Analyze Template
    tmpl_target = local_tmpl
    if tmpl_ext == ".zip":
        extract_tmpl_dir = os.path.join(job_dir, "tmpl_extracted")
        ZipGuard.inspect_and_extract_safe(local_tmpl, extract_tmpl_dir)
        tmpl_target = extract_tmpl_dir

    spec = TemplateAnalyzer.analyze_template(tmpl_target)

    # 4. Parse PPTX and extract images into output project
    out_project_dir = os.path.join(job_dir, "output_project")
    out_images_dir = os.path.join(out_project_dir, "images")
    os.makedirs(out_images_dir, exist_ok=True)

    deck = PptxParser.parse(local_pptx, images_output_dir=out_images_dir)

    # 5. Render Project & Build ZIP
    zip_out_path = os.path.join(job_dir, "converted_presentation.zip")
    render_res = LatexRenderer.render_project(
        deck=deck,
        spec=spec,
        dest_template_dir_or_file=tmpl_target if os.path.isdir(tmpl_target) else None,
        output_dir=out_project_dir,
        output_zip_path=zip_out_path,
        source_filename=pptx_name
    )

    # 6. Attempt compilation if compiler available
    compiler_res = LatexCompiler.compile_project(
        project_dir=out_project_dir,
        entrypoint_tex=spec.entrypoint_tex
    )

    # Re-package ZIP after compilation so the PDF (if generated) is also included in the ZIP
    if os.path.exists(zip_out_path):
        os.remove(zip_out_path)
    with zipfile.ZipFile(zip_out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(out_project_dir):
            for f in files:
                abs_p = os.path.join(root, f)
                rel_p = os.path.relpath(abs_p, out_project_dir)
                zf.write(abs_p, rel_p)

    return {
        "success": True,
        "job_id": job_id,
        "download_url": f"/api/pptx/download/{job_id}",
        "summary": {
            "slide_count": deck.total_slides,
            "generated_frames": len(deck.slides),
            "extracted_images": deck.total_images,
            "converted_tables": deck.total_tables,
            "text_blocks": deck.total_text_blocks,
            "template_class": spec.document_class,
            "is_beamer": spec.is_beamer
        },
        "compilation": {
            "status": compiler_res.get("status"),
            "compiler": compiler_res.get("compiler"),
            "pdf_generated": compiler_res.get("compiled", False),
            "pdf_size_bytes": compiler_res.get("pdf_size_bytes", 0),
            "warnings": compiler_res.get("warnings", []),
            "error_snippet": compiler_res.get("log_snippet")
        },
        "warnings": deck.warnings
    }

@router.get("/download/{job_id}")
@router.get("/download/{job_id}/zip")
def download_zip(job_id: str):
    clean_id = re.sub(r'[^a-zA-Z0-9_\-]', '', job_id)
    zip_path = os.path.join(TEMP_JOBS_DIR, clean_id, "converted_presentation.zip")
    if not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="Converted presentation ZIP not found or expired.")
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename="converted_presentation.zip"
    )
