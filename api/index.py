import os
import sys

# Ensure api directory and project root are in sys.path for Vercel Python serverless runtime
api_dir = os.path.dirname(os.path.abspath(__file__))
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

root_dir = os.path.abspath(os.path.join(api_dir, ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from app.main import app as fastapi_app
    app = fastapi_app
    application = fastapi_app
    handler = fastapi_app
except Exception as _err:
    import traceback
    print(f"[VERCEL_PYTHON_BOOT_ERROR] Failed to import FastAPI application: {_err}\n{traceback.format_exc()}", file=sys.stderr)
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    fallback_app = FastAPI(title="Universal Converter Fallback API")

    @fallback_app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
    async def fallback_handler(path: str):
        return JSONResponse(
            status_code=500,
            content={
                "error": "VERCEL_BOOT_ERROR",
                "message": "FastAPI application failed to initialize on Vercel Python serverless runtime.",
                "detail": str(_err)
            }
        )

    app = fallback_app
    application = fallback_app
    handler = fallback_app
