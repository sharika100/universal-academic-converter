import os
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
        Generates target main.tex, references.bib, and places figure images.
        """
        os.makedirs(output_dir, exist_ok=True)
        created_files = []
        
        # 1. Copy required target template infrastructure files
        if dest_template_dir and os.path.exists(dest_template_dir):
            for root, _, files in os.walk(dest_template_dir):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    rel_p = os.path.relpath(os.path.join(root, f), dest_template_dir)
                    # Copy template files (.cls, .sty, .bst, logos, sample bib) EXCEPT target sample.tex
                    if ext in [".cls", ".sty", ".bst", ".png", ".jpg", ".eps", ".pdf"] or f.endswith(".bib"):
                        dest_file_path = os.path.join(output_dir, rel_p)
                        os.makedirs(os.path.dirname(dest_file_path), exist_ok=True)
                        shutil.copy2(os.path.join(root, f), dest_file_path)
                        created_files.append(rel_p.replace("\\", "/"))

        # 2. Prepare figures directory and write figure images from UDM
        fig_dir = os.path.join(output_dir, "figures")
        os.makedirs(fig_dir, exist_ok=True)
        
        for sec in udm.sections:
            for blk in sec.blocks:
                if blk.get("type") == "figure":
                    b64_data = blk.get("image_data_b64")
                    fname = blk.get("image_filename") or f"{blk.get('id', 'fig')}.png"
                    if b64_data:
                        try:
                            img_path = os.path.join(fig_dir, fname)
                            with open(img_path, "wb") as fh:
                                fh.write(base64.b64decode(b64_data))
                            created_files.append(f"figures/{fname}")
                        except Exception:
                            pass
                            
        # 3. Generate target references.bib
        bib_path = os.path.join(output_dir, "references.bib")
        with open(bib_path, "w", encoding="utf-8") as fh:
            for ref in udm.references:
                if ref.raw_bibtex:
                    fh.write(ref.raw_bibtex.strip() + "\n\n")
                else:
                    authors_str = " and ".join(ref.authors) if ref.authors else "Academic Author"
                    fh.write(f"@article{{{ref.cite_key},\n")
                    fh.write(f"  title = {{{ref.title}}},\n")
                    fh.write(f"  author = {{{authors_str}}},\n")
                    if ref.journal:
                        fh.write(f"  journal = {{{ref.journal}}},\n")
                    if ref.year:
                        fh.write(f"  year = {{{ref.year}}},\n")
                    fh.write("}\n\n")
        created_files.append("references.bib")
        
        # 4. Generate target main.tex matching target TemplateSpecification macros
        main_tex_content = LatexRenderer._generate_main_tex(udm, spec)
        main_tex_path = os.path.join(output_dir, "main.tex")
        with open(main_tex_path, "w", encoding="utf-8") as fh:
            fh.write(main_tex_content)
        created_files.append("main.tex")
        
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
    def _generate_main_tex(udm: UniversalDocumentModel, spec: TemplateSpecification) -> str:
        lines = []
        
        # Documentclass declaration
        opts = f"[{','.join(spec.class_options)}]" if spec.class_options else ""
        cls = spec.document_class or "article"
        lines.append(f"\\documentclass{opts}{{{cls}}}")
        lines.append("\\usepackage{graphicx}")
        lines.append("\\usepackage{amsmath,amssymb}")
        lines.append("\\usepackage{booktabs}")
        lines.append("\\usepackage{url}")
        
        if spec.citation_system == "natbib":
            lines.append("\\usepackage{natbib}")
            
        lines.append("\n\\begin{document}\n")
        
        # Title
        lines.append(f"\\title{{{udm.metadata.title}}}")
        
        # Authors & Affiliations based on spec.author_style
        if spec.author_style == "ieee":
            author_blocks = []
            for idx, a in enumerate(udm.metadata.authors):
                affil_text = udm.metadata.affiliations[idx].institution if idx < len(udm.metadata.affiliations) else "Academic Department"
                author_blocks.append(f"\\IEEEauthorblockN{{{a.name}}}\n\\IEEEauthorblockA{{{affil_text}}}")
            lines.append(f"\\author{{{ ' \\and '.join(author_blocks) }}}\n\\maketitle\n")
            
        elif spec.author_style == "springer":
            for idx, a in enumerate(udm.metadata.authors):
                parts = a.name.split()
                fnm = parts[0] if parts else ""
                sur = " ".join(parts[1:]) if len(parts) > 1 else a.name
                lines.append(f"\\author[1]{{\\fnm{{{fnm}}} \\sur{{{sur}}}}}")
            for aff in udm.metadata.affiliations:
                lines.append(f"\\affiliation[1]{{\\orgname{{{aff.institution}}}}}")
            lines.append("\\maketitle\n")
            
        elif spec.author_style == "elsevier":
            for a in udm.metadata.authors:
                lines.append(f"\\author[1]{{{a.name}}}")
            for aff in udm.metadata.affiliations:
                lines.append(f"\\address[1]{{{aff.institution}}}")
            lines.append("\\maketitle\n")
            
        else: # Standard / ACM
            names = ", ".join([a.name for a in udm.metadata.authors])
            lines.append(f"\\author{{{names}}}")
            if udm.metadata.affiliations:
                lines.append(f"\\institute{{{udm.metadata.affiliations[0].institution}}}")
            lines.append("\\maketitle\n")
            
        # Abstract
        if udm.metadata.abstract:
            lines.append("\\begin{abstract}")
            lines.append(udm.metadata.abstract)
            lines.append("\\end{abstract}\n")
            
        # Keywords
        if udm.metadata.keywords:
            lines.append(f"\\keywords{{{', '.join(udm.metadata.keywords)}}}\n")
            
        # Sections
        for sec in udm.sections:
            cmd = "\\section" if sec.level == 1 else ("\\subsection" if sec.level == 2 else "\\subsubsection")
            lines.append(f"{cmd}{{{sec.title}}}")
            if sec.label:
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
                    lines.append("\\begin{equation}")
                    lines.append(blk.get("math_latex", ""))
                    if blk.get("label"):
                        lines.append(f"  \\label{{{blk.get('label')}}}")
                    lines.append("\\end{equation}\n")
                elif btype == "figure":
                    lines.append("\\begin{figure}[htbp]")
                    lines.append("  \\centering")
                    fname = blk.get("image_filename") or "fig.png"
                    lines.append(f"  \\includegraphics[width=0.8\\linewidth]{{figures/{fname}}}")
                    lines.append(f"  \\caption{{{blk.get('caption', '')}}}")
                    if blk.get("label"):
                        lines.append(f"  \\label{{{blk.get('label')}}}")
                    lines.append("\\end{figure}\n")
                elif btype == "table":
                    lines.append("\\begin{table}[htbp]")
                    lines.append("  \\centering")
                    lines.append(f"  \\caption{{{blk.get('caption', '')}}}")
                    headers = blk.get("headers", [])
                    rows = blk.get("rows", [])
                    num_cols = len(headers) if headers else (len(rows[0]) if rows else 1)
                    cols_fmt = "c" * num_cols
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
        bst = spec.bib_style or "plain"
        lines.append(f"\\bibliographystyle{{{bst}}}")
        lines.append("\\bibliography{references}")
        
        lines.append("\n\\end{document}")
        return "\n".join(lines)
