import os
import re
import zipfile
from typing import Dict, Any, List, Optional
from app.models.template_spec import TemplateSpecification
from app.parsers.zip_utils import find_latex_entrypoint

class BookTemplateSpecification(TemplateSpecification):
    document_class: str = "book"
    has_frontmatter: bool = True
    has_chapters: bool = True
    preamble_tex: str = ""
    title_macro_style: str = "standard"
    author_macro_style: str = "standard"
    bibliography_style: str = "plain"
    bib_filename: str = "references"
    chapter_command: str = "chapter"
    sample_author_strings: List[str] = []
    sample_title_strings: List[str] = []

class BookTemplateAnalyzer:
    @staticmethod
    def analyze_book_template(template_path: str) -> BookTemplateSpecification:
        spec = BookTemplateSpecification(format_type="latex", document_class="book")
        if template_path.endswith(".zip") or os.path.isdir(template_path):
            return BookTemplateAnalyzer._analyze_latex_book_zip(template_path, spec)
        else:
            spec.detected_rules.append("Generic book template uploaded")
            return spec

    @staticmethod
    def _analyze_latex_book_zip(template_path: str, spec: BookTemplateSpecification) -> BookTemplateSpecification:
        files_dict = {}
        if template_path.endswith(".zip"):
            with zipfile.ZipFile(template_path, 'r') as z:
                for fname in z.namelist():
                    if not fname.endswith("/"):
                        try:
                            files_dict[fname] = z.read(fname).decode('utf-8', errors='ignore')
                        except Exception:
                            pass
        else:
            for root, _, files in os.walk(template_path):
                for f in files:
                    rel_path = os.path.relpath(os.path.join(root, f), template_path)
                    try:
                        with open(os.path.join(root, f), 'r', encoding='utf-8', errors='ignore') as fh:
                            files_dict[rel_path] = fh.read()
                    except Exception:
                        pass

        master_file = None
        for candidate in ["main.tex", "book.tex", "index.tex"]:
            if candidate in files_dict:
                master_file = candidate
                break
        if not master_file:
            for fname in files_dict:
                if fname.endswith(".tex") and "\\documentclass" in files_dict[fname]:
                    master_file = fname
                    break

        if not master_file:
            spec.detected_rules.append("No explicit master TeX entrypoint found, fallback to standard book")
            return spec

        spec.entry_point_file = master_file
        master_tex = files_dict[master_file]

        doc_class_match = re.search(r'\\documentclass(?:\[(.*?)\])?\{([^\}]+)\}', master_tex)
        if doc_class_match:
            raw_opts = doc_class_match.group(1) or ""
            spec.class_options = [o.strip() for o in raw_opts.split(",") if o.strip()]
            spec.document_class = doc_class_match.group(2).strip()
            spec.detected_rules.append(f"Document Class: {spec.document_class}")

        if "\\begin{document}" in master_tex:
            preamble = master_tex.split("\\begin{document}")[0]
            spec.preamble_tex = preamble.strip()
        else:
            spec.preamble_tex = master_tex

        spec.has_frontmatter = "\\frontmatter" in master_tex
        spec.has_chapters = "\\chapter" in master_tex or "\\chapter" in str(files_dict)
        spec.chapter_command = "chapter" if spec.has_chapters else "section"

        bib_style_match = re.search(r'\\bibliographystyle\{([^\}]+)\}', master_tex)
        if bib_style_match:
            spec.bibliography_style = bib_style_match.group(1)

        bib_file_match = re.search(r'\\bibliography\{([^\}]+)\}', master_tex)
        if bib_file_match:
            spec.bib_filename = bib_file_match.group(1)

        sample_titles = []
        sample_authors = []
        for fname, content in files_dict.items():
            if fname.endswith(".tex"):
                t_matches = re.findall(r'\\title(?:\[.*?\])?\{([^}]+)\}', content)
                for tm in t_matches:
                    clean_t = re.sub(r'\\[A-Za-z]+|\{|\}', '', tm).strip()
                    if clean_t and len(clean_t) > 3:
                        sample_titles.append(clean_t)

                a_matches = re.findall(r'\\author(?:\[.*?\])?\{([^}]+)\}', content)
                for am in a_matches:
                    clean_a = re.sub(r'\\[A-Za-z]+|\{|\}', '', am).strip()
                    if clean_a and len(clean_a) > 2:
                        sample_authors.append(clean_a)

        spec.sample_title_strings = list(set(sample_titles))
        spec.sample_author_strings = list(set(sample_authors))

        return spec
