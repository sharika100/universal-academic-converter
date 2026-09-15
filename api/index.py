import os
import sys

# Add backend directory to python path for Vercel Serverless Function imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.main import app
