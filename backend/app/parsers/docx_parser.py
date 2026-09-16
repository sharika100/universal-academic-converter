import os
import re
import base64
import hashlib
import io
from typing import List, Dict, Any, Tuple, Optional
import docx
from docx.document import Document as DocxDocument
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph as DocxParagraph
from docx.oxml.ns import qn
from PIL import Image

from app.models.udm import (
    UniversalDocumentModel, Metadata, Author, Affiliation,
    Section, Paragraph, ListBlock, ListItem, Equation, Figure, Table, TableCell,
    Reference, LabelValue, FieldItem, SignatureBlock, Annexure
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
        
        # 0. Document Type Classification
        doc_type = DocxParser.detect_document_type(doc)
        udm.doc_type = doc_type
        udm.metadata.doc_type = doc_type
        
        # 1. Extract Images from document package
        rel_image_map = DocxParser._extract_images(doc)
        occurrence_counter = 0
        
        body_elements = list(doc.element.body)
        title_idx = -1
        first_heading_idx = len(body_elements)
        
        # Locate Title and first Section Heading dynamically
        for idx, elem in enumerate(body_elements):
            if isinstance(elem, CT_P):
                p = DocxParagraph(elem, doc)
                text = p.text.strip()
                style_name = p.style.name.lower() if p.style else ""
                if not text:
                    continue
                if title_idx == -1 and ("title" in style_name or (len(text) > 3 and len(text) < 180 and idx < 5)):
                    title_idx = idx
                
                is_explicit_heading = (
                    "heading 1" in style_name
                    or text.lower().startswith("abstract")
                    or bool(re.match(r'^(?:1\.|I\.|ONE)\s+[A-Za-z]', text, re.I))
                )
                if is_explicit_heading and idx > 0:
                    first_heading_idx = min(first_heading_idx, idx)
                    
        # Parse Title & Author/Affiliation block
        header_lines = []
        if title_idx != -1:
            title_p = DocxParagraph(body_elements[title_idx], doc)
            udm.metadata.title = title_p.text.strip()
            udm.metadata.document_title = title_p.text.strip()
            
            header_end = first_heading_idx
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
            txt = (d.get("full_text", "") if isinstance(d, dict) else str(d)).strip()
            if txt:
                consumed_header_texts.add(txt.lower())

        # 2. Extract Generic Label-Values & Fields across document
        label_values = DocxParser._extract_label_values(doc)
        udm.metadata.label_values = label_values
        for lv in label_values:
            udm.metadata.fields[lv.label] = lv.value

        # 3. Iterate body elements sequentially
        sections = []
        current_section = Section(title="Main Content", level=1, blocks=[])
        
        abstract_found = False
        references_found = False
        first_heading_found = False
        pending_caption = None
        
        def process_paragraph_element(p: DocxParagraph, elem_idx: int, is_inside_table: bool = False):
            nonlocal occurrence_counter, current_section, pending_caption, abstract_found, references_found, first_heading_found
            
            text = p.text.strip()
            style_name = p.style.name.lower() if p.style else ""
            
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
                                    
                    w = img_info.get("width", -1)
                    h = img_info.get("height", -1)
                    ar = img_info.get("aspect_ratio", 0)
                    
                    is_equation_image = (ar > 2.5 and 0 < h < 120) or ("w:math" in p._element.xml or "m:oMath" in p._element.xml)
                    
                    if is_equation_image:
                        current_section.blocks.append(Equation(
                            math_latex=f"\\includegraphics[max width=0.8\\linewidth]{{figures/{fname}}}",
                            label=f"eq_{occurrence_counter}",
                            image_filename=fname,
                            image_data_b64=img_info["b64"],
                            sha256=img_info["sha256"]
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
                if current_section.blocks and isinstance(current_section.blocks[-1], dict) and current_section.blocks[-1].get("type") == "figure":
                    current_section.blocks[-1]["caption"] = text
                else:
                    pending_caption = text
                return
                
            if doc_type == "Research Paper" and elem_idx < first_heading_idx:
                text_lower = text.lower()
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
                if email_match or text_lower in consumed_header_texts:
                    return
                if any(kw in text_lower for kw in ["research scholar", "professor", "associate professor", "assistant professor", "coimbatore", "tamil nadu", "department", "university", "institute"]):
                    return
                if udm.metadata.authors and any(a.name.lower() in text_lower for a in udm.metadata.authors):
                    return
                    
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
                
            if text.lower().startswith("keyword") or text.lower().startswith("index terms"):
                kw_str = re.sub(r'^(keywords?|index terms)[\s:;\.\-—–]*', '', text, flags=re.I).strip()
                udm.metadata.keywords = [k.strip() for k in re.split(r'[,;]', kw_str) if k.strip()]
                return

            if is_inside_table or text.lower().startswith("table"):
                return
                
            # Headings Detection
            is_heading = False
            heading_level = 1
            clean_title = text
            
            m_lvl1 = re.match(r'^(?:\d+|[IVXLCDM]+)\.\s+([A-Za-z].*)$', text)
            m_lvl2 = re.match(r'^[A-Z]\.\s+([A-Za-z].*)$', text)
            m_lvl3 = re.match(r'^\d+\.\d+\.\s+([A-Za-z].*)$', text)
            
            if m_lvl3:
                is_heading = True
                heading_level = 3
                clean_title = m_lvl3.group(1).strip()
            elif m_lvl2:
                is_heading = True
                heading_level = 2
                clean_title = m_lvl2.group(1).strip()
            elif m_lvl1:
                is_heading = True
                heading_level = 1
                clean_title = m_lvl1.group(1).strip()
            elif "heading 1" in style_name or text.endswith(":") and len(text) < 60:
                is_heading = True
                heading_level = 1
                clean_title = text.rstrip(":").strip()
            elif "heading 2" in style_name:
                is_heading = True
                heading_level = 2
                clean_title = text
            elif "heading 3" in style_name:
                is_heading = True
                heading_level = 3
                clean_title = text
                
            if is_heading:
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
                
            if references_found:
                ref_id = f"ref_{len(udm.references)+1}"
                udm.references.append(Reference(
                    id=ref_id,
                    cite_key=ref_id,
                    title=text,
                    raw_bibtex=text
                ))
                return
                
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
                process_paragraph_element(p, idx, is_inside_table=False)
            elif isinstance(elem, CT_Tbl):
                t = DocxTable(elem, doc)
                headers = []
                rows = []
                cell_matrix = []
                colspan_mat = []
                rowspan_mat = []
                
                is_signature_table = False
                
                for r_idx, row in enumerate(t.rows):
                    row_cells_txt = []
                    row_cells_obj = []
                    row_cols = []
                    row_rows = []
                    
                    for cell in row.cells:
                        txt = cell.text.strip()
                        row_cells_txt.append(txt)
                        
                        if any(k in txt.lower() for k in ["signature", "hod", "course instructor", "stream coordinator"]):
                            is_signature_table = True
                            
                        for cell_p in cell.paragraphs:
                            process_paragraph_element(cell_p, idx, is_inside_table=True)
                            
                        tcPr = cell._tc.get_or_add_tcPr()
                        gridSpan = tcPr.find(qn('w:gridSpan'))
                        vMerge = tcPr.find(qn('w:vMerge'))
                        
                        cs = int(gridSpan.get(qn('w:val'))) if gridSpan is not None and gridSpan.get(qn('w:val')) else 1
                        rs = 1
                        if vMerge is not None:
                            val = vMerge.get(qn('w:val'))
                            if val != 'restart':
                                rs = 0
                                
                        row_cols.append(cs)
                        row_rows.append(rs)
                        row_cells_obj.append(TableCell(
                            content=txt,
                            colspan=cs,
                            rowspan=rs,
                            is_header=(r_idx == 0)
                        ))
                        
                    if r_idx == 0:
                        headers = row_cells_txt
                    else:
                        rows.append(row_cells_txt)
                        
                    cell_matrix.append(row_cells_obj)
                    colspan_mat.append(row_cols)
                    rowspan_mat.append(row_rows)
                    
                if is_signature_table:
                    udm.signatures.append(SignatureBlock(
                        title="Signatures",
                        name=" , ".join(headers) if headers else "Signature Block"
                    ))
                    
                tbl_obj = Table(
                    id=f"tbl_{len(current_section.blocks)+1}",
                    headers=headers,
                    rows=rows,
                    cells=cell_matrix,
                    colspan_matrix=colspan_mat,
                    rowspan_matrix=rowspan_mat,
                    caption=f"Table {len(current_section.blocks)+1}"
                )
                current_section.blocks.append(tbl_obj.model_dump())
                
        if current_section.blocks:
            sections.append(current_section)
            
        udm.sections = sections if sections else [Section(title="Main Content", level=1, blocks=[Paragraph(text="Content extracted").model_dump()])]
        
        return udm

    @staticmethod
    def detect_document_type(doc: DocxDocument) -> str:
        """Classifies document type dynamically based on structural & textual signals."""
        full_text = " ".join([p.text for p in doc.paragraphs[:40]]).lower()
        
        if any(kw in full_text for kw in ["course delivery manual", "cdm", "syllabus", "course outcome", "co-po", "learning assessment", "stream coordinator"]):
            return "Course Document"
        elif any(kw in full_text for kw in ["requisition form", "application form", "approval form", "signature of applicant"]):
            return "Institutional Form"
        elif any(kw in full_text for kw in ["annual report", "project report", "progress report", "fdp report"]):
            return "Report"
        else:
            return "Research Paper"

    @staticmethod
    def _extract_label_values(doc: DocxDocument) -> List[LabelValue]:
        label_vals = []
        
        for p in doc.paragraphs:
            txt = p.text.strip()
            if not txt:
                continue
            m = re.match(r'^([A-Za-z0-9\s,\-\(\)\&\/]{3,50})\s*[:=]\s*(.+)$', txt)
            if m:
                lbl = m.group(1).strip()
                val = m.group(2).strip()
                if lbl and val and len(lbl) < 55:
                    label_vals.append(LabelValue(label=lbl, value=val, confidence=0.95, source_location="paragraph"))
                    
        for tbl in doc.tables:
            for row in tbl.rows:
                cells = [c.text.strip() for c in row.cells]
                if len(cells) == 2 and cells[0] and cells[1]:
                    lbl = cells[0].strip().rstrip(":")
                    val = cells[1].strip().lstrip(":")
                    if lbl and val:
                        label_vals.append(LabelValue(label=lbl, value=val, confidence=0.98, source_location="table"))
                elif len(cells) == 4 and cells[0] and cells[1] and cells[2] and cells[3]:
                    lbl1 = cells[0].strip().rstrip(":")
                    val1 = cells[1].strip().lstrip(":")
                    lbl2 = cells[2].strip().rstrip(":")
                    val2 = cells[3].strip().lstrip(":")
                    if lbl1 and val1:
                        label_vals.append(LabelValue(label=lbl1, value=val1, confidence=0.95, source_location="table"))
                    if lbl2 and val2:
                        label_vals.append(LabelValue(label=lbl2, value=val2, confidence=0.95, source_location="table"))
                        
        return label_vals

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
                    
                    w, h = -1, -1
                    try:
                        with Image.open(io.BytesIO(img_bytes)) as pil_img:
                            w, h = pil_img.size
                    except Exception:
                        pass
                        
                    ar = round(w / h, 2) if h > 0 else 0
                    
                    image_map[rId] = {
                        "rId": rId,
                        "b64": b64_str,
                        "sha256": sha256_hash,
                        "bytes": img_bytes,
                        "ext": ext,
                        "width": w,
                        "height": h,
                        "aspect_ratio": ar,
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
                if f'r:embed="{rId}"' in xml_str or f'r:id="{rId}"' in xml_str:
                    found_rids.append(rId)
        return found_rids

    @staticmethod
    def _parse_paragraph_runs(p: DocxParagraph) -> Dict[str, Any]:
        runs_data = []
        full_text = ""
        for run in p.runs:
            txt = run.text
            full_text += txt
            runs_data.append({
                "text": txt,
                "bold": bool(run.bold),
                "italic": bool(run.italic),
                "font_size": run.font.size.pt if run.font and run.font.size else None
            })
        return {"full_text": full_text, "runs": runs_data}

    @staticmethod
    def _parse_author_header(header_lines: List[Any]) -> Tuple[List[Author], List[Affiliation], str]:
        authors = []
        affiliations = []
        header_raw_list = []
        
        email_map = {}
        for line_d in header_lines:
            txt = (line_d.get("full_text", "") if isinstance(line_d, dict) else str(line_d)).strip()
            header_raw_list.append(txt)
            found_emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', txt)
            if found_emails:
                for em in found_emails:
                    user_part = em.split("@")[0].lower()
                    email_map[user_part] = em
                    
        for line_d in header_lines:
            txt = (line_d.get("full_text", "") if isinstance(line_d, dict) else str(line_d)).strip()
            if not txt:
                continue
                
            if any(kw in txt.lower() for kw in ["university", "institute", "college", "department", "school", "coimbatore", "tamil nadu"]):
                aff_id = f"aff{len(affiliations)+1}"
                m_num = re.match(r'^([\d\*†‡§]+)\s*(.+)$', txt)
                if m_num:
                    aff_id = m_num.group(1).strip()
                    inst_text = m_num.group(2).strip()
                else:
                    inst_text = txt
                affiliations.append(Affiliation(
                    id=aff_id,
                    institution=inst_text,
                    raw_text=txt
                ))
                continue
                
            if txt.lower().startswith("abstract") or txt.lower().startswith("keywords"):
                continue

            candidate_names = [txt]
            if "," in txt and not any(kw in txt.lower() for kw in ["abstract", "keywords", "email", "scholar", "professor", "coimbatore", "tamil nadu", "department", "university"]):
                candidate_names = [c.strip() for c in re.split(r',\s*(?=[A-Z])', txt) if c.strip()]

            for cand in candidate_names:
                clean_name = cand.strip()
                m_aff = re.search(r'([\d\*†‡§\s,]+)$', clean_name)
                aff_ids = []
                if m_aff:
                    aff_ids = [a.strip() for a in re.split(r'[,;\s]', m_aff.group(1)) if a.strip()]
                    clean_name = clean_name[:m_aff.start()].strip()
                    
                parts = clean_name.split()
                is_plausible_name = (
                    1 <= len(parts) <= 4
                    and not any(kw in clean_name.lower() for kw in ["department", "university", "institute", "college", "school", "abstract", "keywords", "email", "@", "scholar", "professor", "coimbatore", "tamil nadu", "ndcg", "precision", "recall", "f1", "accuracy", "begin", "end"])
                    and not re.search(r'[\d\\\{\}\[\]]', clean_name)
                )
                
                if is_plausible_name:
                    matched_email = None
                    for u_part, em in email_map.items():
                        if u_part in clean_name.lower() or any(p.lower() in u_part for p in parts if len(p) > 2):
                            matched_email = em
                            break
                            
                    authors.append(Author(
                        name=clean_name,
                        email=matched_email,
                        affiliation_ids=aff_ids or ["aff1"]
                    ))
                
        return authors, affiliations, "\n".join(header_raw_list)
