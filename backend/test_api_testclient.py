import os
import sys
from fastapi.testclient import TestClient

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from test_figure_author_pipeline import test_pipeline

def test_api_with_client():
    print("Testing API endpoints using FastAPI TestClient...")
    client = TestClient(app)
    
    # 1. Health check
    res = client.get("/api/health")
    assert res.status_code == 200
    print("[OK] /api/health:", res.json())
    
    # 2. Presets
    res = client.get("/api/presets")
    assert res.status_code == 200
    print("[OK] /api/presets:", len(res.json()))
    print("API TEST PASSED!")

if __name__ == "__main__":
    test_pipeline()
    test_api_with_client()
