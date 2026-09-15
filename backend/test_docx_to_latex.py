import os
import requests

BASE_URL = "http://127.0.0.1:8000"
SAMPLES_DIR = "C:/Users/shari/.gemini/antigravity/scratch/universal-academic-converter/backend/app/samples"

def test_docx_to_latex():
    docx_path = os.path.join(SAMPLES_DIR, "sample_manuscript.docx")
    springer_zip = os.path.join(SAMPLES_DIR, "springer_template.zip")
    
    print("[TEST] Testing DOCX Source + Springer LaTeX ZIP Template Conversion...")
    
    # 1. Analyze Source (DOCX)
    with open(docx_path, "rb") as f:
        res1 = requests.post(f"{BASE_URL}/api/analyze-source", files={"file": ("sample_manuscript.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert res1.status_code == 200, f"Source DOCX analysis failed: {res1.text}"
    src_json = res1.json()
    job_id = src_json["job_id"]
    print("[OK] Source DOCX Analyzed. Job ID:", job_id)
    print("  Title:", src_json["udm"]["metadata"]["title"])
    print("  Sections extracted:", len(src_json["udm"]["sections"]))
    
    # 2. Analyze Template (LaTeX ZIP)
    with open(springer_zip, "rb") as f:
        res2 = requests.post(f"{BASE_URL}/api/analyze-template", data={"job_id": job_id}, files={"file": ("springer_template.zip", f, "application/zip")})
    assert res2.status_code == 200, f"Template analysis failed: {res2.text}"
    dest_json = res2.json()
    print("[OK] Destination LaTeX ZIP Template Analyzed. Document Class:", dest_json["spec"]["document_class"])
    
    # 3. Convert Document (DOCX -> LaTeX ZIP)
    res3 = requests.post(f"{BASE_URL}/api/convert", data={"job_id": job_id})
    assert res3.status_code == 200, f"Conversion failed: {res3.text}"
    conv_json = res3.json()
    print("[OK] DOCX -> LaTeX ZIP Document Converted Successfully!")
    print("  Conformity Estimate:", conv_json["report"]["conformity_estimate"], "%")
    print("  Converted Files:", conv_json["report"]["converted_files"])
    
    # 4. Check PDF Preview Download
    res_pdf = requests.get(f"{BASE_URL}/api/download/{job_id}/pdf")
    assert res_pdf.status_code == 200, f"PDF preview download failed: {res_pdf.text}"
    print(f"[OK] PDF Preview Downloaded ({len(res_pdf.content)} bytes)")
    
    # 5. Check Output ZIP Download
    res_zip = requests.get(f"{BASE_URL}/api/download/{job_id}/zip")
    assert res_zip.status_code == 200, "Converted Project ZIP download failed"
    print(f"[OK] Converted LaTeX Project ZIP Downloaded ({len(res_zip.content)} bytes)")

if __name__ == "__main__":
    test_docx_to_latex()
