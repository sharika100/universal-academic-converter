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
                        # Extract run-level superscript formatting details
                        header_lines.append(DocxParser._parse_paragraph_runs(p))
                        
            parsed_authors, parsed_affils, header_raw = DocxParser._parse_author_header(header_lines)
            if parsed_authors:
                udm.metadata.authors = parsed_authors
            if parsed_affils:
                udm.metadata.affiliations = parsed_affils
            udm.metadata.header_raw_text = header_raw
            
        # 2. Iterate elements sequentially (Paragraphs, Tables, Drawings, Images)
        sections = []
        current_section = Section(title="Introduction", level=1, blocks=[])
        
        title_found = False
        abstract_found = False
        references_found = False
        pending_caption = None
        
        def process_paragraph_element(p: DocxParagraph, elem_idx: int):
            nonlocal occurrence_counter, current_section, pending_caption, abstract_found, references_found
            
            text = p.text.strip()
            style_name = p.style.name.lower() if p.style else ""
            
            # Extract image relationship IDs from paragraph XML (inline drawings, anchors, blips, imagedata)
            para_rids = DocxParser._get_paragraph_image_rids(p, rel_image_map)
            is_caption = text.lower().startswith(("fig", "figure")) or "caption" in style_name
            
            if para_rids:
                for rId in para_rids:
                    img_info = rel_image_map[rId]
                    occurrence_counter += 1
                    occ_id = f"fig_occ_{occurrence_counter}"
                    fig_id = f"fig_{occurrence_counter}"
                    ext = img_info.get("ext", ".png")
                    fname = f"figure_{occurrence_counter}{ext}"
                    
                    caption_text = text if is_caption else (pending_caption or f"Figure {occurrence_counter}")
                    pending_caption = None
                    
                    fig_obj = Figure(
                        id=fig_id,
                        occurrence_id=occ_id,
                        rel_id=rId,
                        original_filename=os.path.basename(img_info.get("media_path", "")),
                        media_path=img_info.get("media_path"),
                        content_type=f"image/{ext.lstrip('.')}",
                        sha256=img_info.get("sha256"),
                        caption=caption_text,
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
                if current_section.blocks and current_section.blocks[-1].get("type") == "figure":
                    current_section.blocks[-1]["caption"] = text
                else:
                    pending_caption = text
                return
                
            # Skip header lines if already parsed into metadata
            if elem_idx < first_heading_idx and title_idx != -1 and elem_idx > title_idx:
                if udm.metadata.authors and any(a.name in text for a in udm.metadata.authors):
                    return
                if udm.metadata.affiliations and any(aff.institution in text for aff in udm.metadata.affiliations):
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
                if text.lower() in ["references", "bibliography"]:
                    references_found = True
                    return
                if current_section.blocks or current_section.title != "Introduction":
                    sections.append(current_section)
                current_section = Section(title=text, level=heading_level, blocks=[])
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
                if current_section.blocks and current_section.blocks[-1].get("type") == "list":
                    current_section.blocks[-1]["items"].append({"text": clean_item, "depth": 1})
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
                        # Process images inside table cells
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
        
        # Zero-inventing content integrity: If authors or affiliations were unparsed, log warning
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
        
        # Defensive normalization of input header_data elements (accepts dicts, strings, or objects)
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
        
        author_entries = []
        affil_entries = []
        
        for d in normalized_entries:
            line_str = d["full_text"]
            if not line_str:
                continue
            line_lower = line_str.lower()
            if line_lower.startswith(("abstract", "keyword", "intro", "table", "fig", "reference")):
                continue
            # Detect affiliation keywords
            if any(kw in line_lower for kw in ["department", "university", "institute", "college", "school", "laboratory", "center", "centre", "dept", "inc", "ltd"]):
                affil_entries.append(d)
            elif "@" in line_str:
                # Email line
                pass
            else:
                author_entries.append(d)
                
        # Parse affiliations first
        affil_map = {}
        for idx, aff_d in enumerate(affil_entries):
            text = aff_d["full_text"]
            m = re.match(r'^(?:[\$\^\#\[\(]?(\d+)[\$\^\#\]\)]?\s*)?(.*)', text)
            aff_id = m.group(1) if (m and m.group(1)) else str(idx + 1)
            clean_inst = m.group(2).strip() if m else text
            
            aff_obj = Affiliation(id=aff_id, institution=clean_inst, raw_text=text)
            affiliations.append(aff_obj)
            affil_map[aff_id] = aff_obj
            
        # Parse authors
        for a_d in author_entries:
            line_str = a_d["full_text"]
            line_lower = line_str.lower()
            if line_lower.startswith(("abstract", "keyword", "intro", "table", "fig")):
                continue
            # Extract superscript run text markers if present
            runs = a_d.get("runs", [])
            superscripts = [r.get("text", "").strip() for r in runs if isinstance(r, dict) and r.get("is_super") and r.get("text")]
            
            # Replace commas between digits in affiliation tags e.g. "1,2" -> "1;2" to avoid splitting author names on tag commas
            line_str_clean = re.sub(r'(\d)\s*,\s*(\d)', r'\1;\2', line_str)
            
            # Split tokens by comma or 'and'
            tokens = [t.strip() for t in re.split(r',|\band\b|&', line_str_clean) if t.strip()]
            for token in tokens:
                token_norm = token.replace(";", ",")
                m = re.match(r'^(.*?)(?:[\$\^\#\[\(]?([\d\*\,\s]+)[\$\^\#\]\)]?)?$', token_norm)
                if m:
                    name_part = m.group(1).strip()
                    tag_part = m.group(2) if m.group(2) else ""
                    
                    if not name_part or len(name_part) < 2 or name_part.lower().startswith(("abstract", "keyword")):
                        continue
                        
                    aff_ids = [t.strip() for t in re.findall(r'\d+', tag_part)]
                    if not aff_ids and superscripts:
                        aff_ids = [s for s in superscripts if s.isdigit()]
                        
                    is_corr = "*" in tag_part or "corresponding" in token.lower()
                    
                    if not aff_ids and affiliations:
                        aff_ids = [affiliations[0].id]
                    elif not aff_ids:
                        aff_ids = ["1"]
                        
                    parts = name_part.split()
                    g_name = parts[0] if parts else ""
                    s_name = " ".join(parts[1:]) if len(parts) > 1 else ""
                    
                    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', token)
                    email = email_match.group(0) if email_match else None
                    
                    orcid_match = re.search(r'\d{4}-\d{4}-\d{4}-[\dxX]{4}', token)
                    orcid = orcid_match.group(0) if orcid_match else None
                    
                    authors.append(Author(
                        name=name_part,
                        given_name=g_name,
                        surname=s_name,
                        email=email,
                        affiliation_ids=aff_ids,
                        corresponding=is_corr,
                        orcid=orcid
                    ))
                    
        return authors, affiliations, raw_header_str
