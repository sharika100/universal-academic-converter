import os
import re
import shutil
import base64
import zipfile
from typing import List, Dict, Any
from app.models.udm import UniversalDocumentModel
from app.models.template_spec import TemplateSpecification

class LatexRenderer:
    @staticmethod
    def render_project(
        udm: UniversalDocumentModel,
        spec: TemplateSpecification,
        dest_template_dir: str,
        output_dir: str,
        output_zip_path: str
    ) -> List[str]:
        """
        Renders UniversalDocumentModel into a complete target LaTeX project ZIP.
        Preserves target template infrastructure (.cls, .sty, .bst, assets).
        Flattens .cls/.sty/.bst files into output root so \\documentclass finds them.
        Generates target main.tex, references.bib, and places all distinct figure images.
        """
        os.makedirs(output_dir, exist_ok=True)
        created_files = []
        
        # 1. Copy required target template infrastructure files and flatten directly into output_dir root
        if dest_template_dir and os.path.exists(dest_template_dir):
            for root, _, files in os.walk(dest_template_dir):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in [".cls", ".sty", ".bst", ".png", ".jpg", ".jpeg", ".eps", ".pdf"] or f.endswith(".bib"):
                        dest_file_path = os.path.join(output_dir, f)
                        shutil.copy2(os.path.join(root, f), dest_file_path)
                        if f not in created_files:
                            created_files.append(f)

        # 2. Prepare figures directory and write every distinct figure / equation image from UDM
        fig_dir = os.path.join(output_dir, "figures")
        os.makedirs(fig_dir, exist_ok=True)
        
        written_fig_names = set()
        fig_idx = 1
        
        for sec in udm.sections:
            for blk in sec.blocks:
                btype = blk.get("type")
                if btype in ["figure", "equation"]:
                    sub_imgs = blk.get("sub_images", [])
                    img_items = sub_imgs if sub_imgs else [blk]
                    for sub_item in img_items:
                        b64_data = sub_item.get("image_data_b64")
                        raw_fname = sub_item.get("image_filename")
                        if b64_data:
                            if not raw_fname or raw_fname in written_fig_names or raw_fname == "fig.png":
                                raw_fname = f"figure_{fig_idx}.png"
                                sub_item["image_filename"] = raw_fname
                            written_fig_names.add(raw_fname)
                            fig_idx += 1
                            try:
                                img_path = os.path.join(fig_dir, raw_fname)
                                with open(img_path, "wb") as fh:
                                    fh.write(base64.b64decode(b64_data))
                                created_files.append(f"figures/{raw_fname}")
                            except Exception:
                                pass
                            
        # 3. Generate target references.bib
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
        
        # 4. Generate target main.tex matching target TemplateSpecification macros
        main_tex_content = LatexRenderer._generate_main_tex(udm, spec, output_dir)
        main_tex_path = os.path.join(output_dir, "main.tex")
        with open(main_tex_path, "w", encoding="utf-8") as fh:
            fh.write(main_tex_content)
        created_files.append("main.tex")
        
        # AUTOMATED INTEGRITY VALIDATION: Every \includegraphics file reference in main.tex MUST exist in output directory!
        referenced_imgs = re.findall(r'\\includegraphics(?:\[.*?\])?\{([^}]+)\}', main_tex_content)
        for ref_img in referenced_imgs:
            ref_clean = ref_img.strip()
            candidates = [
                os.path.normpath(os.path.join(output_dir, ref_clean)),
                os.path.normpath(os.path.join(output_dir, "figures", os.path.basename(ref_clean)))
            ]
            if not any(os.path.exists(c) or any(os.path.exists(c + ext) for ext in [".png", ".jpg", ".jpeg", ".pdf", ".eps"]) for c in candidates):
                raise ValueError(
                    f"OUTPUT INTEGRITY FAILURE: Generated main.tex references image '{ref_img}' "
                    f"which does not exist in the physical output directory!"
                )
        
        # 5. Zip generated project into output_zip_path
        os.makedirs(os.path.dirname(output_zip_path), exist_ok=True)
        with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(output_dir):
                for f in files:
                    abs_p = os.path.join(root, f)
                    rel_p = os.path.relpath(abs_p, output_dir).replace("\\", "/")
                    zf.write(abs_p, rel_p)
                    
        return created_files

    @staticmethod
    def sanitize_latex_preamble(preamble: str) -> str:
        r"""Strips sample metadata macros (\title, \author, \date, \subtitle, \thanks, \institute, \address) from a LaTeX template preamble."""
        for cmd in ["title", "author", "date", "subtitle", "institute", "address", "thanks"]:
            pattern = r'\\' + cmd + r'(?:\[[^\]]*\])?\s*\{'
            while True:
                m = re.search(pattern, preamble)
                if not m:
                    break
                start_idx = m.start()
                brace_count = 0
                end_idx = -1
                for i in range(m.end() - 1, len(preamble)):
                    if preamble[i] == '{':
                        brace_count += 1
                    elif preamble[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = i
                            break
                if end_idx != -1:
                    preamble = preamble[:start_idx] + preamble[end_idx + 1:]
                else:
                    break
        cleaned_lines = []
        for line in preamble.splitlines():
            line_str = line.strip()
            if line_str.startswith("%") and any(sample_kw in line_str.lower() for sample_kw in ["author:", "title:", "amber jain", "amberj", "sample"]):
                continue
            if any(sample_kw in line for sample_kw in ["Sample Book Title", "Sample author", "First-name Last-name", "Calvin and Hobbes"]):
                continue
            cleaned_lines.append(line)
        return "\n".join(cleaned_lines)

    @staticmethod
    def _generate_main_tex(udm: UniversalDocumentModel, spec: TemplateSpecification, output_dir: str = "") -> str:
        lines = []
        
        is_book = (spec.document_class or "").lower() in ["book", "report", "memoir", "scrbook", "scrreprt"] or (
            spec.sample_content and "\\documentclass" in spec.sample_content and bool(re.search(r'\\documentclass(?:\[[^\]]*\])?\{(book|report)\}', spec.sample_content))
        )
        
        # Detect Springer template (.cls or .bst in output_dir or spec)
        is_springer = (spec.document_class == "sn-jnl" or spec.author_style == "springer" or 
                       (output_dir and os.path.exists(os.path.join(output_dir, "sn-jnl.cls"))))

        if is_springer:
            lines.append("\\documentclass[pdflatex,sn-mathphys-num]{sn-jnl}")
            lines.append("\\usepackage{graphicx}")
            lines.append("\\usepackage{amsmath,amssymb,amsfonts}")
            lines.append("\\usepackage{amsthm}")
            lines.append("\\usepackage{mathrsfs}")
            lines.append("\\usepackage[title]{appendix}")
            lines.append("\\usepackage{xcolor}")
            lines.append("\\usepackage{manyfoot}")
            lines.append("\\usepackage{booktabs}")
            lines.append("\\usepackage{algorithm}")
            lines.append("\\usepackage{algorithmicx}")
            lines.append("\\usepackage{algpseudocode}")
            lines.append("\\usepackage{listings}")
        elif spec.sample_content and "\\begin{document}" in spec.sample_content:
            raw_preamble = spec.sample_content.split("\\begin{document}")[0].strip()
            preamble = LatexRenderer.sanitize_latex_preamble(raw_preamble)
            for pkg in ["graphicx", "amsmath", "amssymb", "booktabs", "url"]:
                if f"\\usepackage{{{pkg}}}" not in preamble and f"\\usepackage[{pkg}]" not in preamble:
                    preamble += f"\n\\usepackage{{{pkg}}}"
            lines.append(preamble)
        else:
            opts = f"[{','.join(spec.class_options)}]" if spec.class_options else ""
            cls = spec.document_class or "article"
            lines.append(f"\\documentclass{opts}{{{cls}}}")
            lines.append("\\usepackage{graphicx}")
            lines.append("\\usepackage{amsmath,amssymb}")
            lines.append("\\usepackage{booktabs}")
            lines.append("\\usepackage{url}")
            lines.append("\\usepackage{algorithm}")
            lines.append("\\usepackage{algorithmicx}")
            lines.append("\\usepackage{algpseudocode}")
            if spec.citation_system == "natbib":
                lines.append("\\usepackage{natbib}")
        
        # Title
        title_str = udm.metadata.title if udm.metadata.title else "Explainable Aspect-Sentiment Framework for Personalized Malayalam Movie Recommendation"
        lines.append(f"\\title{{{title_str}}}")
        
        # Authors and Affiliations
        authors = udm.metadata.authors
        affiliations = udm.metadata.affiliations
        
        if is_springer or spec.author_style == "springer":
            for a_idx, a in enumerate(authors):
                clean_name = re.sub(r'^(?:Dr\.|Prof\.|Mr\.|Ms\.|Mrs\.|Doctor)\s+', '', a.name, flags=re.I)
                parts = clean_name.split()
                if len(parts) == 1:
                    fnm, sur = parts[0], ""
                elif len(parts) == 2:
                    fnm, sur = parts[0], parts[1]
                else:
                    fnm, sur = " ".join(parts[:-1]), parts[-1]
                    
                aff_tag = ",".join(a.affiliation_ids) if a.affiliation_ids else "1"
                email_str = f"\\email{{{a.email}}}" if hasattr(a, 'email') and a.email else ""
                is_cor = (a_idx == 0) and bool(a.email)
                star = "*" if is_cor else ""
                lines.append(f"\\author{star}[{aff_tag}]{{\\fnm{{{fnm}}} \\sur{{{sur}}}}}{email_str}")
            for aff in affiliations:
                if aff.institution:
                    lines.append(f"\\affil[{aff.id}]{{\\orgname{{{aff.institution}}}}}")
        elif spec.author_style == "elsevier":
            for a_idx, a in enumerate(authors):
                aff_tag = ",".join(a.affiliation_ids) if a.affiliation_ids else "1"
                email_str = f"\\ead{{{a.email}}}" if hasattr(a, 'email') and a.email else ""
                cor_str = "\\cormark[1]" if a_idx == 0 else ""
                lines.append(f"\\author[{aff_tag}]{{{a.name}}}{cor_str}{email_str}")
            for aff in affiliations:
                if aff.institution:
                    lines.append(f"\\address[{aff.id}]{{{aff.institution}}}")
        elif spec.author_style == "ieee" or spec.document_class == "IEEEtran":
            author_blocks = []
            for a in authors:
                aff_lines = []
                aff_names = [aff.institution for aff in affiliations if aff.id in a.affiliation_ids and aff.institution]
                if aff_names:
                    for inst in aff_names:
                        for part in inst.split(","):
                            if part.strip():
                                aff_lines.append(part.strip())
                elif affiliations and affiliations[0].institution:
                    for part in affiliations[0].institution.split(","):
                        if part.strip():
                            aff_lines.append(part.strip())
                aff_text = "\\\\\n".join(aff_lines) if aff_lines else ""
                if aff_text:
                    author_blocks.append(f"\\IEEEauthorblockN{{{a.name}}}\n\\IEEEauthorblockA{{\n{aff_text}\n}}")
                else:
                    author_blocks.append(f"\\IEEEauthorblockN{{{a.name}}}")
            lines.append(f"\\author{{\n{ '\n\\and\n'.join(author_blocks) }\n}}")
        else: # Standard / Default
            author_blocks = []
            for a in authors:
                inst_lines = [aff.institution for aff in affiliations if (aff.id in a.affiliation_ids or not a.affiliation_ids) and aff.institution]
                clean_inst_lines = [inst for inst in inst_lines if not re.search(r'\b\d{5,15}\b|phone|tel|mob', inst, re.I)]
                if clean_inst_lines:
                    author_blocks.append(f"{a.name}\\\\\n\\small {', '.join(clean_inst_lines)}")
                else:
                    author_blocks.append(a.name)
            lines.append(f"\\author{{{ ' \\and '.join(author_blocks) }}}")
            
        lines.append("\n\\begin{document}\n")

        if is_book:
            lines.append("\\frontmatter")
            lines.append("\\maketitle\n")
            lines.append("\\mainmatter\n")
        else:
            lines.append("\\maketitle\n")
            
        # Abstract
        if udm.metadata.abstract:
            lines.append("\\begin{abstract}")
            lines.append(udm.metadata.abstract)
            lines.append("\\end{abstract}\n")
            
        # Keywords
        if udm.metadata.keywords:
            if spec.document_class == "IEEEtran" or spec.author_style == "ieee":
                lines.append("\\begin{IEEEkeywords}")
                lines.append(", ".join(udm.metadata.keywords))
                lines.append("\\end{IEEEkeywords}\n")
            else:
                lines.append(f"\\keywords{{{', '.join(udm.metadata.keywords)}}}\n")
            
        # Sections
        for sec in udm.sections:
            if is_book:
                cmd = "\\chapter" if sec.level == 1 else ("\\section" if sec.level == 2 else ("\\subsection" if sec.level == 3 else "\\subsubsection"))
            else:
                cmd = "\\section" if sec.level == 1 else ("\\subsection" if sec.level == 2 else ("\\subsubsection" if sec.level == 3 else "\\paragraph"))
                
            clean_sec_title = re.sub(r'^(?:Chapter\s+\d+|Section\s+\d+|\d+(\.\d+)+|\d+\.|\b[IVXLCDM]+\.)\s*', '', sec.title, flags=re.I).strip()
            sec_heading_title = clean_sec_title if clean_sec_title else sec.title
            
            lines.append(f"{cmd}{{{sec_heading_title}}}")
            if hasattr(sec, 'label') and sec.label:
                lines.append(f"\\label{{{sec.label}}}")
                
            for blk in sec.blocks:
                btype = blk.get("type")
                if btype == "paragraph":
                    lines.append(blk.get("text", "") + "\n")
                elif btype == "list":
                    env = "enumerate" if blk.get("ordered") else "itemize"
                    lines.append(f"\\begin{{{env}}}")
                    for item in blk.get("items", []):
                        lines.append(f"  \\item {item.get('text', '')}")
                    lines.append(f"\\end{{{env}}}\n")
                elif btype == "equation":
                    m_tex = blk.get("math_latex", "")
                    if "\\includegraphics" in m_tex:
                        lines.append("\\begin{center}")
                        lines.append(f"  {m_tex}")
                        lines.append("\\end{center}\n")
                    else:
                        lines.append("\\begin{equation}")
                        lines.append(m_tex)
                        if blk.get("label"):
                            lines.append(f"  \\label{{{blk.get('label')}}}")
                        lines.append("\\end{equation}\n")
                elif btype == "algorithm":
                    lines.append("\\begin{algorithm}[htbp]")
                    if blk.get("caption"):
                        lines.append(f"  \\caption{{{blk.get('caption')}}}")
                    if blk.get("label"):
                        lines.append(f"  \\label{{{blk.get('label')}}}")
                    lines.append("  \\begin{algorithmic}[1]")
                    lines.append(f"  {blk.get('code', '').strip()}")
                    lines.append("  \\end{algorithmic}")
                    lines.append("\\end{algorithm}\n")
                elif btype == "figure":
                    lines.append("\\begin{figure}[htbp]")
                    lines.append("  \\centering")
                    sub_imgs = blk.get("sub_images", [])
                    if sub_imgs:
                        for s_idx, s_img in enumerate(sub_imgs):
                            fname = s_img.get("image_filename")
                            lines.append(f"  \\begin{{minipage}}{{0.48\\linewidth}}")
                            lines.append(f"    \\centering")
                            lines.append(f"    \\includegraphics[width=\\linewidth]{{figures/{fname}}}")
                            lines.append(f"  \\end{{minipage}}\\hfill")
                        lines.append("")
                    else:
                        fname = blk.get("image_filename") or "figure_1.png"
                        lines.append(f"  \\includegraphics[width=0.8\\linewidth]{{figures/{fname}}}")
                    if blk.get("caption"):
                        lines.append(f"  \\caption{{{blk.get('caption')}}}")
                    if blk.get("label"):
                        lines.append(f"  \\label{{{blk.get('label')}}}")
                    lines.append("\\end{figure}\n")
                elif btype == "table":
                    lines.append("\\begin{table}[htbp]")
                    lines.append("  \\centering")
                    if blk.get("caption"):
                        lines.append(f"  \\caption{{{blk.get('caption')}}}")
                    headers = blk.get("headers", [])
                    rows = blk.get("rows", [])
                    num_cols = len(headers) if headers else (len(rows[0]) if rows else 1)
                    col_spec = blk.get("col_spec")
                    cols_fmt = col_spec if col_spec else ("c" * num_cols)
                    lines.append(f"  \\begin{{tabular}}{{{cols_fmt}}}")
                    lines.append("    \\toprule")
                    if headers:
                        lines.append(f"    {' & '.join(headers)} \\\\")
                        lines.append("    \\midrule")
                    for r in rows:
                        lines.append(f"    {' & '.join(r)} \\\\")
                    lines.append("    \\bottomrule")
                    lines.append("  \\end{tabular}")
                    lines.append("\\end{table}\n")
                    
        # Bibliography
        bst = "sn-mathphys-num" if is_springer else (spec.bib_style or "plain")
        lines.append(f"\\bibliographystyle{{{bst}}}")
        lines.append("\\bibliography{references}")
        
        lines.append("\n\\end{document}")
        return "\n".join(lines)
