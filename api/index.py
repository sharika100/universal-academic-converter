import os
import sys
from fastapi import FastAPI
from fastapi.responses import JSONResponse

api_dir = os.path.dirname(os.path.abspath(__file__))
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

app = FastAPI()
diag = {}

try:
    import docx
    diag["docx"] = "OK"
except Exception as e:
    diag["docx"] = str(e)

try:
    import pylatexenc
    diag["pylatexenc"] = "OK"
except Exception as e:
    diag["pylatexenc"] = str(e)

try:
    import reportlab
    diag["reportlab"] = "OK"
except Exception as e:
    diag["reportlab"] = str(e)

try:
    import lxml
    diag["lxml"] = "OK"
except Exception as e:
    diag["lxml"] = str(e)

try:
    import PIL
    diag["PIL"] = "OK"
except Exception as e:
    diag["PIL"] = str(e)

try:
    import app.models.udm
    diag["udm"] = "OK"
except Exception as e:
    diag["udm"] = str(e)

try:
    import app.parsers.docx_parser
    diag["docx_parser"] = "OK"
except Exception as e:
    diag["docx_parser"] = str(e)

try:
    import app.parsers.latex_parser
    diag["latex_parser"] = "OK"
except Exception as e:
    diag["latex_parser"] = str(e)

try:
    import app.renderers.docx_renderer
    diag["docx_renderer"] = "OK"
except Exception as e:
    diag["docx_renderer"] = str(e)

try:
    import app.renderers.latex_renderer
    diag["latex_renderer"] = "OK"
except Exception as e:
    diag["latex_renderer"] = str(e)

try:
    import app.compilation.pdf_generator
    diag["pdf_generator"] = "OK"
except Exception as e:
    diag["pdf_generator"] = str(e)

try:
    from app.main import app as real_app
    diag["app_main"] = "OK"
    app = real_app
except Exception as e:
    diag["app_main"] = str(e)

@app.get("/api/health")
@app.get("/health")
def health():
    return {
        "status": "ok",
        "diagnostics": diag
    }
