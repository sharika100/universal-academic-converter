from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

class TextRunIR(BaseModel):
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    font_name: Optional[str] = None
    font_size_pt: Optional[float] = None
    font_color_rgb: Optional[str] = None
    hyperlink: Optional[str] = None

class ParagraphIR(BaseModel):
    level: int = 0  # 0 = top-level, 1 = sub-bullet, 2 = sub-sub-bullet
    bullet_type: Optional[str] = "bullet"  # "bullet", "numbered", "none"
    alignment: Optional[str] = "left"  # "left", "center", "right", "justify"
    runs: List[TextRunIR] = Field(default_factory=list)

    @property
    def plain_text(self) -> str:
        return "".join(run.text for run in self.runs)

class TextBoxElementIR(BaseModel):
    type: str = "textbox"
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    z_index: int = 0
    is_title: bool = False
    is_subtitle: bool = False
    paragraphs: List[ParagraphIR] = Field(default_factory=list)

class ImageElementIR(BaseModel):
    type: str = "image"
    image_id: str
    filename: str
    rel_path: str  # e.g. "images/slide1_img1.png"
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    z_index: int = 0
    alt_text: Optional[str] = None
    caption: Optional[str] = None
    original_format: Optional[str] = "png"
    is_diagram: Optional[bool] = False

class TableCellIR(BaseModel):
    row_idx: int
    col_idx: int
    text: str
    paragraphs: List[ParagraphIR] = Field(default_factory=list)
    alignment: Optional[str] = "left"
    bold: bool = False
    row_span: int = 1
    col_span: int = 1

class TableElementIR(BaseModel):
    type: str = "table"
    rows: int = 0
    cols: int = 0
    cells: List[List[TableCellIR]] = Field(default_factory=list)
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    z_index: int = 0
    has_header: bool = True

class UnsupportedElementIR(BaseModel):
    type: str = "unsupported"
    shape_type: str
    name: str = ""
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    z_index: int = 0
    warning: str

SlideElementUnion = Union[TextBoxElementIR, ImageElementIR, TableElementIR, UnsupportedElementIR]

class SlideBackgroundIR(BaseModel):
    color_rgb: Optional[str] = None
    image_rel_path: Optional[str] = None

class SlideIR(BaseModel):
    slide_number: int
    title: Optional[str] = None
    subtitle: Optional[str] = None
    layout_name: Optional[str] = None
    elements: List[SlideElementUnion] = Field(default_factory=list)
    speaker_notes: Optional[str] = None
    background: Optional[SlideBackgroundIR] = None

class SlideDeckIR(BaseModel):
    deck_title: Optional[str] = None
    subtitle: Optional[str] = None
    author: Optional[str] = None
    institution: Optional[str] = None
    date: Optional[str] = None
    slide_width_pts: float = 720.0  # Default 10 x 7.5 inches or 16:9
    slide_height_pts: float = 540.0
    aspect_ratio: str = "4:3"  # "4:3" or "16:9"
    slides: List[SlideIR] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def total_slides(self) -> int:
        return len(self.slides)

    @property
    def total_images(self) -> int:
        count = 0
        for s in self.slides:
            for el in s.elements:
                if el.type == "image":
                    count += 1
        return count

    @property
    def total_tables(self) -> int:
        count = 0
        for s in self.slides:
            for el in s.elements:
                if el.type == "table":
                    count += 1
        return count

    @property
    def total_text_blocks(self) -> int:
        count = 0
        for s in self.slides:
            for el in s.elements:
                if el.type == "textbox":
                    count += 1
        return count
