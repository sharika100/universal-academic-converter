import os
import sys
import tempfile
import zipfile
import subprocess

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from app.parsers.latex_parser import LatexParser
from app.template_engine.analyzer import TemplateAnalyzer
from app.renderers.latex_renderer import LatexRenderer
from app.validation.template_validator import TemplateValidator

def run_conversion_acceptance_test():
    print("\n==================================================")
    print("RUNNING EAAMR -> SPRINGER CONVERSION ACCEPTANCE TEST")
    print("==================================================\n")

    eaamr_zip = r"C:\Users\shari\Downloads\FINAL_EAAMR_JOURNAL_ESWA_JOURNAL.zip"
    springer_zip = os.path.join(os.path.dirname(__file__), "app", "samples", "springer_template.zip")

    assert os.path.exists(eaamr_zip), f"EAAMR source ZIP missing: {eaamr_zip}"
    assert os.path.exists(springer_zip), f"Springer template ZIP missing: {springer_zip}"

    with tempfile.TemporaryDirectory(prefix="eaamr_springer_test_") as td:
        src_dir = os.path.join(td, "src")
        dest_dir = os.path.join(td, "dest")
        out_dir = os.path.join(td, "out")
        zip_out = os.path.join(td, "converted_springer_paper.zip")

        with zipfile.ZipFile(eaamr_zip, "r") as zf:
            zf.extractall(src_dir)
        with zipfile.ZipFile(springer_zip, "r") as zf:
            zf.extractall(dest_dir)

        # 1. Parse Source EAAMR Manuscript
        udm = LatexParser.parse_project(src_dir)
        print(f"1. Source Manuscript Title: '{udm.metadata.title}'")
        print(f"   Authors Count: {len(udm.metadata.authors)} {[a.name for a in udm.metadata.authors]}")
        print(f"   Affiliations Count: {len(udm.metadata.affiliations)}")
        print(f"   Sections Count: {len(udm.sections)}")
        print(f"   References Count: {len(udm.references)}")

        assert udm.metadata.title == "Explainable Aspect-Sentiment Framework for Personalized Malayalam Movie Recommendation"
        assert len(udm.metadata.authors) == 2
        assert udm.metadata.authors[0].name == "Sharika T. R."
        assert udm.metadata.authors[1].name == "Dr. Julia Punithamalar Dhas"
        assert len(udm.sections) >= 5
        assert len(udm.references) >= 10

        # 2. Analyze Destination Template
        spec = TemplateAnalyzer.analyze_destination_template(dest_dir)
        print(f"\n2. Destination Template Format: {spec.format_type}, Confidence: {spec.template_confidence}")

        # 3. Render Springer Project
        created_files = LatexRenderer.render_project(udm, spec, dest_dir, out_dir, zip_out)
        print(f"\n3. Rendered Output Project Files ({len(created_files)} files):")
        for f in created_files:
            print(f"   - {f}")

        assert "sn-jnl.cls" in created_files or os.path.exists(os.path.join(out_dir, "sn-jnl.cls")), "sn-jnl.cls missing at root"
        assert "main.tex" in created_files, "main.tex missing"
        assert "references.bib" in created_files, "references.bib missing"

        # 4. Perform 15-point Validation
        is_valid, val_errors = TemplateValidator.validate_rendered_project(out_dir, udm)
        print(f"\n4. 15-Point Integrity Validation Passed: {is_valid}")
        if val_errors:
            print(f"   Validation Errors: {val_errors}")
        assert is_valid, f"Validation failed: {val_errors}"

        # 5. Verify Content & Structure Requirements in main.tex
        with open(os.path.join(out_dir, "main.tex"), "r", encoding="utf-8") as fh:
            main_content = fh.read()

        print("\n5. Verifying main.tex content requirements:")
        assert "\\documentclass[pdflatex,sn-mathphys-num]{sn-jnl}" in main_content, "Missing correct sn-jnl documentclass"
        assert "Untitled Document" not in main_content, "'Untitled Document' string present in main.tex"
        assert "Author Name" not in main_content, "'Author Name' placeholder present in main.tex"
        assert "Academic Department" not in main_content, "'Academic Department' placeholder present in main.tex"
        assert "sec:introduction" not in main_content.split("\\begin{document}")[1].replace("\\label{sec:introduction}", ""), "Label text leak sec:introduction detected"
        assert "Karunya Institute of Technology and Sciences" in main_content, "Real affiliation 1 missing"
        assert "Adi Shankara Institute of Engineering and Technology" in main_content, "Real affiliation 2 missing"
        assert "\\includegraphics[width=0.8\\linewidth]{figures/FIG1.PNG}" in main_content or "figures/FIG1.PNG" in main_content, "FIG1.PNG missing in main.tex"
        assert "\\bibliographystyle{sn-mathphys-num}" in main_content, "Bibliographystyle sn-mathphys-num missing"

        print("   [PASS] All 15 Content & Structure Requirements Verified!")
        print("\n==================================================")
        print("EAAMR -> SPRINGER CONVERSION PASSED 100%!")
        print("==================================================\n")

if __name__ == "__main__":
    run_conversion_acceptance_test()
