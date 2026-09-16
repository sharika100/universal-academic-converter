import os
import re
import base64
import tempfile
import docx
from typing import Optional, List, Dict, Any
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

from app.models.udm import UniversalDocumentModel
from app.models.template_spec import TemplateSpecification

class DocxRenderer:
    @staticmethod
    def render(udm: UniversalDocumentModel, spec: TemplateSpecification, output_docx_path: str, template_path: Optional[str] = None):
        """
        Renders UniversalDocumentModel into a target DOCX file.
        If a valid target template_path is provided, populates the destination template in-place,
        preserving all template headers, footers, logos, margins, fonts, table styles, borders, and section breaks.
        """
        if template_path and os.path.exists(template_path) and template_path.endswith(".docx"):
            DocxRenderer._render_inplace_template(udm, spec, output_docx_path, template_path)
        else:
            DocxRenderer._render_generic_document(udm, spec, output_docx_path)

    @staticmethod
    def _render_inplace_template(udm: UniversalDocumentModel, spec: TemplateSpecification, output_docx_path: str, template_path: str):
        doc = docx.Document(template_path)
        
        # 1. In-Place Label-Value & Field Population
        mapped_labels = set()
        for tbl in doc.tables:
            for r_idx, row in enumerate(tbl.rows):
                cell_txts = [c.text.strip() for c in row.cells]
                if len(cell_txts) >= 2:
                    tgt_lbl = cell_txts[0].strip().rstrip(":")
                    for lv in udm.metadata.label_values:
                        lbl_clean = re.sub(r'[^a-zA-Z0-9]', '', lv.label).lower()
                        tgt_clean = re.sub(r'[^a-zA-Z0-9]', '', tgt_lbl).lower()
                        if lbl_clean and tgt_clean and (lbl_clean in tgt_clean or tgt_clean in lbl_clean):
                            if len(row.cells) > 1:
                                row.cells[1].text = f": {lv.value}"
                                mapped_labels.add(lv.label)
                                break
                                
        # Paragraph Label-Values
        for p in doc.paragraphs:
            txt = p.text.strip()
            if not txt:
                continue
            for lv in udm.metadata.label_values:
                lbl_clean = re.sub(r'[^a-zA-Z0-9]', '', lv.label).lower()
                p_clean = re.sub(r'[^a-zA-Z0-9]', '', txt).lower()
                if lbl_clean and p_clean and lbl_clean in p_clean and len(lbl_clean) > 4:
                    if ":" in txt:
                        prefix = txt.split(":")[0]
                        p.text = f"{prefix}: {lv.value}"
                        mapped_labels.add(lv.label)
                        break

        # 2. Table Data Row Population & Expansion
        source_tables = []
        for sec in udm.sections:
            for blk in sec.blocks:
                if isinstance(blk, dict) and blk.get("type") == "table":
                    source_tables.append(blk)

        for s_tbl in source_tables:
            s_headers = s_tbl.get("headers", [])
            s_rows = s_tbl.get("rows", [])
            s_cols = len(s_headers) if s_headers else (len(s_rows[0]) if s_rows else 0)
            
            best_target_tbl = None
            best_score = 0
            
            for t_idx, tpl_t in enumerate(doc.tables):
                t_cols = len(tpl_t.columns) if tpl_t.rows else 0
                if t_cols == s_cols and t_cols > 1:
                    t_hdr_txt = [c.text.strip() for c in tpl_t.rows[0].cells]
                    overlap = sum(1 for h in s_headers if any(h.lower() in th.lower() for th in t_hdr_txt))
                    score = overlap * 10 + (10 if t_cols == s_cols else 0)
                    if score > best_score:
                        best_score = score
                        best_target_tbl = tpl_t
                        
            if best_target_tbl and s_rows:
                start_r = 1 if len(best_target_tbl.rows) > 1 else 0
                for s_r_idx, s_row_cells in enumerate(s_rows):
                    target_r_idx = start_r + s_r_idx
                    if target_r_idx < len(best_target_tbl.rows):
                        r_cells = best_target_tbl.rows[target_r_idx].cells
                        for c_idx, val in enumerate(s_row_cells):
                            if c_idx < len(r_cells):
                                r_cells[c_idx].text = str(val)
                    else:
                        new_tr = parse_xml(best_target_tbl.rows[-1]._tr.xml)
                        best_target_tbl._tbl.append(new_tr)
                        new_row_cells = best_target_tbl.rows[-1].cells
                        for c_idx, val in enumerate(s_row_cells):
                            if c_idx < len(new_row_cells):
                                new_row_cells[c_idx].text = str(val)

        # 3. Unmapped Content Section
        if hasattr(udm, "unmapped_elements") and udm.unmapped_elements:
            unmapped_lvs = [u for u in udm.unmapped_elements if u.get("element_type") == "label_value"]
            if unmapped_lvs:
                doc.add_page_break()
                p_u_h = doc.add_paragraph()
                r_u_h = p_u_h.add_run("Unmapped Source Information (Annexure)")
                r_u_h.font.bold = True
                r_u_h.font.size = Pt(12)
                p_u_h.paragraph_format.space_after = Pt(6)
                
                t_u = doc.add_table(rows=1, cols=2)
                try:
                    t_u.style = 'Table Grid'
                except Exception:
                    pass
                t_u.rows[0].cells[0].text = "Field Label"
                t_u.rows[0].cells[1].text = "Source Content"
                
                for u_item in unmapped_lvs:
                    r_c = t_u.add_row().cells
                    r_c[0].text = str(u_item.get("label", ""))
                    r_c[1].text = str(u_item.get("value", ""))
                    
        doc.save(output_docx_path)

    @staticmethod
    def _render_generic_document(udm: UniversalDocumentModel, spec: TemplateSpecification, output_docx_path: str):
        doc = docx.Document()
        
        # Configure default page margins
        for section in doc.sections:
            section.top_margin = Inches(1.0)
            section.bottom_margin = Inches(1.0)
            section.left_margin = Inches(1.0)
            section.right_margin = Inches(1.0)
            
        # 1. Render Title
        p_title = doc.add_paragraph()
        p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_title = p_title.add_run(udm.metadata.title)
        run_title.font.name = 'Arial'
        run_title.font.size = Pt(18)
        run_title.font.bold = True
        p_title.paragraph_format.space_after = Pt(12)
        
        # 2. Render Authors & Affiliations
        if udm.metadata.authors:
            p_author = doc.add_paragraph()
            p_author.alignment = WD_ALIGN_PARAGRAPH.CENTER
            author_names = ", ".join([a.name for a in udm.metadata.authors])
            run_author = p_author.add_run(author_names)
            run_author.font.name = 'Arial'
            run_author.font.size = Pt(11)
            run_author.font.italic = True
            p_author.paragraph_format.space_after = Pt(6)
            
        if udm.metadata.affiliations:
            p_affil = doc.add_paragraph()
            p_affil.alignment = WD_ALIGN_PARAGRAPH.CENTER
            affil_text = "; ".join([aff.institution for aff in udm.metadata.affiliations])
            run_affil = p_affil.add_run(affil_text)
            run_affil.font.name = 'Arial'
            run_affil.font.size = Pt(9)
            p_affil.paragraph_format.space_after = Pt(18)
            
        # 3. Render Abstract
        if udm.metadata.abstract:
            p_abs_h = doc.add_paragraph()
            r_abs_h = p_abs_h.add_run("Abstract")
            r_abs_h.font.bold = True
            r_abs_h.font.size = Pt(10)
            p_abs_h.paragraph_format.space_after = Pt(4)
            
            p_abs = doc.add_paragraph()
            r_abs = p_abs.add_run(udm.metadata.abstract)
            r_abs.font.size = Pt(9.5)
            r_abs.font.italic = True
            p_abs.paragraph_format.space_after = Pt(12)
            
        # 4. Render Keywords
        if udm.metadata.keywords:
            p_kw = doc.add_paragraph()
            r_kw_lbl = p_kw.add_run("Keywords: ")
            r_kw_lbl.font.bold = True
            r_kw_lbl.font.size = Pt(9.5)
            r_kw = p_kw.add_run(", ".join(udm.metadata.keywords))
            r_kw.font.size = Pt(9.5)
            p_kw.paragraph_format.space_after = Pt(18)
            
        # 5. Render Sections & Content Blocks
        for sec in udm.sections:
            p_sec = doc.add_paragraph()
            r_sec = p_sec.add_run(sec.title)
            r_sec.font.name = 'Arial'
            r_sec.font.size = Pt(13 if sec.level == 1 else 11)
            r_sec.font.bold = True
            p_sec.paragraph_format.space_before = Pt(12)
            p_sec.paragraph_format.space_after = Pt(6)
            
            for blk in sec.blocks:
                btype = blk.get("type")
                if btype == "paragraph":
                    p = doc.add_paragraph()
                    r = p.add_run(blk.get("text", ""))
                    r.font.name = 'Calibri'
                    r.font.size = Pt(11)
                    p.paragraph_format.space_after = Pt(6)
                    
                elif btype == "list":
                    for item in blk.get("items", []):
                        p = doc.add_paragraph(style='List Bullet')
                        p.add_run(item.get("text", ""))
                        p.paragraph_format.space_after = Pt(3)
                        
                elif btype == "equation":
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    r = p.add_run(f"  {blk.get('math_latex', '')}  ({blk.get('label', 'eq')})")
                    r.font.name = 'Cambria Math'
                    r.font.italic = True
                    p.paragraph_format.space_before = Pt(6)
                    p.paragraph_format.space_after = Pt(6)
                    
                elif btype == "figure":
                    b64_data = blk.get("image_data_b64")
                    if b64_data:
                        try:
                            img_bytes = base64.b64encode(b64_data)
                            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_img:
                                tmp_img.write(img_bytes)
                                tmp_img_path = tmp_img.name
                            
                            p_fig = doc.add_paragraph()
                            p_fig.alignment = WD_ALIGN_PARAGRAPH.CENTER
                            p_fig.add_run().add_picture(tmp_img_path, width=Inches(4.5))
                            os.remove(tmp_img_path)
                        except Exception:
                            pass
                            
                    p_cap = doc.add_paragraph()
                    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    r_cap = p_cap.add_run(f"Figure: {blk.get('caption', '')}")
                    r_cap.font.size = Pt(9)
                    r_cap.font.italic = True
                    p_cap.paragraph_format.space_after = Pt(12)
                    
                elif btype == "table":
                    headers = blk.get("headers", [])
                    rows = blk.get("rows", [])
                    if headers or rows:
                        num_cols = len(headers) if headers else (len(rows[0]) if rows else 1)
                        t = doc.add_table(rows=0, cols=num_cols)
                        try:
                            t.style = 'Table Grid'
                        except Exception:
                            pass
                        
                        if headers:
                            hdr_cells = t.add_row().cells
                            for idx, h in enumerate(headers):
                                if idx < len(hdr_cells):
                                    hdr_cells[idx].text = str(h)
                                    hdr_cells[idx].paragraphs[0].runs[0].font.bold = True
                                    
                        for r_cells in rows:
                            row_cells = t.add_row().cells
                            for idx, val in enumerate(r_cells):
                                if idx < len(row_cells):
                                    row_cells[idx].text = str(val)
                                    
                    if blk.get("caption"):
                        p_tcap = doc.add_paragraph()
                        p_tcap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        r_tcap = p_tcap.add_run(f"Table: {blk.get('caption')}")
                        r_tcap.font.size = Pt(9)
                        p_tcap.paragraph_format.space_after = Pt(12)
                        
        # 6. Render References Section
        if udm.references:
            p_ref_h = doc.add_paragraph()
            r_ref_h = p_ref_h.add_run("References")
            r_ref_h.font.name = 'Arial'
            r_ref_h.font.size = Pt(13)
            r_ref_h.font.bold = True
            p_ref_h.paragraph_format.space_before = Pt(18)
            p_ref_h.paragraph_format.space_after = Pt(6)
            
            for idx, ref in enumerate(udm.references):
                p_ref = doc.add_paragraph()
                authors_str = ", ".join(ref.authors) if ref.authors else ""
                ref_text = f"[{idx+1}] {authors_str}. \"{ref.title}\". {ref.journal or ref.booktitle or ''} ({ref.year or ''})."
                r_ref = p_ref.add_run(ref_text)
                r_ref.font.size = Pt(9)
                p_ref.paragraph_format.space_after = Pt(4)
                
        doc.save(output_docx_path)
