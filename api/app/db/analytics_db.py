import os
import sqlite3
import json
import logging
import hashlib
import secrets
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

import tempfile

logger = logging.getLogger("analytics_db")

DB_PATH = os.path.join(tempfile.gettempdir(), "analytics_local.db")
DATABASE_URL = os.environ.get("DATABASE_URL")

def hash_password(password: str, salt: Optional[str] = None) -> (str, str):
    """Hashes a plaintext password using PBKDF2-HMAC-SHA256."""
    if not salt:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return key.hex(), salt

def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verifies a plaintext password against a stored PBKDF2 hash and salt."""
    computed_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(computed_hash, stored_hash)

def get_pg_url() -> Optional[str]:
    """Resolves PostgreSQL connection string from Vercel / Supabase environment variables."""
    keys = [
        "DATABASE_URL",
        "SUPABASE_POSTGRES_URL",
        "SUPABASE_POSTGRES_PRISMA_URL",
        "POSTGRES_URL",
        "POSTGRES_PRISMA_URL"
    ]
    for k in keys:
        val = os.environ.get(k)
        if val and isinstance(val, str) and (val.startswith("postgres://") or val.startswith("postgresql://")):
            return val.replace("postgres://", "postgresql://", 1)

    # Construct from individual Supabase / Postgres environment variables if URL is missing
    host = os.environ.get("SUPABASE_POSTGRES_HOST") or os.environ.get("POSTGRES_HOST")
    password = os.environ.get("SUPABASE_POSTGRES_PASSWORD") or os.environ.get("POSTGRES_PASSWORD")
    if host and password:
        user = os.environ.get("SUPABASE_POSTGRES_USER") or os.environ.get("POSTGRES_USER") or "postgres"
        db = os.environ.get("SUPABASE_POSTGRES_DATABASE") or os.environ.get("POSTGRES_DATABASE") or "postgres"
        port = os.environ.get("SUPABASE_POSTGRES_PORT") or os.environ.get("POSTGRES_PORT") or "5432"
        return f"postgresql://{user}:{password}@{host}:{port}/{db}"

    return None

def get_db_connection():
    """Returns a database connection (PostgreSQL via pure-Python pg8000 in production/Supabase, or SQLite for local dev)."""
    pg_url = get_pg_url()
    is_production = bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))

    if pg_url:
        try:
            import pg8000.dbapi
            import urllib.parse
            parsed = urllib.parse.urlparse(pg_url)
            db_name = parsed.path.lstrip('/').split('?')[0] or "postgres"
            conn = pg8000.dbapi.connect(
                user=parsed.username or "postgres",
                password=parsed.password or "",
                host=parsed.hostname or "localhost",
                port=parsed.port or 5432,
                database=db_name,
                ssl_context=True
            )
            return conn, "postgres"
        except Exception as e_pg:
            try:
                import psycopg2
                import psycopg2.extras
                conn = psycopg2.connect(pg_url, cursor_factory=psycopg2.extras.RealDictCursor)
                return conn, "postgres"
            except Exception as e_ps:
                err_msg = f"[ANALYTICS_DB] PostgreSQL connection failed (pg8000: {e_pg}, psycopg2: {e_ps})"
                logger.error(err_msg)
                if is_production:
                    raise RuntimeError(err_msg)

    if is_production:
        raise RuntimeError("[ANALYTICS_DB] Production environment detected on Vercel, but no PostgreSQL connection URL (DATABASE_URL / SUPABASE_POSTGRES_URL) was found.")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn, "sqlite"

def init_db():
    """Initializes analytics tables and indexes (pure analytics data only, no user tables)."""
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
            CREATE INDEX IF NOT EXISTS idx_events_created_at ON analytics_events(created_at);
            CREATE INDEX IF NOT EXISTS idx_events_type ON analytics_events(event_type);
            CREATE INDEX IF NOT EXISTS idx_events_status ON analytics_events(status);
            CREATE INDEX IF NOT EXISTS idx_errors_category ON analytics_errors(error_category);
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
            CREATE INDEX IF NOT EXISTS idx_events_created_at ON analytics_events(created_at);
            CREATE INDEX IF NOT EXISTS idx_events_type ON analytics_events(event_type);
            CREATE INDEX IF NOT EXISTS idx_events_status ON analytics_events(status);
            CREATE INDEX IF NOT EXISTS idx_errors_category ON analytics_errors(error_category);
            """)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"[ANALYTICS_DB_INIT_ERROR] {e}")

