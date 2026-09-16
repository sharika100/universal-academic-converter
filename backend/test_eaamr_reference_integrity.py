import os
import sys
import tempfile
import zipfile
import re
import json

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from app.parsers.latex_parser import LatexParser
from app.template_engine.analyzer import TemplateAnalyzer
from app.renderers.latex_renderer import LatexRenderer
from app.validation.template_validator import TemplateValidator
from app.compilation.latex_sandbox import LatexSandbox

def run_reference_integrity_test():
    print("\n==================================================")
    print("RUNNING REFERENCE & CITATION INTEGRITY ACCEPTANCE TEST")
    print("==================================================\n")

    eaamr_zip = r"C:\Users\shari\Downloads\FINAL_EAAMR_JOURNAL_ESWA_JOURNAL.zip"
    springer_zip = os.path.join(os.path.dirname(__file__), "app", "samples", "springer_template.zip")

    assert os.path.exists(eaamr_zip), f"EAAMR source ZIP missing: {eaamr_zip}"
    assert os.path.exists(springer_zip), f"Springer template ZIP missing: {springer_zip}"

    with tempfile.TemporaryDirectory(prefix="ref_test_") as td:
        src_dir = os.path.join(td, "src")
        dest_dir = os.path.join(td, "dest")
        out_dir = os.path.join(td, "out")
        zip_out = os.path.join(td, "converted.zip")
        pdf_out = os.path.join(td, "preview.pdf")

        with zipfile.ZipFile(eaamr_zip, "r") as zf:
            zf.extractall(src_dir)
        with zipfile.ZipFile(springer_zip, "r") as zf:
            zf.extractall(dest_dir)

        # 1. Source Diagnostic
        with open(os.path.join(src_dir, "EAAMRWITHAUTHOR.tex"), "r", encoding="utf-8", errors="ignore") as fh:
            src_tex = fh.read()

        uncommented_src = re.sub(r'%\s*\n', '\n', src_tex)
        uncommented_src = re.sub(r'%.*', '', uncommented_src)
        src_citations = re.findall(r'\\(cite[a-z]*)(?:\[[^\]]*\])?\{([^}]+)\}', uncommented_src)
        src_cited_keys = set(k.strip() for _, ks in src_citations for k in ks.split(','))

        src_bib_p = os.path.join(src_dir, "cas-refs.bib")
        with open(src_bib_p, "r", encoding="utf-8", errors="ignore") as fh:
            src_bib_text = fh.read()
        src_bib_keys = re.findall(r'@\w+\s*\{\s*([^,\s]+)\s*,', src_bib_text)

        # 2. Render Converted Project
        udm = LatexParser.parse_project(src_dir)
        spec = TemplateAnalyzer.analyze_destination_template(dest_dir)
        created_files = LatexRenderer.render_project(udm, spec, dest_dir, out_dir, zip_out)

        # 3. Output Diagnostic
        with open(os.path.join(out_dir, "main.tex"), "r", encoding="utf-8", errors="ignore") as fh:
            gen_tex = fh.read()
        with open(os.path.join(out_dir, "references.bib"), "r", encoding="utf-8", errors="ignore") as fh:
            gen_bib_text = fh.read()

        gen_citations = re.findall(r'\\(cite[a-z]*)(?:\[[^\]]*\])?\{([^}]+)\}', gen_tex)
        gen_cited_keys = set(k.strip() for _, ks in gen_citations for k in ks.split(','))
        gen_bib_keys = re.findall(r'@\w+\s*\{\s*([^,\s]+)\s*,', gen_bib_text)

        missing_citations = list(src_cited_keys - gen_cited_keys)
        missing_bib_entries = list(gen_cited_keys - set(gen_bib_keys))
        undefined_citations = [k for k in gen_cited_keys if k not in gen_bib_keys]
        orphan_bib_entries = list(set(gen_bib_keys) - gen_cited_keys)

        # 4. Sandbox Compilation
        compiled, log_out = LatexSandbox.compile_project(out_dir, "main.tex", udm, pdf_out)

        report = {
            "source_citations": len(src_citations),
            "generated_citations": len(gen_citations),
            "source_bib_entries": len(src_bib_keys),
            "generated_bib_entries": len(gen_bib_keys),
            "missing_citations": missing_citations,
            "missing_bib_entries": missing_bib_entries,
            "undefined_citations": undefined_citations,
            "orphan_bib_entries": len(orphan_bib_entries),
            "bibliography_rendered": os.path.exists(os.path.join(out_dir, "references.bib")) and len(gen_bib_keys) > 0,
            "compilation_success": compiled
        }

        print("REFERENCE INTEGRITY REPORT:")
        print(json.dumps(report, indent=2))

        assert report["generated_citations"] == report["source_citations"], "In-text citations count mismatch!"
        assert report["generated_bib_entries"] == report["source_bib_entries"], "BibTeX entries count mismatch!"
        assert len(report["missing_citations"]) == 0, f"Missing citations: {report['missing_citations']}"
        assert len(report["undefined_citations"]) == 0, f"Undefined citations: {report['undefined_citations']}"
        assert report["bibliography_rendered"] is True, "Bibliography failed to render!"
        assert report["compilation_success"] is True, "Compilation failed!"

        print("\n==================================================")
        print("ALL CITATION & REFERENCE INTEGRITY TESTS PASSED 100%!")
        print("==================================================\n")

if __name__ == "__main__":
    run_reference_integrity_test()
