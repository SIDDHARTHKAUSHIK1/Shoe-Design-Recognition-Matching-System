"""
SQLite Metadata & Query Logging Database Manager.
"""
import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from backend.config import DB_PATH

import math
from backend.config import DB_PATH, load_thresholds_config

logger = logging.getLogger(__name__)


def get_db_connection() -> sqlite3.Connection:
    """Establish a connection to the SQLite database with row factory enabled."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for high read/write performance
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def normalize_category(cat: Optional[str]) -> str:
    """
    Normalize any footwear category or style into 'shoe' or 'slipper'.
    """
    if not cat:
        return "shoe"
    c = cat.strip().lower()
    slipper_keywords = ["slipper", "slide", "flip", "flop", "sandal", "mule", "clog", "thong", "chappal", "croc"]
    if any(k in c for k in slipper_keywords):
        return "slipper"
    return "shoe"


def is_slipper_category(cat: Optional[str]) -> bool:
    """Return True if the category normalizes to 'slipper'. Used as a hard gate."""
    return normalize_category(cat) == "slipper"


def calculate_calibrated_confidence(similarity: float, category: str = "shoe") -> float:
    """
    Convert raw cosine similarity into calibrated confidence probability using fitted Platt scaling parameters.
    P(Match | s) = 1 / (1 + e^-(a*s + b))
    """
    thresholds = load_thresholds_config()
    cat_config = thresholds.get(normalize_category(category), thresholds.get("global", {}))
    platt = cat_config.get("platt_scaling", {"a": 15.0, "b": -8.5})
    
    a = platt.get("a", 15.0)
    b = platt.get("b", -8.5)
    
    try:
        logit = a * float(similarity) + b
        logit = max(-50.0, min(50.0, logit))
        prob = 1.0 / (1.0 + math.exp(-logit))
        return round(float(prob * 100.0), 2)
    except Exception:
        return round(max(0.0, min(100.0, similarity * 100.0)), 2)


def init_db():
    """Initialize database tables if they do not exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Users & Roles Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('employee', 'admin')),
                full_name TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                must_change_password INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP NULL
            );
        """)

        try:
            cursor.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER DEFAULT 0;")
        except sqlite3.OperationalError:
            pass

        # 2. Designs Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS designs (
                design_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT DEFAULT 'Sneaker',
                description TEXT DEFAULT '',
                created_by TEXT DEFAULT 'Design Team',
                shelf_location TEXT DEFAULT 'Warehouse A - Rack 03 - Shelf B-02',
                materials TEXT DEFAULT 'Full Grain Leather / Anti-Slip Rubber',
                season TEXT DEFAULT 'Collection 2026',
                production_status TEXT DEFAULT 'Sample Archive',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                thumbnail_path TEXT DEFAULT '',
                drawer TEXT DEFAULT '',
                slot TEXT DEFAULT '',
                shoe_match_tag TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                is_archived INTEGER DEFAULT 0
            );
        """)
        
        # Automatic column migrations for existing databases
        for col, col_def in [
            ("shelf_location", "TEXT DEFAULT 'Warehouse A - Rack 03 - Shelf B-02'"),
            ("materials", "TEXT DEFAULT 'Full Grain Leather / Anti-Slip Rubber'"),
            ("season", "TEXT DEFAULT 'Collection 2026'"),
            ("production_status", "TEXT DEFAULT 'Sample Archive'"),
            ("drawer", "TEXT DEFAULT ''"),
            ("slot", "TEXT DEFAULT ''"),
            ("shoe_match_tag", "TEXT DEFAULT ''"),
            ("is_active", "INTEGER DEFAULT 1"),
            ("is_archived", "INTEGER DEFAULT 0")
        ]:
            try:
                cursor.execute(f"ALTER TABLE designs ADD COLUMN {col} {col_def};")
            except sqlite3.OperationalError:
                pass

        for col, col_def in [
            ("detected_category", "TEXT DEFAULT 'shoe'"),
            ("user_id", "INTEGER NULL")
        ]:
            try:
                cursor.execute(f"ALTER TABLE query_logs ADD COLUMN {col} {col_def};")
            except sqlite3.OperationalError:
                pass
        
        # 3. Reference Images Table (links each angle photo to a FAISS vector ID)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reference_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                design_id TEXT NOT NULL,
                image_path TEXT NOT NULL,
                angle TEXT DEFAULT 'side',
                faiss_id INTEGER UNIQUE NOT NULL,
                color_histogram TEXT DEFAULT '',
                dominant_colors TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (design_id) REFERENCES designs(design_id) ON DELETE CASCADE
            );
        """)
        
        for col, col_def in [
            ("color_histogram", "TEXT DEFAULT ''"),
            ("dominant_colors", "TEXT DEFAULT ''")
        ]:
            try:
                cursor.execute(f"ALTER TABLE reference_images ADD COLUMN {col} {col_def};")
            except sqlite3.OperationalError:
                pass
        
        # 4. Query Audit Logs Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS query_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_image_path TEXT NOT NULL,
                top_match_id TEXT,
                top_match_name TEXT,
                confidence_pct REAL,
                latency_ms REAL,
                results_json TEXT,
                detected_category TEXT DEFAULT 'shoe',
                user_id INTEGER NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 5. Match Feedback Table for Continuous Improvement
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS match_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_id INTEGER,
                user_verdict TEXT NOT NULL,
                correct_design_id TEXT,
                notes TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        conn.commit()

    # Seed Default Admin and Employee Accounts if users table is empty
    from backend.auth import hash_password
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            admin_pwd = hash_password("admin123")
            emp_pwd = hash_password("emp123")
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, full_name, must_change_password)
                VALUES 
                    ('admin', ?, 'admin', 'System Administrator', 1),
                    ('employee', ?, 'employee', 'Warehouse Operations Staff', 1);
            """, (admin_pwd, emp_pwd))
            conn.commit()
            logger.info("Seeded default 'admin' and 'employee' accounts with forced password change on first login.")
        # Ensure seeded default accounts require password change on first login
        cursor.execute("UPDATE users SET must_change_password = 1 WHERE username IN ('admin', 'employee');")
        conn.commit()

    logger.info(f"Database initialized successfully at {DB_PATH}")


