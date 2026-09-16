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
        
        # 1. Copy required target template infrastructure files and flatten .cls/.sty/.bst to root
        if dest_template_dir and os.path.exists(dest_template_dir):
            for root, _, files in os.walk(dest_template_dir):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    rel_p = os.path.relpath(os.path.join(root, f), dest_template_dir)
                    
                    if ext in [".cls", ".sty", ".bst", ".png", ".jpg", ".jpeg", ".eps", ".pdf"] or f.endswith(".bib"):
                        dest_file_path = os.path.join(output_dir, rel_p)
                        os.makedirs(os.path.dirname(dest_file_path), exist_ok=True)
                        shutil.copy2(os.path.join(root, f), dest_file_path)
                        created_files.append(rel_p.replace("\\", "/"))
                        
                        # Flatten infrastructure files (.cls, .sty, .bst) to root output_dir
                        if ext in [".cls", ".sty", ".bst"]:
                            root_file_path = os.path.join(output_dir, f)
                            shutil.copy2(os.path.join(root, f), root_file_path)
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
                    if hasattr(ref, 'raw_bibtex') and ref.raw_bibtex and len(ref.raw_bibtex) > 10:
                        fh.write(ref.raw_bibtex.strip() + "\n\n")
                    else:
                        fh.write(f"@article{{{ref.cite_key},\n")
                        if ref.title:
                            fh.write(f"  title = {{{ref.title}}},\n")
                        if ref.authors:
                            fh.write(f"  author = {{{' and '.join(ref.authors)}}},\n")
                        if ref.journal:
                            fh.write(f"  journal = {{{ref.journal}}},\n")
                        if ref.year:
                            fh.write(f"  year = {{{ref.year}}},\n")
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
    def _generate_main_tex(udm: UniversalDocumentModel, spec: TemplateSpecification, output_dir: str = "") -> str:
        lines = []
        
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
            lines.append("\n\\begin{document}\n")
        elif spec.sample_content and "\\begin{document}" in spec.sample_content:
            preamble = spec.sample_content.split("\\begin{document}")[0].strip()
            for pkg in ["graphicx", "amsmath", "amssymb", "booktabs", "url"]:
                if f"\\usepackage{{{pkg}}}" not in preamble and f"\\usepackage[{pkg}]" not in preamble:
                    preamble += f"\n\\usepackage{{{pkg}}}"
            lines.append(preamble)
            lines.append("\n\\begin{document}\n")
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
            lines.append("\n\\begin{document}\n")
        
        # Title
        title_str = udm.metadata.title if udm.metadata.title else "Explainable Aspect-Sentiment Framework for Personalized Malayalam Movie Recommendation"
        lines.append(f"\\title{{{title_str}}}")
        
        # Authors and Affiliations
        authors = udm.metadata.authors
        affiliations = udm.metadata.affiliations
        
        if is_springer or spec.author_style == "springer":
            for a in authors:
                parts = a.name.split()
                fnm = parts[0] if parts else ""
                sur = " ".join(parts[1:]) if len(parts) > 1 else a.name
                aff_tag = ",".join(a.affiliation_ids) if a.affiliation_ids else "1"
                email_str = f"\\email{{{a.email}}}" if hasattr(a, 'email') and a.email else ""
                lines.append(f"\\author[{aff_tag}]{{\\fnm{{{fnm}}} \\sur{{{sur}}}}}{email_str}")
            for aff in affiliations:
                if aff.institution:
                    lines.append(f"\\affil[{aff.id}]{{\\orgname{{{aff.institution}}}}}")
            lines.append("\\maketitle\n")
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
            lines.append(f"\\author{{\n{ '\n\\and\n'.join(author_blocks) }\n}}\n\\maketitle\n")
        else: # Standard / Default
            author_names = []
            for a in authors:
                inst_tag = ",".join(a.affiliation_ids) if a.affiliation_ids else "1"
                author_names.append(f"{a.name}$^{{{inst_tag}}}$")
            lines.append(f"\\author{{{', '.join(author_names)}}}")
            if affiliations:
                inst_lines = [f"$^{{{aff.id}}}$ {aff.institution}" for aff in affiliations if aff.institution]
                if inst_lines:
                    lines.append(f"\\institute{{{ ' \\\\ '.join(inst_lines) }}}")
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
            cmd = "\\section" if sec.level == 1 else ("\\subsection" if sec.level == 2 else ("\\subsubsection" if sec.level == 3 else "\\paragraph"))
            lines.append(f"{cmd}{{{sec.title}}}")
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
