import os
import re
import shutil
import zipfile
import json
import logging
from typing import Dict, Any, List, Optional
from app.pptx_engine.models.slide_ir import SlideDeckIR
from app.pptx_engine.analyzer.template_analyzer import LatexTemplateSpecification
from app.pptx_engine.mapper.slide_mapper import SlideMapper, escape_latex

logger = logging.getLogger("latex_renderer")

class LatexRenderer:
    @staticmethod
    def render_project(
        deck: SlideDeckIR,
        spec: LatexTemplateSpecification,
        dest_template_dir_or_file: Optional[str],
        output_dir: str,
        output_zip_path: Optional[str] = None,
        source_filename: str = "presentation.pptx"
    ) -> Dict[str, Any]:
        """
        Assembles a complete, self-contained LaTeX project in output_dir
        and packages it into output_zip_path.
        """
        os.makedirs(output_dir, exist_ok=True)
        img_dir = os.path.join(output_dir, "images")
        os.makedirs(img_dir, exist_ok=True)

        # 1. Copy template assets if a template directory or ZIP exists
        if dest_template_dir_or_file:
            if os.path.isdir(dest_template_dir_or_file):
                for root, dirs, files in os.walk(dest_template_dir_or_file):
                    for f in files:
                        src_file = os.path.join(root, f)
                        rel_p = os.path.relpath(src_file, dest_template_dir_or_file)
                        dest_file = os.path.join(output_dir, rel_p)
                        os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                        shutil.copy2(src_file, dest_file)
            elif os.path.isfile(dest_template_dir_or_file) and dest_template_dir_or_file.lower().endswith('.zip'):
                from security.zip_guard import ZipGuard
                ZipGuard.inspect_and_extract_safe(dest_template_dir_or_file, output_dir)

        # 2. Map slides to LaTeX frames
        frames_latex = SlideMapper.map_deck_to_latex(deck, spec)

        # 3. Assemble main.tex
        main_tex_content = LatexRenderer._assemble_main_tex(deck, spec, frames_latex)
        entry_name = spec.entrypoint_tex or "main.tex"
        main_tex_path = os.path.join(output_dir, entry_name)
        with open(main_tex_path, "w", encoding="utf-8") as f:
            f.write(main_tex_content)

        # Also write main.tex if entry_name was different (e.g. beamer_template.tex)
        if entry_name != "main.tex":
            with open(os.path.join(output_dir, "main.tex"), "w", encoding="utf-8") as f:
                f.write(main_tex_content)

        # 4. Generate Conversion Report
        report_data = {
            "source_filename": source_filename,
            "slide_count": deck.total_slides,
            "generated_frames": len(deck.slides),
            "extracted_images": deck.total_images,
            "converted_tables": deck.total_tables,
            "text_blocks": deck.total_text_blocks,
            "template_detected": {
                "document_class": spec.document_class,
                "is_beamer": spec.is_beamer,
                "theme": spec.theme,
                "slide_environment": spec.slide_environment
            },
            "warnings": list(deck.warnings) + (["Some embedded PowerPoint objects could not be converted and require manual verification."] if any("unsupported shape" in w.lower() or "embedded_ole" in w.lower() for w in deck.warnings) else []),
            "compilation_status": "PENDING"
        }

        with open(os.path.join(output_dir, "conversion_report.json"), "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)

        with open(os.path.join(output_dir, "conversion_report.txt"), "w", encoding="utf-8") as f:
            f.write(LatexRenderer._format_text_report(report_data))

        # 5. Build ZIP archive
        created_files = []
        for root, _, files in os.walk(output_dir):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), output_dir)
                created_files.append(rel)

        if output_zip_path:
            os.makedirs(os.path.dirname(output_zip_path), exist_ok=True)
            with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for rel in created_files:
                    abs_p = os.path.join(output_dir, rel)
                    zf.write(abs_p, rel)

        return {
            "output_dir": output_dir,
            "output_zip_path": output_zip_path,
            "entrypoint_tex": spec.entrypoint_tex,
            "files_count": len(created_files),
            "report": report_data
        }

    @staticmethod
    def _assemble_main_tex(
        deck: SlideDeckIR, spec: LatexTemplateSpecification, frames_latex: str
    ) -> str:
        preamble = spec.preamble_raw

        # Ensure required packages and robust symbol fallbacks exist in preamble
        required_pkgs = ["graphicx", "booktabs", "hyperref", "amsmath"]
        for pkg in required_pkgs:
            if f"\\usepackage{{{pkg}}}" not in preamble and f"\\usepackage[{pkg}]" not in preamble:
                idx = preamble.find("\\begin{document}")
                if idx != -1:
                    preamble = preamble[:idx] + f"\\usepackage{{{pkg}}}\n" + preamble[idx:]

        # Inject robust macros if missing
        safe_macros = [
            "\\providecommand{\\checkmark}{\\ensuremath{\\surd}}",
            "\\providecommand{\\textrightarrow}{\\ensuremath{\\rightarrow}}"
        ]
        idx = preamble.find("\\begin{document}")
        if idx != -1:
            macro_block = "\n".join(safe_macros) + "\n"
            preamble = preamble[:idx] + macro_block + preamble[idx:]

        # Update template metadata: replace template placeholders with actual PPTX presentation metadata
        preamble = LatexRenderer._update_template_metadata(preamble, deck)

        body = f"\n{frames_latex}\n"
        postamble = spec.postamble_raw

        return preamble + body + postamble

    @staticmethod
    def _update_template_metadata(preamble: str, deck: SlideDeckIR) -> str:
        """
        Replaces template placeholder metadata with genuine presentation metadata.
        Ensures placeholder author, title, subtitle, date are never retained.
        """
        def replace_cmd(text: str, cmd: str, val: Optional[str]) -> str:
            target = f"\\{cmd}"
            pos = 0
            found = False
            while True:
                idx = text.find(target, pos)
                if idx == -1:
                    break
                end_cmd = idx + len(target)
                if end_cmd < len(text) and text[end_cmd].isalpha():
                    pos = end_cmd
                    continue

                i = end_cmd
                while i < len(text) and text[i].isspace():
                    i += 1

                opt_str = None
                if i < len(text) and text[i] == '[':
                    depth = 1
                    start_opt = i + 1
                    i += 1
                    while i < len(text) and depth > 0:
                        if text[i] == '[': depth += 1
                        elif text[i] == ']': depth -= 1
                        i += 1
                    if depth == 0:
                        opt_str = text[start_opt : i - 1]
                    while i < len(text) and text[i].isspace():
                        i += 1

                if i < len(text) and text[i] == '{':
                    depth = 1
                    start_arg = i + 1
                    i += 1
                    while i < len(text) and depth > 0:
                        if text[i] == '{': depth += 1
                        elif text[i] == '}': depth -= 1
                        i += 1
                    if depth == 0:
                        found = True
                        if val:
                            if opt_str is not None:
                                new_opt = re.sub(r'short-title\s*=\s*\{?[^,\]\}]+\}?', f'short-title = {{{escape_latex(val[:35])}}}', opt_str)
                                replacement = f"\\{cmd}[{new_opt}]{{{escape_latex(val)}}}"
                            else:
                                replacement = f"\\{cmd}{{{escape_latex(val)}}}"
                        else:
                            replacement = f"\\{cmd}{{}}"
                        return text[:idx] + replacement + text[i:]
                pos = end_cmd

            if not found and val:
                # Only insert standard preamble commands if missing; do not invent non-standard commands like \subtitle
                if cmd in ['title', 'author', 'date']:
                    doc_idx = text.find(r'\begin{document}')
                    if doc_idx != -1:
                        return text[:doc_idx] + f"\\{cmd}{{{escape_latex(val)}}}\n" + text[doc_idx:]
            return text

        p = preamble
        if deck.deck_title:
            p = replace_cmd(p, 'title', deck.deck_title)
        else:
            p = replace_cmd(p, 'title', None)

        if deck.subtitle:
            p = replace_cmd(p, 'subtitle', deck.subtitle)
        else:
            p = replace_cmd(p, 'subtitle', None)

        if deck.author:
            p = replace_cmd(p, 'author', deck.author)
        else:
            p = replace_cmd(p, 'author', None)

        if deck.date:
            p = replace_cmd(p, 'date', deck.date)

        if deck.institution:
            p = replace_cmd(p, 'institute', deck.institution)

        return p

    @staticmethod
    def _format_text_report(r: Dict[str, Any]) -> str:
        lines = [
            "==================================================",
            "PPTX -> LaTeX Template Converter - Conversion Report",
            "==================================================",
            f"Source File:         {r.get('source_filename')}",
            f"Slides in PPTX:      {r.get('slide_count')}",
            f"Generated Frames:    {r.get('generated_frames')}",
            f"Extracted Images:    {r.get('extracted_images')}",
            f"Converted Tables:    {r.get('converted_tables')}",
            f"Text Blocks:         {r.get('text_blocks')}",
            f"Template Class:      {r.get('template_detected', {}).get('document_class')}",
            f"Beamer Template:     {r.get('template_detected', {}).get('is_beamer')}",
            f"Compilation Status:  {r.get('compilation_status')}",
            "--------------------------------------------------",
            "Warnings & Unsupported Elements:"
        ]
        warnings = r.get('warnings', [])
        if warnings:
            for w in warnings:
                lines.append(f"  - {w}")
        else:
            lines.append("  (None - All elements mapped successfully)")
        lines.append("==================================================")
        return "\n".join(lines)
