import os
import sqlite3
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger("analytics_db")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "analytics_local.db")
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    """Returns a database connection (PostgreSQL if DATABASE_URL set, otherwise SQLite)."""
    if DATABASE_URL and (DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")):
        try:
            import psycopg2
            import psycopg2.extras
            # Fix postgres:// URL for psycopg2 if needed
            pg_url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
            conn = psycopg2.connect(pg_url, cursor_factory=psycopg2.extras.RealDictCursor)
            return conn, "postgres"
        except Exception as e:
            logger.warning(f"[ANALYTICS_DB] PostgreSQL connection failed, falling back to SQLite: {e}")
            
    # SQLite fallback
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn, "sqlite"

def init_db():
    """Initializes analytics tables if they do not exist."""
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        
        if db_type == "postgres":
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS analytics_sessions (
                session_id VARCHAR(64) PRIMARY KEY,
                started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                last_active_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                is_returning BOOLEAN DEFAULT FALSE,
                browser_family VARCHAR(50)
            );
            CREATE TABLE IF NOT EXISTS analytics_events (
                event_id SERIAL PRIMARY KEY,
                session_id VARCHAR(64),
                event_type VARCHAR(50) NOT NULL,
                conversion_type VARCHAR(50),
                destination_template VARCHAR(50),
                status VARCHAR(20),
                upload_time_ms INT,
                conversion_time_ms INT,
                download_time_ms INT,
                total_time_ms INT,
                validation_passed BOOLEAN,
                compilation_passed BOOLEAN,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS analytics_errors (
                error_id SERIAL PRIMARY KEY,
                session_id VARCHAR(64),
                error_category VARCHAR(50) NOT NULL,
                error_code VARCHAR(100),
                conversion_type VARCHAR(50),
                destination_template VARCHAR(50),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS analytics_feedback (
                feedback_id SERIAL PRIMARY KEY,
                session_id VARCHAR(64),
                rating INT,
                is_useful BOOLEAN,
                feedback_text TEXT,
                conversion_type VARCHAR(50),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """)
        else: # SQLite
            cursor.executescript("""
            CREATE TABLE IF NOT EXISTS analytics_sessions (
                session_id TEXT PRIMARY KEY,
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_active_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_returning INTEGER DEFAULT 0,
                browser_family TEXT
            );
            CREATE TABLE IF NOT EXISTS analytics_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                event_type TEXT NOT NULL,
                conversion_type TEXT,
                destination_template TEXT,
                status TEXT,
                upload_time_ms INTEGER,
                conversion_time_ms INTEGER,
                download_time_ms INTEGER,
                total_time_ms INTEGER,
                validation_passed INTEGER,
                compilation_passed INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS analytics_errors (
                error_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                error_category TEXT NOT NULL,
                error_code TEXT,
                conversion_type TEXT,
                destination_template TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS analytics_feedback (
                feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                rating INTEGER,
                is_useful INTEGER,
                feedback_text TEXT,
                conversion_type TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"[ANALYTICS_DB_INIT_ERROR] {e}")

def record_session(session_id: str, is_returning: bool = False, browser_family: str = "Unknown"):
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        if db_type == "postgres":
            cursor.execute("""
            INSERT INTO analytics_sessions (session_id, is_returning, browser_family)
            VALUES (%s, %s, %s)
            ON CONFLICT (session_id) DO UPDATE SET last_active_at = CURRENT_TIMESTAMP, is_returning = %s;
            """, (session_id, is_returning, browser_family, is_returning))
        else:
            cursor.execute("""
            INSERT INTO analytics_sessions (session_id, is_returning, browser_family)
            VALUES (?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET last_active_at = CURRENT_TIMESTAMP, is_returning = ?;
            """, (session_id, 1 if is_returning else 0, browser_family, 1 if is_returning else 0))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"[ANALYTICS_RECORD_SESSION_ERROR] {e}")

def record_event(
    session_id: str,
    event_type: str,
    conversion_type: Optional[str] = None,
    destination_template: Optional[str] = None,
    status: Optional[str] = None,
    upload_time_ms: Optional[int] = None,
    conversion_time_ms: Optional[int] = None,
    download_time_ms: Optional[int] = None,
    total_time_ms: Optional[int] = None,
    validation_passed: Optional[bool] = None,
    compilation_passed: Optional[bool] = None
):
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        if db_type == "postgres":
            cursor.execute("""
            INSERT INTO analytics_events (
                session_id, event_type, conversion_type, destination_template, status,
                upload_time_ms, conversion_time_ms, download_time_ms, total_time_ms,
                validation_passed, compilation_passed
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (
                session_id, event_type, conversion_type, destination_template, status,
                upload_time_ms, conversion_time_ms, download_time_ms, total_time_ms,
                validation_passed, compilation_passed
            ))
        else:
            cursor.execute("""
            INSERT INTO analytics_events (
                session_id, event_type, conversion_type, destination_template, status,
                upload_time_ms, conversion_time_ms, download_time_ms, total_time_ms,
                validation_passed, compilation_passed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                session_id, event_type, conversion_type, destination_template, status,
                upload_time_ms, conversion_time_ms, download_time_ms, total_time_ms,
                1 if validation_passed else (0 if validation_passed is not None else None),
                1 if compilation_passed else (0 if compilation_passed is not None else None)
            ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"[ANALYTICS_RECORD_EVENT_ERROR] {e}")

def record_error(
    session_id: str,
    error_category: str,
    error_code: Optional[str] = None,
    conversion_type: Optional[str] = None,
    destination_template: Optional[str] = None
):
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        if db_type == "postgres":
            cursor.execute("""
            INSERT INTO analytics_errors (session_id, error_category, error_code, conversion_type, destination_template)
            VALUES (%s, %s, %s, %s, %s);
            """, (session_id, error_category, error_code, conversion_type, destination_template))
        else:
            cursor.execute("""
            INSERT INTO analytics_errors (session_id, error_category, error_code, conversion_type, destination_template)
            VALUES (?, ?, ?, ?, ?);
            """, (session_id, error_category, error_code, conversion_type, destination_template))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"[ANALYTICS_RECORD_ERROR_ERROR] {e}")

def record_feedback(
    session_id: str,
    rating: int,
    is_useful: bool,
    feedback_text: Optional[str] = None,
    conversion_type: Optional[str] = None
):
    try:
        clean_text = (feedback_text or "").strip()[:500]
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        if db_type == "postgres":
            cursor.execute("""
            INSERT INTO analytics_feedback (session_id, rating, is_useful, feedback_text, conversion_type)
            VALUES (%s, %s, %s, %s, %s);
            """, (session_id, rating, is_useful, clean_text, conversion_type))
        else:
            cursor.execute("""
            INSERT INTO analytics_feedback (session_id, rating, is_useful, feedback_text, conversion_type)
            VALUES (?, ?, ?, ?, ?);
            """, (session_id, rating, 1 if is_useful else 0, clean_text, conversion_type))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"[ANALYTICS_RECORD_FEEDBACK_ERROR] {e}")

def get_dashboard_data() -> Dict[str, Any]:
    """Queries and returns aggregated analytics metrics for the dashboard."""
    init_db()
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as cnt FROM analytics_sessions;")
        row = cursor.fetchone()
        total_sessions = dict(row)["cnt"] if row else 0
        
        cursor.execute("SELECT COUNT(*) as cnt FROM analytics_sessions WHERE is_returning = 1 OR is_returning = true;")
        row = cursor.fetchone()
        returning_sessions = dict(row)["cnt"] if row else 0
        
        cursor.execute("SELECT COUNT(*) as cnt FROM analytics_events WHERE event_type = 'conversion_attempt';")
        row = cursor.fetchone()
        total_conversion_attempts = dict(row)["cnt"] if row else 0
        
        cursor.execute("SELECT COUNT(*) as cnt FROM analytics_events WHERE event_type = 'conversion_result' AND status = 'SUCCESS';")
        row = cursor.fetchone()
        successful_conversions = dict(row)["cnt"] if row else 0

        cursor.execute("SELECT COUNT(*) as cnt FROM analytics_events WHERE event_type = 'download_click';")
        row = cursor.fetchone()
        total_downloads = dict(row)["cnt"] if row else 0
        
        cursor.execute("SELECT COUNT(*) as cnt FROM analytics_errors;")
        row = cursor.fetchone()
        total_errors = dict(row)["cnt"] if row else 0

        success_rate_percent = round((successful_conversions / max(1, total_conversion_attempts)) * 100.0, 1) if total_conversion_attempts > 0 else 100.0
        
        cursor.execute("""
        SELECT 
            COALESCE(conversion_type, 'unknown') as wf,
            COUNT(*) as attempts,
            SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as success_cnt
        FROM analytics_events
        WHERE event_type IN ('conversion_attempt', 'conversion_result')
        GROUP BY conversion_type;
        """)
        wf_rows = [dict(r) for r in cursor.fetchall()]
        workflows = []
        for r in wf_rows:
            att = r["attempts"] or 0
            succ = r["success_cnt"] or 0
            rate = round((succ / max(1, att)) * 100.0, 1) if att > 0 else 0.0
            workflows.append({
                "type": r["wf"],
                "attempts": att,
                "successful": succ,
                "failed": att - succ,
                "success_rate": rate
            })
            
        cursor.execute("""
        SELECT 
            COALESCE(destination_template, 'Standard') as tmpl,
            COUNT(*) as cnt
        FROM analytics_events
        WHERE event_type = 'conversion_attempt'
        GROUP BY destination_template;
        """)
        tmpl_rows = [dict(r) for r in cursor.fetchall()]
        templates = []
        for r in tmpl_rows:
            cnt = r["cnt"] or 0
            pct = round((cnt / max(1, total_conversion_attempts)) * 100.0, 1) if total_conversion_attempts > 0 else 0.0
            templates.append({
                "template": r["tmpl"],
                "count": cnt,
                "percentage": pct
            })
            
        cursor.execute("""
        SELECT total_time_ms, upload_time_ms, conversion_time_ms
        FROM analytics_events
        WHERE event_type = 'conversion_result' AND total_time_ms > 0
        ORDER BY total_time_ms ASC;
        """)
        times_rows = [dict(r) for r in cursor.fetchall()]
        
        if times_rows:
            total_times = [r["total_time_ms"] for r in times_rows]
            avg_time_s = round((sum(total_times) / len(total_times)) / 1000.0, 2)
            median_idx = len(total_times) // 2
            median_time_s = round(total_times[median_idx] / 1000.0, 2)
            p95_idx = int(len(total_times) * 0.95)
            p95_time_s = round(total_times[min(p95_idx, len(total_times)-1)] / 1000.0, 2)
            
            upload_times = [r["upload_time_ms"] for r in times_rows if r["upload_time_ms"]]
            avg_upload_s = round((sum(upload_times) / len(upload_times)) / 1000.0, 2) if upload_times else 0.0
        else:
            avg_time_s, median_time_s, p95_time_s, avg_upload_s = 0.0, 0.0, 0.0, 0.0
            
        performance = {
            "avg_processing_time_s": avg_time_s,
            "median_processing_time_s": median_time_s,
            "p95_processing_time_s": p95_time_s,
            "avg_upload_time_s": avg_upload_s
        }
        
        cursor.execute("""
        SELECT error_category, COUNT(*) as cnt
        FROM analytics_errors
        GROUP BY error_category
        ORDER BY cnt DESC;
        """)
        err_rows = [dict(r) for r in cursor.fetchall()]
        error_categories = []
        for r in err_rows:
            cnt = r["cnt"] or 0
            pct = round((cnt / max(1, total_errors)) * 100.0, 1) if total_errors > 0 else 0.0
            error_categories.append({
                "category": r["error_category"],
                "count": cnt,
                "percentage": pct
            })

        cursor.execute("""
        SELECT 
            SUM(CASE WHEN validation_passed = 1 OR validation_passed = true THEN 1 ELSE 0 END) as val_pass,
            COUNT(validation_passed) as val_total,
            SUM(CASE WHEN compilation_passed = 1 OR compilation_passed = true THEN 1 ELSE 0 END) as comp_pass,
            COUNT(compilation_passed) as comp_total
        FROM analytics_events
        WHERE event_type = 'conversion_result';
        """)
        q_row = dict(cursor.fetchone()) if cursor.rowcount != 0 else {}
        val_pass = q_row.get("val_pass") or 0
        val_total = q_row.get("val_total") or 0
        comp_pass = q_row.get("comp_pass") or 0
        comp_total = q_row.get("comp_total") or 0
        
        val_rate = round((val_pass / max(1, val_total)) * 100.0, 1) if val_total > 0 else 100.0
        comp_rate = round((comp_pass / max(1, comp_total)) * 100.0, 1) if comp_total > 0 else 100.0
        
        quality_indicators = {
            "validation_pass_rate": val_rate,
            "validation_passed_count": val_pass,
            "validation_total_count": val_total,
            "compilation_pass_rate": comp_rate,
            "compilation_passed_count": comp_pass,
            "compilation_total_count": comp_total,
            "overall_delivery_rate": success_rate_percent
        }
        
        cursor.execute("""
        SELECT 
            AVG(rating) as avg_rating,
            COUNT(*) as total_feedback,
            SUM(CASE WHEN is_useful = 1 OR is_useful = true THEN 1 ELSE 0 END) as useful_cnt
        FROM analytics_feedback;
        """)
        fb_row = dict(cursor.fetchone()) if cursor.rowcount != 0 else {}
        avg_rating = round(fb_row.get("avg_rating") or 5.0, 1)
        tot_fb = fb_row.get("total_feedback") or 0
        use_cnt = fb_row.get("useful_cnt") or 0
        useful_rate = round((use_cnt / max(1, tot_fb)) * 100.0, 1) if tot_fb > 0 else 100.0
        
        cursor.execute("""
        SELECT feedback_text, rating, conversion_type, created_at
        FROM analytics_feedback
        WHERE feedback_text IS NOT NULL AND LENGTH(feedback_text) > 2
        ORDER BY feedback_id DESC
        LIMIT 10;
        """)
        comments = [dict(c) for c in cursor.fetchall()]
        
        user_feedback = {
            "average_rating": avg_rating,
            "total_responses": tot_fb,
            "useful_percentage": useful_rate,
            "recent_comments": comments
        }
        
        conn.close()
        
        return {
            "summary": {
                "total_sessions": total_sessions,
                "returning_sessions": returning_sessions,
                "total_conversion_attempts": total_conversion_attempts,
                "successful_conversions": successful_conversions,
                "failed_conversions": total_conversion_attempts - successful_conversions,
                "success_rate_percent": success_rate_percent,
                "total_downloads": total_downloads,
                "total_errors": total_errors
            },
            "workflows": workflows,
            "templates": templates,
            "performance": performance,
            "error_categories": error_categories,
            "quality_indicators": quality_indicators,
            "user_feedback": user_feedback
        }
    except Exception as e:
        logger.warning(f"[ANALYTICS_GET_DASHBOARD_DATA_ERROR] {e}")
        return {
            "summary": {"total_sessions": 0, "total_conversion_attempts": 0, "successful_conversions": 0, "failed_conversions": 0, "success_rate_percent": 100.0, "total_downloads": 0, "total_errors": 0},
            "workflows": [],
            "templates": [],
            "performance": {"avg_processing_time_s": 0.0, "median_processing_time_s": 0.0, "p95_processing_time_s": 0.0, "avg_upload_time_s": 0.0},
            "error_categories": [],
            "quality_indicators": {"validation_pass_rate": 100.0, "compilation_pass_rate": 100.0, "overall_delivery_rate": 100.0},
            "user_feedback": {"average_rating": 5.0, "total_responses": 0, "useful_percentage": 100.0, "recent_comments": []}
        }

try:
    init_db()
except Exception:
    pass
