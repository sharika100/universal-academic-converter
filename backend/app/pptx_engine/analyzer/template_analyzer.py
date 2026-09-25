import os
import re
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field

class LatexTemplateSpecification(BaseModel):
    is_project_zip: bool = False
    entrypoint_tex: str = "main.tex"
    document_class: str = "beamer"
    documentclass_options: Optional[str] = None
    is_beamer: bool = True
    theme: Optional[str] = None
    color_theme: Optional[str] = None
    font_theme: Optional[str] = None
    packages: List[str] = Field(default_factory=list)
    custom_commands: List[str] = Field(default_factory=list)
    slide_environment: str = "frame"
    has_titlepage_command: bool = True
    has_author_command: bool = True
    has_institute_command: bool = False
    has_date_command: bool = True
    preamble_raw: str = ""
    postamble_raw: str = "\\end{document}\n"
    sample_frames: List[str] = Field(default_factory=list)
    template_files: List[str] = Field(default_factory=list)
    aspect_ratio: Optional[str] = None

class TemplateAnalyzer:
    @staticmethod
    def analyze_template(template_path: str) -> LatexTemplateSpecification:
        """
        Analyzes a LaTeX template (.tex file, .zip archive, or extracted template directory).
        Detects class, beamer themes, frame syntax, preamble, and title macros.
        """
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template path not found: {template_path}")

        if os.path.isfile(template_path) and template_path.lower().endswith(".zip"):
            import tempfile
            from security.zip_guard import ZipGuard
            temp_dir = tempfile.mkdtemp(prefix="tmpl_zip_")
            try:
                ZipGuard.inspect_and_extract_safe(template_path, temp_dir)
                spec = TemplateAnalyzer._analyze_directory_template(temp_dir)
                spec.is_project_zip = True
                return spec
            finally:
                # Do not delete immediately if needed or keep extracted files in spec
                pass

        is_dir = os.path.isdir(template_path)
        if is_dir:
            return TemplateAnalyzer._analyze_directory_template(template_path)
        else:
            return TemplateAnalyzer._analyze_single_tex_file(template_path)

    @staticmethod
    def _analyze_single_tex_file(tex_path: str) -> LatexTemplateSpecification:
        with open(tex_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        spec = TemplateAnalyzer._parse_tex_content(content, os.path.basename(tex_path))
        spec.template_files = [os.path.basename(tex_path)]
        spec.is_project_zip = False
        return spec

    @staticmethod
    def _analyze_directory_template(template_dir: str) -> LatexTemplateSpecification:
        entrypoint, all_files = TemplateAnalyzer._find_entrypoint(template_dir)
        entry_full_path = os.path.join(template_dir, entrypoint)
        with open(entry_full_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        spec = TemplateAnalyzer._parse_tex_content(content, entrypoint)
        spec.template_files = all_files
        spec.is_project_zip = True
        return spec

    @staticmethod
    def _find_entrypoint(template_dir: str) -> Tuple[str, List[str]]:
        all_files = []
        tex_files = []
        for root, _, files in os.walk(template_dir):
            for file in files:
                rel = os.path.relpath(os.path.join(root, file), template_dir).replace('\\', '/')
                all_files.append(rel)
                if file.lower().endswith('.tex'):
                    tex_files.append(rel)

        if not tex_files:
            raise ValueError("No .tex files found in the template directory.")

        # Candidate ranking
        candidates = []
        for tf in tex_files:
            full_p = os.path.join(template_dir, tf)
            try:
                with open(full_p, "r", encoding="utf-8", errors="ignore") as f:
                    txt = f.read()
                score = 0
                if "\\documentclass" in txt:
                    score += 50
                if "\\begin{document}" in txt:
                    score += 40
                if "\\begin{frame}" in txt or "\\frame{" in txt:
                    score += 20
                if os.path.basename(tf).lower() in ["main.tex", "presentation.tex", "beamer.tex", "slides.tex"]:
                    score += 10
                candidates.append((score, tf))
            except Exception:
                pass

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1], all_files

    @staticmethod
    def _parse_tex_content(content: str, entrypoint_name: str) -> LatexTemplateSpecification:
        spec = LatexTemplateSpecification(entrypoint_tex=entrypoint_name)

        # 1. Document class
        doc_class_match = re.search(r'\\documentclass(?:\s*\[(.*?)\])?\s*\{([a-zA-Z0-9_\-]+)\}', content)
        if doc_class_match:
            spec.documentclass_options = doc_class_match.group(1)
            spec.document_class = doc_class_match.group(2).strip()
            spec.is_beamer = (spec.document_class.lower() == "beamer")
            if spec.documentclass_options and "aspectratio=169" in spec.documentclass_options:
                spec.aspect_ratio = "16:9"

        # 2. Beamer Themes
        theme_match = re.search(r'\\usetheme(?:\[.*?\])?\{([a-zA-Z0-9_\-]+)\}', content)
        if theme_match:
            spec.theme = theme_match.group(1)

        color_match = re.search(r'\\usecolortheme(?:\[.*?\])?\{([a-zA-Z0-9_\-]+)\}', content)
        if color_match:
            spec.color_theme = color_match.group(1)

        font_match = re.search(r'\\usefonttheme(?:\[.*?\])?\{([a-zA-Z0-9_\-]+)\}', content)
        if font_match:
            spec.font_theme = font_match.group(1)

        # 3. Packages
        pkgs = re.findall(r'\\usepackage(?:\[.*?\])?\{([a-zA-Z0-9_,\-\s]+)\}', content)
        all_pkgs = []
        for pkg_str in pkgs:
            for p in pkg_str.split(','):
                p_clean = p.strip()
                if p_clean and p_clean not in all_pkgs:
                    all_pkgs.append(p_clean)
        spec.packages = all_pkgs

        # 4. Slide Environment (default: frame)
        if re.search(r'\\begin\{(slide|frame|slides)\}', content):
            env_m = re.search(r'\\begin\{(slide|frame|slides)\}', content)
            spec.slide_environment = env_m.group(1)

        # 5. Title / Author capabilities
        spec.has_titlepage_command = bool(re.search(r'\\(?:titlepage|maketitle)', content))
        spec.has_author_command = "\\author" in content
        spec.has_institute_command = "\\institute" in content
        spec.has_date_command = "\\date" in content

        # 6. Preamble Extraction
        doc_begin_idx = content.find("\\begin{document}")
        if doc_begin_idx != -1:
            spec.preamble_raw = content[:doc_begin_idx + len("\\begin{document}")].strip() + "\n\n"
        else:
            # Fallback minimal beamer preamble
            spec.preamble_raw = (
                "\\documentclass{beamer}\n"
                "\\usetheme{Madrid}\n"
                "\\usepackage[utf8]{inputenc}\n"
                "\\usepackage{graphicx}\n"
                "\\usepackage{booktabs}\n"
                "\\usepackage{hyperref}\n"
                "\\begin{document}\n\n"
            )

        # 7. Postamble Extraction
        doc_end_idx = content.rfind("\\end{document}")
        if doc_end_idx != -1:
            spec.postamble_raw = "\n" + content[doc_end_idx:].strip() + "\n"
        else:
            spec.postamble_raw = "\n\\end{document}\n"

        return spec
