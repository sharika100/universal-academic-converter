from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class TemplateSpecification(BaseModel):
    format_type: str = "latex" # "latex" or "docx"
    document_class: str = "article" # e.g. "IEEEtran", "sn-jnl", "elsarticle", "acmart", "article"
    class_options: List[str] = Field(default_factory=list)
    layout: Dict[str, Any] = Field(default_factory=lambda: {
        "columns": 1,
        "paper_size": "letterpaper",
        "margins": "standard"
    })
    author_style: str = "standard" # "ieee", "springer", "elsevier", "acm", "standard"
    citation_system: str = "numeric" # "numeric", "author-year", "natbib", "biblatex"
    bib_style: Optional[str] = None # e.g. "IEEEtran", "sn-mathphys"
    entry_point_file: str = "main.tex"
    required_files: List[str] = Field(default_factory=list)
    custom_macros: Dict[str, str] = Field(default_factory=dict)
    custom_environments: List[str] = Field(default_factory=list)
    template_confidence: float = 98.0
    detected_rules: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
