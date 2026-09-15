import os
import sys
import traceback
from fastapi import FastAPI
from fastapi.responses import JSONResponse

api_dir = os.path.dirname(os.path.abspath(__file__))
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

backend_dir = os.path.abspath(os.path.join(api_dir, "..", "backend"))
if os.path.exists(backend_dir) and backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

IMPORT_SUCCESS = False
IMPORT_ERROR = None
IMPORT_TRACEBACK = None
EXC_OBJ = None

try:
    from app.main import app as real_app
    app = real_app
    IMPORT_SUCCESS = True
except BaseException as e:
    EXC_OBJ = e
    IMPORT_SUCCESS = False
    IMPORT_ERROR = f"{type(e).__name__}: {str(e)}"
    IMPORT_TRACEBACK = traceback.format_exc()
    
    app = FastAPI()

    @app.get("/api/health")
    @app.get("/health")
    def diagnostic_health():
        return JSONResponse(
            status_code=200,
            content={
                "import_success": False,
                "exception_type": type(EXC_OBJ).__name__ if EXC_OBJ else "Unknown",
                "exception": str(EXC_OBJ) if EXC_OBJ else "Unknown",
                "traceback": IMPORT_TRACEBACK,
                "python_version": sys.version,
                "sys_path": sys.path
            }
        )
