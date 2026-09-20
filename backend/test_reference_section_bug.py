import os
import shutil
import tempfile
import zipfile
import unittest
import sys

from app.parsers.docx_parser import DocxParser
from app.models.template_spec import TemplateSpecification
from app.renderers.latex_renderer import LatexRenderer
from app.compilation.pdf_generator import PdfPreviewGenerator

def run_reference_section_bug_test():
    print("=" * 60)
    print("RUNNING RESEARCH PAPER REFERENCE SECTION BUG REGRESSION TEST")
    print("=" * 60)

    docx_path = r"C:\Users\shari\Downloads\Aspect-Aware Malayalam Movie Recommendation Using Sentiment Importance Learning.docx"
    if not os.path.exists(docx_path):
        print(f"[SKIP] Source docx not found at {docx_path}")
        return

    # 1. Parse DOCX
    udm = DocxParser.parse(docx_path)

    # Assertion 1 & 2: Check UDM sections & references
    ref_sec_in_udm = [s.title for s in udm.sections if "reference" in s.title.lower() and "preference" not in s.title.lower()]
    assert len(ref_sec_in_udm) == 0, f"Reference section improperly left in UDM.sections: {ref_sec_in_udm}"
    print("[PASS] 1. Reference section heading 'References for this Related Work' removed from UDM.sections.")

    assert len(udm.references) == 8, f"Expected 8 structured references in UDM, found {len(udm.references)}"
    print(f"[PASS] 2. Extracted {len(udm.references)} structured UDM references.")

    # 2. Render Project
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = os.path.join(temp_dir, "output")
        zip_path = os.path.join(temp_dir, "output.zip")
        spec = TemplateSpecification(document_class="sn-jnl", author_style="springer")

        LatexRenderer.render_project(
            udm=udm,
            spec=spec,
            dest_template_dir="",
            output_dir=output_dir,
            output_zip_path=zip_path
        )

        main_tex_path = os.path.join(output_dir, "main.tex")
        ref_bib_path = os.path.join(output_dir, "references.bib")

        assert os.path.exists(main_tex_path), "main.tex missing from output"
        assert os.path.exists(ref_bib_path), "references.bib missing from output"

        with open(main_tex_path, "r", encoding="utf-8") as f:
            main_tex = f.read()

        with open(ref_bib_path, "r", encoding="utf-8") as f:
            ref_bib = f.read()

        # Assertion 3: references.bib is NOT empty
        assert "% Empty references" not in ref_bib, "references.bib is empty!"
        print("[PASS] 3. references.bib is NOT empty.")

        # Assertion 4: references.bib contains 8 valid BibTeX entries
        entries = [line for line in ref_bib.splitlines() if line.strip().startswith("@")]
        assert len(entries) == 8, f"Expected 8 BibTeX entries, found {len(entries)}"
        print(f"[PASS] 4. references.bib contains {len(entries)} valid BibTeX entries.")

        # Assertion 5 & 6: main.tex bibliography commands
        assert "\\bibliography{references}" in main_tex, "main.tex missing \\bibliography{references}"
        assert "\\bibliographystyle{sn-mathphys-num}" in main_tex, "main.tex missing \\bibliographystyle{sn-mathphys-num}"
        print("[PASS] 5 & 6. main.tex contains \\bibliography{references} and \\bibliographystyle{sn-mathphys-num}.")

        # Assertion 7: No plain text [1]...[8] or \subsection{References for this Related Work} in main.tex
        assert "References for this Related Work" not in main_tex, "Plain text reference subsection heading found in main.tex!"
        assert "[1] S. Hong" not in main_tex, "Plain text reference entry [1] found in main.tex!"
        assert "\\cite{" in main_tex, "No \\cite{} commands found in main.tex!"
        print("[PASS] 7. Plain text reference section and lines removed; \\cite{} commands present in main.tex.")

        # Assertion 8: PDF Generation
        pdf_path = os.path.join(temp_dir, "preview.pdf")
        PdfPreviewGenerator.generate_pdf(udm, pdf_path)
        assert os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0, "PDF generation failed"
        print("[PASS] 8. PDF Preview generated successfully.")

    print("=" * 60)
    print("RESEARCH PAPER REFERENCE SECTION BUG FIX PASSED 100%!")
    print("=" * 60)

if __name__ == "__main__":
    run_reference_section_bug_test()
