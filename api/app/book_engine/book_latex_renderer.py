import os
import re
import shutil
import base64
import zipfile
import logging
import io
from PIL import Image
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

        # Build image map from source manuscript in job_dir if b64_data was stripped for storage optimization
        source_image_map = {}
        parent_dir = os.path.dirname(output_dir)
        if parent_dir and os.path.exists(parent_dir):
            for root_d, _, files_d in os.walk(parent_dir):
                for fd in files_d:
                    if fd.startswith("source_") and fd.endswith(".docx"):
                        try:
                            import docx
                            from app.parsers.docx_parser import DocxParser
                            sdoc = docx.Document(os.path.join(root_d, fd))
                            rel_map = DocxParser._extract_images(sdoc)
                            for rId, img_info in rel_map.items():
                                if img_info.get("b64"):
                                    source_image_map[rId] = img_info["b64"]
                                    if img_info.get("media_path"):
                                        source_image_map[img_info["media_path"]] = img_info["b64"]
                                    if img_info.get("sha256"):
                                        source_image_map[img_info["sha256"]] = img_info["b64"]
                        except Exception as sdoc_err:
                            logger.warning(f"Could not extract images from source docx package: {sdoc_err}")

        fig_dir = os.path.join(output_dir, "figures")
        os.makedirs(fig_dir, exist_ok=True)
        fig_idx = 1
        for sec in udm.sections:
            for blk in sec.blocks:
                b64_data = blk.get("image_data_b64") if isinstance(blk, dict) else getattr(blk, "image_data_b64", None)
                rel_id = blk.get("rel_id") if isinstance(blk, dict) else getattr(blk, "rel_id", None)
                sha256 = blk.get("sha256") if isinstance(blk, dict) else getattr(blk, "sha256", None)
                media_path = blk.get("media_path") if isinstance(blk, dict) else getattr(blk, "media_path", None)

                if not b64_data and source_image_map:
                    b64_data = source_image_map.get(rel_id) or source_image_map.get(media_path) or source_image_map.get(sha256)

                raw_fname = blk.get("image_filename") if isinstance(blk, dict) else getattr(blk, "image_filename", "")
                if b64_data:
                    if not raw_fname:
                        raw_fname = f"figure_{fig_idx}.png"
                        fig_idx += 1
                    try:
                        img_bytes = base64.b64decode(b64_data)
                        orig_ext = os.path.splitext(raw_fname)[1].lower() if "." in raw_fname else ".emf"

                        is_png = img_bytes.startswith(b"\x89PNG\r\n\x1a\n")
                        is_jpeg = img_bytes.startswith(b"\xff\xd8\xff")
                        is_pdf = img_bytes.startswith(b"%PDF")

                        if is_png or is_jpeg or is_pdf:
                            target_fname = get_latex_compatible_filename(raw_fname)
                        else:
                            img_bytes, out_ext = convert_image_to_latex_compatible(img_bytes, raw_fname or ".emf")
                            base_name = os.path.splitext(raw_fname)[0] if "." in raw_fname else raw_fname
                            target_fname = f"{base_name}{out_ext}"

                        if target_fname.lower().endswith(".png"):
                            try:
                                with Image.open(io.BytesIO(img_bytes)) as test_im:
                                    test_im.verify()
                            except Exception:
                                img_bytes, out_ext = convert_image_to_latex_compatible(img_bytes, ".emf")
                                base_name = os.path.splitext(raw_fname)[0] if "." in raw_fname else raw_fname
                                target_fname = f"{base_name}{out_ext}"

                        if not os.path.splitext(target_fname)[1]:
                            target_fname = f"{target_fname}.png"

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
        main_tex_content = re.sub(r'figures/([^}\s]*?)\.(emf|wmf|tif|tiff|bmp|gif|webp|svg|ico)', r'figures/\1.png', main_tex_content, flags=re.I)
        main_tex_content = re.sub(r'max width=', r'width=', main_tex_content)

        # Automated Package Integrity Check: referenced image -> file exists -> valid image -> usable by LaTeX
        inc_refs = re.findall(r'\\includegraphics(?:\[.*?\])?\{([^}]*)\}', main_tex_content)
        for ref in inc_refs:
            clean_ref = ref.strip().replace('/', os.sep)
            abs_ref_path = os.path.join(output_dir, clean_ref)

            if not os.path.exists(abs_ref_path):
                base_no_ext = os.path.splitext(abs_ref_path)[0]
                dir_name = os.path.dirname(abs_ref_path)
                alt_found = False
                if os.path.exists(dir_name):
                    for existing_file in os.listdir(dir_name):
                        existing_abs = os.path.join(dir_name, existing_file)
                        if existing_abs == base_no_ext or os.path.splitext(existing_abs)[0] == base_no_ext:
                            try:
                                with open(existing_abs, "rb") as efh:
                                    e_bytes = efh.read()
                                converted_bytes, _ = convert_image_to_latex_compatible(e_bytes, ".emf")
                                with open(abs_ref_path, "wb") as o_fh:
                                    o_fh.write(converted_bytes)
                                alt_found = True
                                logger.info(f"Fixed missing image reference {ref} from {existing_file}")
                                break
                            except Exception as cv_err:
                                logger.warning(f"Failed converting alternate image {existing_file}: {cv_err}")

                if not alt_found:
                    fb_buf = io.BytesIO()
                    fb_img = Image.new("RGBA", (400, 300), (240, 240, 240, 255))
                    fb_img.save(fb_buf, format="PNG")
                    os.makedirs(os.path.dirname(abs_ref_path), exist_ok=True)
                    with open(abs_ref_path, "wb") as o_fh:
                        o_fh.write(fb_buf.getvalue())
                    logger.error(f"Created fallback PNG for missing referenced image: {ref}")

            try:
                with Image.open(abs_ref_path) as test_im:
                    test_im.verify()
            except Exception:
                fb_buf = io.BytesIO()
                fb_img = Image.new("RGBA", (400, 300), (240, 240, 240, 255))
                fb_img.save(fb_buf, format="PNG")
                with open(abs_ref_path, "wb") as o_fh:
                    o_fh.write(fb_buf.getvalue())
                logger.error(f"Replaced invalid image file {ref} with valid PNG")

            rel_created_path = os.path.relpath(abs_ref_path, output_dir).replace('\\', '/')
            if rel_created_path not in created_files:
                created_files.append(rel_created_path)

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
            lines.append("\\usepackage[utf8]{inputenc}")
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
