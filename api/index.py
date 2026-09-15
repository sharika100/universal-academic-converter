import os
import sys
from fastapi import FastAPI

api_dir = os.path.dirname(os.path.abspath(__file__))
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

app = FastAPI()

status = {}

modules_to_test = [
    ("udm", "app.models.udm"),
    ("template_spec", "app.models.template_spec"),
    ("report", "app.models.report"),
    ("error_response", "app.models.error_response"),
    ("zip_guard", "app.security.zip_guard"),
    ("zip_utils", "app.parsers.zip_utils"),
    ("docx_parser", "app.parsers.docx_parser"),
    ("latex_parser", "app.parsers.latex_parser"),
    ("analyzer", "app.template_engine.analyzer"),
    ("mapping_engine", "app.mappers.mapping_engine"),
    ("docx_renderer", "app.renderers.docx_renderer"),
    ("latex_renderer", "app.renderers.latex_renderer"),
    ("integrity_checker", "app.validation.integrity_checker"),
    ("template_validator", "app.validation.template_validator"),
    ("latex_sandbox", "app.compilation.latex_sandbox"),
    ("main_module", "app.main")
]

for key, modname in modules_to_test:
    try:
        __import__(modname)
        status[key] = "OK"
    except Exception as e:
        status[key] = f"FAIL: {type(e).__name__}: {str(e)}"

@app.get("/api/health")
@app.get("/health")
def health():
    return {
        "status": "ok",
        "internal_modules": status
    }
