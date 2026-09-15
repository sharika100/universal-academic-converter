import uuid
import datetime
from pydantic import BaseModel
from typing import Optional

class StructuredAPIError(BaseModel):
    success: bool = False
    stage: str
    error_code: str
    message: str
    detail: Optional[str] = None
    reference_id: str
    timestamp: str

def create_error_payload(
    stage: str,
    error_code: str,
    message: str,
    detail: Optional[str] = None,
    ref_id: Optional[str] = None
) -> dict:
    if not ref_id:
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
        rand_str = uuid.uuid4().hex[:6].upper()
        ref_id = f"REF-{now_str}-{rand_str}"
        
    return StructuredAPIError(
        success=False,
        stage=stage,
        error_code=error_code,
        message=message,
        detail=detail,
        reference_id=ref_id,
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
    ).model_dump()
