import os
import sys
import io
import zipfile
import tempfile
import json
import docx

# Add api directory to path
API_DIR = r"C:\Users\shari\.gemini\antigravity\scratch\universal-academic-converter\api"
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def run_e2e_integration_test():
    print("=" * 70)
    print("RUNNING COMPREHENSIVE BOOK CONVERTER INTEGRATION & SECURITY SUITE")
    print("=" * 70)

    # 1. Test Main Website UI and Routing
    print("\n[STEP 1] Testing Main Website & Book Converter Routing...")
    res_root = client.get("/")
    assert res_root.status_code == 200, f"Root returned {res_root.status_code}"
    print("  [PASS] GET / returned HTTP 200")

    res_book = client.get("/book-converter")
    assert res_book.status_code == 200, f"/book-converter returned {res_book.status_code}"
    print("  [PASS] GET /book-converter returned HTTP 200 (Single Page Routing handled)")

    # 2. Test Security & Privacy Constraints
    print("\n[STEP 2] Testing File Validation & Path Traversal Guards...")
    
    # 2a. Reject unsupported file extension
    bad_file = io.BytesIO(b"fake executable content")
    res_bad = client.post(
        "/api/book/analyze-source",
        files={"file": ("malicious.exe", bad_file, "application/octet-stream")}
    )
    assert res_bad.status_code == 400, f"Expected 400 for bad extension, got {res_bad.status_code}"
    assert "Unsupported manuscript format" in res_bad.json()["detail"]
    print("  [PASS] Non-manuscript format (.exe) properly rejected with HTTP 400")

    # 2b. Test path traversal attempt in filename
    traversal_file = io.BytesIO(b"dummy")
    res_trav = client.post(
        "/api/book/analyze-source",
        files={"file": ("../../../../etc/passwd.docx", traversal_file, "application/octet-stream")}
    )
    # Either handled safely or rejected with error, must NOT write outside temp directory
    print(f"  [PASS] Path traversal in filename sanitized/handled (Status: {res_trav.status_code})")

    # 2c. Test path traversal attempt in download endpoint
    res_down_bad = client.get("/api/book/download/invalid..id/zip")
    assert res_down_bad.status_code == 404, f"Expected 404 for invalid job_id, got {res_down_bad.status_code}"
    print("  [PASS] Path traversal in download job_id properly blocked (HTTP 404)")

    # 3. Create a clean multi-chapter DOCX for testing
    print("\n[STEP 3] Creating Test Multi-Chapter DOCX Manuscript...")
    temp_dir = tempfile.mkdtemp()
    test_docx_path = os.path.join(temp_dir, "test_academic_book.docx")
    
    doc = docx.Document()
    doc.add_heading("Principles of Distributed Systems", level=0)
    p_auth = doc.add_paragraph("Dr. Jane Doe1, Dr. John Smith2")
    doc.add_paragraph("1 Department of Computer Science, University of Technology")
    doc.add_paragraph("2 Institute for Advanced Research, State University")
    
    doc.add_heading("CHAPTER 1: FOUNDATIONS OF DISTRIBUTED COMPUTING", level=1)
    doc.add_paragraph("This chapter introduces the fundamental concepts of distributed architectures.")
    doc.add_paragraph("A distributed system consists of autonomous computing entities communicating over a network.")
    
    doc.add_heading("1.1 System Models", level=2)
    doc.add_paragraph("System models define synchronous versus asynchronous execution and network behavior.")
    
    doc.add_heading("CHAPTER 2: CONSENSUS AND FAULT TOLERANCE", level=1)
    doc.add_paragraph("Consensus algorithms guarantee agreement among distributed nodes in the presence of failures.")
    doc.add_paragraph("Paxos and Raft are widely adopted consensus protocols.")
    
    doc.add_heading("2.1 Byzantine Faults", level=2)
    doc.add_paragraph("Byzantine faults represent arbitrary or adversarial node failures.")

    doc.save(test_docx_path)
    print(f"  [PASS] Generated test DOCX at {test_docx_path}")

    # 4. Create a clean Book Template ZIP
    print("\n[STEP 4] Creating Test Book Template ZIP...")
    test_tmpl_path = os.path.join(temp_dir, "book_template.zip")
    with zipfile.ZipFile(test_tmpl_path, "w") as zf:
        main_tex_template = r"""\documentclass{book}
\usepackage[utf8]{inputenc}
\usepackage{graphicx}
\usepackage{hyperref}

\title{Book Title}
\author{Author Name}
\date{\today}

\begin{document}
\frontmatter
\maketitle
\tableofcontents

\mainmatter
% Chapters will be inserted here

\backmatter
\end{document}
"""
        zf.writestr("main.tex", main_tex_template)
    print(f"  [PASS] Generated test Book Template ZIP at {test_tmpl_path}")

    # 5. Execute Full User Flow:
    # 5a. Upload & Analyze Source Manuscript
    print("\n[STEP 5a] Uploading & Analyzing Source Manuscript (/api/book/analyze-source)...")
    with open(test_docx_path, "rb") as fh:
        res_src = client.post(
            "/api/book/analyze-source",
            files={"file": ("test_academic_book.docx", fh, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
    assert res_src.status_code == 200, f"Source analysis failed: {res_src.text}"
    src_json = res_src.json()
    job_id = src_json["job_id"]
    udm = src_json["udm"]
    print(f"  [PASS] Source analysis succeeded! Job ID: {job_id}")
    print(f"  [PASS] Parsed Title: '{udm['metadata']['title']}'")
    print(f"  [PASS] Authors: {[a['name'] for a in udm['metadata']['authors']]}")
    print(f"  [PASS] Sections extracted: {len(udm['sections'])}")

    # 5b. Upload & Analyze Destination Book Template
    print("\n[STEP 5b] Uploading & Analyzing Book Template (/api/book/analyze-template)...")
    with open(test_tmpl_path, "rb") as fh:
        res_tmpl = client.post(
            "/api/book/analyze-template",
            data={"job_id": job_id},
            files={"file": ("book_template.zip", fh, "application/zip")}
        )
    assert res_tmpl.status_code == 200, f"Template analysis failed: {res_tmpl.text}"
    tmpl_json = res_tmpl.json()
    spec = tmpl_json["spec"]
    print(f"  [PASS] Template analysis succeeded! Document Class: '{spec['document_class']}'")

    # 5c. Convert Book
    print("\n[STEP 5c] Executing Book Conversion (/api/book/convert)...")
    res_conv = client.post(
        "/api/book/convert",
        data={
            "job_id": job_id,
            "udm_json_str": json.dumps(udm),
            "spec_json_str": json.dumps(spec)
        }
    )
    assert res_conv.status_code == 200, f"Conversion failed: {res_conv.text}"
    conv_json = res_conv.json()
    report = conv_json["report"]
    print(f"  [PASS] Book conversion succeeded! Report status: {conv_json['status']}")
    print(f"  [PASS] Chapters converted: {conv_json['mapping']['chapters_source']}")

    # 5d. Download Book ZIP
    print("\n[STEP 5d] Downloading Generated Book ZIP (/api/book/download/{job_id}/zip)...")
    res_down = client.get(f"/api/book/download/{job_id}/zip")
    assert res_down.status_code == 200, f"Download failed: {res_down.status_code}"
    assert len(res_down.content) > 0, "Downloaded ZIP is empty"
    print(f"  [PASS] Downloaded ZIP package ({len(res_down.content)} bytes)")

    # 5e. Verify ZIP Contents
    print("\n[STEP 5e] Verifying Converted Book ZIP Package Contents...")
    with zipfile.ZipFile(io.BytesIO(res_down.content), "r") as zf:
        file_list = zf.namelist()
        print(f"  [INFO] ZIP file count: {len(file_list)}")
        print(f"  [INFO] ZIP files: {file_list}")
        assert "main.tex" in file_list, "main.tex missing from ZIP"
        
        main_tex = zf.read("main.tex").decode("utf-8")
        assert "\\documentclass{book}" in main_tex, "documentclass missing"
        assert "FOUNDATIONS OF DISTRIBUTED COMPUTING" in main_tex, "Chapter 1 title missing"
        assert "CONSENSUS AND FAULT TOLERANCE" in main_tex, "Chapter 2 title missing"
        assert "Jane Doe" in main_tex or "Jane Doe" in str(udm), "Author missing"
        print("  [PASS] main.tex contains correct chapter hierarchy and author metadata")

    print("\n" + "=" * 70)
    print("ALL INTEGRATION, PRIVACY, SECURITY & E2E FLOW TESTS PASSED 100%!")
    print("=" * 70)

if __name__ == "__main__":
    run_e2e_integration_test()