def verify_admin_credentials(username: str, password: str) -> bool:
    """Verifies single-admin credentials strictly against server-side environment variables."""
    env_user = os.environ.get("ADMIN_USERNAME", "admin").strip()
    env_pass = os.environ.get("ADMIN_PASSWORD", "admin123").strip()
    
    user_match = secrets.compare_digest(username.strip(), env_user)
    pass_match = secrets.compare_digest(password.strip(), env_pass)
    
    return user_match and pass_match

verify_admin_db_credentials = verify_admin_credentials

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
                session_id, event_type, conversion_type, destination_template,
                status, upload_time_ms, conversion_time_ms, download_time_ms,
                total_time_ms, validation_passed, compilation_passed
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (
                session_id, event_type, conversion_type, destination_template,
                status, upload_time_ms, conversion_time_ms, download_time_ms,
                total_time_ms, validation_passed, compilation_passed
            ))
        else:
            cursor.execute("""
            INSERT INTO analytics_events (
                session_id, event_type, conversion_type, destination_template,
                status, upload_time_ms, conversion_time_ms, download_time_ms,
                total_time_ms, validation_passed, compilation_passed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                session_id, event_type, conversion_type, destination_template,
                status, upload_time_ms, conversion_time_ms, download_time_ms,
                total_time_ms, 1 if validation_passed else (0 if validation_passed is False else None),
                1 if compilation_passed else (0 if compilation_passed is False else None)
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
            INSERT INTO analytics_errors (
                session_id, error_category, error_code, conversion_type, destination_template
            ) VALUES (%s, %s, %s, %s, %s);
            """, (session_id, error_category, error_code, conversion_type, destination_template))
        else:
            cursor.execute("""
            INSERT INTO analytics_errors (
                session_id, error_category, error_code, conversion_type, destination_template
            ) VALUES (?, ?, ?, ?, ?);
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
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        clean_text = feedback_text.strip()[:1000] if feedback_text else None
        if db_type == "postgres":
            cursor.execute("""
            INSERT INTO analytics_feedback (
                session_id, rating, is_useful, feedback_text, conversion_type
            ) VALUES (%s, %s, %s, %s, %s);
            """, (session_id, rating, is_useful, clean_text, conversion_type))
        else:
            cursor.execute("""
            INSERT INTO analytics_feedback (
                session_id, rating, is_useful, feedback_text, conversion_type
            ) VALUES (?, ?, ?, ?, ?);
            """, (session_id, rating, 1 if is_useful else 0, clean_text, conversion_type))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"[ANALYTICS_RECORD_FEEDBACK_ERROR] {e}")

def get_dashboard_data(days: Optional[int] = None) -> Dict[str, Any]:
    """Queries and returns aggregated metrics, date filtering, and evidence-backed factual insights."""
    init_db()
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        
        date_clause = ""
        session_date_clause = ""
        if days and days > 0:
            if db_type == "postgres":
                date_clause = f" WHERE created_at >= NOW() - INTERVAL '{days} day'"
                session_date_clause = f" WHERE last_active_at >= NOW() - INTERVAL '{days} day'"
            else:
                cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
                date_clause = f" WHERE created_at >= '{cutoff}'"
                session_date_clause = f" WHERE last_active_at >= '{cutoff}'"
        
        cursor.execute(f"SELECT COUNT(*) as cnt FROM analytics_sessions{session_date_clause};")
        row = cursor.fetchone()
        total_sessions = dict(row)["cnt"] if row else 0
        
        cursor.execute(f"SELECT COUNT(*) as cnt FROM analytics_sessions {session_date_clause + (' AND' if session_date_clause else 'WHERE')} (is_returning = 1 OR is_returning = true);")
        row = cursor.fetchone()
        returning_sessions = dict(row)["cnt"] if row else 0
        
        cursor.execute(f"SELECT COUNT(*) as cnt FROM analytics_events{date_clause} AND event_type = 'conversion_attempt';" if date_clause else "SELECT COUNT(*) as cnt FROM analytics_events WHERE event_type = 'conversion_attempt';")
        row = cursor.fetchone()
        total_conversion_attempts = dict(row)["cnt"] if row else 0
        
        cursor.execute(f"SELECT COUNT(*) as cnt FROM analytics_events{date_clause} AND event_type = 'conversion_result' AND (status = 'SUCCESS' OR status = 'completed');" if date_clause else "SELECT COUNT(*) as cnt FROM analytics_events WHERE event_type = 'conversion_result' AND (status = 'SUCCESS' OR status = 'completed');")
        row = cursor.fetchone()
        successful_conversions = dict(row)["cnt"] if row else 0

        cursor.execute(f"SELECT COUNT(*) as cnt FROM analytics_events{date_clause} AND event_type = 'download_click';" if date_clause else "SELECT COUNT(*) as cnt FROM analytics_events WHERE event_type = 'download_click';")
        row = cursor.fetchone()
        total_downloads = dict(row)["cnt"] if row else 0
        
        cursor.execute(f"SELECT COUNT(*) as cnt FROM analytics_errors{date_clause};" if date_clause else "SELECT COUNT(*) as cnt FROM analytics_errors;")
        row = cursor.fetchone()
        total_errors = dict(row)["cnt"] if row else 0

        # Strict Metric Rule: Return None if zero attempts (Do NOT return hardcoded 100%)
        success_rate_percent = round((successful_conversions / total_conversion_attempts) * 100.0, 1) if total_conversion_attempts > 0 else None
        
        cursor.execute(f"""
        SELECT 
            COALESCE(conversion_type, 'Standard Conversion') as wf,
            COUNT(*) as attempts,
            SUM(CASE WHEN status IN ('SUCCESS', 'completed') THEN 1 ELSE 0 END) as success_cnt
        FROM analytics_events
        {date_clause if date_clause else 'WHERE 1=1'} AND event_type IN ('conversion_attempt', 'conversion_result')
        GROUP BY conversion_type;
        """)
        wf_rows = [dict(r) for r in cursor.fetchall()]
        workflows = []
        for r in wf_rows:
            att = r["attempts"] or 0
            succ = r["success_cnt"] or 0
            rate = round((succ / att) * 100.0, 1) if att > 0 else None
            workflows.append({
                "conversion_type": r["wf"],
                "count": att,
                "successful": succ,
                "failed": att - succ,
                "percentage": round((att / total_conversion_attempts) * 100.0, 1) if total_conversion_attempts > 0 else 0.0,
                "success_rate": rate
            })
            
        cursor.execute(f"""
        SELECT 
            COALESCE(destination_template, 'Springer Journal') as tmpl,
            COUNT(*) as cnt
        FROM analytics_events
        {date_clause if date_clause else 'WHERE 1=1'} AND event_type IN ('conversion_attempt', 'conversion_result')
        GROUP BY destination_template;
        """)
        tmpl_rows = [dict(r) for r in cursor.fetchall()]
        templates = []
        for r in tmpl_rows:
            cnt = r["cnt"] or 0
            pct = round((cnt / total_conversion_attempts) * 100.0, 1) if total_conversion_attempts > 0 else 0.0
            templates.append({
                "template_name": r["tmpl"],
                "count": cnt,
                "percentage": pct
            })
            
        cursor.execute(f"""
        SELECT total_time_ms, upload_time_ms, conversion_time_ms
        FROM analytics_events
        {date_clause if date_clause else 'WHERE 1=1'} AND event_type = 'conversion_result' AND total_time_ms > 0
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
            
            upload_times = [r["upload_time_ms"] for r in times_rows if r.get("upload_time_ms")]
            avg_upload_s = round((sum(upload_times) / len(upload_times)) / 1000.0, 2) if upload_times else None
        else:
            avg_time_s, median_time_s, p95_time_s, avg_upload_s = None, None, None, None
            
        performance = {
            "avg_processing_time_s": avg_time_s,
            "median_processing_time_s": median_time_s,
            "p95_processing_time_s": p95_time_s,
            "avg_upload_time_s": avg_upload_s
        }
        
        cursor.execute(f"""
        SELECT error_category, COUNT(*) as cnt
        FROM analytics_errors
        {date_clause}
        GROUP BY error_category
        ORDER BY cnt DESC;
        """)
        err_rows = [dict(r) for r in cursor.fetchall()]
        error_categories = []
        for r in err_rows:
            cnt = r["cnt"] or 0
            pct = round((cnt / total_errors) * 100.0, 1) if total_errors > 0 else 0.0
            error_categories.append({
                "category": r["error_category"],
                "count": cnt,
                "percentage": pct
            })

        cursor.execute(f"""
        SELECT 
            SUM(CASE WHEN validation_passed = 1 OR validation_passed = true THEN 1 ELSE 0 END) as val_pass,
            COUNT(validation_passed) as val_total,
            SUM(CASE WHEN compilation_passed = 1 OR compilation_passed = true THEN 1 ELSE 0 END) as comp_pass,
            COUNT(compilation_passed) as comp_total
        FROM analytics_events
        {date_clause if date_clause else 'WHERE 1=1'} AND event_type = 'conversion_result';
        """)
        q_row = dict(cursor.fetchone()) if cursor.rowcount != 0 else {}
        val_pass = q_row.get("val_pass") or 0
        val_total = q_row.get("val_total") or 0
        comp_pass = q_row.get("comp_pass") or 0
        comp_total = q_row.get("comp_total") or 0
        
        # Strict Metric Rules: Return None when count is 0
        val_rate = round((val_pass / val_total) * 100.0, 1) if val_total > 0 else None
        comp_rate = round((comp_pass / comp_total) * 100.0, 1) if comp_total > 0 else None
        
        quality_indicators = {
            "validation_pass_rate": val_rate,
            "validation_passed_count": val_pass,
            "validation_total_count": val_total,
            "compilation_pass_rate": comp_rate,
            "compilation_passed_count": comp_pass,
            "compilation_total_count": comp_total,
            "overall_delivery_rate": success_rate_percent
        }
        
        cursor.execute(f"""
        SELECT 
            AVG(rating) as avg_rating,
            COUNT(*) as total_feedback,
            SUM(CASE WHEN is_useful = 1 OR is_useful = true THEN 1 ELSE 0 END) as useful_cnt
        FROM analytics_feedback
        {date_clause};
        """)
        fb_row = dict(cursor.fetchone()) if cursor.rowcount != 0 else {}
        raw_avg = fb_row.get("avg_rating")
        tot_fb = fb_row.get("total_feedback") or 0
        use_cnt = fb_row.get("useful_cnt") or 0
        
        # Strict Metric Rules: Return None when no feedback responses
        avg_rating = round(raw_avg, 1) if (tot_fb > 0 and raw_avg is not None) else None
        useful_rate = round((use_cnt / tot_fb) * 100.0, 1) if tot_fb > 0 else None
        
        cursor.execute(f"""
        SELECT feedback_text, rating, is_useful, conversion_type, created_at
        FROM analytics_feedback
        {date_clause}
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
        
        # Build Factual Evidence-Backed Insights
        insights = []
        if workflows:
            top_wf = max(workflows, key=lambda x: x["count"])
            insights.append(f"Most used conversion workflow: {top_wf['conversion_type']} ({top_wf['count']} attempts)")
        if templates:
            top_tmpl = max(templates, key=lambda x: x["count"])
            insights.append(f"Most popular target publisher template: {top_tmpl['template_name']} ({top_tmpl['count']} conversions)")
        if performance["avg_processing_time_s"] is not None and performance["avg_processing_time_s"] > 0:
            insights.append(f"Average conversion duration: {performance['avg_processing_time_s']} seconds (P95: {performance['p95_processing_time_s']}s)")
        if total_conversion_attempts > 0:
            insights.append(f"Conversion success rate: {success_rate_percent}% across {total_conversion_attempts} conversion attempts")
        if error_categories:
            top_err = error_categories[0]
            insights.append(f"Most common error category: {top_err['category']} ({top_err['count']} occurrences)")
        elif total_conversion_attempts > 0:
            insights.append("Zero conversion errors recorded in telemetry window.")
        else:
            insights.append("Zero conversion telemetry data recorded in active window.")

        conn.close()
        
        return {
            "db_connected": True,
            "db_provider": "PostgreSQL" if db_type == "postgres" else "SQLite",
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
            "user_feedback": user_feedback,
            "insights": insights
        }
    except Exception as e:
        logger.warning(f"[ANALYTICS_GET_DASHBOARD_DATA_ERROR] {e}")
        return {
            "db_connected": False,
            "db_provider": None,
            "error": "Analytics database unavailable",
            "summary": {
                "total_sessions": 0,
                "returning_sessions": 0,
                "total_conversion_attempts": 0,
                "successful_conversions": 0,
                "failed_conversions": 0,
                "success_rate_percent": None,
                "total_downloads": 0,
                "total_errors": 0
            },
            "workflows": [],
            "templates": [],
            "performance": {
                "avg_processing_time_s": None,
                "median_processing_time_s": None,
                "p95_processing_time_s": None,
                "avg_upload_time_s": None
            },
            "error_categories": [],
            "quality_indicators": {
                "validation_pass_rate": None,
                "compilation_pass_rate": None,
                "overall_delivery_rate": None
            },
            "user_feedback": {
                "average_rating": None,
                "total_responses": 0,
                "useful_percentage": None,
                "recent_comments": []
            },
            "insights": ["Analytics database unavailable"]
        }

