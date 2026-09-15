import os
import sys
import tempfile
import hashlib
import docx
from docx.shared import Inches
from PIL import Image, ImageDraw

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.udm import UniversalDocumentModel, Author, Affiliation
from app.models.template_spec import TemplateSpecification
from app.parsers.docx_parser import DocxParser
from app.renderers.latex_renderer import LatexRenderer
from app.compilation.latex_sandbox import LatexSandbox

def run_regression_tests():
    temp_dir = tempfile.mkdtemp(prefix="docx_regression_")
    print(f"=== RUNNING DOCX REGRESSION SUITE IN {temp_dir} ===")

    # -------------------------------------------------------------
    # TEST 1: Simple DOCX with normal paragraphs
    # -------------------------------------------------------------
    docx1 = os.path.join(temp_dir, "test1_simple.docx")
    doc1 = docx.Document()
    doc1.add_heading("Simple Academic Paper", level=0)
    doc1.add_paragraph("Alice Smith")
    doc1.add_paragraph("Department of CS, Stanford")
    doc1.add_heading("1. Introduction", level=1)
    doc1.add_paragraph("This is a simple paragraph text in section 1.")
    doc1.save(docx1)
    
    udm1 = DocxParser.parse(docx1)
    assert udm1.metadata.title == "Simple Academic Paper"
    assert len(udm1.sections) >= 1
    print("[PASS] TEST 1: Simple DOCX with normal paragraphs")

    # -------------------------------------------------------------
    # TEST 2: DOCX with multiple authors and affiliations
    # -------------------------------------------------------------
    docx2 = os.path.join(temp_dir, "test2_authors.docx")
    doc2 = docx.Document()
    doc2.add_heading("Multi-Author Manuscript", level=0)
    doc2.add_paragraph("Alice Smith1, Bob Jones1,2, Charlie Brown2")
    doc2.add_paragraph("1 Department of Computer Science, Stanford University, CA, USA")
    doc2.add_paragraph("2 Department of Electrical Engineering, MIT, MA, USA")
    doc2.add_paragraph("Abstract: Testing multi-author affiliation parsing.")
    doc2.add_heading("1. Introduction", level=1)
    doc2.add_paragraph("Intro text.")
    doc2.save(docx2)
    
    udm2 = DocxParser.parse(docx2)
    assert len(udm2.metadata.authors) == 3, f"Expected 3 authors, got {len(udm2.metadata.authors)}"
    assert len(udm2.metadata.affiliations) == 2, f"Expected 2 affiliations, got {len(udm2.metadata.affiliations)}"
    assert udm2.metadata.authors[1].affiliation_ids == ["1", "2"], f"Expected Bob Jones affil ['1', '2'], got {udm2.metadata.authors[1].affiliation_ids}"
    print("[PASS] TEST 2: DOCX with multiple authors & affiliations")

    # -------------------------------------------------------------
    # TEST 3 & TEST 4: DOCX with 3+ different figures & captions
    # -------------------------------------------------------------
    docx3 = os.path.join(temp_dir, "test3_figures.docx")
    doc3 = docx.Document()
    doc3.add_heading("Multi-Figure Manuscript", level=0)
    doc3.add_paragraph("Author One")
    doc3.add_paragraph("University Dept")
    doc3.add_heading("1. Methods", level=1)
    
    colors = [(200, 50, 50), (50, 200, 50), (50, 50, 200)]
    labels = ["Arch Diagram", "Workflow Map", "Performance Plot"]
    
    for idx in range(3):
        img_p = os.path.join(temp_dir, f"fig_{idx+1}.png")
        img = Image.new("RGB", (200, 100), color=colors[idx])
        d = ImageDraw.Draw(img)
        d.text((20, 40), labels[idx], fill=(255, 255, 255))
        img.save(img_p)
        
        doc3.add_paragraph(f"Body text prior to figure {idx+1}")
        doc3.add_picture(img_p, width=Inches(2.5))
        doc3.add_paragraph(f"Figure {idx+1}: {labels[idx]} caption details")
        
    doc3.save(docx3)
    
    udm3 = DocxParser.parse(docx3)
    figs3 = [b for sec in udm3.sections for b in sec.blocks if isinstance(b, dict) and b.get("type") == "figure"]
    assert len(figs3) == 3, f"Expected 3 figures, got {len(figs3)}"
    fig_hashes = set(b.get("sha256") or b.get("image_data_b64") for b in figs3)
    assert len(fig_hashes) == 3, "Figure content hashes are not distinct!"
    print("[PASS] TEST 3 & TEST 4: DOCX with 3+ distinct figures & captions")

    # -------------------------------------------------------------
    # TEST 5: DOCX with tables
    # -------------------------------------------------------------
    docx5 = os.path.join(temp_dir, "test5_tables.docx")
    doc5 = docx.Document()
    doc5.add_heading("Table Manuscript", level=0)
    doc5.add_paragraph("Author One")
    doc5.add_heading("1. Results", level=1)
    
    t = doc5.add_table(rows=3, cols=3)
    for r_idx in range(3):
        for c_idx in range(3):
            t.cell(r_idx, c_idx).text = f"Cell_{r_idx}_{c_idx}"
            
    doc5.save(docx5)
    
    udm5 = DocxParser.parse(docx5)
    tbls5 = [b for sec in udm5.sections for b in sec.blocks if isinstance(b, dict) and b.get("type") == "table"]
    assert len(tbls5) >= 1, "Expected table in UDM"
    print("[PASS] TEST 5: DOCX with tables")

    # -------------------------------------------------------------
    # TEST 6: Exact scenario triggering "string indices must be integers, not 'str'"
    # -------------------------------------------------------------
    # A) Direct call to _parse_author_header with plain strings (List[str])
    authors_str, affils_str, _ = DocxParser._parse_author_header(["Alice Smith", "1 Department of CS, Stanford"])
    assert len(authors_str) >= 1, "Failed to parse authors from string list"
    assert len(affils_str) >= 1, "Failed to parse affils from string list"
    
    # B) Direct call with dicts (List[Dict])
    authors_dict, affils_dict, _ = DocxParser._parse_author_header([{"full_text": "Bob Jones", "runs": []}])
    assert len(authors_dict) >= 1, "Failed to parse authors from dict list"
    
    # C) Full parse of manuscript without explicit title style
    docx6 = os.path.join(temp_dir, "test6_malformed_header.docx")
    doc6 = docx.Document()
    doc6.add_paragraph("Explainable Aspect-Sentiment Framework for Malayalam Movie Recommendation")
    doc6.add_paragraph("John Doe1, Jane Smith2")
    doc6.add_paragraph("1 Dept of CS, Univ A")
    doc6.add_paragraph("2 Dept of EE, Univ B")
    doc6.add_paragraph("Abstract: This is the abstract text of the movie recommendation paper.")
    doc6.add_paragraph("1. INTRODUCTION")
    doc6.add_paragraph("Personalized recommendation systems are widely used...")
    doc6.save(docx6)
    
    udm6 = DocxParser.parse(docx6)
    assert udm6.metadata.title is not None
    assert len(udm6.metadata.authors) >= 2
    print("[PASS] TEST 6: Type safety & header normalization ('string indices must be integers') resolved!")

    # -------------------------------------------------------------
    # PRINT SOURCE COUNTS & VERIFY COMPLETE CONVERSION PIPELINE
    # -------------------------------------------------------------
    print("\n=== UDM SOURCE COUNTS FOR TEST MANUSCRIPT ===")
    print(f"  Source format: {udm2.source_format}")
    print(f"  Authors: {len(udm2.metadata.authors)}")
    print(f"  Affiliations: {len(udm2.metadata.affiliations)}")
    print(f"  Figures: {len(figs3)}")
    print(f"  Tables: {len(tbls5)}")
    print(f"  Sections: {len(udm2.sections)}")
    print(f"  References: {len(udm2.references)}")

    # -------------------------------------------------------------
    # TEST COMPLETE PIPELINE (DOCX -> UDM -> TEMPLATE -> LATEX -> PDF)
    # -------------------------------------------------------------
    spec = TemplateSpecification(format_type="latex", author_style="springer", document_class="sn-jnl")
    proj_out = os.path.join(temp_dir, "pipeline_out")
    zip_out = os.path.join(temp_dir, "pipeline_out.zip")
    pdf_out = os.path.join(temp_dir, "pipeline_out.pdf")
    
    created_files = LatexRenderer.render_project(
        udm=udm3,
        spec=spec,
        dest_template_dir="",
        output_dir=proj_out,
        output_zip_path=zip_out
    )
    assert os.path.exists(os.path.join(proj_out, "main.tex")), "main.tex missing from output"
    assert os.path.exists(zip_out), "output ZIP missing"
    
    compiled, log = LatexSandbox.compile_project(
        project_dir=proj_out,
        entrypoint="main.tex",
        udm=udm3,
        output_pdf_path=pdf_out
    )
    assert compiled is True, f"PDF sandbox compilation failed: {log}"
    print("\n==================================================")
    print("ALL REGRESSION TESTS (1, 2, 3, 4, 5, 6) PASSED 100%!")
    print("COMPLETE PIPELINE DOCX -> UDM -> TEMPLATE -> LATEX -> PDF SUCCEEDED!")
    print("==================================================")

if __name__ == "__main__":
    run_regression_tests()
