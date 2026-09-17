import os
import time
import logging
import jwt
from typing import Optional, Dict, Any
from fastapi import APIRouter, BackgroundTasks, Request, Response, HTTPException, Depends, Cookie
from pydantic import BaseModel, Field
from app.db import analytics_db

logger = logging.getLogger("analytics_api")

router = APIRouter()

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
ADMIN_JWT_SECRET = os.environ.get("ADMIN_JWT_SECRET", "univ-academic-converter-admin-secret-key-2026")

class SessionRecordRequest(BaseModel):
    session_id: str
    is_returning: Optional[bool] = False
    browser_family: Optional[str] = "Unknown"

class EventRecordRequest(BaseModel):
    session_id: str
    event_type: str
    conversion_type: Optional[str] = None
    destination_template: Optional[str] = None
    status: Optional[str] = None
    upload_time_ms: Optional[int] = None
    conversion_time_ms: Optional[int] = None
    download_time_ms: Optional[int] = None
    total_time_ms: Optional[int] = None
    validation_passed: Optional[bool] = None
    compilation_passed: Optional[bool] = None
    is_returning: Optional[bool] = False
    browser_family: Optional[str] = "Unknown"

class ErrorRecordRequest(BaseModel):
    session_id: str
    error_category: str
    error_code: Optional[str] = None
    conversion_type: Optional[str] = None
    destination_template: Optional[str] = None

class FeedbackRecordRequest(BaseModel):
    session_id: str
    rating: int = Field(ge=1, le=5)
    is_useful: bool
    feedback_text: Optional[str] = None
    conversion_type: Optional[str] = None

class AdminLoginRequest(BaseModel):
    username: str
    password: str

def verify_admin_auth(request: Request, admin_session: Optional[str] = Cookie(None)) -> str:
    """FastAPI Dependency guarding admin endpoints."""
    token = admin_session
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        
    if not token:
        raise HTTPException(status_code=401, detail="Admin authentication required.")
        
    try:
        payload = jwt.decode(token, ADMIN_JWT_SECRET, algorithms=["HS256"])
        if payload.get("username") != ADMIN_USERNAME:
            raise HTTPException(status_code=403, detail="Invalid admin session.")
        return payload.get("username")
    except Exception:
        raise HTTPException(status_code=401, detail="Expired or invalid admin session token.")

@router.post("/api/analytics/event")
def log_analytics_event(req: EventRecordRequest):
    """Synchronous public telemetry endpoint guaranteeing database insertion before Vercel process freeze."""
    try:
        analytics_db.record_session(req.session_id, req.is_returning or False, req.browser_family or "Unknown")
        analytics_db.record_event(
            session_id=req.session_id,
            event_type=req.event_type,
            conversion_type=req.conversion_type,
            destination_template=req.destination_template,
            status=req.status,
            upload_time_ms=req.upload_time_ms,
            conversion_time_ms=req.conversion_time_ms,
            download_time_ms=req.download_time_ms,
            total_time_ms=req.total_time_ms,
            validation_passed=req.validation_passed,
            compilation_passed=req.compilation_passed
        )
        return {"status": "recorded"}
    except Exception as e:
        logger.warning(f"[ANALYTICS_EVENT_LOG_ERROR] {e}")
        return {"status": "error", "detail": str(e)}

@router.post("/api/analytics/error")
def log_analytics_error(req: ErrorRecordRequest):
    """Synchronous error logging endpoint."""
    try:
        analytics_db.record_error(
            session_id=req.session_id,
            error_category=req.error_category,
            error_code=req.error_code,
            conversion_type=req.conversion_type,
            destination_template=req.destination_template
        )
        return {"status": "recorded"}
    except Exception as e:
        logger.warning(f"[ANALYTICS_ERROR_LOG_ERROR] {e}")
        return {"status": "error", "detail": str(e)}

@router.post("/api/analytics/feedback")
def log_analytics_feedback(req: FeedbackRecordRequest):
    """Synchronous voluntary user feedback logging endpoint."""
    try:
        analytics_db.record_feedback(
            session_id=req.session_id,
            rating=req.rating,
            is_useful=req.is_useful,
            feedback_text=req.feedback_text,
            conversion_type=req.conversion_type
        )
        return {"status": "recorded"}
    except Exception as e:
        logger.warning(f"[ANALYTICS_FEEDBACK_LOG_ERROR] {e}")
        return {"status": "error", "detail": str(e)}

@router.post("/api/admin/login")
def admin_login(req: AdminLoginRequest, response: Response):
    """Single-admin login endpoint setting HTTP-only cookie and returning JWT token after verifying server-side environment variables."""
    is_valid = analytics_db.verify_admin_credentials(req.username, req.password)
    if is_valid:
        token = jwt.encode({
            "username": req.username.strip(),
            "exp": time.time() + 28800 # 8 hours
        }, ADMIN_JWT_SECRET, algorithm="HS256")
        
        response.set_cookie(
            key="admin_session",
            value=token,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=28800
        )
        return {"success": True, "token": token, "username": req.username.strip()}
    else:
        raise HTTPException(status_code=401, detail="Invalid admin username or password.")

@router.get("/api/admin/me")
def admin_me(username: str = Depends(verify_admin_auth)):
    return {"authenticated": True, "username": username}

@router.post("/api/admin/logout")
def admin_logout(response: Response):
    response.delete_cookie("admin_session")
    return {"success": True}

@router.get("/api/admin/analytics")
def get_analytics_dashboard(days: Optional[int] = None, username: str = Depends(verify_admin_auth)):
    """Protected endpoint returning full aggregated dashboard metrics and factual insights."""
    data = analytics_db.get_dashboard_data(days=days)
    return data

@router.get("/api/analytics/status")
def analytics_status():
    """Diagnostic health status returning database connection provider and telemetry event counts."""
    return analytics_db.get_dashboard_data(days=1)
