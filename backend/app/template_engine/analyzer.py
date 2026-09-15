import os
import re
import docx
from typing import Tuple, List, Dict, Any
from app.models.template_spec import TemplateSpecification
from app.parsers.zip_utils import find_latex_entrypoint

class TemplateAnalyzer:
    @staticmethod
    def analyze_destination_template(template_path: str) -> TemplateSpecification:
        """Analyzes a target DOCX template file or LaTeX ZIP template project."""
        if template_path.endswith(".docx"):
            return TemplateAnalyzer._analyze_docx_template(template_path)
        elif template_path.endswith(".zip") or os.path.isdir(template_path):
            return TemplateAnalyzer._analyze_latex_zip_template(template_path)
        else:
            # Single .tex or .cls file
            spec = TemplateSpecification(format_type="latex")
            spec.detected_rules.append("Single TeX/CLS template file uploaded")
            return spec

    @staticmethod
    def _analyze_docx_template(docx_path: str) -> TemplateSpecification:
        spec = TemplateSpecification(format_type="docx", document_class="Word Template")
        doc = docx.Document(docx_path)
        
        detected_styles = [s.name for s in doc.styles]
        spec.detected_rules.append(f"Detected {len(detected_styles)} DOCX paragraph/character styles")
        
        # Check title / author / heading styles
        if "Title" in detected_styles:
            spec.detected_rules.append("Title style detected")
        if "Author" in detected_styles or "Subtitle" in detected_styles:
            spec.detected_rules.append("Author block style detected")
        if "Heading 1" in detected_styles:
            spec.detected_rules.append("Heading hierarchy detected")
        if "Caption" in detected_styles:
            spec.detected_rules.append("Figure/Table caption style detected")
            
        spec.template_confidence = 97.0
        return spec

    @staticmethod
    def _analyze_latex_zip_template(project_dir: str) -> TemplateSpecification:
        spec = TemplateSpecification(format_type="latex")
        rules = []
        warnings = []
        required_files = []
        
        # 1. Find all required infrastructure files (.cls, .sty, .bst, logos)
        for root, _, files in os.walk(project_dir):
            for f in files:
                rel_f = os.path.relpath(os.path.join(root, f), project_dir).replace("\\", "/")
                ext = os.path.splitext(f)[1].lower()
                if ext in [".cls", ".sty", ".bst"] or f.endswith(".png") or f.endswith(".eps") or f.endswith(".pdf"):
                    required_files.append(rel_f)
                    
        spec.required_files = required_files
        rules.append(f"Detected {len(required_files)} target template infrastructure files (.cls, .sty, .bst, assets)")
        
        # 2. Find primary sample entry point .tex
        entrypoint_rel, candidates, _ = find_latex_entrypoint(project_dir)
        if entrypoint_rel:
            spec.entry_point_file = entrypoint_rel
            main_p = os.path.join(project_dir, entrypoint_rel)
            try:
                with open(main_p, "r", encoding="utf-8", errors="ignore") as fh:
                    sample_content = fh.read()
                    
                # Document class
                cls_match = re.search(r'\\documentclass(?:\[([^\]]*)\])?\{([^}]+)\}', sample_content)
                if cls_match:
                    opts_str = cls_match.group(1)
                    spec.document_class = cls_match.group(2).strip()
                    if opts_str:
                        spec.class_options = [o.strip() for o in opts_str.split(",")]
                    rules.append(f"Document class: \\documentclass[{opts_str or ''}]{{{spec.document_class}}}")
                    
                # Determine Author Formatting Style
                if "IEEEauthorblockN" in sample_content:
                    spec.author_style = "ieee"
                    rules.append("Author block: IEEE (\IEEEauthorblockN & \IEEEauthorblockA)")
                elif r"\fnm" in sample_content or r"\sur" in sample_content or "sn-jnl" in spec.document_class:
                    spec.author_style = "springer"
                    rules.append("Author block: Springer (\author[id]{\fnm{} \sur{}})")
                elif "elsarticle" in spec.document_class or r"\address" in sample_content:
                    spec.author_style = "elsevier"
                    rules.append("Author block: Elsevier (\author[id]{}, \address[id]{})")
                elif "acmart" in spec.document_class:
                    spec.author_style = "acm"
                    rules.append("Author block: ACM (\author{}, \affiliation{})")
                else:
                    spec.author_style = "standard"
                    rules.append("Author block: Standard LaTeX (\author{}, \institute{})")
                    
                # Bibliography / Citation System
                bst_match = re.search(r'\\bibliographystyle\{([^}]+)\}', sample_content)
                if bst_match:
                    spec.bib_style = bst_match.group(1).strip()
                    rules.append(f"Bibliography style: \\bibliographystyle{{{spec.bib_style}}}")
                    
                if "natbib" in sample_content:
                    spec.citation_system = "natbib"
                    rules.append("Citation system: natbib")
                elif "biblatex" in sample_content:
                    spec.citation_system = "biblatex"
                    rules.append("Citation system: biblatex")
                else:
                    spec.citation_system = "numeric"
                    rules.append("Citation system: Standard numeric")
                    
            except Exception as e:
                warnings.append(f"Sample file analysis warning: {str(e)}")
        else:
            warnings.append("No sample .tex entrypoint detected in target template zip.")
            
        spec.detected_rules = rules
        spec.warnings = warnings
        spec.template_confidence = 98.0
        return spec
