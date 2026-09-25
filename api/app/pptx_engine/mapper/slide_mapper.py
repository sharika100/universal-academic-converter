import re
from typing import List, Optional, Tuple
from app.pptx_engine.models.slide_ir import (
    SlideDeckIR, SlideIR, SlideElementUnion, TextBoxElementIR,
    ParagraphIR, TextRunIR, ImageElementIR, TableElementIR, TableCellIR,
    UnsupportedElementIR
)
from app.pptx_engine.analyzer.template_analyzer import LatexTemplateSpecification

UNICODE_MAP = {
    '\u2013': '--',             # en-dash
    '\u2014': '---',            # em-dash
    '\u2018': "`",              # left single quote
    '\u2019': "'",              # right single quote
    '\u201c': '``',             # left double quote
    '\u201d': "''",             # right double quote
    '\u2022': '\\textbullet{}', # bullet
    '\u2026': '\\dots{}',       # ellipsis
    '\u2032': "$'$",            # prime symbol (n')
    '\u2264': '$\\le$',         # less than or equal to
    '\u2265': '$\\ge$',         # greater than or equal to
    '\u2260': '$\\ne$',         # not equal to
    '\u2248': '$\\approx$',     # approx equal to
    '\u2192': '$\\rightarrow$', # right arrow
    '\u2190': '$\\leftarrow$',  # left arrow
    '\u00b1': '$\\pm$',         # plus-minus
    '\u00d7': '$\\times$',      # multiplication sign
    '\u00f7': '$\\div$',        # division sign
    '\u2705': '\\checkmark{}',  # checkmark emoji
    '\u2713': '\\checkmark{}',  # checkmark
    '\u274c': '$\\times$',      # cross mark emoji
    '\u2717': '$\\times$',      # cross mark
    '\U0001f449': '$\\Rightarrow$', # pointing right finger emoji
    '\U0001f3c6': '\\textbf{[Optimal]}', # trophy emoji
    '\U0001f44d': '\\textbf{[+]}',    # thumbs up
}

def escape_latex(text: str) -> str:
    """
    Safely escapes special LaTeX characters: &, %, $, #, _, {, }, ~, ^, \\
    and maps unicode symbols (math, quotes, dashes, emojis) into clean LaTeX.
    """
    if not text:
        return ""

    # 1. Check if text is a single backslash
    if text == "\\":
        return "\\textbackslash{}"

    # 2. Escape reserved LaTeX characters on raw text
    t = text.replace('\\', '\x00')
    t = t.replace('&', '\\&')
    t = t.replace('%', '\\%')
    t = t.replace('$', '\\$')
    t = t.replace('#', '\\#')
    t = t.replace('_', '\\_')
    t = t.replace('{', '\\{')
    t = t.replace('}', '\\}')
    t = t.replace('~', '\\textasciitilde{}')
    t = t.replace('^', '\\textasciicircum{}')
    t = t.replace('\x00', '\\textbackslash{}')

    # 3. Map unicode math, typography, and emojis to LaTeX macros
    for uchar, repl in UNICODE_MAP.items():
        t = t.replace(uchar, repl)

    # 4. Remove any unencodable non-ascii surrogate/astral characters
    sanitized_chars = []
    for ch in t:
        if ord(ch) > 0xFFFF:
            continue
        sanitized_chars.append(ch)
    return "".join(sanitized_chars)

