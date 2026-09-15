import os
import re
import base64
from typing import List, Dict, Any, Tuple, Optional

from app.models.udm import (
    UniversalDocumentModel, Metadata, Author, Affiliation,
    Section, Paragraph, ListBlock, ListItem, Equation, Figure, Table, Reference
)
from app.parsers.zip_utils import find_latex_entrypoint

class LatexParser:
    @staticmethod
    def parse_project(project_dir: str, selected_entrypoint: Optional[str] = None) -> UniversalDocumentModel:
        """Parses a full LaTeX project directory into a UniversalDocumentModel."""
        primary_rel, candidates, all_tex = find_latex_entrypoint(project_dir)
        
        entrypoint_rel = selected_entrypoint or primary_rel
        if not entrypoint_rel:
            raise ValueError("No valid .tex entrypoint containing \\documentclass found in project.")
            
        main_tex_path = os.path.join(project_dir, entrypoint_rel)
        full_content = LatexParser._resolve_includes(main_tex_path, project_dir)
        
        udm = UniversalDocumentModel(source_format="LaTeX Project")
        warnings = []
        
        # 1. Parse Metadata (Title, Authors, Affiliations, Abstract, Keywords)
        udm.metadata = LatexParser._parse_metadata(full_content)
        
        # 2. Parse Bibliography / .bib file
        bib_references = LatexParser._parse_bib_files(project_dir, full_content)
        udm.references = bib_references
        
        # 3. Extract Acknowledgements & Appendices
        ack_m = re.search(r'\\begin\{acknowledgements?\}(.*?)\\end\{acknowledgements?\}', full_content, re.DOTALL | re.I)
        if ack_m:
            udm.acknowledgements = ack_m.group(1).strip()
            
        # 4. Parse Sections, Paragraphs, Equations, Figures, Tables
        sections, parsed_warnings = LatexParser._parse_body(full_content, project_dir)
        udm.sections = sections
        udm.warnings.extend(parsed_warnings)
        
        # 5. Extract Custom Packages & Commands
        packages = re.findall(r'\\usepackage(?:\[[^\]]*\])?\{([^}]+)\}', full_content)
        custom_cmds = re.findall(r'\\(?:newcommand|def)\{\\([a-zA-Z]+)\}', full_content)
        if custom_cmds:
            udm.warnings.append(f"Custom commands detected: \\{', \\'.join(custom_cmds[:4])}")
            
        # Calculate parsing confidence
        confidence = 96.0
        if not udm.metadata.title or udm.metadata.title == "Untitled Document":
            confidence -= 10.0
        if not udm.sections:
            confidence -= 15.0
            
        udm.parsing_confidence = max(50.0, confidence)
        return udm

    @staticmethod
    def _resolve_includes(file_path: str, base_dir: str, visited=None) -> str:
        if visited is None:
            visited = set()
        if file_path in visited or not os.path.exists(file_path):
            return ""
        visited.add(file_path)
        
        with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
            content = fh.read()
            
        # Replace \input{file} and \include{file}
        def replacer(match):
            sub_file = match.group(1).strip()
            if not sub_file.endswith(".tex"):
                sub_file += ".tex"
            sub_path = os.path.join(os.path.dirname(file_path), sub_file)
            if not os.path.exists(sub_path):
                sub_path = os.path.join(base_dir, sub_file)
            return LatexParser._resolve_includes(sub_path, base_dir, visited)

        content = re.sub(r'\\(?:input|include)\{([^}]+)\}', replacer, content)
        return content

    @staticmethod
    def _parse_metadata(content: str) -> Metadata:
        metadata = Metadata()
        
        # Title
        title_match = re.search(r'\\title(?:\[[^\]]*\])?\{([^}]+)\}', content, re.DOTALL)
        if title_match:
            raw_t = title_match.group(1).strip()
            clean_t = re.sub(r'\\[a-zA-Z]+\{([^}]+)\}', r'\1', raw_t)
            clean_t = re.sub(r'\\[a-zA-Z]+', '', clean_t).strip()
            metadata.title = clean_t
            
        # Authors & Affiliations (IEEE, Springer, Elsevier, ACM, Standard formats)
        authors = []
        affiliations = []
        
        # IEEE format (\author{\IEEEauthorblockN{Name}\IEEEauthorblockA{Affil}})
        ieee_authors = re.findall(r'\\IEEEauthorblockN\{([^}]+)\}', content)
        ieee_affils = re.findall(r'\\IEEEauthorblockA\{([^}]+)\}', content)
        if ieee_authors:
            for idx, a_name in enumerate(ieee_authors):
                affil_id = str(idx+1)
                authors.append(Author(name=a_name.strip(), affiliation_ids=[affil_id]))
                if idx < len(ieee_affils):
                    affiliations.append(Affiliation(id=affil_id, institution=ieee_affils[idx].strip()))
        else:
            # Springer / standard format (\author{Name}, \institute{Affil})
            author_matches = re.findall(r'\\author(?:\[[^\]]*\])?\{([^}]+)\}', content)
            for a_str in author_matches:
                clean_name = re.sub(r'\\(?:fnm|sur|email|orcid)\{([^}]+)\}', r'\1', a_str)
                clean_name = re.sub(r'\\[a-zA-Z]+', '', clean_name).strip()
                if clean_name and len(clean_name) < 80:
                    authors.append(Author(name=clean_name))
                    
            inst_matches = re.findall(r'\\(?:institute|orgname|affiliation)\{([^}]+)\}', content)
            for idx, inst_str in enumerate(inst_matches):
                clean_inst = re.sub(r'\\[a-zA-Z]+\{([^}]+)\}', r'\1', inst_str).strip()
                affiliations.append(Affiliation(id=str(idx+1), institution=clean_inst))
                
        metadata.authors = authors if authors else [Author(name="Corresponding Author")]
        metadata.affiliations = affiliations if affiliations else [Affiliation(id="1", institution="Academic Department")]
        
        # Abstract
        abs_match = re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', content, re.DOTALL)
        if abs_match:
            metadata.abstract = abs_match.group(1).strip()
            
        # Keywords
        kw_match = re.search(r'\\(?:keywords|begin\{keywords\})(.*?)(?:\\end\{keywords\}|\}\n|\}\r)', content, re.DOTALL)
        if kw_match:
            kw_raw = kw_match.group(1).replace('{', '').replace('}', '').strip()
            metadata.keywords = [k.strip() for k in re.split(r'[,;•\n]', kw_raw) if k.strip()]
            
        return metadata

    @staticmethod
    def _parse_bib_files(base_dir: str, content: str) -> List[Reference]:
        references = []
        
        # Find all .bib files in base_dir
        found_bib_paths = []
        for root, _, files in os.walk(base_dir):
            for f in files:
                if f.endswith(".bib"):
                    found_bib_paths.append(os.path.join(root, f))
                    
        for bib_p in found_bib_paths:
            try:
                with open(bib_p, "r", encoding="utf-8", errors="ignore") as fh:
                    bib_text = fh.read()
                    
                entries = re.findall(r'@(\w+)\s*\{\s*([^,\s]+)\s*,(.*?)\n\}', bib_text, re.DOTALL)
                for entry_type, cite_key, fields_str in entries:
                    title_m = re.search(r'title\s*=\s*[\"\{](.*?)[\"\}],', fields_str, re.I | re.DOTALL)
                    author_m = re.search(r'author\s*=\s*[\"\{](.*?)[\"\}],', fields_str, re.I | re.DOTALL)
                    year_m = re.search(r'year\s*=\s*[\"\{]?(\d{4})[\"\}]?', fields_str, re.I)
                    journal_m = re.search(r'journal\s*=\s*[\"\{](.*?)[\"\}],', fields_str, re.I | re.DOTALL)
                    
                    title = title_m.group(1).strip() if title_m else "Untitled Reference"
                    author_list = [a.strip() for a in author_m.group(1).split("and")] if author_m else []
                    
                    references.append(Reference(
                        id=f"ref_{cite_key}",
                        cite_key=cite_key,
                        entry_type=entry_type.lower(),
                        title=title,
                        authors=author_list,
                        journal=journal_m.group(1).strip() if journal_m else None,
                        year=year_m.group(1) if year_m else None,
                        raw_bibtex=f"@{entry_type}{{{cite_key},\n{fields_str}\n}}"
                    ))
            except Exception:
                pass
                
        # Fallback: parse \bibitem entries in \begin{thebibliography}
        if not references:
            bibitems = re.findall(r'\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}(.*?)(?=\\bibitem|\\end\{thebibliography\}|$)', content, re.DOTALL)
            for cite_key, b_text in bibitems:
                clean_text = re.sub(r'\\[a-zA-Z]+', '', b_text).strip()
                references.append(Reference(
                    id=f"ref_{cite_key}",
                    cite_key=cite_key,
                    title=clean_text[:100],
                    raw_bibtex=clean_text
                ))
                
        return references

    @staticmethod
    def _parse_body(content: str, base_dir: str) -> Tuple[List[Section], List[str]]:
        sections = []
        warnings = []
        
        # Split content by \section
        raw_sections = re.split(r'\\section\*?\{([^}]+)\}', content)
        
        for i in range(1, len(raw_sections), 2):
            sec_title = raw_sections[i].strip()
            sec_body = raw_sections[i+1] if i+1 < len(raw_sections) else ""
            
            section_obj = Section(title=sec_title, level=1, blocks=[])
            
            # Subsections
            subsections = re.split(r'\\subsection\*?\{([^}]+)\}', sec_body)
            
            for j in range(0, len(subsections)):
                if j == 0:
                    text_block = subsections[j]
                else:
                    if j % 2 == 1:
                        sub_title = subsections[j]
                        sub_body = subsections[j+1] if j+1 < len(subsections) else ""
                        text_block = f"\\subsection{{{sub_title}}}\n" + sub_body
                    else:
                        continue
                        
                # Extract figures
                fig_matches = re.findall(r'\\begin\{figure[*]?\}(.*?)\\end\{figure[*]?\}', text_block, re.DOTALL)
                for fig_str in fig_matches:
                    img_match = re.search(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}', fig_str)
                    cap_match = re.search(r'\\caption\{([^}]+)\}', fig_str)
                    lbl_match = re.search(r'\\label\{([^}]+)\}', fig_str)
                    
                    img_path = img_match.group(1).strip() if img_match else "figure.png"
                    caption = cap_match.group(1).strip() if cap_match else ""
                    label = lbl_match.group(1).strip() if lbl_match else None
                    
                    b64_str = LatexParser._load_image_b64(base_dir, img_path)
                    
                    fig_id = f"fig_{len(section_obj.blocks)+1}"
                    section_obj.blocks.append(Figure(
                        id=fig_id,
                        caption=caption,
                        label=label,
                        image_filename=os.path.basename(img_path),
                        image_data_b64=b64_str,
                        original_path=img_path
                    ).model_dump())
                    
                # Extract tables
                tbl_matches = re.findall(r'\\begin\{table[*]?\}(.*?)\\end\{table[*]?\}', text_block, re.DOTALL)
                for tbl_str in tbl_matches:
                    cap_match = re.search(r'\\caption\{([^}]+)\}', tbl_str)
                    lbl_match = re.search(r'\\label\{([^}]+)\}', tbl_str)
                    caption = cap_match.group(1).strip() if cap_match else ""
                    
                    tab_match = re.search(r'\\begin\{tabular\}\{([^}]+)\}(.*?)\\end\{tabular\}', tbl_str, re.DOTALL)
                    rows = []
                    headers = []
                    if tab_match:
                        raw_tab = tab_match.group(2)
                        raw_rows = [r.strip() for r in raw_tab.split(r'\\') if r.strip()]
                        for r_idx, r_str in enumerate(raw_rows):
                            cells = [re.sub(r'\\[a-zA-Z]+', '', c).strip() for c in r_str.split('&')]
                            if r_idx == 0:
                                headers = cells
                            else:
                                rows.append(cells)
                                
                    section_obj.blocks.append(Table(
                        id=f"tbl_{len(section_obj.blocks)+1}",
                        caption=caption,
                        label=lbl_match.group(1) if lbl_match else None,
                        headers=headers,
                        rows=rows
                    ).model_dump())
                    
                # Extract Equations
                eq_matches = re.findall(r'\\begin\{(?:equation|align)[*]?\}(.*?)\\end\{(?:equation|align)[*]?\}', text_block, re.DOTALL)
                for eq_str in eq_matches:
                    lbl_m = re.search(r'\\label\{([^}]+)\}', eq_str)
                    clean_eq = re.sub(r'\\label\{[^}]+\}', '', eq_str).strip()
                    section_obj.blocks.append(Equation(
                        math_latex=clean_eq,
                        label=lbl_m.group(1) if lbl_m else None
                    ).model_dump())
                    
                # Clean text paragraphs
                clean_p_text = re.sub(r'\\begin\{(?:figure|table|equation|align)[*]?\}.*?\\end\{(?:figure|table|equation|align)[*]?\}', '', text_block, flags=re.DOTALL)
                clean_p_text = re.sub(r'\\[a-zA-Z]+\{([^}]+)\}', r'\1', clean_p_text)
                clean_p_text = re.sub(r'\\[a-zA-Z]+', '', clean_p_text).strip()
                
                paras = [p.strip() for p in clean_p_text.split("\n\n") if len(p.strip()) > 10]
                for p in paras:
                    section_obj.blocks.append(Paragraph(text=p).model_dump())
                    
            sections.append(section_obj)
            
        return sections, warnings

    @staticmethod
    def _load_image_b64(base_dir: str, rel_path: str) -> Optional[str]:
        possible_paths = [
            os.path.join(base_dir, rel_path),
            os.path.join(base_dir, "figures", os.path.basename(rel_path)),
            os.path.join(base_dir, "images", os.path.basename(rel_path)),
        ]
        for ext in ["", ".png", ".jpg", ".jpeg", ".pdf"]:
            for p in possible_paths:
                full_p = p + ext
                if os.path.exists(full_p) and os.path.isfile(full_p):
                    try:
                        with open(full_p, "rb") as fh:
                            return base64.b64encode(fh.read()).decode("utf-8")
                    except Exception:
                        pass
        return None
