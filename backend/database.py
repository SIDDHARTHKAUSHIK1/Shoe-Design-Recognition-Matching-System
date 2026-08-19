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
        
        # 1. Designs Table
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
                thumbnail_path TEXT DEFAULT ''
            );
        """)
        
        # Automatic column migrations for existing databases
        for col, col_def in [
            ("shelf_location", "TEXT DEFAULT 'Warehouse A - Rack 03 - Shelf B-02'"),
            ("materials", "TEXT DEFAULT 'Full Grain Leather / Anti-Slip Rubber'"),
            ("season", "TEXT DEFAULT 'Collection 2026'"),
            ("production_status", "TEXT DEFAULT 'Sample Archive'")
        ]:
            try:
                cursor.execute(f"ALTER TABLE designs ADD COLUMN {col} {col_def};")
            except sqlite3.OperationalError:
                pass

        try:
            cursor.execute("ALTER TABLE query_logs ADD COLUMN detected_category TEXT DEFAULT 'shoe';")
        except sqlite3.OperationalError:
            pass
        
        # 2. Reference Images Table (links each angle photo to a FAISS vector ID)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reference_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                design_id TEXT NOT NULL,
                image_path TEXT NOT NULL,
                angle TEXT DEFAULT 'side',
                faiss_id INTEGER UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (design_id) REFERENCES designs(design_id) ON DELETE CASCADE
            );
        """)
        
        # 3. Query Audit Logs Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS query_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_image_path TEXT NOT NULL,
                top_match_id TEXT,
                top_match_name TEXT,
                confidence_pct REAL,
                latency_ms REAL,
                results_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
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
            WHERE r.faiss_id = ?;
        """, (faiss_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


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
    detected_category: str = "shoe"
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
                detected_category
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (
            query_image_path,
            top_match_id,
            top_match_name,
            round(confidence_pct, 2),
            round(latency_ms, 2),
            json.dumps(results),
            detected_category
        ))
        conn.commit()
        return cursor.lastrowid


def get_query_logs(limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch recent query logs."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM query_logs
            ORDER BY id DESC
            LIMIT ?;
        """, (limit,))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if "detected_category" not in d or not d["detected_category"]:
                d["detected_category"] = "shoe"
            try:
                d["results"] = json.loads(d.get("results_json", "[]"))
            except Exception:
                d["results"] = []
            result.append(d)
        return result


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
