import os
import re
import base64
from typing import List, Dict, Any, Tuple
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
        
        # 1. Extract Images / Figures from document package
        image_map = DocxParser._extract_images(doc)
        
        # 2. Iterate elements sequentially
        current_section = Section(title="Introduction", level=1, blocks=[])
        sections = []
        
        title_found = False
        abstract_found = False
        references_found = False
        
        raw_paragraphs = []
        authors_raw = []
        
        for elem in doc.element.body:
            if isinstance(elem, CT_P):
                p = DocxParagraph(elem, doc)
                text = p.text.strip()
                style_name = p.style.name.lower() if p.style else ""
                
                if not text:
                    # Check for inline image figures
                    figs = DocxParser._check_paragraph_figures(p, image_map)
                    for fig in figs:
                        current_section.blocks.append(fig.model_dump())
                    continue
                
                # Check for Title
                if "title" in style_name or (not title_found and len(text) > 5 and len(text) < 150 and not sections):
                    if not title_found:
                        udm.metadata.title = text
                        title_found = True
                        continue
                        
                # Check for Authors / Affiliations
                if "author" in style_name or "subtitle" in style_name:
                    udm.metadata.authors.append(Author(name=text))
                    continue
                    
                # Check for Abstract
                if text.lower().startswith("abstract") or "abstract" in style_name:
                    clean_abs = re.sub(r'^(abstract[:\.\s-]*)', '', text, flags=re.I).strip()
                    if clean_abs:
                        udm.metadata.abstract = clean_abs
                    abstract_found = True
                    continue
                elif abstract_found and not udm.metadata.abstract and len(text) > 30:
                    udm.metadata.abstract = text
                    continue
                    
                # Check for Keywords
                if text.lower().startswith("keyword"):
                    kw_str = re.sub(r'^(keywords?[:\.\s-]*)', '', text, flags=re.I)
                    udm.metadata.keywords = [k.strip() for k in re.split(r'[,;]', kw_str) if k.strip()]
                    continue
                    
                # Check for Headings
                is_heading = False
                heading_level = 1
                if "heading 1" in style_name or text.isupper() and len(text) < 60:
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
                    # Push previous section if non-empty
                    if current_section.blocks or current_section.title != "Introduction":
                        sections.append(current_section)
                    current_section = Section(title=text, level=heading_level, blocks=[])
                    continue
                    
                # If in References section, parse reference item
                if references_found:
                    ref_id = f"ref_{len(udm.references)+1}"
                    udm.references.append(Reference(
                        id=ref_id,
                        cite_key=ref_id,
                        title=text,
                        raw_bibtex=text
                    ))
                    continue
                    
                # Check for Figures / Captions
                if text.lower().startswith("fig") or "caption" in style_name:
                    # Treat as caption for last figure or new figure block
                    fig_id = f"fig_{len(current_section.blocks)+1}"
                    fig_obj = Figure(
                        id=fig_id,
                        caption=text,
                        image_filename=f"{fig_id}.png"
                    )
                    current_section.blocks.append(fig_obj.model_dump())
                    continue
                    
                # Check for List Bullet
                if "bullet" in style_name or "list" in style_name or text.startswith("•") or text.startswith("-"):
                    clean_item = text.lstrip("•- ").strip()
                    # Append to existing list or start new list
                    if current_section.blocks and current_section.blocks[-1].get("type") == "list":
                        current_section.blocks[-1]["items"].append({"text": clean_item, "depth": 1})
                    else:
                        current_section.blocks.append(ListBlock(
                            ordered="number" in style_name,
                            items=[ListItem(text=clean_item, depth=1)]
                        ).model_dump())
                    continue
                    
                # Check for Equation (OMML or Math indicators)
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
                for idx, row in enumerate(t.rows):
                    row_cells = [cell.text.strip() for cell in row.cells]
                    if idx == 0:
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
        
        # If no authors detected, add default
        if not udm.metadata.authors:
            udm.metadata.authors.append(Author(name="Academic Author", email="author@univ.edu"))
        if not udm.metadata.affiliations:
            udm.metadata.affiliations.append(Affiliation(id="1", institution="Department of Computer Science, University"))
            
        udm.warnings = warnings
        return udm

    @staticmethod
    def _extract_images(doc: DocxDocument) -> Dict[str, str]:
        image_map = {}
        count = 1
        for rel in doc.part.rels.values():
            if "image" in rel.target_ref:
                try:
                    img_part = rel.target_part
                    img_bytes = img_part.blob
                    b64_str = base64.b64encode(img_bytes).decode("utf-8")
                    img_id = f"fig_{count}"
                    image_map[rel.rId] = b64_str
                    count += 1
                except Exception:
                    pass
        return image_map

    @staticmethod
    def _check_paragraph_figures(p: DocxParagraph, image_map: Dict[str, str]) -> List[Figure]:
        figures = []
        # Find graphic XML tags
        if "graphic" in p._element.xml:
            for rId, b64 in image_map.items():
                if rId in p._element.xml:
                    fig_id = f"fig_{len(figures)+1}"
                    figures.append(Figure(
                        id=fig_id,
                        caption=f"Figure {fig_id}",
                        image_filename=f"{fig_id}.png",
                        image_data_b64=b64
                    ))
        return figures
