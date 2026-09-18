import re
from typing import List, Dict, Any, Tuple
from app.models.udm import UniversalDocumentModel, Section, Paragraph, Figure, Table, Equation, Author, Affiliation
from app.book_engine.book_template_analyzer import BookTemplateSpecification
from app.book_engine.image_converter import get_latex_compatible_filename

def clean_latex_text(text: str) -> str:
    if not text:
        return ""
    if text.startswith("\\") or text.startswith("$"):
        return text
    text = re.sub(r'(?<!\\)&', r'\&', text)
    text = re.sub(r'(?<!\\)%', r'\%', text)
    text = re.sub(r'(?<!\\)_', r'\_', text)
    text = re.sub(r'(?<!\\)#', r'\#', text)
    return text

class BookMappingEngine:
    @staticmethod
    def map_book_structure(udm: UniversalDocumentModel, spec: BookTemplateSpecification) -> Dict[str, Any]:
        mapped = {
            "title": udm.metadata.title or "Untitled Book",
            "authors_latex": "",
            "affiliations_latex": "",
            "abstract_latex": "",
            "chapters_latex": [],
            "references_latex": ""
        }

        if udm.metadata.authors:
            author_names = [a.name for a in udm.metadata.authors if a.name and a.name.strip()]
            if author_names:
                mapped["authors_latex"] = "\\author{\\textsc{" + " \\and ".join(author_names) + "}}"
            else:
                mapped["authors_latex"] = ""
        else:
            mapped["authors_latex"] = ""

        if udm.metadata.abstract:
            mapped["abstract_latex"] = (
                "\\chapter*{Abstract}\n"
                f"{clean_latex_text(udm.metadata.abstract)}\n\n"
            )

        chapters = []
        for sec in udm.sections:
            chap_title = clean_latex_text(sec.title)
            level = sec.level
            
            if level == 1:
                cmd = f"\\chapter{{{chap_title}}}"
            elif level == 2:
                cmd = f"\\section{{{chap_title}}}"
            else:
                cmd = f"\\subsection{{{chap_title}}}"

            chap_blocks = [cmd]

            for blk in sec.blocks:
                btype = blk.get("type") if isinstance(blk, dict) else getattr(blk, "type", "paragraph")
                
                if btype == "paragraph":
                    txt = blk.get("text") if isinstance(blk, dict) else getattr(blk, "text", "")
                    if txt:
                        chap_blocks.append(clean_latex_text(txt) + "\n")
                elif btype == "equation":
                    latex = blk.get("math_latex") if isinstance(blk, dict) else getattr(blk, "math_latex", "")
                    lbl = blk.get("label") if isinstance(blk, dict) else getattr(blk, "label", "")
                    if latex:
                        eq_str = "\\begin{equation}\n" + latex + "\n"
                        if lbl:
                            eq_str += f"\\label{{{lbl}}}\n"
                        eq_str += "\\end{equation}\n"
                        chap_blocks.append(eq_str)
                elif btype == "figure":
                    fname = blk.get("image_filename") if isinstance(blk, dict) else getattr(blk, "image_filename", "")
                    caption = blk.get("caption") if isinstance(blk, dict) else getattr(blk, "caption", "")
                    if fname:
                        fname = get_latex_compatible_filename(fname)
                    fig_str = "\\begin{figure}[htbp]\n\\centering\n"
                    if fname:
                        fig_str += f"\\includegraphics[width=0.8\\linewidth]{{figures/{fname}}}\n"
                    if caption:
                        fig_str += f"\\caption{{{clean_latex_text(caption)}}}\n"
                    fig_str += "\\end{figure}\n"
                    chap_blocks.append(fig_str)
                elif btype == "table":
                    headers = blk.get("headers", []) if isinstance(blk, dict) else getattr(blk, "headers", [])
                    rows = blk.get("rows", []) if isinstance(blk, dict) else getattr(blk, "rows", [])
                    caption = blk.get("caption", "") if isinstance(blk, dict) else getattr(blk, "caption", "")
                    
                    if headers or rows:
                        col_count = len(headers) if headers else (len(rows[0]) if rows else 1)
                        col_spec = "c" * col_count
                        tbl_str = "\\begin{table}[htbp]\n\\centering\n"
                        if caption:
                            tbl_str += f"\\caption{{{clean_latex_text(caption)}}}\n"
                        tbl_str += f"\\begin{{tabular}}{{{col_spec}}}\n\\toprule\n"
                        if headers:
                            tbl_str += " & ".join([clean_latex_text(h) for h in headers]) + " \\\\\n\\midrule\n"
                        for r in rows:
                            tbl_str += " & ".join([clean_latex_text(str(cell)) for cell in r]) + " \\\\\n"
                        tbl_str += "\\bottomrule\n\\end{tabular}\n\\end{table}\n"
                        chap_blocks.append(tbl_str)

            chapters.append("\n".join(chap_blocks))

        mapped["chapters_latex"] = chapters
        return mapped
