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
        
        # 1. Extract Images / Figures from document package with unique identities
        rel_image_map = DocxParser._extract_images(doc)
        
        # Track figures globally across document
        global_fig_count = 0
        used_image_hashes = set()
        
        # Collect top header paragraphs for Author/Affiliation parsing
        header_paragraphs = []
        body_elements = list(doc.element.body)
        
        # Find title index
        title_idx = -1
        first_heading_idx = len(body_elements)
        
        for idx, elem in enumerate(body_elements):
            if isinstance(elem, CT_P):
                p = DocxParagraph(elem, doc)
                text = p.text.strip()
                style_name = p.style.name.lower() if p.style else ""
                if not text:
                    continue
                if title_idx == -1 and ("title" in style_name or (len(text) > 5 and len(text) < 180)):
                    title_idx = idx
                if "heading 1" in style_name or (text.isupper() and len(text) < 60 and idx > 0):
                    first_heading_idx = min(first_heading_idx, idx)
                    
        # Parse Title and Author/Affiliation block from header region
        if title_idx != -1:
            title_p = DocxParagraph(body_elements[title_idx], doc)
            udm.metadata.title = title_p.text.strip()
            header_end = min(first_heading_idx, title_idx + 10)
            for idx in range(title_idx + 1, header_end):
                elem = body_elements[idx]
                if isinstance(elem, CT_P):
                    p = DocxParagraph(elem, doc)
                    if p.text.strip():
                        header_paragraphs.append(p.text.strip())
                        
            parsed_authors, parsed_affils = DocxParser._parse_author_header(header_paragraphs)
            if parsed_authors:
                udm.metadata.authors = parsed_authors
            if parsed_affils:
                udm.metadata.affiliations = parsed_affils
                
        # 2. Iterate elements sequentially for document content
        sections = []
        current_section = Section(title="Introduction", level=1, blocks=[])
        
        title_found = False
        abstract_found = False
        references_found = False
        
        pending_caption = None
        
        for idx, elem in enumerate(body_elements):
            # Skip title paragraph if already consumed
            if idx == title_idx:
                continue
                
            if isinstance(elem, CT_P):
                p = DocxParagraph(elem, doc)
                text = p.text.strip()
                style_name = p.style.name.lower() if p.style else ""
                
                # Check for images in this paragraph
                para_rids = DocxParser._get_paragraph_image_rids(p, rel_image_map)
                
                # Check if paragraph text is a figure caption
                is_caption = text.lower().startswith(("fig", "figure")) or "caption" in style_name
                
                if para_rids:
                    # Paragraph contains one or more images
                    for rId in para_rids:
                        img_info = rel_image_map[rId]
                        img_hash = img_info["hash"]
                        
                        global_fig_count += 1
                        fig_id = f"fig_{global_fig_count}"
                        ext = img_info.get("ext", ".png")
                        fname = f"figure_{global_fig_count}{ext}"
                        
                        caption_text = text if is_caption else (pending_caption or f"Figure {global_fig_count}")
                        pending_caption = None
                        
                        fig_obj = Figure(
                            id=fig_id,
                            caption=caption_text,
                            image_filename=fname,
                            image_data_b64=img_info["b64"],
                            original_path=img_info.get("original_ref")
                        )
                        current_section.blocks.append(fig_obj.model_dump())
                        used_image_hashes.add(img_hash)
                    if not is_caption:
                        continue
                        
                if not text:
                    continue
                    
                # If this paragraph is a caption but had no inline rId image, attach to last figure or save as pending
                if is_caption:
                    if current_section.blocks and current_section.blocks[-1].get("type") == "figure":
                        current_section.blocks[-1]["caption"] = text
                    else:
                        pending_caption = text
                    continue
                    
                # Skip header author/affiliation lines if already parsed into metadata
                if idx < first_heading_idx and title_idx != -1 and idx > title_idx:
                    if any(a.name in text for a in udm.metadata.authors) or any(aff.institution in text for aff in udm.metadata.affiliations):
                        continue
                        
                # Check for Abstract
                if text.lower().startswith("abstract") or "abstract" in style_name:
                    clean_abs = re.sub(r'^(abstract[:\.\s-]*)', '', text, flags=re.I).strip()
                    if clean_abs:
                        udm.metadata.abstract = clean_abs
                    abstract_found = True
                    continue
                elif abstract_found and not udm.metadata.abstract and len(text) > 20:
                    udm.metadata.abstract = text
                    abstract_found = False
                    continue
                    
                # Check for Keywords
                if text.lower().startswith("keyword"):
                    kw_str = re.sub(r'^(keywords?[:\.\s-]*)', '', text, flags=re.I)
                    udm.metadata.keywords = [k.strip() for k in re.split(r'[,;]', kw_str) if k.strip()]
                    continue
                    
                # Check for Headings
                is_heading = False
                heading_level = 1
                if "heading 1" in style_name or (text.isupper() and len(text) < 60 and idx >= first_heading_idx):
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
                        continue
                    if current_section.blocks or current_section.title != "Introduction":
                        sections.append(current_section)
                    current_section = Section(title=text, level=heading_level, blocks=[])
                    continue
                    
                # References section parsing
                if references_found:
                    ref_id = f"ref_{len(udm.references)+1}"
                    udm.references.append(Reference(
                        id=ref_id,
                        cite_key=ref_id,
                        title=text,
                        raw_bibtex=text
                    ))
                    continue
                    
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
                    continue
                    
                # Equation
                if "w:math" in elem.xml or "m:oMath" in elem.xml or (text.startswith("$$") and text.endswith("$$")):
                    math_tex = re.sub(r'^\$\$|\$\$$', '', text).strip()
                    current_section.blocks.append(Equation(
                        math_latex=math_tex or text,
                        label=f"eq_{len(current_section.blocks)+1}"
                    ).model_dump())
                    continue
                    
                # Standard paragraph
                current_section.blocks.append(Paragraph(text=text).model_dump())
                
            elif isinstance(elem, CT_Tbl):
                t = DocxTable(elem, doc)
                headers = []
                rows = []
                for r_idx, row in enumerate(t.rows):
                    row_cells = [cell.text.strip() for cell in row.cells]
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
        
        # Ensure default metadata if unparsed
        if not udm.metadata.authors:
            udm.metadata.authors.append(Author(name="Academic Author", email="author@univ.edu", affiliation_ids=["1"]))
        if not udm.metadata.affiliations:
            udm.metadata.affiliations.append(Affiliation(id="1", institution="Department of Computer Science, University"))
            
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
                    img_hash = hashlib.md5(img_bytes).hexdigest()
                    ext = os.path.splitext(rel.target_ref)[1].lower() or ".png"
                    image_map[rId] = {
                        "rId": rId,
                        "b64": b64_str,
                        "hash": img_hash,
                        "ext": ext,
                        "original_ref": rel.target_ref
                    }
                except Exception:
                    pass
        return image_map

    @staticmethod
    def _get_paragraph_image_rids(p: DocxParagraph, rel_image_map: Dict[str, Dict[str, Any]]) -> List[str]:
        found_rids = []
        xml_str = p._element.xml
        if "graphic" in xml_str or "imagedata" in xml_str or "blip" in xml_str:
            for rId in rel_image_map.keys():
                if rId in xml_str:
                    found_rids.append(rId)
        return found_rids

    @staticmethod
    def _parse_author_header(lines: List[str]) -> Tuple[List[Author], List[Affiliation]]:
        authors: List[Author] = []
        affiliations: List[Affiliation] = []
        
        author_lines = []
        affil_lines = []
        
        for line in lines:
            line_str = line.strip()
            if not line_str or line_str.lower().startswith("abstract"):
                break
            # If contains department/university/institute/college/school/laboratory
            if any(kw in line_str.lower() for kw in ["department", "university", "institute", "college", "school", "laboratory", "center", "centre", "dept", "inc", "ltd"]):
                affil_lines.append(line_str)
            elif "@" in line_str:
                # Email line
                pass
            else:
                author_lines.append(line_str)
                
        # Parse affiliations first
        affil_map = {}
        for idx, aff_text in enumerate(affil_lines):
            # Check for leading number tag e.g. "1 Department of..." or "^1 Department..."
            m = re.match(r'^(?:[\$\^\#\[\(]?(\d+)[\$\^\#\]\)]?\s*)?(.*)', aff_text)
            aff_id = m.group(1) if (m and m.group(1)) else str(idx + 1)
            clean_inst = m.group(2).strip() if m else aff_text
            affil_obj = Affiliation(id=aff_id, institution=clean_inst, raw_text=aff_text)
            affiliations.append(affil_obj)
            affil_map[aff_id] = affil_obj
            
        # Parse authors
        for a_line in author_lines:
            # Split multiple authors separated by commas or 'and'
            raw_tokens = [t.strip() for t in re.split(r',|\band\b', a_line) if t.strip()]
            for token in raw_tokens:
                # Check for affiliation tags attached to name, e.g. "Alice Smith1,2" or "Alice Smith 1" or "Alice Smith*"
                m = re.match(r'^(.*?)(?:[\$\^\#\[\(]?([\d\*\,\s]+)[\$\^\#\]\)]?)?$', token)
                if m:
                    name_part = m.group(1).strip()
                    tag_part = m.group(2) if m.group(2) else ""
                    
                    if not name_part or len(name_part) < 2:
                        continue
                        
                    aff_ids = [t.strip() for t in re.findall(r'\d+', tag_part)]
                    is_corr = "*" in tag_part or "corresponding" in token.lower()
                    
                    # If no explicit tag, assign default 1
                    if not aff_ids and affiliations:
                        aff_ids = [affiliations[0].id]
                    elif not aff_ids:
                        aff_ids = ["1"]
                        
                    authors.append(Author(
                        name=name_part,
                        affiliation_ids=aff_ids,
                        corresponding=is_corr
                    ))
                    
        return authors, affiliations
