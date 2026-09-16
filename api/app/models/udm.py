from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

class Author(BaseModel):
    name: str
    given_name: Optional[str] = None
    surname: Optional[str] = None
    email: Optional[str] = None
    affiliation_ids: List[str] = Field(default_factory=list)
    corresponding: bool = False
    orcid: Optional[str] = None
    role: Optional[str] = None

class Affiliation(BaseModel):
    id: str
    institution: str
    department: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    raw_text: Optional[str] = None

class LabelValue(BaseModel):
    type: str = "label_value"
    label: str
    value: str
    confidence: float = 1.0
    source_location: str = ""

class FieldItem(BaseModel):
    type: str = "field"
    field_name: str
    value: str
    placeholder: Optional[str] = None

class SignatureBlock(BaseModel):
    type: str = "signature_block"
    title: str
    name: Optional[str] = None
    signature: Optional[str] = None
    date: Optional[str] = None

class Annexure(BaseModel):
    type: str = "annexure"
    title: str
    content_blocks: List[Dict[str, Any]] = Field(default_factory=list)

class HeaderFooterBlock(BaseModel):
    type: str = "header_footer"
    is_header: bool = True
    text: str = ""

class PageBreak(BaseModel):
    type: str = "page_break"

class Metadata(BaseModel):
    title: str = "Untitled Document"
    doc_type: str = "General Document"
    document_title: Optional[str] = None
    institution: Optional[str] = None
    authors: List[Author] = Field(default_factory=list)
    affiliations: List[Affiliation] = Field(default_factory=list)
    abstract: str = ""
    keywords: List[str] = Field(default_factory=list)
    fields: Dict[str, str] = Field(default_factory=dict)
    label_values: List[LabelValue] = Field(default_factory=list)
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)
    header_raw_text: Optional[str] = None

class InlineElement(BaseModel):
    element_type: str  # text, math, citation, ref, footnote
    text: str
    target_label: Optional[str] = None
    value: Optional[str] = None

class Paragraph(BaseModel):
    type: str = "paragraph"
    text: str
    inline_elements: List[InlineElement] = Field(default_factory=list)
    style_hint: Optional[str] = None

class ListItem(BaseModel):
    text: str
    depth: int = 1

class ListBlock(BaseModel):
    type: str = "list"
    ordered: bool = False
    items: List[ListItem] = Field(default_factory=list)

class Equation(BaseModel):
    type: str = "equation"
    math_latex: str
    label: Optional[str] = None
    number: Optional[str] = None
    display_mode: str = "block"  # block or inline
    image_filename: Optional[str] = None
    image_data_b64: Optional[str] = None
    sha256: Optional[str] = None

class Figure(BaseModel):
    type: str = "figure"
    id: str
    occurrence_id: Optional[str] = None
    rel_id: Optional[str] = None
    original_filename: Optional[str] = None
    media_path: Optional[str] = None
    content_type: Optional[str] = "image/png"
    sha256: Optional[str] = None
    caption: str = ""
    label: Optional[str] = None
    image_filename: str = ""
    image_data_b64: Optional[str] = None
    width_hint: Optional[str] = "0.8\\linewidth"
    original_path: Optional[str] = None
    position_index: int = 0

class TableCell(BaseModel):
    content: str
    align: str = "left"
    is_header: bool = False
    colspan: int = 1
    rowspan: int = 1
    cell_style: Optional[str] = None
    borders: Optional[Dict[str, Any]] = None

class Table(BaseModel):
    type: str = "table"
    id: str
    caption: str = ""
    label: Optional[str] = None
    col_spec: Optional[str] = None
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)
    alignments: List[str] = Field(default_factory=list)
    cells: List[List[TableCell]] = Field(default_factory=list)
    colspan_matrix: List[List[int]] = Field(default_factory=list)
    rowspan_matrix: List[List[int]] = Field(default_factory=list)

class Algorithm(BaseModel):
    type: str = "algorithm"
    id: str
    caption: str = ""
    label: Optional[str] = None
    code: str = ""

class Section(BaseModel):
    title: str
    level: int = 1
    label: Optional[str] = None
    blocks: List[Dict[str, Any]] = Field(default_factory=list)

class Reference(BaseModel):
    id: str
    cite_key: str
    title: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    journal: Optional[str] = None
    year: Optional[str] = None
    raw_bibtex: Optional[str] = None

class UniversalDocumentModel(BaseModel):
    version: str = "1.0"
    source_format: str = "DOCX"
    doc_type: str = "General Document"
    metadata: Metadata = Field(default_factory=Metadata)
    sections: List[Section] = Field(default_factory=list)
    signatures: List[SignatureBlock] = Field(default_factory=list)
    annexures: List[Annexure] = Field(default_factory=list)
    references: List[Reference] = Field(default_factory=list)
    unmapped_elements: List[Dict[str, Any]] = Field(default_factory=list)
    parsing_confidence: float = 96.0
    warnings: List[str] = Field(default_factory=list)
