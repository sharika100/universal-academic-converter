from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class TemplateSpecification(BaseModel):
    format_type: str = "latex"
    document_class: str = "article"
    doc_type_hint: str = "General Document"
    class_options: List[str] = Field(default_factory=list)
    layout: Dict[str, Any] = Field(default_factory=lambda: {
        "columns": 1,
        "paper_size": "letterpaper",
        "margins": "standard"
    })
    author_style: str = "standard"
    citation_system: str = "numeric"
    bib_style: Optional[str] = None
    entry_point_file: str = "main.tex"
    sample_content: Optional[str] = None
    required_files: List[str] = Field(default_factory=list)
    custom_macros: Dict[str, str] = Field(default_factory=dict)
    custom_environments: List[str] = Field(default_factory=list)
    author_macro_config: Dict[str, Any] = Field(default_factory=dict)
    
    # Generic Template Attributes for DOCX / Universal Templates
    placeholders: List[Dict[str, Any]] = Field(default_factory=list)
    template_tables: List[Dict[str, Any]] = Field(default_factory=list)
    field_labels: List[str] = Field(default_factory=list)
    signature_slots: List[Dict[str, Any]] = Field(default_factory=list)
    page_setup: Dict[str, Any] = Field(default_factory=dict)

    template_confidence: float = 98.0
    detected_rules: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
