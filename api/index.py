from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

import_status = {}

try:
    import docx
    import_status["docx"] = "OK"
except Exception as e:
    import_status["docx"] = str(e)

try:
    import pylatexenc
    import_status["pylatexenc"] = "OK"
except Exception as e:
    import_status["pylatexenc"] = str(e)

try:
    import reportlab
    import_status["reportlab"] = "OK"
except Exception as e:
    import_status["reportlab"] = str(e)

try:
    import lxml
    import_status["lxml"] = "OK"
except Exception as e:
    import_status["lxml"] = str(e)

try:
    import PIL
    import_status["pillow"] = "OK"
except Exception as e:
    import_status["pillow"] = str(e)

try:
    from app.main import app as backend_app
    import_status["backend_app"] = "OK"
    app = backend_app
except Exception as e:
    import_status["backend_app"] = str(e)

    @app.get("/api/health")
    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "import_status": import_status
        }
