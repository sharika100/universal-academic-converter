from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class CountComparison(BaseModel):
    paragraphs_source: int = 0
    paragraphs_output: int = 0
    figures_source: int = 0
    figures_output: int = 0
    tables_source: int = 0
    tables_output: int = 0
    equations_source: int = 0
    equations_output: int = 0
    references_source: int = 0
    references_output: int = 0
    match_status: str = "PERFECT_MATCH"

class ValidationCheck(BaseModel):
    category: str
    status: str # "PASS", "WARN", "FAIL"
    message: str

class ConversionReport(BaseModel):
    job_id: str
    source_format: str
    destination_format: str
    source_confidence: float
    template_confidence: float
    conformity_estimate: float
    integrity: CountComparison
    validation_checks: List[ValidationCheck] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    converted_files: List[str] = Field(default_factory=list)
    pdf_compiled: bool = False
    sandbox_log: str = ""
