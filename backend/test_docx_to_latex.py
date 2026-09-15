import os
import requests

BASE_URL = "http://127.0.0.1:8000"
SAMPLES_DIR = "C:/Users/shari/.gemini/antigravity/scratch/universal-academic-converter/samples"

def test_docx_to_latex():
    docx_file = os.path.join(SAMPLES_DIR, "sample_manuscript.docx")
    springer_zip = os.path.join(SAMPLES_DIR, "springer_template.zip")
    
    # 1. Analyze Source DOCX
    with open(docx_file, "rb") as f:
        res1 = requests.post(f"{BASE_URL}/api/analyze-source", files={"file": ("sample_manuscript.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert res1.status_code == 200, f"Source analysis failed: {res1.text}"
    src_json = res1.json()
    job_id = src_json["job_id"]
    print("[OK] DOCX Source Analyzed. Job ID:", job_id)
    
    # 2. Analyze Destination Template
    with open(springer_zip, "rb") as f:
        res2 = requests.post(f"{BASE_URL}/api/analyze-template", data={"job_id": job_id}, files={"file": ("springer_template.zip", f, "application/zip")})
    assert res2.status_code == 200, f"Template analysis failed: {res2.text}"
    
    # 3. Convert Document
    res3 = requests.post(f"{BASE_URL}/api/convert", data={"job_id": job_id})
    assert res3.status_code == 200, f"Conversion failed: {res3.text}"
    conv_json = res3.json()
    print("[OK] DOCX -> LaTeX ZIP Converted Successfully!")
    print("  Conformity Estimate:", conv_json["report"]["conformity_estimate"], "%")
    print("  Converted Files:", conv_json["report"]["converted_files"])
    
    # 4. Check PDF download
    res_pdf = requests.get(f"{BASE_URL}/api/download/{job_id}/pdf")
    assert res_pdf.status_code == 200
    print(f"[OK] PDF Preview Downloaded ({len(res_pdf.content)} bytes)")

if __name__ == "__main__":
    test_docx_to_latex()
