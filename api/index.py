import os
import sys

# Ensure api directory and project root are in sys.path for Vercel Python serverless runtime
api_dir = os.path.dirname(os.path.abspath(__file__))
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

root_dir = os.path.abspath(os.path.join(api_dir, ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app.main import app as _fastapi_app

app = _fastapi_app
application = app
handler = app


