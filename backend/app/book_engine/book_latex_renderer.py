import os
import re
import shutil
import base64
import zipfile
import logging
from typing import List, Dict, Any
from app.models.udm import UniversalDocumentModel
from app.book_engine.book_template_analyzer import BookTemplateSpecification
from app.book_engine.book_mapping_engine import BookMappingEngine
from app.book_engine.image_converter import is_unsupported_latex_image, convert_image_to_latex_compatible, get_latex_compatible_filename

logger = logging.getLogger("BookLatexRenderer")

class BookLatexRenderer:
    @staticmethod
    def render_book_project(
        udm: UniversalDocumentModel,
        spec: BookTemplateSpecification,
        dest_template_dir: str,
        output_dir: str,
        output_zip_path: str
    ) -> List[str]:
        os.makedirs(output_dir, exist_ok=True)
        created_files = []

        if dest_template_dir and os.path.exists(dest_template_dir):
            for root, _, files in os.walk(dest_template_dir):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in [".cls", ".sty", ".bst", ".png", ".jpg", ".jpeg", ".eps", ".pdf"] or f.endswith(".bib"):
                        dest_file_path = os.path.join(output_dir, f)
                        shutil.copy2(os.path.join(root, f), dest_file_path)
                        if f not in created_files:
                            created_files.append(f)

        fig_dir = os.path.join(output_dir, "figures")
        os.makedirs(fig_dir, exist_ok=True)
        fig_idx = 1
        for sec in udm.sections:
            for blk in sec.blocks:
                b64_data = blk.get("image_data_b64") if isinstance(blk, dict) else getattr(blk, "image_data_b64", None)
                raw_fname = blk.get("image_filename") if isinstance(blk, dict) else getattr(blk, "image_filename", "")
                if b64_data:
                    if not raw_fname:
                        raw_fname = f"figure_{fig_idx}.png"
                        fig_idx += 1
                    try:
                        img_bytes = base64.b64decode(b64_data)
                        orig_ext = os.path.splitext(raw_fname)[1].lower()
                        if is_unsupported_latex_image(orig_ext):
                            img_bytes, _ = convert_image_to_latex_compatible(img_bytes, orig_ext)
                            target_fname = get_latex_compatible_filename(raw_fname)
                        else:
                            target_fname = raw_fname

                        img_path = os.path.join(fig_dir, target_fname)
                        with open(img_path, "wb") as fh:
                            fh.write(img_bytes)
                        if f"figures/{target_fname}" not in created_files:
                            created_files.append(f"figures/{target_fname}")
                    except Exception as img_err:
                        logger.warning(f"Failed to process figure {raw_fname}: {img_err}")

        bib_path = os.path.join(output_dir, "references.bib")
        with open(bib_path, "w", encoding="utf-8") as fh:
            if udm.references:
                for ref in udm.references:
                    raw = getattr(ref, 'raw_bibtex', '') or ''
                    if raw.strip().startswith('@'):
                        fh.write(raw.strip() + "\n\n")
                    else:
                        title = getattr(ref, 'title', '') or 'Untitled'
                        authors = getattr(ref, 'authors', []) or []
                        year = getattr(ref, 'year', '') or ''
                        journal = getattr(ref, 'journal', '') or ''
                        cite_key = getattr(ref, 'cite_key', '') or getattr(ref, 'id', 'ref')
                        
                        fh.write(f"@article{{{cite_key},\n")
                        fh.write(f"  title = {{{title}}},\n")
                        if authors:
                            fh.write(f"  author = {{{' and '.join(authors)}}},\n")
                        if journal:
                            fh.write(f"  journal = {{{journal}}},\n")
                        if year:
                            fh.write(f"  year = {{{year}}},\n")
                        fh.write("}\n\n")
            else:
                fh.write("% Empty references\n")
        created_files.append("references.bib")

        mapped = BookMappingEngine.map_book_structure(udm, spec)
        main_tex_content = BookLatexRenderer._assemble_main_tex(mapped, spec)
        
        # Enforce LaTeX-compatible image file extensions in main.tex
        main_tex_content = re.sub(r'figures/([^}\s]*?)\.(emf|wmf|tif|tiff|bmp)', r'figures/\1.png', main_tex_content, flags=re.I)

        main_tex_path = os.path.join(output_dir, "main.tex")
        with open(main_tex_path, "w", encoding="utf-8") as fh:
            fh.write(main_tex_content)
        created_files.append("main.tex")

        if output_zip_path:
            with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(output_dir):
                    for f in files:
                        abs_p = os.path.join(root, f)
                        rel_p = os.path.relpath(abs_p, output_dir)
                        zf.write(abs_p, rel_p)

        return created_files

    @staticmethod
    def _assemble_main_tex(mapped: Dict[str, Any], spec: BookTemplateSpecification) -> str:
        lines = []

        if spec.preamble_tex:
            clean_preamble = re.sub(r'\\title(?:\[.*?\])?\{[^}]*\}', '', spec.preamble_tex)
            clean_preamble = re.sub(r'\\author(?:\[.*?\])?\{[^}]*\}', '', clean_preamble)
            lines.append(clean_preamble.strip())
        else:
            lines.append("\\documentclass[11pt,a4paper]{book}")
            lines.append("\\usepackage[utf8]{utf8}")
            lines.append("\\usepackage{graphicx}")
            lines.append("\\usepackage{booktabs}")
            lines.append("\\usepackage{amsmath,amssymb}")
            lines.append("\\usepackage{hyperref}")

        lines.append("\n\\begin{document}\n")

        title_str = mapped["title"].replace('_', '\\_').replace('&', '\\&')
        lines.append(f"\\title{{{title_str}}}")

        if mapped["authors_latex"]:
            lines.append(mapped["authors_latex"])
        lines.append("\\maketitle\n")

        if spec.has_frontmatter:
            lines.append("\\frontmatter")
            if mapped["abstract_latex"]:
                lines.append(mapped["abstract_latex"])
            lines.append("\\tableofcontents\n")
            lines.append("\\mainmatter\n")
        else:
            if mapped["abstract_latex"]:
                lines.append(mapped["abstract_latex"])
            lines.append("\\tableofcontents\n")

        for chap in mapped["chapters_latex"]:
            lines.append(chap)
            lines.append("\n")

        if spec.has_frontmatter:
            lines.append("\\backmatter\n")

        bib_style = spec.bibliography_style or "plain"
        lines.append(f"\\bibliographystyle{{{bib_style}}}")
        lines.append("\\bibliography{references}")

        lines.append("\n\\end{document}")

        return "\n".join(lines)
