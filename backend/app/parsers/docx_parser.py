import os
import re
import base64
import hashlib
from typing import List, Dict, Any, Tuple, Optional
import docx
from docx.document import Document as DocxDocument
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph as DocxParagraph

from app.models.udm import (
    UniversalDocumentModel, Metadata, Author, Affiliation,
    Section, Paragraph, ListBlock, ListItem, Equation, Figure, Table, Reference
)

class DocxParser:
    @staticmethod
    def parse(docx_path: str) -> UniversalDocumentModel:
        try:
            doc = docx.Document(docx_path)
        except Exception as e:
            raise ValueError(f"Could not open file as DOCX package: {str(e)}")
            
        udm = UniversalDocumentModel(source_format="DOCX")
        warnings = []
        
        # 1. Extract Images from document package
        rel_image_map = DocxParser._extract_images(doc)
        
        # Global state for document traversal
        occurrence_counter = 0
        
        body_elements = list(doc.element.body)
        title_idx = -1
        first_heading_idx = len(body_elements)
        
        # Locate Title and first Section Heading
        for idx, elem in enumerate(body_elements):
            if isinstance(elem, CT_P):
                p = DocxParagraph(elem, doc)
                text = p.text.strip()
                style_name = p.style.name.lower() if p.style else ""
                if not text:
                    continue
                if title_idx == -1 and ("title" in style_name or (len(text) > 5 and len(text) < 180 and idx < 5)):
                    title_idx = idx
                if "heading 1" in style_name or (text.isupper() and len(text) < 60 and idx > 0):
                    first_heading_idx = min(first_heading_idx, idx)
                    
        # Parse Title & Author/Affiliation block from top section
        header_lines = []
        if title_idx != -1:
            title_p = DocxParagraph(body_elements[title_idx], doc)
            udm.metadata.title = title_p.text.strip()
            header_end = min(first_heading_idx, title_idx + 12)
            
            for idx in range(title_idx + 1, header_end):
                elem = body_elements[idx]
                if isinstance(elem, CT_P):
                    p = DocxParagraph(elem, doc)
                    if p.text.strip():
                        header_lines.append(DocxParser._parse_paragraph_runs(p))
                        
            parsed_authors, parsed_affils, header_raw = DocxParser._parse_author_header(header_lines)
            if parsed_authors:
                udm.metadata.authors = parsed_authors
            if parsed_affils:
                udm.metadata.affiliations = parsed_affils
            udm.metadata.header_raw_text = header_raw
            
        consumed_header_texts = set()
        for d in header_lines:
            txt = d.get("full_text", "").strip()
            if txt:
                consumed_header_texts.add(txt.lower())

        # 2. Iterate elements sequentially (Paragraphs, Tables, Drawings, Images)
        sections = []
        current_section = Section(title="Introduction", level=1, blocks=[])
        
        title_found = False
        abstract_found = False
        references_found = False
        first_heading_found = False
        pending_caption = None
        
        def process_paragraph_element(p: DocxParagraph, elem_idx: int):
            nonlocal occurrence_counter, current_section, pending_caption, abstract_found, references_found, first_heading_found
            
            text = p.text.strip()
            style_name = p.style.name.lower() if p.style else ""
            
            # Extract image relationship IDs from paragraph XML
            para_rids = DocxParser._get_paragraph_image_rids(p, rel_image_map)
            is_caption = bool(re.match(r'^(fig|figure|chart|diagram)\b', text, re.I)) or "caption" in style_name
            
            if para_rids:
                for rId in para_rids:
                    img_info = rel_image_map[rId]
                    occurrence_counter += 1
                    occ_id = f"fig_occ_{occurrence_counter}"
                    fig_id = f"fig_{occurrence_counter}"
                    ext = img_info.get("ext", ".png")
                    fname = f"figure_{occurrence_counter}{ext}"
                    
                    caption_text = ""
                    if is_caption:
                        caption_text = text
                    elif pending_caption:
                        caption_text = pending_caption
                        pending_caption = None
                    else:
                        for next_i in range(elem_idx + 1, min(len(body_elements), elem_idx + 3)):
                            next_elem = body_elements[next_i]
                            if isinstance(next_elem, CT_P):
                                next_p = DocxParagraph(next_elem, doc)
                                next_txt = next_p.text.strip()
                                if re.match(r'^(fig|figure)\b', next_txt, re.I):
                                    caption_text = next_txt
                                    break
                                    
                    is_equation = not caption_text and ("w:math" in p._element.xml or "m:oMath" in p._element.xml)
                    
                    if is_equation:
                        current_section.blocks.append(Equation(
                            math_latex=f"\\includegraphics[max width=0.8\\linewidth]{{figures/{fname}}}",
                            label=f"eq_{occurrence_counter}"
                        ).model_dump())
                    else:
                        fig_obj = Figure(
                            id=fig_id,
                            occurrence_id=occ_id,
                            rel_id=rId,
                            original_filename=os.path.basename(img_info.get("media_path", "")),
                            media_path=img_info.get("media_path"),
                            content_type=f"image/{ext.lstrip('.')}",
                            sha256=img_info.get("sha256"),
                            caption=caption_text or f"Figure {occurrence_counter}",
                            image_filename=fname,
                            image_data_b64=img_info["b64"],
                            position_index=occurrence_counter
                        )
                        current_section.blocks.append(fig_obj.model_dump())
                if not is_caption:
                    return
                    
            if not text:
                return
                
            if is_caption:
                if current_section.blocks and isinstance(current_section.blocks[-1], dict) and current_section.blocks[-1].get("type") == "figure":
                    current_section.blocks[-1]["caption"] = text
                else:
                    pending_caption = text
                return
                
            # Prevent header metadata and author emails from leaking into body text
            if elem_idx < first_heading_idx:
                text_lower = text.lower()
                if "@" in text or text_lower in consumed_header_texts:
                    return
                if any(kw in text_lower for kw in ["research scholar", "professor", "associate professor", "assistant professor", "coimbatore", "tamil nadu", "department", "university", "institute"]):
                    return
                if udm.metadata.authors and any(a.name.lower() in text_lower for a in udm.metadata.authors):
                    return
                if udm.metadata.affiliations and any(aff.institution.lower() in text_lower for aff in udm.metadata.affiliations):
                    return
                    
            # Check for Abstract
            if text.lower().startswith("abstract") or "abstract" in style_name:
                clean_abs = re.sub(r'^(abstract[:\.\s-]*)', '', text, flags=re.I).strip()
                if clean_abs:
                    udm.metadata.abstract = clean_abs
                abstract_found = True
                return
            elif abstract_found and not udm.metadata.abstract and len(text) > 20:
                udm.metadata.abstract = text
                abstract_found = False
                return
                
            # Check for Keywords
            if text.lower().startswith("keyword"):
                kw_str = re.sub(r'^(keywords?[:\.\s-]*)', '', text, flags=re.I)
                udm.metadata.keywords = [k.strip() for k in re.split(r'[,;]', kw_str) if k.strip()]
                return
                
            # Check for Headings
            is_heading = False
            heading_level = 1
            if "heading 1" in style_name or (text.isupper() and len(text) < 60 and elem_idx >= first_heading_idx):
                is_heading = True
                heading_level = 1
            elif "heading 2" in style_name:
                is_heading = True
                heading_level = 2
            elif "heading 3" in style_name:
                is_heading = True
                heading_level = 3
                
            if is_heading:
                clean_title = re.sub(r'^\d+[\.\s]*', '', text).strip() or text
                if clean_title.lower() in ["references", "bibliography"]:
                    references_found = True
                    return
                if not first_heading_found:
                    first_heading_found = True
                    if not current_section.blocks or current_section.title.lower() in ["introduction", "main content"]:
                        current_section.title = clean_title
                        current_section.level = heading_level
                        return
                if current_section.blocks:
                    sections.append(current_section)
                current_section = Section(title=clean_title, level=heading_level, blocks=[])
                return
                
            # References
            if references_found:
                ref_id = f"ref_{len(udm.references)+1}"
                udm.references.append(Reference(
                    id=ref_id,
                    cite_key=ref_id,
                    title=text,
                    raw_bibtex=text
                ))
                return
                
            # List Bullet
            if "bullet" in style_name or "list" in style_name or text.startswith("•") or text.startswith("-"):
                clean_item = text.lstrip("•- ").strip()
                if current_section.blocks and isinstance(current_section.blocks[-1], dict) and current_section.blocks[-1].get("type") == "list":
                    if "items" in current_section.blocks[-1] and isinstance(current_section.blocks[-1]["items"], list):
                        current_section.blocks[-1]["items"].append({"text": clean_item, "depth": 1})
                    else:
                        current_section.blocks[-1]["items"] = [{"text": clean_item, "depth": 1}]
                else:
                    current_section.blocks.append(ListBlock(
                        ordered="number" in style_name,
                        items=[ListItem(text=clean_item, depth=1)]
                    ).model_dump())
                return
                
            # Equation
            if "w:math" in p._element.xml or "m:oMath" in p._element.xml or (text.startswith("$$") and text.endswith("$$")):
                math_tex = re.sub(r'^\$\$|\$\$$', '', text).strip()
                current_section.blocks.append(Equation(
                    math_latex=math_tex or text,
                    label=f"eq_{len(current_section.blocks)+1}"
                ).model_dump())
                return
                
            # Paragraph
            current_section.blocks.append(Paragraph(text=text).model_dump())

        for idx, elem in enumerate(body_elements):
            if idx == title_idx:
                continue
            if isinstance(elem, CT_P):
                p = DocxParagraph(elem, doc)
                process_paragraph_element(p, idx)
            elif isinstance(elem, CT_Tbl):
                t = DocxTable(elem, doc)
                headers = []
                rows = []
                for r_idx, row in enumerate(t.rows):
                    row_cells = []
                    for cell in row.cells:
                        for cell_p in cell.paragraphs:
                            process_paragraph_element(cell_p, idx)
                        row_cells.append(cell.text.strip())
                    if r_idx == 0:
                        headers = row_cells
                    else:
                        rows.append(row_cells)
                        
                tbl_obj = Table(
                    id=f"tbl_{len(current_section.blocks)+1}",
                    headers=headers,
                    rows=rows,
                    caption=f"Table {len(current_section.blocks)+1}"
                )
                current_section.blocks.append(tbl_obj.model_dump())

        if current_section.blocks:
            sections.append(current_section)
            
        udm.sections = sections if sections else [Section(title="Main Content", level=1, blocks=[Paragraph(text="Content extracted").model_dump()])]
        
        if not udm.metadata.authors:
            warnings.append("Header author metadata was not deterministically structured; preserving original header text.")
        if not udm.metadata.affiliations:
            warnings.append("Header affiliation metadata was not deterministically structured.")
            
        udm.warnings = warnings
        return udm

    @staticmethod
    def _extract_images(doc: DocxDocument) -> Dict[str, Dict[str, Any]]:
        image_map = {}
        for rId, rel in doc.part.rels.items():
            if "image" in rel.target_ref:
                try:
                    img_part = rel.target_part
                    img_bytes = img_part.blob
                    b64_str = base64.b64encode(img_bytes).decode("utf-8")
                    sha256_hash = hashlib.sha256(img_bytes).hexdigest()
                    ext = os.path.splitext(rel.target_ref)[1].lower() or ".png"
                    image_map[rId] = {
                        "rId": rId,
                        "b64": b64_str,
                        "sha256": sha256_hash,
                        "bytes": img_bytes,
                        "ext": ext,
                        "media_path": rel.target_ref
                    }
                except Exception:
                    pass
        return image_map

    @staticmethod
    def _get_paragraph_image_rids(p: DocxParagraph, rel_image_map: Dict[str, Dict[str, Any]]) -> List[str]:
        found_rids = []
        xml_str = p._element.xml
        if any(kw in xml_str for kw in ["drawing", "imagedata", "blip", "object", "shape"]):
            for rId in rel_image_map.keys():
                if rId in xml_str:
                    found_rids.append(rId)
        return found_rids

    @staticmethod
    def _parse_paragraph_runs(p: DocxParagraph) -> Dict[str, Any]:
        runs_info = []
        full_text = []
        for run in p.runs:
            txt = run.text
            full_text.append(txt)
            is_super = False
            if run._r.rPr is not None and run._r.rPr.vertAlign is not None:
                val = run._r.rPr.vertAlign.val
                if val in ["superscript", "super"]:
                    is_super = True
            runs_info.append({"text": txt, "is_super": is_super})
        return {"full_text": "".join(full_text).strip(), "runs": runs_info}

    @staticmethod
    def _parse_author_header(header_data: List[Any]) -> Tuple[List[Author], List[Affiliation], str]:
        authors: List[Author] = []
        affiliations: List[Affiliation] = []
        
        normalized_entries: List[Dict[str, Any]] = []
        raw_lines: List[str] = []
        
        for item in header_data:
            if isinstance(item, str):
                txt = item.strip()
                if txt:
                    normalized_entries.append({"full_text": txt, "runs": [{"text": txt, "is_super": False}]})
                    raw_lines.append(txt)
            elif isinstance(item, dict):
                txt = str(item.get("full_text", "")).strip()
                runs = item.get("runs", [])
                if txt:
                    normalized_entries.append({"full_text": txt, "runs": runs if isinstance(runs, list) else []})
                    raw_lines.append(txt)
            elif hasattr(item, "text"):
                txt = str(getattr(item, "text", "")).strip()
                if txt:
                    normalized_entries.append({"full_text": txt, "runs": [{"text": txt, "is_super": False}]})
                    raw_lines.append(txt)
                    
        raw_header_str = "\n".join(raw_lines)
        
        role_kw = ["research scholar", "professor", "associate professor", "assistant professor", "lecturer", "scholar", "student", "engineer", "researcher", "scientist", "member, ieee", "senior member", "fellow, ieee", "head", "dean", "director", "chair"]
        inst_kw = ["department", "university", "institute", "college", "school", "laboratory", "center", "centre", "dept", "inc", "ltd", "corp", "technology", "sciences", "engineering"]
        loc_patterns = [r'\bcoimbatore\b', r'\bchennai\b', r'\bbangalore\b', r'\bmumbai\b', r'\bdelhi\b', r'\btamil nadu\b', r'\bkerala\b', r'\bindia\b', r'\busa\b', r'\buk\b', r'\bcalifornia\b', r'\bca\b', r'\bma\b', r'\bny\b']
        ignore_prefix = ("abstract", "keyword", "intro", "table", "fig", "reference", "index terms")
        
        def classify_line(s: str) -> str:
            sl = s.lower().strip()
            if not sl or sl.startswith(ignore_prefix):
                return "ignore"
            if "@" in s or sl.startswith("email"):
                return "email"
            if sl.startswith(('dr.', 'prof.', 'mr.', 'ms.', 'mrs.')):
                return "name_candidate"
            if any(r in sl for r in role_kw):
                return "role"
            if any(ik in sl for ik in inst_kw):
                return "institution"
            if any(re.search(pat, sl) for pat in loc_patterns):
                return "location"
            return "name_candidate"

        current_author: Optional[Author] = None
        current_affil_lines: List[str] = []
        affil_map: Dict[str, Affiliation] = {}
        
        for d in normalized_entries:
            line_str = d["full_text"]
            l_type = classify_line(line_str)
            
            if l_type == "ignore":
                continue
                
            if l_type == "email":
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', line_str)
                email_val = email_match.group(0) if email_match else line_str
                if current_author:
                    current_author.email = email_val
                elif authors:
                    authors[-1].email = email_val
                continue
                
            if l_type == "role":
                if current_author:
                    current_author.role = line_str
                elif authors:
                    authors[-1].role = line_str
                continue
                
            if l_type in ["institution", "location"]:
                current_affil_lines.append(line_str)
                if current_author and current_author.affiliation_ids:
                    aff_id = current_author.affiliation_ids[0]
                    if aff_id in affil_map:
                        existing = affil_map[aff_id].institution
                        if line_str not in existing:
                            affil_map[aff_id].institution = f"{existing}, {line_str}"
                continue
                
            # Process Author Name line or Multiple Author Names
            runs = d.get("runs", [])
            superscripts = [r.get("text", "").strip() for r in runs if isinstance(r, dict) and r.get("is_super") and r.get("text")]
            
            line_str_clean = re.sub(r'(\d)\s*,\s*(\d)', r'\1;\2', line_str)
            tokens = [t.strip() for t in re.split(r',|\band\b|&', line_str_clean) if t.strip()]
            
            for token in tokens:
                token_norm = token.replace(";", ",")
                m = re.match(r'^(.*?)(?:[\$\^\#\[\(]?([\d\*\,\s]+)[\$\^\#\]\)]?)?$', token_norm)
                if m:
                    name_part = m.group(1).strip()
                    tag_part = m.group(2) if m.group(2) else ""
                    
                    if not name_part or len(name_part) < 2 or classify_line(name_part) not in ["name_candidate", "name_or_text"]:
                        continue
                        
                    aff_ids = [t.strip() for t in re.findall(r'\d+', tag_part)]
                    if not aff_ids and superscripts:
                        aff_ids = [s for s in superscripts if s.isdigit()]
                        
                    is_corr = "*" in tag_part or "corresponding" in token.lower()
                    
                    aff_id = aff_ids[0] if aff_ids else str(len(affiliations) + 1)
                    if not aff_ids:
                        aff_ids = [aff_id]
                        
                    if aff_id not in affil_map:
                        inst_text = ", ".join(current_affil_lines) if current_affil_lines else "Academic Department"
                        aff_obj = Affiliation(id=aff_id, institution=inst_text, raw_text=line_str)
                        affiliations.append(aff_obj)
                        affil_map[aff_id] = aff_obj
                        current_affil_lines = []
                        
                    parts = name_part.split()
                    g_name = parts[0] if parts else ""
                    s_name = " ".join(parts[1:]) if len(parts) > 1 else ""
                    
                    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', token)
                    email = email_match.group(0) if email_match else None
                    
                    orcid_match = re.search(r'\d{4}-\d{4}-\d{4}-[\dxX]{4}', token)
                    orcid = orcid_match.group(0) if orcid_match else None
                    
                    author_obj = Author(
                        name=name_part,
                        given_name=g_name,
                        surname=s_name,
                        email=email,
                        affiliation_ids=aff_ids,
                        corresponding=is_corr,
                        orcid=orcid
                    )
                    authors.append(author_obj)
                    current_author = author_obj
                    
        if current_affil_lines and affiliations:
            extra_text = ", ".join(current_affil_lines)
            if extra_text not in affiliations[0].institution:
                affiliations[0].institution += f", {extra_text}"
                
        return authors, affiliations, raw_header_str
