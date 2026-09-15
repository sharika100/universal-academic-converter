import os
import requests

BASE_URL = "http://127.0.0.1:8000"
SAMPLES_DIR = "C:/Users/shari/.gemini/antigravity/scratch/universal-academic-converter/samples"

def test_e2e():
    ieee_zip = os.path.join(SAMPLES_DIR, "ieee_paper.zip")
    springer_zip = os.path.join(SAMPLES_DIR, "springer_template.zip")
    
    # 1. Analyze Source
    with open(ieee_zip, "rb") as f:
        res1 = requests.post(f"{BASE_URL}/api/analyze-source", files={"file": ("ieee_paper.zip", f, "application/zip")})
    assert res1.status_code == 200, f"Source analysis failed: {res1.text}"
    src_json = res1.json()
    job_id = src_json["job_id"]
    print("[OK] Source Analyzed. Job ID:", job_id)
    print("  Title:", src_json["udm"]["metadata"]["title"])
    print("  Confidence:", src_json["confidence"])
    
    # 2. Analyze Template
    with open(springer_zip, "rb") as f:
        res2 = requests.post(f"{BASE_URL}/api/analyze-template", data={"job_id": job_id}, files={"file": ("springer_template.zip", f, "application/zip")})
    assert res2.status_code == 200, f"Template analysis failed: {res2.text}"
    dest_json = res2.json()
    print("[OK] Destination Template Analyzed.")
    print("  Class:", dest_json["spec"]["document_class"])
    
    # 3. Convert Document
    res3 = requests.post(f"{BASE_URL}/api/convert", data={"job_id": job_id})
    assert res3.status_code == 200, f"Conversion failed: {res3.text}"
    conv_json = res3.json()
    print("[OK] Document Converted Successfully!")
    print("  Conformity Estimate:", conv_json["report"]["conformity_estimate"], "%")
    print("  Match Status:", conv_json["report"]["integrity"]["match_status"])
    print("  Converted Files:", conv_json["report"]["converted_files"])
    
    # 4. Check Download PDF & ZIP
    res_pdf = requests.get(f"{BASE_URL}/api/download/{job_id}/pdf")
    print("PDF status code:", res_pdf.status_code)
    if res_pdf.status_code != 200:
        print("PDF response text:", res_pdf.text)
    assert res_pdf.status_code == 200, f"PDF download failed: {res_pdf.text}"
    print(f"[OK] PDF Preview Downloaded ({len(res_pdf.content)} bytes)")
    
    res_zip = requests.get(f"{BASE_URL}/api/download/{job_id}/zip")
    assert res_zip.status_code == 200, "ZIP download failed"
    print(f"[OK] Converted Project ZIP Downloaded ({len(res_zip.content)} bytes)")

if __name__ == "__main__":
    test_e2e()
