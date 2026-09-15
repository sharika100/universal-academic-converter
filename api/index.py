import os
import sys

# Add api directory to sys.path so Vercel serverless environment resolves the bundled 'app' package
api_dir = os.path.dirname(os.path.abspath(__file__))
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

backend_dir = os.path.abspath(os.path.join(api_dir, "..", "backend"))
if os.path.exists(backend_dir) and backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app
