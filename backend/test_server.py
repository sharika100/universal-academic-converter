import os
import sys
import shutil
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.abspath("api"))

from app.models.udm import UniversalDocumentModel
from app.models.template_spec import TemplateSpecification
from app.parsers.docx_parser import DocxParser
from app.parsers.latex_parser import LatexParser
from app.template_engine.analyzer import TemplateAnalyzer
from app.mappers.mapping_engine import MappingEngine
from app.renderers.latex_renderer import LatexRenderer
from app.renderers.docx_renderer import DocxRenderer

class TestCompilerPipeline(unittest.TestCase):
    def test_latex_to_latex_conversion(self):
        sample_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "samples"))
        ieee_zip = os.path.join(sample_dir, "ieee_paper.zip")
        springer_zip = os.path.join(sample_dir, "springer_template.zip")
        
        # 1. Parse Source IEEE project
        extract_src = os.path.join(sample_dir, "test_extract_src")
        from app.security.zip_guard import ZipGuard
        ZipGuard.inspect_and_extract_safe(ieee_zip, extract_src)
        
        udm = LatexParser.parse_project(extract_src)
        self.assertEqual(udm.source_format, "LaTeX Project")
        self.assertTrue(len(udm.sections) > 0)
        self.assertTrue(len(udm.references) > 0)
        
        # 2. Analyze Target Springer template
        extract_dest = os.path.join(sample_dir, "test_extract_dest")
        ZipGuard.inspect_and_extract_safe(springer_zip, extract_dest)
        
        spec = TemplateAnalyzer.analyze_destination_template(extract_dest)
        self.assertEqual(spec.format_type, "latex")
        self.assertTrue(spec.document_class is not None)
        
        # 3. Map & Evaluate
        mapping = MappingEngine.map_and_evaluate(udm, spec)
        self.assertTrue(mapping["compatibility"]["overall"] > 80.0)
        
        # 4. Render Target Springer project
        out_dir = os.path.join(sample_dir, "test_out")
        out_zip = os.path.join(sample_dir, "converted_springer_paper.zip")
        files = LatexRenderer.render_project(udm, spec, extract_dest, out_dir, out_zip)
        
        self.assertTrue("main.tex" in files)
        self.assertTrue("references.bib" in files)
        self.assertTrue(os.path.exists(out_zip))
        
        # Cleanup
        shutil.rmtree(extract_src, ignore_errors=True)
        shutil.rmtree(extract_dest, ignore_errors=True)
        shutil.rmtree(out_dir, ignore_errors=True)
        
    def test_docx_parsing(self):
        sample_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "samples"))
        docx_path = os.path.join(sample_dir, "sample_manuscript.docx")
        udm = DocxParser.parse(docx_path)
        self.assertEqual(udm.source_format, "DOCX")
        self.assertTrue(len(udm.sections) > 0)

if __name__ == "__main__":
    unittest.main()
