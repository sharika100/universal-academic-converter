import os
import uuid
import shutil
import tempfile
import zipfile
import json
import logging
from typing import Optional, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from app.models.udm import UniversalDocumentModel
from app.models.report import ConversionReport, CountComparison
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

class BookConvertRequest(BaseModel):
    job_id: str
    udm: Optional[Dict[str, Any]] = None
    spec: Optional[Dict[str, Any]] = None

@router.post("/analyze-source")
async def analyze_book_source(
    file: UploadFile = File(...)
):
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(TEMP_STORAGE, job_id)
    os.makedirs(job_dir, exist_ok=True)

    filename = file.filename or "manuscript"
    file_path = os.path.join(job_dir, f"source_{filename}")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        if filename.endswith(".docx"):
            udm = DocxParser.parse(file_path)
            file_tree = [{"name": filename, "type": "file"}]
        elif filename.endswith(".zip"):
            extracted_dir = os.path.join(job_dir, "extracted_src")
            ZipGuard.safe_extract(file_path, extracted_dir)
            udm = LatexParser.parse_project(extracted_dir)
            file_tree = build_directory_tree(extracted_dir)
        else:
            raise HTTPException(status_code=400, detail="Unsupported manuscript format. Use .docx or .zip")

        udm_json_path = os.path.join(job_dir, "source_udm.json")
        with open(udm_json_path, "w", encoding="utf-8") as fh:
            fh.write(udm.model_dump_json())

        return JSONResponse({
            "job_id": job_id,
            "status": "SUCCESS",
            "udm": udm.model_dump(),
            "file_tree": file_tree
        })
    except Exception as e:
        logger.error(f"Book source analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Source analysis failed: {str(e)}")

@router.post("/analyze-template")
async def analyze_book_template(
    file: UploadFile = File(...),
    job_id: str = Form(...)
):
    job_dir = os.path.join(TEMP_STORAGE, job_id)
    os.makedirs(job_dir, exist_ok=True)

    filename = file.filename or "template"
    file_path = os.path.join(job_dir, f"template_{filename}")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        if filename.endswith(".zip"):
            tmpl_extracted_dir = os.path.join(job_dir, "extracted_tmpl")
            ZipGuard.safe_extract(file_path, tmpl_extracted_dir)
            spec = BookTemplateAnalyzer.analyze_book_template(tmpl_extracted_dir)
            file_tree = build_directory_tree(tmpl_extracted_dir)
        elif filename.endswith(".docx"):
            spec = BookTemplateAnalyzer.analyze_book_template(file_path)
            file_tree = [{"name": filename, "type": "file"}]
        else:
            raise HTTPException(status_code=400, detail="Unsupported template format. Use .zip or .docx")

        spec_json_path = os.path.join(job_dir, "template_spec.json")
        with open(spec_json_path, "w", encoding="utf-8") as fh:
            fh.write(spec.model_dump_json())

        return JSONResponse({
            "job_id": job_id,
            "status": "SUCCESS",
            "spec": spec.model_dump(),
            "file_tree": file_tree
        })
    except Exception as e:
        logger.error(f"Book template analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Template analysis failed: {str(e)}")

@router.post("/convert")
async def convert_book(
    job_id: str = Form(...),
    udm_json_str: Optional[str] = Form(None),
    spec_json_str: Optional[str] = Form(None)
):
    job_dir = os.path.join(TEMP_STORAGE, job_id)
    if not os.path.exists(job_dir):
        os.makedirs(job_dir, exist_ok=True)

    try:
        if udm_json_str:
            udm = UniversalDocumentModel.model_validate_json(udm_json_str)
        else:
            udm_path = os.path.join(job_dir, "source_udm.json")
            if not os.path.exists(udm_path):
                raise HTTPException(status_code=400, detail="Missing source UDM state.")
            with open(udm_path, "r", encoding="utf-8") as fh:
                udm = UniversalDocumentModel.model_validate_json(fh.read())

        if spec_json_str:
            spec = BookTemplateSpecification.model_validate_json(spec_json_str)
        else:
            spec_path = os.path.join(job_dir, "template_spec.json")
            if not os.path.exists(spec_path):
                raise HTTPException(status_code=400, detail="Missing template specification state.")
            with open(spec_path, "r", encoding="utf-8") as fh:
                spec = BookTemplateSpecification.model_validate_json(fh.read())

        tmpl_extracted_dir = os.path.join(job_dir, "extracted_tmpl")
        out_project_dir = os.path.join(job_dir, "output_project")
        zip_out_path = os.path.join(job_dir, "converted_book.zip")
        pdf_out_path = os.path.join(job_dir, "preview.pdf")

        created_files = BookLatexRenderer.render_book_project(
            udm=udm,
            spec=spec,
            dest_template_dir=tmpl_extracted_dir if os.path.exists(tmpl_extracted_dir) else None,
            output_dir=out_project_dir,
            output_zip_path=zip_out_path
        )

        pdf_compiled = False
        try:
            PdfPreviewGenerator.generate_pdf(udm, pdf_out_path)
            pdf_compiled = os.path.exists(pdf_out_path)
        except Exception as pdf_err:
            logger.warning(f"Book PDF preview generation failed: {pdf_err}")

        main_tex_path = os.path.join(out_project_dir, "main.tex")
        main_tex_content = ""
        if os.path.exists(main_tex_path):
            with open(main_tex_path, "r", encoding="utf-8") as fh:
                main_tex_content = fh.read()

        val_res = BookTemplateValidator.validate_book_output(
            main_tex_content=main_tex_content,
            udm=udm,
            spec=spec,
            output_dir=out_project_dir
        )

        report = ConversionReport(
            status="SUCCESS",
            source_type=udm.source_format,
            dest_type="Book Template",
            created_files=created_files,
            pdf_compiled=pdf_compiled,
            validation_checks={
                "overall_passed": val_res["overall_passed"],
                "checks": val_res["checks"],
                "sample_content_leaked": val_res["sample_content_leaked"]
            }
        )

        return JSONResponse({
            "job_id": job_id,
            "status": "SUCCESS",
            "report": report.model_dump(),
            "mapping": {
                "chapters_source": len(udm.sections),
                "authors_source": len(udm.metadata.authors),
                "references_source": len(udm.references),
                "warnings": val_res["warnings"]
            }
        })
    except Exception as e:
        logger.error(f"Book conversion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Book conversion failed: {str(e)}")

@router.get("/download/{job_id}/zip")
async def download_book_zip(job_id: str):
    job_dir = os.path.join(TEMP_STORAGE, job_id)
    zip_path = os.path.join(job_dir, "converted_book.zip")

    if not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="Requested book download file not found.")

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename="converted_academic_book.zip"
    )
