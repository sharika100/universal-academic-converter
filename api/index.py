import os
import sys

# Add backend directory to python path for Vercel Serverless Function imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

try:
    from app.main import app
except Exception as e:
    import logging
    logging.exception("Failed to import backend app in api/index.py")
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    app = FastAPI()
    
    @app.api_route("/{catchall:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
    def startup_error(catchall: str = ""):
        return JSONResponse(
            status_code=500,
            content={
                "error": "Backend Startup Failed",
                "detail": str(e),
                "type": type(e).__name__
            }
        )
