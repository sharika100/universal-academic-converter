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
        
        # Strip LaTeX comments (% ...) before parsing metadata and body
        uncommented_content = re.sub(r'%\s*\n', '\n', full_content)
        uncommented_content = re.sub(r'%.*', '', uncommented_content)

        udm = UniversalDocumentModel(source_format="LaTeX Project")
        warnings = []
        
        # 1. Parse Metadata (Title, Authors, Affiliations, Abstract, Keywords)
        udm.metadata = LatexParser._parse_metadata(uncommented_content)
        
        # 2. Parse Bibliography / .bib file
        bib_references = LatexParser._parse_bib_files(project_dir, uncommented_content)
        udm.references = bib_references
        
        # 3. Extract Acknowledgements & Appendices
        ack_m = re.search(r'\\begin\{acknowledgements?\}(.*?)\\end\{acknowledgements?\}', uncommented_content, re.DOTALL | re.I)
        if ack_m:
            udm.acknowledgements = ack_m.group(1).strip()
            
        # 4. Parse Sections, Paragraphs, Equations, Figures, Tables
        sections, parsed_warnings = LatexParser._parse_body(uncommented_content, project_dir)
        udm.sections = sections
        udm.warnings.extend(parsed_warnings)
        
        # 5. Extract Custom Packages & Commands
        packages = re.findall(r'\\usepackage(?:\[[^\]]*\])?\{([^}]+)\}', uncommented_content)
        custom_cmds = re.findall(r'\\(?:newcommand|def)\{\\([a-zA-Z]+)\}', uncommented_content)
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
        title_match = re.search(r'\\title\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}', content, re.DOTALL)
        if title_match:
            raw_t = title_match.group(1).strip()
            raw_t = re.sub(r'\\(?:tnoteref|fnref|corref|thanks|label)\{[^}]*\}', '', raw_t)
            clean_t = re.sub(r'\\[a-zA-Z]+\{([^}]+)\}', r'\1', raw_t)
            clean_t = re.sub(r'\\[a-zA-Z]+', '', clean_t).strip()
            if clean_t and clean_t.lower() not in ["untitled document", "template", "sample"]:
                metadata.title = clean_t
            
        authors = []
        affiliations = []
        
        # 1. IEEE format (\author{\IEEEauthorblockN{Name}\IEEEauthorblockA{Affil}})
        ieee_authors = re.findall(r'\\IEEEauthorblockN\{([^}]+)\}', content)
        ieee_affils = re.findall(r'\\IEEEauthorblockA\{([^}]+)\}', content)
        if ieee_authors:
            for idx, a_name in enumerate(ieee_authors):
                affil_id = str(idx+1)
                authors.append(Author(name=a_name.strip(), affiliation_ids=[affil_id]))
                if idx < len(ieee_affils):
                    affiliations.append(Affiliation(id=affil_id, institution=ieee_affils[idx].strip()))
        else:
            # 2. Parse Affiliations first (Key-value or string macros)
            affil_map = {}
            
            # Key-Value / Nested Macro Affiliations: \affiliation[id]{ organization={...}, addressline={...}, ... }
            affil_macro_pattern = re.compile(r'\\(?:affiliation|address|institute)(?:\[([^\]]*)\])?\s*\{')
            for m in affil_macro_pattern.finditer(content):
                aff_id = m.group(1) or str(len(affil_map) + 1)
                start_idx = m.end()
                depth = 1
                i = start_idx
                while i < len(content) and depth > 0:
                    if content[i] == '{':
                        depth += 1
                    elif content[i] == '}':
                        depth -= 1
                    i += 1
                aff_body = content[start_idx:i-1]
                
                # Check for key-values
                kv = dict(re.findall(r'(\w+)\s*=\s*\{([^}]+)\}', aff_body))
                if kv:
                    parts = [kv[k].strip() for k in ['organization', 'addressline', 'city', 'postcode', 'state', 'country'] if k in kv and kv[k].strip()]
                    full_inst = ', '.join(parts) if parts else aff_body.strip()
                else:
                    full_inst = re.sub(r'\\[a-zA-Z]+\{([^}]+)\}', r'\1', aff_body)
                    full_inst = re.sub(r'\\[a-zA-Z]+', '', full_inst).strip()
                    
                if full_inst and aff_id not in affil_map:
                    affil_map[aff_id] = Affiliation(id=aff_id, institution=full_inst)
                    
            for aff_obj in affil_map.values():
                affiliations.append(aff_obj)

            # 3. Parse Authors: \author[aff_ids]{Name}
            author_macro_pattern = re.compile(r'\\author(?:\[([^\]]*)\])?\s*\{([^}]+)\}')
            seen_author_names = set()

            for m in author_macro_pattern.finditer(content):
                aff_tags = m.group(1) or ""
                a_name_raw = m.group(2).strip()
                
                clean_name = re.sub(r'\\(?:fnm|sur|email|orcid|corref|fnref)\{([^}]+)\}', r'\1', a_name_raw)
                clean_name = re.sub(r'\\[a-zA-Z]+', '', clean_name).strip()
                clean_name = re.sub(r'[^a-zA-Z0-9\s.-]', '', clean_name).strip()
                
                name_lower = clean_name.lower()
                placeholder_names = ["author name", "first author", "second author", "third author", "fourth author", "jane doe", "john doe", "author 1", "author 2", "sample author"]
                
                if clean_name and len(clean_name) < 80 and not any(p in name_lower for p in placeholder_names):
                    # Check for duplicate names
                    norm_key = re.sub(r'[^a-z]', '', name_lower)
                    if norm_key not in seen_author_names:
                        seen_author_names.add(norm_key)
                        aff_ids = [t.strip() for t in aff_tags.split(',') if t.strip()]
                        if not aff_ids and affiliations:
                            aff_ids = [affiliations[0].id]
                        authors.append(Author(name=clean_name, affiliation_ids=aff_ids))

        if authors:
            metadata.authors = authors
        if affiliations:
            metadata.affiliations = affiliations
        
        # Abstract
        abs_match = re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', content, re.DOTALL)
        if abs_match:
            metadata.abstract = abs_match.group(1).strip()
            
        # Keywords
        kw_match = re.search(r'\\(?:keywords|begin\{keywords\})(.*?)(?:\\end\{keywords\}|\}\n|\}\r|\n\n)', content, re.DOTALL)
        if kw_match:
            kw_raw = kw_match.group(1).replace('{', '').replace('}', '').strip()
            metadata.keywords = [k.strip() for k in re.split(r'[,;•\n]', kw_raw) if k.strip()]
            
        return metadata

    @staticmethod
    def _parse_bib_files(base_dir: str, content: str) -> List[Reference]:
        references = []
        
        found_bib_paths = []
        for root, _, files in os.walk(base_dir):
            for f in files:
                if f.endswith(".bib"):
                    found_bib_paths.append(os.path.join(root, f))
                    
        for bib_p in found_bib_paths:
            try:
                with open(bib_p, "r", encoding="utf-8", errors="ignore") as fh:
                    bib_text = fh.read()
                    
                entries = re.findall(r'@(\w+)\s*\{\s*([^,\s]+)\s*,(.*?)(?=\n@|\Z)', bib_text, re.DOTALL)
                for entry_type, cite_key, fields_str in entries:
                    title_m = re.search(r'title\s*=\s*[\"\{](.*?)[\"\}],', fields_str, re.I | re.DOTALL)
                    author_m = re.search(r'author\s*=\s*[\"\{](.*?)[\"\}],', fields_str, re.I | re.DOTALL)
                    year_m = re.search(r'year\s*=\s*[\"\{]?(\d{4})[\"\}]?', fields_str, re.I)
                    journal_m = re.search(r'journal\s*=\s*[\"\{](.*?)[\"\}],', fields_str, re.I | re.DOTALL)
                    
                    title = title_m.group(1).strip() if title_m else "Untitled Reference"
                    author_list = [a.strip() for a in author_m.group(1).split("and")] if author_m else []
                    
                    f_strip = fields_str.strip()
                    if not f_strip.endswith('}'):
                        f_strip += '\n}'
                        
                    references.append(Reference(
                        id=f"ref_{cite_key}",
                        cite_key=cite_key,
                        entry_type=entry_type.lower(),
                        title=title,
                        authors=author_list,
                        journal=journal_m.group(1).strip() if journal_m else None,
                        year=year_m.group(1) if year_m else None,
                        raw_bibtex=f"@{entry_type}{{{cite_key},\n{f_strip}"
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
        
        # Strip non-body metadata commands and bio environments before section splitting
        content = re.sub(r'\\(?:bibliography|bibliographystyle|nocite|biboptions|printbibliography)\{[^}]*\}', '', content, flags=re.DOTALL)
        content = re.sub(r'\\begin\{bio(?:graphy)?\}.*?\\end\{bio(?:graphy)?\}', '', content, flags=re.DOTALL)
        content = re.sub(r'\\bio(?:\[[^\]]*\])?\{[^}]*\}.*?(?=\\endbio|\\section|\Z)', '', content, flags=re.DOTALL)
        
        # Split content by \section
        raw_sections = re.split(r'\\section\*?\{([^}]+)\}', content)
        
        for i in range(1, len(raw_sections), 2):
            sec_title = raw_sections[i].strip()
            sec_body = raw_sections[i+1] if i+1 < len(raw_sections) else ""
            
            # Extract section label if present at start of sec_body
            sec_lbl_m = re.match(r'\s*\\label\{([^}]+)\}', sec_body)
            sec_label = sec_lbl_m.group(1) if sec_lbl_m else None
            
            section_obj = Section(title=sec_title, level=1, label=sec_label, blocks=[])
            
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
                        
                block_list = []
                
                # Extract figures (\includegraphics)
                img_matches = re.finditer(r'\\includegraphics(?:\[([^\]]*)\])?\{([^}]+)\}', text_block)
                for m in img_matches:
                    img_path = m.group(2).strip()
                    pos = m.start()
                    surrounding = text_block[max(0, pos-300):min(len(text_block), pos+400)]
                    
                    cap_m = re.search(r'\\caption(?:of\{figure\})?\{([^}]+)\}', surrounding)
                    lbl_m = re.search(r'\\label\{([^}]+)\}', surrounding)
                    
                    caption = cap_m.group(1).strip() if cap_m else ""
                    label = lbl_m.group(1).strip() if lbl_m else None
                    
                    found_p, b64_str = LatexParser._load_image_b64(base_dir, img_path)
                    
                    fig_id = f"fig_{len(section_obj.blocks)+len(block_list)+1}"
                    fig_dict = Figure(
                        id=fig_id,
                        caption=caption,
                        label=label,
                        image_filename=os.path.basename(found_p or img_path),
                        image_data_b64=b64_str,
                        original_path=img_path
                    ).model_dump()
                    fig_dict["_pos"] = pos
                    block_list.append(fig_dict)
                    
                # Extract tables
                tbl_matches = re.finditer(r'\\begin\{table[*]?\}(.*?)\\end\{table[*]?\}', text_block, re.DOTALL)
                for tm in tbl_matches:
                    tbl_str = tm.group(1)
                    pos = tm.start()
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
                            cell_list = []
                            for c in r_str.split('&'):
                                c_str = c.strip()
                                c_placeholders = []
                                def protect_cell_cite(m_c):
                                    c_placeholders.append(m_c.group(0))
                                    return f"___CELL_CITE_{len(c_placeholders)-1}___"
                                c_str = re.sub(r'\\cite[a-zA-Z]*(?:\[[^\]]*\])*\{[^}]+\}', protect_cell_cite, c_str)
                                c_str = re.sub(r'\\[a-zA-Z]+\{([^}]+)\}', r'\1', c_str)
                                c_str = re.sub(r'\\(?:textbf|textit|emph|hline|toprule|midrule|bottomrule)', '', c_str).strip()
                                for c_idx, orig_c in enumerate(c_placeholders):
                                    c_str = c_str.replace(f"___CELL_CITE_{c_idx}___", orig_macro) if 'orig_macro' in locals() else c_str.replace(f"___CELL_CITE_{c_idx}___", orig_c)
                                cell_list.append(c_str)
                            if r_idx == 0:
                                headers = cell_list
                            else:
                                rows.append(cell_list)
                                
                    tbl_dict = Table(
                        id=f"tbl_{len(section_obj.blocks)+len(block_list)+1}",
                        caption=caption,
                        label=lbl_match.group(1) if lbl_match else None,
                        headers=headers,
                        rows=rows
                    ).model_dump()
                    tbl_dict["_pos"] = pos
                    block_list.append(tbl_dict)
                    
                # Extract Equations
                eq_matches = re.finditer(r'\\begin\{(?:equation|align)[*]?\}(.*?)\\end\{(?:equation|align)[*]?\}', text_block, re.DOTALL)
                for em in eq_matches:
                    eq_str = em.group(1)
                    pos = em.start()
                    lbl_m = re.search(r'\\label\{([^}]+)\}', eq_str)
                    clean_eq = re.sub(r'\\label\{[^}]+\}', '', eq_str).strip()
                    eq_dict = Equation(
                        math_latex=clean_eq,
                        label=lbl_m.group(1) if lbl_m else None
                    ).model_dump()
                    eq_dict["_pos"] = pos
                    block_list.append(eq_dict)
                    
                # Extract Lists (\begin{itemize}...\end{itemize} and \begin{enumerate}...\end{enumerate})
                list_matches = re.finditer(r'\\begin\{(itemize|enumerate)\}(.*?)\\end\{\1\}', text_block, re.DOTALL)
                for lm in list_matches:
                    env_type = lm.group(1)
                    list_body = lm.group(2)
                    pos = lm.start()
                    is_ordered = (env_type == "enumerate")
                    
                    raw_items = re.findall(r'\\item\s*(.*?)(?=\\item|\Z)', list_body, re.DOTALL)
                    items = []
                    for raw_i in raw_items:
                        clean_i = raw_i.strip()
                        if clean_i:
                            i_placeholders = []
                            def protect_item_macro(match):
                                i_placeholders.append(match.group(0))
                                return f"___ITEM_MACRO_{len(i_placeholders)-1}___"
                            clean_i = re.sub(r'\\cite[a-zA-Z]*(?:\[[^\]]*\])*\{[^}]+\}', protect_item_macro, clean_i)
                            clean_i = re.sub(r'\\(?:ref|pageref|eqref)\{[^}]+\}', protect_item_macro, clean_i)
                            clean_i = re.sub(r'\$[^$]+\$', protect_item_macro, clean_i)
                            
                            clean_i = re.sub(r'\\[a-zA-Z]+\{([^}]+)\}', r'\1', clean_i)
                            clean_i = re.sub(r'\\(?:textbf|textit|emph|textrm|sf|tt|large|small|noindent)', '', clean_i).strip()
                            
                            for p_idx, orig_macro in enumerate(i_placeholders):
                                clean_i = clean_i.replace(f"___ITEM_MACRO_{p_idx}___", orig_macro)
                            items.append({"text": clean_i})
                            
                    if items:
                        block_list.append({
                            "_pos": pos,
                            "type": "list",
                            "ordered": is_ordered,
                            "items": items
                        })
                    
                # Clean text paragraphs while preserving in-text citations (\cite, \citep, \citet), refs, and math
                clean_p_text = re.sub(r'\\begin\{(?:figure|table|equation|align|strip|itemize|enumerate)[*]?\}.*?\\end\{(?:figure|table|equation|align|strip|itemize|enumerate)[*]?\}', '', text_block, flags=re.DOTALL)
                clean_p_text = re.sub(r'\\item\b', '', clean_p_text)
                clean_p_text = re.sub(r'\\includegraphics(?:\[[^\]]*\])?\{[^}]+\}', '', clean_p_text)
                clean_p_text = re.sub(r'\\caption(?:of\{figure\})?\{[^}]+\}', '', clean_p_text)
                clean_p_text = re.sub(r'\\label\{[^}]+\}', '', clean_p_text) # STRIP LABELS PREVENTING LEAK
                clean_p_text = re.sub(r'\\(?:bibliography|bibliographystyle|nocite|biboptions|printbibliography)\{[^}]*\}', '', clean_p_text, flags=re.DOTALL)
                clean_p_text = re.sub(r'\\begin\{bio(?:graphy)?\}.*?\\end\{bio(?:graphy)?\}', '', clean_p_text, flags=re.DOTALL)
                clean_p_text = re.sub(r'\\bio(?:\[[^\]]*\])?\{[^}]*\}.*?(?=\\endbio|\Z)', '', clean_p_text, flags=re.DOTALL)
                
                # Protect citations, refs, and math using temporary placeholders
                placeholders = []
                def protect_macro(match):
                    placeholders.append(match.group(0))
                    return f"___MACRO_HOLDER_{len(placeholders)-1}___"
                
                # Protect \cite, \citep, \citet, \citeauthor, \citeyear, \citealt, \citealp
                clean_p_text = re.sub(r'\\cite[a-zA-Z]*(?:\[[^\]]*\])*\{[^}]+\}', protect_macro, clean_p_text)
                # Protect \ref, \pageref, \eqref
                clean_p_text = re.sub(r'\\(?:ref|pageref|eqref)\{[^}]+\}', protect_macro, clean_p_text)
                # Protect inline math ($...$)
                clean_p_text = re.sub(r'\$[^$]+\$', protect_macro, clean_p_text)
                
                # Clean remaining formatting macros
                clean_p_text = re.sub(r'\\[a-zA-Z]+\{([^}]+)\}', r'\1', clean_p_text)
                clean_p_text = re.sub(r'\\(?:textbf|textit|emph|textrm|sf|tt|large|small|noindent)', '', clean_p_text).strip()
                
                # Restore protected citations, refs, and math
                for p_idx, orig_macro in enumerate(placeholders):
                    clean_p_text = clean_p_text.replace(f"___MACRO_HOLDER_{p_idx}___", orig_macro)
                
                paras = [p.strip() for p in clean_p_text.split("\n\n") if len(p.strip()) > 15]
                for p in paras:
                    if not re.match(r'^(?:sec|fig|tab|eq):[a-zA-Z0-9_-]+$', p.strip()):
                        p_pos = text_block.find(p[:25])
                        if p_pos == -1:
                            p_pos = text_block.find(p[:15])
                        if p_pos == -1:
                            p_pos = 999999
                        p_dict = Paragraph(text=p).model_dump()
                        p_dict["_pos"] = p_pos
                        block_list.append(p_dict)
                        
                block_list.sort(key=lambda b: b.get("_pos", 0))
                for b in block_list:
                    b.pop("_pos", None)
                    section_obj.blocks.append(b)
                    
            sections.append(section_obj)
            
        return sections, warnings

    @staticmethod
    def _load_image_b64(base_dir: str, rel_path: str) -> Tuple[Optional[str], Optional[str]]:
        rel_clean = rel_path.strip().replace('\\', '/')
        fname = os.path.basename(rel_clean)
        fname_no_ext = os.path.splitext(fname)[0]
        
        search_dirs = [
            base_dir,
            os.path.join(base_dir, 'figures'),
            os.path.join(base_dir, 'images'),
            os.path.dirname(os.path.join(base_dir, rel_clean))
        ]
        
        extensions = ['', '.png', '.PNG', '.jpg', '.JPG', '.jpeg', '.pdf', '.eps']
        for d in search_dirs:
            for ext in extensions:
                target = os.path.join(d, fname_no_ext + ext) if ext else os.path.join(d, fname)
                if os.path.exists(target) and os.path.isfile(target):
                    try:
                        with open(target, 'rb') as fh:
                            return target, base64.b64encode(fh.read()).decode('utf-8')
                    except Exception:
                        pass
        return None, None
