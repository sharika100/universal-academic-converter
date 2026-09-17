import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.parsers.docx_parser import DocxParser
from app.book_engine.book_template_analyzer import BookTemplateAnalyzer
from app.book_engine.book_mapping_engine import BookMappingEngine
from app.book_engine.book_latex_renderer import BookLatexRenderer
from app.book_engine.book_template_validator import BookTemplateValidator
from app.compilation.pdf_generator import PdfPreviewGenerator

def run_book_converter_acceptance_test():
    print("==================================================")
    print("RUNNING ISOLATED BOOK CONVERTER ACCEPTANCE TEST")
    print("==================================================")

    source_docx = r"C:\teaching\book article\Role of Technology in a Hybrid Teaching Mode.docx"
    amber_zip = r"C:\Users\shari\Downloads\Basic_book_template__by_Amber_Jain_.zip"

    assert os.path.exists(source_docx), f"Source DOCX missing: {source_docx}"
    assert os.path.exists(amber_zip), f"Amber Jain ZIP missing: {amber_zip}"

    # 1. Parse Source Book Manuscript (DOCX)
    udm = DocxParser.parse(source_docx)
    print(f"\n1. Source Manuscript Title: '{udm.metadata.title}'")
    print(f"   Authors Count: {len(udm.metadata.authors)} {[a.name for a in udm.metadata.authors]}")
    print(f"   Affiliations Count: {len(udm.metadata.affiliations)}")
    print(f"   Sections (Chapters) Count: {len(udm.sections)} {[s.title for s in udm.sections]}")

    assert udm.metadata.title == "Role of Technology in a Hybrid Teaching Mode", "Title must be parsed correctly!"
    assert len(udm.metadata.authors) == 1 and udm.metadata.authors[0].name == "SHARIKA T R", "Author must be SHARIKA T R!"
    assert len(udm.sections) == 8, f"Expected 8 chapters/sections, got {len(udm.sections)}"

    # 2. Analyze Target Book Template
    with tempfile.TemporaryDirectory(prefix="book_test_") as td:
        tmpl_dir = os.path.join(td, "tmpl")
        out_dir = os.path.join(td, "out")
        os.makedirs(tmpl_dir, exist_ok=True)
        os.makedirs(out_dir, exist_ok=True)

        with zipfile.ZipFile(amber_zip, 'r') as zf:
            zf.extractall(tmpl_dir)

        spec = BookTemplateAnalyzer.analyze_book_template(tmpl_dir)
        print(f"\n2. Target Book Template Document Class: '{spec.document_class}'")
        print(f"   Chapter Command: '{spec.chapter_command}'")
        print(f"   Has Frontmatter? {spec.has_frontmatter}")
        print(f"   Detected Sample Titles: {spec.sample_title_strings}")
        print(f"   Detected Sample Authors: {spec.sample_author_strings}")

        # 3. Render Target Book Project
        zip_out = os.path.join(td, "converted_book.zip")
        created_files = BookLatexRenderer.render_book_project(
            udm=udm,
            spec=spec,
            dest_template_dir=tmpl_dir,
            output_dir=out_dir,
            output_zip_path=zip_out
        )

        print(f"\n3. Rendered Output Project Files ({len(created_files)} files):")
        for f in created_files[:10]:
            print(f"   - {f}")

        assert os.path.exists(zip_out), "Output ZIP must exist!"

        main_tex_path = os.path.join(out_dir, "main.tex")
        with open(main_tex_path, "r", encoding="utf-8") as fh:
            main_tex = fh.read()

        # 4. Validate Integrity & Zero Sample Content Leakage
        val_res = BookTemplateValidator.validate_book_output(
            main_tex_content=main_tex,
            udm=udm,
            spec=spec,
            output_dir=out_dir
        )

        print("\n4. Book Output Validation Results:")
        for chk in val_res["checks"]:
            print("  ", chk)

        assert val_res["overall_passed"], "Book output validation must pass!"
        assert not val_res["sample_content_leaked"], "ZERO sample content leakage allowed!"

        # 5. Verify Content Preservation
        print("\n5. Verifying main.tex content requirements:")
        assert "\\author{\\textsc{SHARIKA T R}}" in main_tex or "SHARIKA T R" in main_tex, "Source author SHARIKA T R must be present!"
        assert "First-name Last-name" not in main_tex, "Sample author 'First-name Last-name' must be removed!"
        assert "Sample Book Title" not in main_tex, "Sample title 'Sample Book Title' must be removed!"
        assert "\\chapter{Introduction}" in main_tex, "Introduction chapter must exist!"
        assert "\\chapter{Conclusion}" in main_tex, "Conclusion chapter must exist!"
        print("   [PASS] All Book Content & Integrity Checks Verified!")

    print("\n==================================================")
    print("ISOLATED BOOK CONVERTER TEST PASSED 100%!")
    print("==================================================\n")

if __name__ == "__main__":
    run_book_converter_acceptance_test()
