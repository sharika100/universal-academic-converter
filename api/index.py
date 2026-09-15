import os
import sys
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse

api_dir = os.path.dirname(os.path.abspath(__file__))
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

backend_dir = os.path.abspath(os.path.join(api_dir, "..", "backend"))
if os.path.exists(backend_dir) and backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app as backend_app

app = FastAPI()

@app.get("/debug-scope")
@app.get("/api/debug-scope")
def debug_scope(request: Request):
    return {
        "url_path": request.url.path,
        "scope_path": request.scope.get("path"),
        "scope_root_path": request.scope.get("root_path"),
        "scope_raw_path": request.scope.get("raw_path").decode("utf-8") if request.scope.get("raw_path") else None,
        "headers": dict(request.headers)
    }

# Mount backend_app under FastAPI or delegate all routes
app.mount("/", backend_app)
