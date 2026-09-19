import re
from typing import List, Dict, Any, Tuple
from app.models.udm import UniversalDocumentModel, Section, Paragraph, Figure, Table, Equation, Author, Affiliation
from app.book_engine.book_template_analyzer import BookTemplateSpecification
from app.book_engine.image_converter import get_latex_compatible_filename

UNICODE_LATEX_MAP = {
    '\u00a0': '~',
    '\u200b': '',
    '±': r'\pm',
    '×': r'\times',
    '÷': r'\div',
    '°': r'^\circ',
    '—': r'---',
    '–': r'--',
    '…': r'\dots ',
    '“': r'``',
    '”': r"''",
    '‘': r'`',
    '’': r"'",
    '•': r'\textbullet ',
    '₹': r'Rs.\ ',
    '€': r'\euro ',
    '£': r'\pounds ',
    '¥': r'\yen ',
    '↔': r'\leftrightarrow',
    '→': r'\rightarrow',
    '←': r'\leftarrow',
    '⇒': r'\Rightarrow',
    '⇐': r'\Leftarrow',
    '⇔': r'\Leftrightarrow',
    '≤': r'\le',
    '≥': r'\ge',
    '≠': r'\neq',
    '−': r'-',
    '′': r"'",
    '″': r"''",
    '√': r'\sqrt{}',
    '∈': r'\in',
    '∉': r'\notin',
    '⊂': r'\subset',
    '⊄': r'\not\subset ',
    '⊆': r'\subseteq',
    '⊈': r'\nsubseteq',
    '⊃': r'\supset',
    '⊅': r'\not\supset ',
    '⊇': r'\supseteq',
    '⊉': r'\nsupseteq',
    '∪': r'\cup',
    '∩': r'\cap',
    '∧': r'\land',
    '∨': r'\lor',
    '¬': r'\neg',
    '∀': r'\forall',
    '∃': r'\exists',
    '≡': r'\equiv',
    '≈': r'\approx',
    '∞': r'\infty',
    '∅': r'\emptyset',
    '⨝': r'\bowtie',
    '⋈': r'\bowtie',
    '⟕': r'\ltimes',
    '⋉': r'\ltimes',
    '⟖': r'\rtimes',
    '⋊': r'\rtimes',
    '₀': r'_0',
    '₁': r'_1',
    '₂': r'_2',
    '₃': r'_3',
    '₄': r'_4',
    '₅': r'_5',
    '₆': r'_6',
    '₇': r'_7',
    '₈': r'_8',
    '₉': r'_9',
    'ₐ': r'_a',
    'ₑ': r'_e',
    'ₕ': r'_h',
    'ᵢ': r'_i',
    'ⱼ': r'_j',
    'ₖ': r'_k',
    'ₗ': r'_l',
    'ₘ': r'_m',
    'ₙ': r'_n',
    'ₒ': r'_o',
    'ₚ': r'_p',
    'ᵣ': r'_r',
    'ₛ': r'_s',
    'ₜ': r'_t',
    'ᵤ': r'_u',
    'ᵥ': r'_v',
    'ₓ': r'_x',
    '⁰': r'^0',
    '¹': r'^1',
    '²': r'^2',
    '³': r'^3',
    '⁴': r'^4',
    '⁵': r'^5',
    '⁶': r'^6',
    '⁷': r'^7',
    '⁸': r'^8',
    '⁹': r'^9',
    'ⁿ': r'^n',
    'ⁱ': r'^i',
    'α': r'\alpha',
    'β': r'\beta',
    'γ': r'\gamma',
    'δ': r'\delta',
    'ε': r'\epsilon',
    'ζ': r'\zeta',
    'η': r'\eta',
    'θ': r'\theta',
    'ι': r'\iota',
    'κ': r'\kappa',
    'λ': r'\lambda',
    'μ': r'\mu',
    'ν': r'\nu',
    'ξ': r'\xi',
    'π': r'\pi',
    'ρ': r'\rho',
    'σ': r'\sigma',
    'ς': r'\varsigma',
    'τ': r'\tau',
    'υ': r'\upsilon',
    'φ': r'\phi',
    'χ': r'\chi',
    'ψ': r'\psi',
    'ω': r'\omega',
    'Γ': r'\Gamma',
    'Δ': r'\Delta',
    'Θ': r'\Theta',
    'Λ': r'\Lambda',
    'Ξ': r'\Xi',
    'Π': r'\Pi',
    'Σ': r'\Sigma',
    'Υ': r'\Upsilon',
    'Φ': r'\Phi',
    'Ψ': r'\Psi',
    'Ω': r'\Omega',
}

