import os
import base64
import tempfile
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table as RLTable, TableStyle, Image as RLImage, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from app.models.udm import UniversalDocumentModel

class PdfPreviewGenerator:
    @staticmethod
    def generate_pdf(udm: UniversalDocumentModel, output_pdf_path: str):
        """Generates a PDF document preview from UDM using ReportLab."""
        doc = SimpleDocTemplate(
            output_pdf_path,
            pagesize=letter,
            rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54
        )
        
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            alignment=1, # Center
            spaceAfter=12,
            textColor=colors.HexColor("#1A202C")
        )
        
        author_style = ParagraphStyle(
            'DocAuthor',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=10,
            leading=14,
            alignment=1,
            spaceAfter=6,
            textColor=colors.HexColor("#2D3748")
        )
        
        affil_style = ParagraphStyle(
            'DocAffil',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=12,
            alignment=1,
            spaceAfter=16,
            textColor=colors.HexColor("#4A5568")
        )
        
        abs_h_style = ParagraphStyle(
            'AbsHeading',
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=12,
            spaceAfter=4,
            textColor=colors.HexColor("#1A202C")
        )
        
        abs_style = ParagraphStyle(
            'DocAbs',
            parent=styles['Normal'],
            fontName='Times-Italic',
            fontSize=9.5,
            leading=13.5,
            spaceAfter=14,
            leftIndent=18,
            rightIndent=18,
            textColor=colors.HexColor("#2D3748")
        )
        
        h1_style = ParagraphStyle(
            'DocH1',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=16,
            spaceBefore=12,
            spaceAfter=6,
            textColor=colors.HexColor("#0F172A")
        )
        
        body_style = ParagraphStyle(
            'DocBody',
            parent=styles['Normal'],
            fontName='Times-Roman',
            fontSize=10,
            leading=14,
            spaceAfter=6,
            textColor=colors.HexColor("#1E293B")
        )
        
        cap_style = ParagraphStyle(
            'DocCap',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=8.5,
            leading=11,
            alignment=1,
            spaceAfter=10,
            textColor=colors.HexColor("#64748B")
        )
        
        tmp_img_files = []
        story = []
        
        def safe_xml(s: str) -> str:
            if not s:
                return ""
            s = str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            s = s.replace('&lt;b&gt;', '<b>').replace('&lt;/b&gt;', '</b>')
            s = s.replace('&lt;i&gt;', '<i>').replace('&lt;/i&gt;', '</i>')
            return s

        # Title
        story.append(Paragraph(safe_xml(udm.metadata.title), title_style))
        
        # Authors & Affiliations
        if udm.metadata.authors:
            names = ", ".join([a.name for a in udm.metadata.authors])
            story.append(Paragraph(safe_xml(names), author_style))
        if udm.metadata.affiliations:
            affs = "; ".join([aff.institution for aff in udm.metadata.affiliations])
            story.append(Paragraph(safe_xml(affs), affil_style))
            
        # Abstract
        if udm.metadata.abstract:
            story.append(Paragraph("Abstract", abs_h_style))
            story.append(Paragraph(safe_xml(udm.metadata.abstract), abs_style))
            
        # Keywords
        if udm.metadata.keywords:
            kw_str = f"<b>Keywords:</b> {safe_xml(', '.join(udm.metadata.keywords))}"
            story.append(Paragraph(kw_str, body_style))
            story.append(Spacer(1, 10))
            
        # Sections
        for sec in udm.sections:
            story.append(Paragraph(safe_xml(sec.title), h1_style))
            
            for blk in sec.blocks:
                btype = blk.get("type")
                if btype == "paragraph":
                    story.append(Paragraph(safe_xml(blk.get("text", "")), body_style))
                elif btype == "equation":
                    lbl = str(blk.get('label', '') or '').strip()
                    lbl_part = f" &nbsp;&nbsp;&nbsp; ({safe_xml(lbl)})" if lbl and lbl not in ["None", "null", "undefined"] else ""
                    eq_str = f"<i>{safe_xml(blk.get('math_latex', ''))}</i>{lbl_part}"
                    story.append(Paragraph(eq_str, body_style))
                elif btype == "figure":
                    b64_data = blk.get("image_data_b64")
                    if b64_data:
                        try:
                            img_bytes = base64.b64decode(b64_data)
                            tmp_f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                            tmp_f.write(img_bytes)
                            tmp_f.close()
                            tmp_img_files.append(tmp_f.name)
                            story.append(RLImage(tmp_f.name, width=320, height=180))
                        except Exception:
                            pass
                    story.append(Paragraph(f"Figure: {blk.get('caption', '')}", cap_style))
                elif btype == "table":
                    headers = blk.get("headers", [])
                    rows = blk.get("rows", [])
                    table_data = []
                    if headers:
                        table_data.append([Paragraph(f"<b>{h}</b>", body_style) for h in headers])
                    for r in rows:
                        table_data.append([Paragraph(str(cell), body_style) for cell in r])
                        
                    if table_data:
                        t = RLTable(table_data)
                        t.setStyle(TableStyle([
                            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
                            ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#0F172A")),
                            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
                            ('TOPPADDING', (0,0), (-1,-1), 4),
                            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                        ]))
                        story.append(t)
                        story.append(Paragraph(f"Table: {blk.get('caption', '')}", cap_style))
                        
        # References
        if udm.references:
            story.append(Paragraph("References", h1_style))
            for idx, ref in enumerate(udm.references):
                authors_str = ", ".join(ref.authors) if ref.authors else ""
                ref_text = f"[{idx+1}] {authors_str}. <i>{ref.title}</i>. {ref.journal or ''} ({ref.year or ''})."
                story.append(Paragraph(ref_text, body_style))
                
        doc.build(story)
        
        for fpath in tmp_img_files:
            try:
                os.remove(fpath)
            except Exception:
                pass
