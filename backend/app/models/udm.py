from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

class Author(BaseModel):
    name: str
    email: Optional[str] = None
    affiliation_ids: List[str] = Field(default_factory=list)
    corresponding: bool = False
    orcid: Optional[str] = None

class Affiliation(BaseModel):
    id: str
    institution: str
    department: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    raw_text: Optional[str] = None

class Metadata(BaseModel):
    title: str = "Untitled Document"
    authors: List[Author] = Field(default_factory=list)
    affiliations: List[Affiliation] = Field(default_factory=list)
    abstract: str = ""
    keywords: List[str] = Field(default_factory=list)
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)

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

class Figure(BaseModel):
    type: str = "figure"
    id: str
    caption: str = ""
    label: Optional[str] = None
    image_filename: str = ""
    image_data_b64: Optional[str] = None
    width_hint: Optional[str] = "0.8\\linewidth"
    original_path: Optional[str] = None

class TableCell(BaseModel):
    content: str
    align: str = "left"
    is_header: bool = False
    colspan: int = 1
    rowspan: int = 1

class Table(BaseModel):
    type: str = "table"
    id: str
    caption: str = ""
    label: Optional[str] = None
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)
    alignments: List[str] = Field(default_factory=list)

class Section(BaseModel):
    title: str
    level: int = 1
    label: Optional[str] = None
    blocks: List[Dict[str, Any]] = Field(default_factory=list)

class Reference(BaseModel):
    id: str
    cite_key: str
    entry_type: str = "article"
    title: str
    authors: List[str] = Field(default_factory=list)
    journal: Optional[str] = None
    booktitle: Optional[str] = None
    year: Optional[str] = None
    volume: Optional[str] = None
    number: Optional[str] = None
    pages: Optional[str] = None
    publisher: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    raw_bibtex: Optional[str] = None

class UniversalDocumentModel(BaseModel):
    metadata: Metadata = Field(default_factory=Metadata)
    sections: List[Section] = Field(default_factory=list)
    acknowledgements: Optional[str] = None
    appendices: List[Section] = Field(default_factory=list)
    references: List[Reference] = Field(default_factory=list)
    cross_references: Dict[str, str] = Field(default_factory=dict)
    conversion_mode: str = "FORMAT_ONLY" # "FORMAT_ONLY", "FORMAT_STRUCTURAL_FIX", "FORMAT_SUBMISSION_CHECK"
    parsing_confidence: float = 96.0
    warnings: List[str] = Field(default_factory=list)
    source_format: str = "unknown"