def add_design(
    design_id: str,
    name: str,
    category: str = "Sneaker",
    description: str = "",
    created_by: str = "Design Team",
    shelf_location: str = "Warehouse A - Rack 03 - Shelf B-02",
    materials: str = "Full Grain Leather / Anti-Slip Rubber",
    season: str = "Collection 2026",
    production_status: str = "Sample Archive",
    thumbnail_path: str = ""
) -> bool:
    """Add a new shoe design to the catalog."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO designs (
                design_id, name, category, description, created_by, 
                shelf_location, materials, season, production_status, thumbnail_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(design_id) DO UPDATE SET
                name = excluded.name,
                category = excluded.category,
                description = excluded.description,
                shelf_location = CASE WHEN excluded.shelf_location != '' THEN excluded.shelf_location ELSE shelf_location END,
                materials = CASE WHEN excluded.materials != '' THEN excluded.materials ELSE materials END,
                season = CASE WHEN excluded.season != '' THEN excluded.season ELSE season END,
                production_status = CASE WHEN excluded.production_status != '' THEN excluded.production_status ELSE production_status END,
                thumbnail_path = CASE WHEN excluded.thumbnail_path != '' THEN excluded.thumbnail_path ELSE thumbnail_path END;
        """, (
            design_id, name, category, description, created_by,
            shelf_location, materials, season, production_status, thumbnail_path
        ))
        conn.commit()
        return True


def update_design_location(design_id: str, shelf_location: str, production_status: Optional[str] = None) -> bool:
    """Update warehouse shelf location and production status for a shoe design."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if production_status:
            cursor.execute("""
                UPDATE designs 
                SET shelf_location = ?, production_status = ?
                WHERE design_id = ?;
            """, (shelf_location, production_status, design_id))
        else:
            cursor.execute("""
                UPDATE designs 
                SET shelf_location = ?
                WHERE design_id = ?;
            """, (shelf_location, design_id))
        conn.commit()
        return cursor.rowcount > 0


def update_design_status(design_id: str, is_active: Optional[int] = None, is_archived: Optional[int] = None) -> bool:
    """Update active/archived status for a catalog design."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        updates = []
        params = []
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(is_active)
        if is_archived is not None:
            updates.append("is_archived = ?")
            params.append(is_archived)
        if not updates:
            return False
        params.append(design_id)
        cursor.execute(f"UPDATE designs SET {', '.join(updates)} WHERE design_id = ?", tuple(params))
        conn.commit()
        return cursor.rowcount > 0