MATH_CMDS = {
    r'\leftrightarrow', r'\rightarrow', r'\leftarrow', r'\Rightarrow', r'\Leftarrow', r'\Leftrightarrow',
    r'\le', r'\ge', r'\neq', r'\pm', r'\times', r'\div', r'^\circ', r'\sqrt{}',
    r'\in', r'\notin', r'\subset', r'\not\subset', r'\subseteq', r'\nsubseteq', r'\supset', r'\not\supset', r'\supseteq', r'\nsupseteq', r'\cup', r'\cap', r'\land', r'\lor', r'\neg', r'\forall', r'\exists', r'\equiv', r'\approx', r'\infty', r'\emptyset', r'\bowtie', r'\ltimes', r'\rtimes',
    r'_0', r'_1', r'_2', r'_3', r'_4', r'_5', r'_6', r'_7', r'_8', r'_9',
    r'_a', r'_e', r'_h', r'_i', r'_j', r'_k', r'_l', r'_m', r'_n', r'_o', r'_p', r'_r', r'_s', r'_t', r'_u', r'_v', r'_x',
    r'^0', r'^1', r'^2', r'^3', r'^4', r'^5', r'^6', r'^7', r'^8', r'^9', r'^n', r'^i',
    r'\alpha', r'\beta', r'\gamma', r'\delta', r'\epsilon', r'\zeta', r'\eta', r'\theta', r'\iota', r'\kappa', r'\lambda', r'\mu', r'\nu', r'\xi', r'\pi', r'\rho', r'\sigma', r'\varsigma', r'\tau', r'\upsilon', r'\phi', r'\chi', r'\psi', r'\omega',
    r'\Gamma', r'\Delta', r'\Theta', r'\Lambda', r'\Xi', r'\Pi', r'\Sigma', r'\Upsilon', r'\Phi', r'\Psi', r'\Omega'
}

PROTECTED_PATTERN = re.compile(
    r'(\$[^\$]+\$|\\(?:includegraphics|label|cite|ref|pageref|url|href|begin|end|usepackage|UsePackage|documentclass|input|include)(?:\[[^\]]*\])?\{[^{}]*\}|\\[a-zA-Z]+)'
)

def escape_plain_text(s: str) -> str:
    s = re.sub(r'(?<!\\)&', r'\&', s)
    s = re.sub(r'(?<!\\)%', r'\%', s)
    s = re.sub(r'(?<!\\)_', r'\_', s)
    s = re.sub(r'(?<!\\)#', r'\#', s)
    return s

def clean_latex_text(text: str) -> str:
    if not text:
        return ""

    parts = text.split('$')
    new_parts = []
    for idx, part in enumerate(parts):
        in_math = (idx % 2 == 1)
        part_str = part
        for char, repl in UNICODE_LATEX_MAP.items():
            if char in part_str:
                if repl in MATH_CMDS:
                    if in_math:
                        part_str = part_str.replace(char, f" {repl} ")
                    else:
                        part_str = part_str.replace(char, f"${repl}$")
                else:
                    part_str = part_str.replace(char, repl)
        new_parts.append(part_str)
    text = '$'.join(new_parts)

    tokens = PROTECTED_PATTERN.split(text)
    res = []
    for tok in tokens:
        if not tok:
            continue
        if PROTECTED_PATTERN.fullmatch(tok):
            res.append(tok)
        else:
            res.append(escape_plain_text(tok))
    return ''.join(res)

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
                if chap_title.upper() in ["PREFACE", "FOREWORD", "ABSTRACT", "ACKNOWLEDGEMENTS", "ACKNOWLEDGEMENT"]:
                    cmd = f"\\chapter*{{{chap_title}}}"
                else:
                    cmd = f"\\chapter{{{chap_title}}}"
            elif level == 2:
                cmd = f"\\section{{{chap_title}}}"
            elif level == 3:
                cmd = f"\\subsection{{{chap_title}}}"
            else:
                cmd = f"\\subsubsection{{{chap_title}}}"

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
                        if "\\includegraphics" in latex:
                            latex = re.sub(
                                r'figures/([^}\s]+)',
                                lambda m: f"figures/{get_latex_compatible_filename(m.group(1))}",
                                latex
                            )
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
