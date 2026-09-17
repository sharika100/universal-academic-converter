import os
import sys
import logging
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vercel_api_index")

api_dir = os.path.dirname(os.path.abspath(__file__))
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

try:
    from app.main import app
except Exception as e:
    tb = traceback.format_exc()
    logger.error(f"Failed to import app.main: {e}\n{tb}")
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    app = FastAPI()
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
    def index_error(path: str):
        return JSONResponse(status_code=500, content={
            "error": "VERCEL_IMPORT_ERROR",
            "message": str(e),
            "traceback": tb.split("\n")
        })