def update_design_metadata(design_id: str, **kwargs) -> bool:
    """Update general design metadata attributes."""
    allowed = {"name", "category", "description", "shelf_location", "materials", "season", "production_status", "drawer", "slot", "shoe_match_tag"}
    updates = []
    params = []
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            updates.append(f"{k} = ?")
            params.append(v)
    if not updates:
        return False
    params.append(design_id)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE designs SET {', '.join(updates)} WHERE design_id = ?", tuple(params))
        conn.commit()
        return cursor.rowcount > 0


def add_reference_image(
    design_id: str,
    image_path: str,
    angle: str,
    faiss_id: int
) -> int:
    """Register a reference angle photo with its assigned FAISS vector index ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO reference_images (design_id, image_path, angle, faiss_id)
            VALUES (?, ?, ?, ?);
        """, (design_id, image_path, angle, faiss_id))
        
        # Update design thumbnail if empty
        cursor.execute("""
            UPDATE designs
            SET thumbnail_path = ?
            WHERE design_id = ? AND (thumbnail_path IS NULL OR thumbnail_path = '');
        """, (image_path, design_id))
        
        conn.commit()
        return cursor.lastrowid


def get_all_designs() -> List[Dict[str, Any]]:
    """Retrieve all catalog designs along with image counts."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                d.design_id,
                d.name,
                d.category,
                d.description,
                d.created_by,
                d.shelf_location,
                d.materials,
                d.season,
                d.production_status,
                d.created_at,
                d.thumbnail_path,
                COUNT(r.id) as image_count
            FROM designs d
            LEFT JOIN reference_images r ON d.design_id = r.design_id
            GROUP BY d.design_id
            ORDER BY d.created_at DESC;
        """)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_design(design_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single design and all its associated reference images."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM designs WHERE design_id = ?;", (design_id,))
        design_row = cursor.fetchone()
        if not design_row:
            return None
            
        design_dict = dict(design_row)
        cursor.execute("""
            SELECT id, image_path, angle, faiss_id, created_at
            FROM reference_images
            WHERE design_id = ?
            ORDER BY id ASC;
        """, (design_id,))
        design_dict["reference_images"] = [dict(r) for r in cursor.fetchall()]
        return design_dict


def get_reference_image_by_faiss_id(faiss_id: int) -> Optional[Dict[str, Any]]:
    """Look up reference image and parent design details by FAISS ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                r.id as ref_id,
                r.image_path,
                r.angle,
                r.faiss_id,
                r.color_histogram,
                r.dominant_colors,
                d.design_id,
                d.name,
                d.category,
                d.description,
                d.created_by,
                d.shelf_location,
                d.materials,
                d.season,
                d.production_status
            FROM reference_images r
            JOIN designs d ON r.design_id = d.design_id
            WHERE r.faiss_id = ? AND (d.is_active IS NULL OR d.is_active = 1) AND (d.is_archived IS NULL OR d.is_archived = 0);
        """, (faiss_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_reference_image_color(
    faiss_id: int, 
    color_histogram: List[float], 
    dominant_colors: List[Dict[str, Any]]
) -> bool:
    """Update color histogram and dominant colors for a catalog reference image."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE reference_images
            SET color_histogram = ?, dominant_colors = ?
            WHERE faiss_id = ?;
        """, (
            json.dumps([float(x) for x in color_histogram]),
            json.dumps(dominant_colors),
            faiss_id
        ))
        conn.commit()
        return cursor.rowcount > 0


def get_all_reference_images() -> List[Dict[str, Any]]:
    """Get all reference image records ordered by FAISS ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                r.id,
                r.design_id,
                r.image_path,
                r.angle,
                r.faiss_id,
                d.name as design_name,
                d.category as design_category
            FROM reference_images r
            JOIN designs d ON r.design_id = d.design_id
            ORDER BY r.faiss_id ASC;
        """)
        return [dict(r) for r in cursor.fetchall()]


