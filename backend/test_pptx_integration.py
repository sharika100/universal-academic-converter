import os
import sys
import zipfile
import io
from fastapi.testclient import TestClient

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app

SAMPLE_PPTX = os.path.abspath(os.path.join(os.path.dirname(__file__), "app", "samples", "sample_presentation.pptx"))
SAMPLE_ZIP = os.path.abspath(os.path.join(os.path.dirname(__file__), "app", "samples", "beamer_template.zip"))

DC_PPTX = r"C:\teaching\phd\implementation\DC MEETING\PPT V1.pptx"
UOM_ZIP = r"C:\Users\shari\Downloads\University_of_Manchester_presentation_template__ltx_talk_based_.zip"

def test_pptx_api_endpoints():
    client = TestClient(app)
    
    # 1. Health check
    h_res = client.get("/api/pptx/health")
    assert h_res.status_code == 200
    data = h_res.json()
    assert data["status"] == "healthy"
    assert data["service"] == "pptx-latex-template-converter"
    print("[PASS] /api/pptx/health")

    # 2. Analyze template endpoint
    assert os.path.exists(SAMPLE_ZIP), f"Missing {SAMPLE_ZIP}"
    with open(SAMPLE_ZIP, "rb") as f:
        a_res = client.post(
            "/api/pptx/analyze-template",
            files={"template_file": ("beamer_template.zip", f, "application/zip")}
        )
    assert a_res.status_code == 200
    a_data = a_res.json()
    assert a_data["success"] is True
    assert a_data["spec"]["document_class"] == "cleanpresentation"
    print("[PASS] /api/pptx/analyze-template")

    # 3. Convert endpoint
    assert os.path.exists(SAMPLE_PPTX), f"Missing {SAMPLE_PPTX}"
    with open(SAMPLE_PPTX, "rb") as f_ppt, open(SAMPLE_ZIP, "rb") as f_tmpl:
        c_res = client.post(
            "/api/pptx/convert",
            files={
                "pptx_file": ("sample_presentation.pptx", f_ppt, "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
                "template_file": ("beamer_template.zip", f_tmpl, "application/zip")
            }
        )
    assert c_res.status_code == 200
    c_data = c_res.json()
    assert c_data["success"] is True
    assert c_data["summary"]["slide_count"] == 4
    assert c_data["summary"]["extracted_images"] >= 1
    assert c_data["summary"]["converted_tables"] >= 1
    job_id = c_data["job_id"]
    print(f"[PASS] /api/pptx/convert: job_id={job_id}")

    # 4. Download endpoint
    d_res = client.get(f"/api/pptx/download/{job_id}")
    assert d_res.status_code == 200
    assert d_res.headers["content-type"] == "application/zip"
    assert len(d_res.content) > 1000
    
    with zipfile.ZipFile(io.BytesIO(d_res.content), "r") as zf:
        namelist = zf.namelist()
        assert "main.tex" in namelist
        assert "conversion_report.json" in namelist
        assert "conversion_report.txt" in namelist
    print("[PASS] /api/pptx/download ZIP verified")

def test_pptx_real_world_dc_meeting():
    if not (os.path.exists(DC_PPTX) and os.path.exists(UOM_ZIP)):
        print("Skipping DC Meeting real-world test (files not present in environment)")
        return

    client = TestClient(app)
    with open(DC_PPTX, "rb") as f_ppt, open(UOM_ZIP, "rb") as f_tmpl:
        c_res = client.post(
            "/api/pptx/convert",
            files={
                "pptx_file": ("PPT_V1.pptx", f_ppt, "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
                "template_file": ("uom_template.zip", f_tmpl, "application/zip")
            }
        )
    assert c_res.status_code == 200
    c_data = c_res.json()
    assert c_data["success"] is True
    assert c_data["summary"]["slide_count"] == 27
    assert c_data["summary"]["generated_frames"] == 27
    assert c_data["summary"]["converted_tables"] == 11
    assert c_data["summary"]["extracted_images"] == 4

    job_id = c_data["job_id"]
    d_res = client.get(f"/api/pptx/download/{job_id}")
    assert d_res.status_code == 200

    with zipfile.ZipFile(io.BytesIO(d_res.content), "r") as zf:
        namelist = zf.namelist()
        assert "main.tex" in namelist
        assert "images/slide12_block_diagram.png" in namelist
        assert "images/slide17_block_diagram.png" in namelist

        with zf.open("main.tex") as mf:
            tex_content = mf.read().decode("utf-8")
            assert "slide12_block_diagram" in tex_content
            assert "slide17_block_diagram" in tex_content
            assert tex_content.count(r"\begin{frame}") == 27

    print("[PASS] DC Meeting Real-World Acceptance Test with Block Diagrams PASSED 100%!")

if __name__ == "__main__":
    test_pptx_api_endpoints()
    test_pptx_real_world_dc_meeting()