class SlideMapper:
    @staticmethod
    def map_deck_to_latex(deck: SlideDeckIR, spec: LatexTemplateSpecification) -> str:
        """
        Maps the entire SlideDeckIR into a sequence of LaTeX presentation frames
        compatible with the analyzed destination template.
        """
        frames_latex: List[str] = []

        for idx, slide in enumerate(deck.slides):
            frame_str = SlideMapper.map_slide(slide, deck, spec, is_first_slide=(idx == 0))
            if frame_str:
                frames_latex.append(frame_str)

        return "\n\n".join(frames_latex)

    @staticmethod
    def map_slide(
        slide: SlideIR, deck: SlideDeckIR, spec: LatexTemplateSpecification, is_first_slide: bool = False
    ) -> str:
        title = escape_latex(slide.title.strip()) if slide.title else ""
        subtitle = escape_latex(slide.subtitle.strip()) if slide.subtitle else ""

        # Title slide mapping (First slide if it only contains title/subtitle)
        non_title_elements = [el for el in slide.elements if not (isinstance(el, TextBoxElementIR) and (el.is_title or el.is_subtitle))]
        if is_first_slide and len(non_title_elements) == 0 and (title or subtitle):
            return SlideMapper._render_title_frame(title, subtitle, deck, spec)

        lines: List[str] = []
        frame_env = spec.slide_environment or "frame"

        # Frame start with title & subtitle
        title_args = f"{{{title}}}" if title else ""
        if title_args and subtitle:
            title_args += f"{{{subtitle}}}"
        elif not title_args and subtitle:
            title_args = f"{{{subtitle}}}"

        # Check if frame contains verbatim elements that necessitate [fragile]
        needs_fragile = False
        for el in slide.elements:
            if isinstance(el, TextBoxElementIR):
                for p in el.paragraphs:
                    for r in p.runs:
                        if any(v in r.text.lower() for v in ["\\begin{verbatim}", "\\verbatiminput", "\\verb"]):
                            needs_fragile = True
                            break

        fragile_opt = "[fragile]" if needs_fragile else ""
        lines.append(f"\\begin{{{frame_env}}}{fragile_opt}{title_args}")

        # Check for side-by-side elements (two-column layout)
        column_groups = SlideMapper._detect_columns(slide.elements, deck.slide_width_pts)
        if len(column_groups) == 2:
            lines.append("  \\begin{columns}[T]")
            for col in column_groups:
                col_width = "0.48\\textwidth"
                lines.append(f"    \\begin{{column}}{{{col_width}}}")
                for el in col:
                    rendered_el = SlideMapper._render_element(el, deck, indent="      ")
                    if rendered_el:
                        lines.append(rendered_el)
                lines.append("    \\end{column}")
            lines.append("  \\end{columns}")
        else:
            for el in slide.elements:
                # Skip title box if title is already on the frame header
                if isinstance(el, TextBoxElementIR) and el.is_title and slide.title:
                    continue
                rendered_el = SlideMapper._render_element(el, deck, indent="  ")
                if rendered_el:
                    lines.append(rendered_el)

        # Speaker notes
        if slide.speaker_notes:
            safe_notes = escape_latex(slide.speaker_notes)
            lines.append(f"  \\note{{{safe_notes}}}")

        lines.append(f"\\end{{{frame_env}}}")
        return "\n".join(lines)

    @staticmethod
    def _render_title_frame(title: str, subtitle: str, deck: SlideDeckIR, spec: LatexTemplateSpecification) -> str:
        lines = [f"\\begin{{{spec.slide_environment}}}[plain]"]
        if spec.has_titlepage_command:
            lines.append("  \\titlepage")
        else:
            lines.append("  \\centering")
            if title:
                lines.append(f"  {{\\LARGE \\textbf{{{title}}}}}\\\\[1em]")
            if subtitle:
                lines.append(f"  {{\\large \\textit{{{subtitle}}}}}\\\\[1.5em]")
            if deck.author:
                lines.append(f"  {{\\normalsize {escape_latex(deck.author)}}}\\\\[0.5em]")
            if deck.institution:
                lines.append(f"  {{\\small {escape_latex(deck.institution)}}}\\\\[0.5em]")
            if deck.date:
                lines.append(f"  {{\\small {escape_latex(deck.date)}}}")
        lines.append(f"\\end{{{spec.slide_environment}}}")
        return "\n".join(lines)

    @staticmethod
    def _detect_columns(elements: List[SlideElementUnion], slide_width_pts: float) -> List[List[SlideElementUnion]]:
        """
        Detects if elements are arranged horizontally side-by-side on the slide.
        """
        content_elements = [el for el in elements if not (isinstance(el, TextBoxElementIR) and el.is_title)]
        if len(content_elements) < 2 or len(content_elements) > 4:
            return []

        midpoint = slide_width_pts / 2.0
        left_col = []
        right_col = []

        for el in content_elements:
            center_x = el.x + (el.width / 2.0)
            if center_x < midpoint:
                left_col.append(el)
            else:
                right_col.append(el)

        # Valid 2-column only if both columns have at least one element
        if left_col and right_col and (len(left_col) + len(right_col) == len(content_elements)):
            return [left_col, right_col]

        return []

    @staticmethod
    def _render_element(element: SlideElementUnion, deck: SlideDeckIR, indent: str = "  ") -> str:
        if isinstance(element, TextBoxElementIR):
            return SlideMapper._render_textbox(element, indent)
        elif isinstance(element, ImageElementIR):
            return SlideMapper._render_image(element, deck, indent)
        elif isinstance(element, TableElementIR):
            return SlideMapper._render_table(element, indent)
        elif isinstance(element, UnsupportedElementIR):
            return f"{indent}% Warning: Unsupported shape '{escape_latex(element.name)}' ({escape_latex(element.shape_type)})"
        return ""

    @staticmethod
    def _render_textbox(tb: TextBoxElementIR, indent: str) -> str:
        lines: List[str] = []
        in_itemize = False
        current_level = 0

        for p in tb.paragraphs:
            rendered_p = SlideMapper._render_paragraph(p)
            if not rendered_p:
                continue

            if p.bullet_type == "bullet" or p.level > 0:
                if not in_itemize:
                    lines.append(f"{indent}\\begin{{itemize}}")
                    in_itemize = True
                    current_level = 0

                # Handle sub-level indenting
                if p.level > current_level:
                    for _ in range(p.level - current_level):
                        lines.append(f"{indent}  \\begin{{itemize}}")
                    current_level = p.level
                elif p.level < current_level:
                    for _ in range(current_level - p.level):
                        lines.append(f"{indent}  \\end{{itemize}}")
                    current_level = p.level

                lines.append(f"{indent}  \\item {rendered_p}")
            else:
                if in_itemize:
                    while current_level > 0:
                        lines.append(f"{indent}  \\end{{itemize}}")
                        current_level -= 1
                    lines.append(f"{indent}\\end{{itemize}}")
                    in_itemize = False

                align_prefix = ""
                if p.alignment == "center":
                    align_prefix = "\\centering "
                elif p.alignment == "right":
                    align_prefix = "\\raggedleft "

                lines.append(f"{indent}{align_prefix}{rendered_p}\\\\[0.3em]")

        if in_itemize:
            while current_level > 0:
                lines.append(f"{indent}  \\end{{itemize}}")
                current_level -= 1
            lines.append(f"{indent}\\end{{itemize}}")

        return "\n".join(lines)

    @staticmethod
    def _render_paragraph(p: ParagraphIR) -> str:
        run_parts = []
        for r in p.runs:
            safe_text = escape_latex(r.text)
            if not safe_text:
                continue

            part = safe_text
            if r.bold and r.italic:
                part = f"\\textbf{{\\textit{{{part}}}}}"
            elif r.bold:
                part = f"\\textbf{{{part}}}"
            elif r.italic:
                part = f"\\textit{{{part}}}"
            if r.underline:
                part = f"\\underline{{{part}}}"
            if r.hyperlink:
                safe_url = escape_latex(r.hyperlink)
                part = f"\\href{{{safe_url}}}{{{part}}}"

            run_parts.append(part)

        return "".join(run_parts).strip()

    @staticmethod
    def _render_image(img: ImageElementIR, deck: SlideDeckIR, indent: str) -> str:
        if getattr(img, "is_diagram", False) or (img.width / (deck.slide_width_pts or 720.0) > 0.65):
            lines = [
                f"{indent}\\begin{{center}}",
                f"{indent}  \\includegraphics[",
                f"{indent}    width=\\textwidth,",
                f"{indent}    height=0.78\\textheight,",
                f"{indent}    keepaspectratio",
                f"{indent}  ]{{{img.rel_path}}}",
                f"{indent}\\end{{center}}"
            ]
            if img.caption:
                lines.insert(len(lines) - 1, f"{indent}  \\caption{{{escape_latex(img.caption)}}}")
            return "\n".join(lines)

        # Scale width relative to slide width, capped at 0.9\textwidth
        ratio = img.width / (deck.slide_width_pts or 720.0)
        latex_width = min(max(ratio * 1.1, 0.3), 0.9)
        width_str = f"{latex_width:.2f}\\textwidth"

        lines = [
            f"{indent}\\begin{{center}}",
            f"{indent}  \\includegraphics[width={width_str},keepaspectratio]{{{img.rel_path}}}"
        ]
        if img.caption:
            lines.append(f"{indent}  \\caption{{{escape_latex(img.caption)}}}")
        lines.append(f"{indent}\\end{{center}}")
        return "\n".join(lines)

    @staticmethod
    def _render_table(table: TableElementIR, indent: str) -> str:
        if not table.cells:
            return ""

        col_count = table.cols or (len(table.cells[0]) if table.cells else 1)
        col_spec = "c" * col_count

        lines = [
            f"{indent}\\begin{{center}}",
            f"{indent}\\small",
            f"{indent}\\begin{{tabular}}{{{col_spec}}}",
            f"{indent}  \\toprule"
        ]

        for r_idx, row in enumerate(table.cells):
            cell_strs = []
            for cell in row:
                cell_text = escape_latex(cell.text.strip())
                if cell.bold:
                    cell_text = f"\\textbf{{{cell_text}}}"
                cell_strs.append(cell_text)

            row_line = " & ".join(cell_strs) + " \\\\"
            lines.append(f"{indent}  {row_line}")
            if r_idx == 0 and table.has_header:
                lines.append(f"{indent}  \\midrule")

        lines.append(f"{indent}  \\bottomrule")
        lines.append(f"{indent}\\end{{tabular}}")
        lines.append(f"{indent}\\end{{center}}")
        return "\n".join(lines)
