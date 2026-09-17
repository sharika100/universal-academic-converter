import os
import sys
import shutil
import tempfile
import docx
import unittest

sys.path.insert(0, os.path.abspath("api"))
sys.path.insert(0, os.path.abspath("backend"))

from app.parsers.docx_parser import DocxParser
from app.template_engine.analyzer import TemplateAnalyzer
from app.mappers.mapping_engine import MappingEngine
from app.renderers.latex_renderer import LatexRenderer
from app.compilation.latex_sandbox import LatexSandbox


class TestAmberJainAndSpringerRegression(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_amber_jain_")
        
        # Use actual user file if available on disk, otherwise fallback to synthetic docx
        actual_user_file = "C:/teaching/book article/Role of Technology in a Hybrid Teaching Mode.docx"
        if os.path.exists(actual_user_file):
            self.docx_path = actual_user_file
        else:
            self.docx_path = os.path.join(self.test_dir, "Role of Technology in a Hybrid Teaching Mode.docx")
            doc = docx.Document()
            doc.add_paragraph("Role of Technology in a Hybrid Teaching Mode")
            doc.add_paragraph("Name of Author: SHARIKA T R")
            doc.add_paragraph("Designation: Assistant Professor, Department of CSE, Sree Narayana Gurukulam College of Engineering")
            doc.add_paragraph("Phone Number: 9562799289")
            doc.add_paragraph("Abstract: This paper explores the integration of ICT in hybrid teaching mode.")
            doc.add_paragraph("Keywords: Hybrid Education, ICT, Blended Learning")
            
            sections_data = [
                ("Introduction", "Hybrid teaching integrates face-to-face instruction with online learning environments to maximize educational impact."),
                ("Hybrid vs Blended Learning", "While blended learning often refers to supplementary online components, hybrid learning fundamentally alters course delivery."),
                ("ICT and Hybrid Education", "Information and Communication Technologies form the backbone of modern hybrid pedagogical models."),
                ("ICT for Hybrid Educators", "Educators utilize learning management systems and digital assessment tools to facilitate interaction."),
                ("ICT for Hybrid Learners", "Learners benefit from self-paced modules, interactive simulations, and instant feedback systems."),
                ("Benefits of Hybrid Learning", "Hybrid education offers flexibility, accessibility, and improved engagement for diverse student populations."),
                ("Challenges in Hybrid Education", "Challenges include digital divide, infrastructure limitations, and requiring enhanced digital literacy."),
                ("Conclusion", "Technology plays a pivotal role in enabling scalable and effective hybrid teaching environments.")
            ]
            
            for sec_title, sec_text in sections_data:
                p = doc.add_paragraph(sec_title)
                p.style = "List Paragraph"
                p.runs[0].bold = True
                doc.add_paragraph(sec_text)
                
            t1 = doc.add_table(rows=3, cols=3)
            t1.cell(0, 0).text = "Category"
            t1.cell(0, 1).text = "Traditional"
            t1.cell(0, 2).text = "Hybrid Mode"
            t1.cell(1, 0).text = "Delivery"
            t1.cell(1, 1).text = "Classroom Only"
            t1.cell(1, 2).text = "Blended Classroom + Digital"
            t1.cell(2, 0).text = "Flexibility"
            t1.cell(2, 1).text = "Low"
            t1.cell(2, 2).text = "High"
            doc.add_paragraph("Table 1: Comparison of Educational Delivery Modes")

            t2 = doc.add_table(rows=3, cols=2)
            t2.cell(0, 0).text = "Tool Type"
            t2.cell(0, 1).text = "Primary Function"
            t2.cell(1, 0).text = "LMS"
            t2.cell(1, 1).text = "Course Content Management"
            t2.cell(2, 0).text = "Video Conferencing"
            t2.cell(2, 1).text = "Synchronous Interaction"
            doc.add_paragraph("Table 2: ICT Tools in Hybrid Mode")

            doc.save(self.docx_path)

        self.amber_template_zip = "C:/Users/shari/Downloads/Basic_book_template__by_Amber_Jain_.zip"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_amber_jain_generic_book_conversion(self):
        self.assertTrue(os.path.exists(self.amber_template_zip), "Amber Jain template zip missing!")
        
        # 1. Parse Source DOCX
        udm = DocxParser.parse(self.docx_path)
        
        # 14-POINT REGRESSION ASSERTIONS:
        
        # Point 1: Title
        self.assertEqual(udm.metadata.title, "Role of Technology in a Hybrid Teaching Mode")
        
        # Point 2: Exactly one author
        self.assertEqual(len(udm.metadata.authors), 1, f"Expected 1 author, got {len(udm.metadata.authors)}: {[a.name for a in udm.metadata.authors]}")
        
        # Point 3: Author name == "SHARIKA T R"
        self.assertEqual(udm.metadata.authors[0].name, "SHARIKA T R")
        
        # Point 4 & 5: No phone number or designation in author names
        author_names = [a.name for a in udm.metadata.authors]
        self.assertNotIn("Phone Number:9562799289", author_names)
        self.assertNotIn("Phone Number: 9562799289", author_names)
        self.assertNotIn("Designation", author_names)
        self.assertNotIn("Assistant Professor", author_names)
        self.assertNotIn("Introduction", author_names)
        self.assertNotIn("Hybrid vs Blended Learning", author_names)
        self.assertNotIn("Conclusion", author_names)
        
        # Point 6: Structural sections vs ListBlocks
        section_titles = [s.title for s in udm.sections]
        self.assertGreaterEqual(len(udm.sections), 7, f"Expected at least 7 sections, got {len(udm.sections)}: {section_titles}")
        self.assertTrue(any("Hybrid vs Blended" in t for t in section_titles))
        self.assertTrue(any("ICT and Hybrid" in t for t in section_titles))
        self.assertTrue(any("Conclusion" in t for t in section_titles))
        
        # Point 7: Paragraph count preserved
        total_paras = sum(1 for s in udm.sections for b in s.blocks if b.get("type") == "paragraph")
        self.assertGreaterEqual(total_paras, 15, f"Expected at least 15 paragraphs, got {total_paras}")
        
        # Point 8: Table count preserved
        total_tables = sum(1 for s in udm.sections for b in s.blocks if b.get("type") == "table")
        self.assertEqual(total_tables, 2, f"Expected 2 tables, got {total_tables}")
        
        # Point 9: Source paragraph text preserved
        all_text = " ".join([b.get("text", "") for s in udm.sections for b in s.blocks if b.get("type") == "paragraph"])
        self.assertIn("hybrid teaching", all_text.lower())
        self.assertIn("blended learning", all_text.lower())
        
        # 2. Analyze Destination Template
        template_extract_dir = os.path.join(self.test_dir, "template_extracted")
        import zipfile
        with zipfile.ZipFile(self.amber_template_zip, "r") as zf:
            zf.extractall(template_extract_dir)
            
        spec = TemplateAnalyzer.analyze_destination_template(template_extract_dir)
        
        # 3. Render Output LaTeX Project
        output_dir = os.path.join(self.test_dir, "output")
        output_zip = os.path.join(self.test_dir, "converted_project.zip")
        
        created_files = LatexRenderer.render_project(udm, spec, template_extract_dir, output_dir, output_zip)
        
        main_tex_path = os.path.join(output_dir, "main.tex")
        self.assertTrue(os.path.exists(main_tex_path))
        
        with open(main_tex_path, "r", encoding="utf-8") as fh:
            main_tex = fh.read()
            
        # Point 10: Generated LaTeX contains author
        self.assertIn("SHARIKA T R", main_tex)
        
        # Point 11: Generated LaTeX does NOT contain template sample author
        self.assertNotIn("First-name Last-name", main_tex)
        self.assertNotIn("Amber Jain", main_tex)
        
        # Point 12: Generated LaTeX does NOT contain "Sample Book Title"
        self.assertNotIn("Sample Book Title", main_tex)
        
        # Point 13: Generated LaTeX does NOT contain "Lorem ipsum"
        self.assertNotIn("Lorem ipsum", main_tex)
        
        # Point 14: PDF compilation
        output_pdf = os.path.join(self.test_dir, "preview.pdf")
        success, log = LatexSandbox.compile_project(output_dir, "main.tex", udm, output_pdf)
        self.assertTrue(success, f"PDF compilation failed:\n{log}")


if __name__ == "__main__":
    unittest.main()