def get_all_shoe_reference_images() -> List[Dict[str, Any]]:
    """
    Get ONLY shoe (non-slipper) reference image records ordered by FAISS ID.
    Use this for ALL FAISS index rebuild paths to guarantee slippers are never re-indexed.
    """
    all_refs = get_all_reference_images()
    return [r for r in all_refs if not is_slipper_category(r.get("design_category", ""))]




def delete_design(design_id: str) -> bool:
    """Delete a design and its associated reference images."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM designs WHERE design_id = ?;", (design_id,))
        conn.commit()
        return cursor.rowcount > 0


def log_query(
    query_image_path: str,
    top_match_id: Optional[str],
    top_match_name: Optional[str],
    confidence_pct: float,
    latency_ms: float,
    results: List[Dict[str, Any]],
    detected_category: str = "shoe",
    user_id: Optional[int] = None
) -> int:
    """Log an inference query for auditing and threshold tuning."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO query_logs (
                query_image_path,
                top_match_id,
                top_match_name,
                confidence_pct,
                latency_ms,
                results_json,
                detected_category,
                user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            query_image_path,
            top_match_id,
            top_match_name,
            round(confidence_pct, 2),
            round(latency_ms, 2),
            json.dumps(results),
            detected_category,
            user_id
        ))
        conn.commit()
        return cursor.lastrowid


def get_query_logs(limit: int = 50, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Fetch recent query logs, optionally filtered by user_id."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if user_id is not None:
            cursor.execute("""
                SELECT * FROM query_logs
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?;
            """, (user_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM query_logs
                ORDER BY id DESC
                LIMIT ?;
            """, (limit,))
        logs = [dict(row) for row in cursor.fetchall()]
        for log in logs:
            if log.get("results_json"):
                try:
                    log["results"] = json.loads(log["results_json"])
                except Exception:
                    log["results"] = []
        return logs


def get_catalog_stats() -> Dict[str, Any]:
    """Retrieve summary metrics for the catalog."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM designs;")
        total_designs = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM reference_images;")
        total_images = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*), AVG(latency_ms), AVG(confidence_pct) FROM query_logs;")
        q_count, avg_lat, avg_conf = cursor.fetchone()
        
        return {
            "total_designs": total_designs,
            "total_reference_images": total_images,
            "total_queries_logged": q_count or 0,
            "average_latency_ms": round(avg_lat or 0.0, 1),
            "average_confidence_pct": round(avg_conf or 0.0, 1)
        }


def record_feedback(
    query_id: Optional[int],
    user_verdict: str,
    correct_design_id: Optional[str] = None,
    notes: str = ""
) -> Dict[str, Any]:
    """
    Record user feedback on a search result for auditing and dataset curation.
    Allowed verdicts: 'correct', 'wrong_match', 'not_in_catalog', 'wrong_category'
    """
    valid_verdicts = {"correct", "wrong_match", "not_in_catalog", "wrong_category"}
    if user_verdict not in valid_verdicts:
        user_verdict = "wrong_match"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO match_feedback (
                query_id,
                user_verdict,
                correct_design_id,
                notes
            ) VALUES (?, ?, ?, ?);
        """, (query_id, user_verdict, correct_design_id, notes))
        conn.commit()
        feedback_id = cursor.lastrowid
        
        return {
            "id": feedback_id,
            "query_id": query_id,
            "user_verdict": user_verdict,
            "correct_design_id": correct_design_id,
            "notes": notes,
            "status": "recorded"
        }


def get_feedback_logs(limit: int = 100) -> List[Dict[str, Any]]:
    """Fetch recent match feedback records joined with query log metadata."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                f.id,
                f.query_id,
                f.user_verdict,
                f.correct_design_id,
                f.notes,
                f.created_at,
                q.query_image_path,
                q.top_match_id,
                q.top_match_name,
                q.confidence_pct,
                q.detected_category
            FROM match_feedback f
            LEFT JOIN query_logs q ON f.query_id = q.id
            ORDER BY f.id DESC
            LIMIT ?;
        """, (limit,))
        return [dict(r) for r in cursor.fetchall()]
