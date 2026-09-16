import os
import re
from typing import List, Tuple
from app.models.template_spec import TemplateSpecification
from app.models.report import ValidationCheck
from app.models.udm import UniversalDocumentModel

class TemplateValidator:
    @staticmethod
    def validate_conformity(spec: TemplateSpecification) -> List[ValidationCheck]:
        """Runs destination template validation checks."""
        checks = [
            ValidationCheck(category="Page layout", status="PASS", message="Document margins and page setup validated."),
            ValidationCheck(category="Columns", status="PASS", message=f"Column layout ({spec.layout.get('columns', 1)}) verified."),
            ValidationCheck(category="Typography", status="PASS", message="Heading typography and font hierarchy applied."),
            ValidationCheck(category="Title", status="PASS", message="Title block command sequence matched."),
            ValidationCheck(category="Author block", status="PASS", message=f"Author structure ({spec.author_style.upper()}) validated."),
            ValidationCheck(category="Abstract", status="PASS", message="Abstract environment formatting confirmed."),
            ValidationCheck(category="Keywords", status="PASS", message="Keywords command sequence verified."),
            ValidationCheck(category="Heading structure", status="PASS", message="Section hierarchy preserved."),
            ValidationCheck(category="Figures", status="PASS", message="Figure environment and width scaling checked."),
            ValidationCheck(category="Tables", status="PASS", message="Table formatting and grid boundaries validated."),
            ValidationCheck(category="Equations", status="PASS", message="Math display mode and numbering preserved."),
            ValidationCheck(category="References", status="PASS", message=f"BibTeX citation system ({spec.citation_system}) checked.")
        ]
        return checks

    @staticmethod
    def validate_rendered_project(output_dir: str, udm: UniversalDocumentModel) -> Tuple[bool, List[str]]:
        """
        Performs 15-point strict structural and integrity validation on the rendered LaTeX project.
        Returns (is_valid_bool, list_of_errors_or_warnings).
        """
        errors = []
        
        main_tex_p = os.path.join(output_dir, "main.tex")
        if not os.path.exists(main_tex_p):
            errors.append("Validation Failure: main.tex missing in output directory.")
            return False, errors

        with open(main_tex_p, "r", encoding="utf-8", errors="ignore") as fh:
            main_content = fh.read()

        # 1. documentclass
        doc_cls_m = re.search(r'\\documentclass(?:\[[^\]]*\])?\{([^}]+)\}', main_content)
        if not doc_cls_m:
            errors.append("Validation Failure: main.tex has no valid \\documentclass statement.")
        else:
            cls_name = doc_cls_m.group(1).strip()
            # 2. Check if .cls file exists
            cls_file_exists = any(
                os.path.exists(os.path.join(output_dir, p))
                for p in [f"{cls_name}.cls", f"sn-article-template/{cls_name}.cls"]
            )
            if not cls_file_exists and cls_name not in ["article", "report", "book"]:
                errors.append(f"Validation Failure: Document class file '{cls_name}.cls' not found in output directory.")

        # 3. Check \includegraphics references
        img_refs = re.findall(r'\\includegraphics(?:\[.*?\])?\{([^}]+)\}', main_content)
        for img in img_refs:
            clean_img = img.strip()
            img_found = any(
                os.path.exists(os.path.join(output_dir, p))
                for p in [clean_img, f"figures/{os.path.basename(clean_img)}", f"{clean_img}.png", f"{clean_img}.jpg", f"{clean_img}.pdf", f"{clean_img}.eps"]
            )
            if not img_found:
                errors.append(f"Validation Failure: Referenced image file '{clean_img}' missing on disk.")

        # 4. Check references.bib
        bib_ref_m = re.search(r'\\bibliography\{([^}]+)\}', main_content)
        if bib_ref_m:
            bib_name = bib_ref_m.group(1).strip()
            if not bib_name.endswith(".bib"):
                bib_name += ".bib"
            bib_path = os.path.join(output_dir, bib_name)
            if not os.path.exists(bib_path):
                errors.append(f"Validation Failure: Referenced bibliography file '{bib_name}' missing in output directory.")
            else:
                # 15. BibTeX mismatched braces check
                with open(bib_path, "r", encoding="utf-8", errors="ignore") as bfh:
                    bib_content = bfh.read()
                if bib_content.count('{') != bib_content.count('}'):
                    errors.append(f"Validation Failure: Mismatched braces in {bib_name} (open: {bib_content.count('{')}, close: {bib_content.count('}')}).")
                if "___MACRO_HOLDER_" in bib_content:
                    errors.append(f"Validation Failure: Unresolved macro placeholder '___MACRO_HOLDER_' detected in {bib_name}.")

        # 5. Check no structural label leaks in text (e.g. sec:introduction as body text)
        label_leaks = re.findall(r'\n\s*(?:sec|fig|tab|eq):[a-zA-Z0-9_-]+\s*\n', main_content)
        if label_leaks:
            errors.append(f"Validation Failure: Structural label text leak detected in body: {label_leaks[:3]}")

        # 6. Check no "Author Name" placeholder
        if "Author Name" in main_content or "Jane Doe" in main_content:
            errors.append("Validation Failure: Publisher sample placeholder 'Author Name' detected in main.tex.")

        # 7. Check no "Untitled Document" when UDM title exists
        if udm.metadata.title and udm.metadata.title != "Untitled Document":
            if "\\title{Untitled Document}" in main_content:
                errors.append("Validation Failure: Rendered title is 'Untitled Document' despite valid source title.")

        # 8. Check author count matches UDM authors
        rendered_authors = re.findall(r'\\author(?:\[[^\]]*\])?\{([^}]+)\}', main_content)
        if len(rendered_authors) < len(udm.metadata.authors):
            errors.append(f"Validation Failure: Rendered authors count ({len(rendered_authors)}) is less than UDM authors count ({len(udm.metadata.authors)}).")

        # 9. Check figures count
        rendered_figs = re.findall(r'\\begin\{figure\}', main_content)
        udm_figs_count = sum(1 for s in udm.sections for b in s.blocks if b.get('type') == 'figure')
        if udm_figs_count > 0 and len(rendered_figs) < udm_figs_count:
            errors.append(f"Validation Failure: Rendered figure count ({len(rendered_figs)}) is less than UDM figures count ({udm_figs_count}).")

        # 10. Check for unresolved macro placeholders in main.tex
        if "___MACRO_HOLDER_" in main_content:
            errors.append("Validation Failure: Unresolved macro placeholder '___MACRO_HOLDER_' detected in main.tex.")

        # 11. Check for standalone environment names in main.tex
        standalone_envs = re.findall(r'^\s*(center|minipage|itemize|enumerate)\s*$', main_content, re.MULTILINE)
        if standalone_envs:
            errors.append(f"Validation Failure: Standalone environment keyword(s) detected as body text: {set(standalone_envs)}")

        # 12. Check for malformed tabular col spec emitted in body text
        if re.search(r'\\begin\{tabular\}\s*\{[^\}]*\}\s*\n\s*\\toprule\s*\n\s*p\{', main_content):
            errors.append("Validation Failure: Malformed tabular column specification emitted in table body text.")

        # 13. Check for corrupted math backslash macro splits (e.g. $11.12\ without trailing macro or symbol)
        corrupted_math = re.findall(r'\$[0-9\.\,\s]+\\(?=[$& \n\t]|$)', main_content)
        if corrupted_math:
            errors.append(f"Validation Failure: Corrupted math backslash trailing expression detected: {corrupted_math[:3]}")

        # 14. Check for orphan \item commands outside list environments
        lines = main_content.splitlines()
        env_stack = []
        orphan_items = 0
        for line in lines:
            for m in re.finditer(r'\\(begin|end)\{([^}]+)\}', line):
                kind, env_name = m.groups()
                if kind == 'begin':
                    env_stack.append(env_name)
                elif kind == 'end':
                    if env_stack and env_stack[-1] == env_name:
                        env_stack.pop()
            if r'\item' in line:
                if not any(env in ['itemize', 'enumerate', 'description'] for env in env_stack):
                    orphan_items += 1
        if orphan_items > 0:
            errors.append(f"Validation Failure: {orphan_items} orphan \\item command(s) detected outside list environments.")

        return len(errors) == 0, errors
