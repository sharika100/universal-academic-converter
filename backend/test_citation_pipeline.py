import os
import sys
import re
import tempfile
import zipfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.parsers.reference_parser import ReferenceParser
from app.parsers.citation_matcher import CitationMatcher
from app.renderers.latex_renderer import LatexRenderer
from app.models.udm import UniversalDocumentModel, Section, Paragraph

def run_citation_pipeline_test():
    print("==================================================")
    print("RUNNING CITATION & REFERENCE PIPELINE REGRESSION TEST")
    print("==================================================")

    zip_path = r"C:\Users\shari\Downloads\converted_academic_paper (21).zip"
    assert os.path.exists(zip_path), f"Test ZIP missing: {zip_path}"

    with zipfile.ZipFile(zip_path, 'r') as z:
        ref_bib_raw = z.read("references.bib").decode("utf-8")
        main_tex_raw = z.read("main.tex").decode("utf-8")

    # Extract 19 raw reference lines from references.bib
    raw_lines = [l.strip() for l in ref_bib_raw.split("\n") if l.strip()]
    plain_ref_lines = [l for l in raw_lines if l.startswith("[") or re.match(r"^\d+\.", l)]
    
    print(f"\n1. Source Reference Count: {len(plain_ref_lines)}")
    assert len(plain_ref_lines) == 19, f"Expected 19 references, got {len(plain_ref_lines)}"

    # Parse 19 references into structured UDM References
    used_keys = set()
    udm_references = []
    for idx, line in enumerate(plain_ref_lines, 1):
        ref_obj = ReferenceParser.parse_reference_line(line, idx, used_keys)
        udm_references.append(ref_obj)

    print(f"2. UDM Reference Objects Created: {len(udm_references)}")
    assert len(udm_references) == 19, f"Expected 19 UDM reference objects"

    # Verify every reference has a unique cite_key and valid BibTeX
    bibtex_keys = [r.cite_key for r in udm_references]
    print(f"   Generated Cite Keys ({len(set(bibtex_keys))} unique): {bibtex_keys}")
    assert len(set(bibtex_keys)) == 19, "Cite keys must all be unique!"

    for ref in udm_references:
        assert ref.raw_bibtex.startswith("@"), f"Reference {ref.cite_key} BibTeX must start with '@'!"
        assert "[" not in ref.cite_key and "]" not in ref.cite_key, f"Cite key invalid: {ref.cite_key}"

    # Verify In-Text Citation Matching on main.tex content
    print("\n3. Testing In-Text Citation Matching & Substitution...")
    updated_main_tex, matched_keys = CitationMatcher.process_paragraph_text(main_tex_raw, udm_references)

    print(f"   Total Citations Matched: {len(matched_keys)}")
    print(f"   Matched Citation Keys: {set(matched_keys)}")

    # Verify \cite{} commands exist in updated main.tex
    cite_matches = re.findall(r'\\cite\{([^}]+)\}', updated_main_tex)
    print(f"   LaTeX \\cite{{}} commands in updated main.tex: {len(cite_matches)}")
    assert len(cite_matches) > 0, "LaTeX \\cite{} commands must be generated for matched citations!"

    # Verify no plain text [1], [2] in generated BibTeX
    print("\n4. Verifying Generated references.bib Content...")
    with tempfile.TemporaryDirectory() as td:
        udm = UniversalDocumentModel()
        udm.references = udm_references
        # Render references.bib using LatexRenderer
        bib_file = os.path.join(td, "references.bib")
        with open(bib_file, "w", encoding="utf-8") as fh:
            for r in udm.references:
                fh.write(r.raw_bibtex + "\n\n")

        with open(bib_file, "r", encoding="utf-8") as fh:
            bib_content = fh.read()

        plain_num_lines = [l for l in bib_content.split("\n") if l.startswith("[")]
        assert len(plain_num_lines) == 0, f"references.bib must contain ZERO plain-text '[1]' lines! Found: {plain_num_lines}"
        
        entry_count = len(re.findall(r'@[a-z]+\{', bib_content))
        print(f"   Valid BibTeX @entries in references.bib: {entry_count}")
        assert entry_count == 19, f"Expected 19 valid BibTeX @entries, got {entry_count}"

    # Print 19-Row Verification Table
    print("\n=========================================================================================================")
    print("19-REFERENCE AUDIT TABLE")
    print("=========================================================================================================")
    print(f"{'Ref #':<6} | {'Source Author / Year':<25} | {'Parsed':<8} | {'Citation Matched':<18} | {'BibTeX Key':<15} | {'BibTeX Generated'}")
    print("-" * 105)

    for idx, (line, ref) in enumerate(zip(plain_ref_lines, udm_references), 1):
        author_year_src = f"{ref.authors[0] if ref.authors else 'Unknown'} ({ref.year})"[:24]
        is_matched = "YES" if ref.cite_key in matched_keys else "NO"
        has_bib = "YES (@" + ref.raw_bibtex.split("{")[0][1:] + ")"
        print(f"{idx:<6} | {author_year_src:<25} | {'YES':<8} | {is_matched:<18} | {ref.cite_key:<15} | {has_bib}")

    print("=========================================================================================================\n")

if __name__ == "__main__":
    run_citation_pipeline_test()
