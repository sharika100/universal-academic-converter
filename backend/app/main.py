import os
import uuid
import shutil
import tempfile
import zipfile
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.models.udm import UniversalDocumentModel
from app.models.template_spec import TemplateSpecification
from app.models.report import ConversionReport, CountComparison
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

app = FastAPI(title="Universal Academic Format Converter API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_STORAGE = os.path.join(tempfile.gettempdir(), "universal_converter_storage")
os.makedirs(TEMP_STORAGE, exist_ok=True)

# Locate samples directory robustly across local and Vercel serverless environments
SAMPLES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "samples"))
if not os.path.exists(SAMPLES_DIR):
    SAMPLES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "samples"))
if not os.path.exists(SAMPLES_DIR):
    SAMPLES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "samples"))

DIST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))

# Serve samples static directory
if os.path.exists(SAMPLES_DIR):
    app.mount("/samples", StaticFiles(directory=SAMPLES_DIR), name="samples")

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
    job_dir = os.path.join(TEMP_STORAGE, job_id, "source")
    os.makedirs(job_dir, exist_ok=True)
    
    clean_filename = os.path.basename(file.filename) if file.filename else "manuscript.docx"
    file_path = os.path.join(job_dir, clean_filename)
    
    # Read bytes asynchronously for Vercel ASGI serverless compatibility
    content = await file.read()
    if not content or len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty (0 bytes).")
        
    with open(file_path, "wb") as buffer:
        buffer.write(content)
        
    tree = []
    warnings = []
    candidates = []
    
    try:
        if clean_filename.endswith(".zip"):
            if not zipfile.is_zipfile(file_path):
                raise HTTPException(status_code=400, detail="Uploaded file is not a valid ZIP archive.")
            extract_dir = os.path.join(job_dir, "extracted")
            rel_files, zip_warns = ZipGuard.inspect_and_extract_safe(file_path, extract_dir)
            warnings.extend(zip_warns)
            tree = build_directory_tree(extract_dir)
            _, candidates, all_tex = find_latex_entrypoint(extract_dir)
            if all_tex:
                udm = LatexParser.parse_project(extract_dir, selected_entrypoint=selected_entrypoint)
            else:
                docx_files = [os.path.join(root, f) for root, _, files in os.walk(extract_dir) for f in files if f.endswith(".docx")]
                if docx_files:
                    udm = DocxParser.parse(docx_files[0])
                    udm.source_format = "DOCX (ZIP Archive)"
                else:
                    raise HTTPException(status_code=400, detail="No valid .tex or .docx manuscript files found in uploaded ZIP archive.")
        elif clean_filename.endswith(".docx"):
            tree = [{"path": clean_filename, "name": clean_filename, "type": "docx", "size": os.path.getsize(file_path)}]
            udm = DocxParser.parse(file_path)
        else:
            # Single TeX file
            tree = [{"path": clean_filename, "name": clean_filename, "type": "code", "size": os.path.getsize(file_path)}]
            with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                single_tex_content = fh.read()
            udm = UniversalDocumentModel(source_format="LaTeX File")
            udm.metadata = LatexParser._parse_metadata(single_tex_content)
            sections, parsed_warns = LatexParser._parse_body(single_tex_content, os.path.dirname(file_path))
            udm.sections = sections
            udm.warnings.extend(parsed_warns)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Source parsing error: {str(e)}")
        
    udm.warnings.extend(warnings)
    
    # Store UDM in job folder
    udm_json_path = os.path.join(TEMP_STORAGE, job_id, "udm.json")
    with open(udm_json_path, "w", encoding="utf-8") as fh:
        fh.write(udm.model_dump_json())
        
    return {
        "job_id": job_id,
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
async def analyze_template(
    file: UploadFile = File(...),
    job_id: str = Form(...)
):
    job_dir = os.path.join(TEMP_STORAGE, job_id, "template")
    os.makedirs(job_dir, exist_ok=True)
    
    clean_filename = os.path.basename(file.filename) if file.filename else "template.zip"
    file_path = os.path.join(job_dir, clean_filename)
    
    # Read bytes asynchronously for Vercel ASGI serverless compatibility
    content = await file.read()
    if not content or len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded template file is empty (0 bytes).")
        
    with open(file_path, "wb") as buffer:
        buffer.write(content)
        
    tree = []
    target_extract_dir = job_dir
    try:
        if clean_filename.endswith(".zip"):
            if not zipfile.is_zipfile(file_path):
                raise HTTPException(status_code=400, detail="Uploaded template is not a valid ZIP archive.")
            target_extract_dir = os.path.join(job_dir, "extracted")
            _, zip_warns = ZipGuard.inspect_and_extract_safe(file_path, target_extract_dir)
            tree = build_directory_tree(target_extract_dir)
        else:
            tree = [{"path": clean_filename, "name": clean_filename, "type": "docx" if clean_filename.endswith(".docx") else "code", "size": os.path.getsize(file_path)}]
            
        spec = TemplateAnalyzer.analyze_destination_template(target_extract_dir if clean_filename.endswith(".zip") else file_path)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Template analysis error: {str(e)}")
    
    spec_json_path = os.path.join(TEMP_STORAGE, job_id, "spec.json")
    with open(spec_json_path, "w", encoding="utf-8") as fh:
        fh.write(spec.model_dump_json())
        
    return {
        "job_id": job_id,
        "filename": clean_filename,
        "format": spec.format_type,
        "confidence": spec.template_confidence,
        "file_tree": tree,
        "spec": spec.model_dump()
    }

@app.post("/api/convert")
@app.post("/convert")
async def convert_document(job_id: str = Form(...)):
    job_dir = os.path.join(TEMP_STORAGE, job_id)
    udm_json_path = os.path.join(job_dir, "udm.json")
    spec_json_path = os.path.join(job_dir, "spec.json")
    
    if not os.path.exists(udm_json_path) or not os.path.exists(spec_json_path):
        raise HTTPException(status_code=400, detail="Missing source or template analysis data for this job.")
        
    with open(udm_json_path, "r", encoding="utf-8") as fh:
        udm = UniversalDocumentModel.model_validate_json(fh.read())
    with open(spec_json_path, "r", encoding="utf-8") as fh:
        spec = TemplateSpecification.model_validate_json(fh.read())
        
    mapping_res = MappingEngine.map_and_evaluate(udm, spec)
    
    output_dir = os.path.join(job_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    
    created_files = []
    output_pdf_path = os.path.join(output_dir, "preview.pdf")
    
    if spec.format_type == "latex":
        output_zip_path = os.path.join(output_dir, "converted_project.zip")
        dest_template_dir = os.path.join(job_dir, "template", "extracted")
        
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
        "report": report.model_dump(),
        "mapping": mapping_res
    }

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

# Mount built frontend dist static files if present
if os.path.exists(DIST_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST_DIR, "assets")), name="assets")

    @app.get("/{catchall:path}")
    def serve_frontend(catchall: str):
        file_path = os.path.join(DIST_DIR, catchall)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(DIST_DIR, "index.html"))
