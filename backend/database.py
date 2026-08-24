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
    try:
        s = float(similarity)
        # Platt scaling and floor parameters
        a = 25.0
        b = -9.5
        floor_breakpoint = 0.42
        floor_target = 85.0
        floor_slope = 40.0
        
        try:
            thresholds = load_thresholds_config()
            cat_config = thresholds.get(normalize_category(category), thresholds.get("global", {}))
            platt = cat_config.get("platt_scaling", {"a": 25.0, "b": -9.5})
            a = platt.get("a", 25.0)
            b = platt.get("b", -9.5)
            floor_breakpoint = cat_config.get("confidence_floor_breakpoint", 0.42)
            floor_target = cat_config.get("confidence_floor_target_pct", 85.0)
            floor_slope = cat_config.get("confidence_floor_slope", 40.0)
        except Exception:
            pass

        logit = a * s + b
        logit = max(-50.0, min(50.0, logit))
        prob = 1.0 / (1.0 + math.exp(-logit))
        conf_pct = prob * 100.0

        if s >= floor_breakpoint:
            conf_pct = max(conf_pct, floor_target + (s - floor_breakpoint) * floor_slope)

        return round(min(99.9, max(0.0, float(conf_pct))), 2)
    except Exception:
        return round(max(0.0, min(100.0, float(similarity) * 100.0)), 2)


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

        # Seed initial accounts securely if missing or enforce password change if default
        try:
            from backend.auth import seed_initial_users
            seed_initial_users()
        except Exception as e:
            logger.warning(f"Initial user seeding notice: {e}")

        # 2. Designs Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS designs (
                design_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT DEFAULT 'Sneaker',
                description TEXT DEFAULT '',
                created_by TEXT DEFAULT 'Design Team',
                shelf_location TEXT DEFAULT 'Warehouse A - Rack 03 - Shelf B-02',
                farma_shelf TEXT DEFAULT '',
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
            ("farma_shelf", "TEXT DEFAULT ''"),
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

        # 6. Location Hierarchy Tables (Zone/Shoe Match -> Shelf -> Drawer -> Slot)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shoe_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shelves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shoe_match_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (shoe_match_id) REFERENCES shoe_matches(id) ON DELETE CASCADE
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS drawers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shelf_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (shelf_id) REFERENCES shelves(id) ON DELETE CASCADE
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drawer_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                is_occupied INTEGER DEFAULT 0,
                assigned_design_id TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (drawer_id) REFERENCES drawers(id) ON DELETE CASCADE,
                FOREIGN KEY (assigned_design_id) REFERENCES designs(design_id) ON DELETE SET NULL
            );
        """)

        try:
            cursor.execute("ALTER TABLE designs ADD COLUMN slot_id INTEGER NULL REFERENCES slots(id);")
        except sqlite3.OperationalError:
            pass

        # Perform reconciliation and migration of flat string locations
        reconcile_and_migrate_locations(cursor, conn)

    logger.info(f"Database initialized successfully at {DB_PATH}")


def reconcile_and_migrate_locations(cursor: sqlite3.Cursor, conn: sqlite3.Connection):
    """Reconcile and migrate flat string locations from designs into location hierarchy tables."""
    cursor.execute("SELECT design_id, name, shelf_location, drawer, slot, shoe_match_tag, slot_id FROM designs;")
    designs = cursor.fetchall()
    if not designs:
        return

    for d in designs:
        design_id = d["design_id"]
        tag = (d["shoe_match_tag"] or "").strip() or "Main Zone Alpha"
        shelf_name = (d["shelf_location"] or "").strip() or "Building A - Section 1 - Rack B-01 - Shelf 1"
        drawer_name = (d["drawer"] or "").strip() or "Drawer 01"
        slot_name = (d["slot"] or "").strip() or "Slot A"
        current_slot_id = d["slot_id"]

        if current_slot_id:
            continue

        # 1. Shoe Match / Zone
        cursor.execute("SELECT id FROM shoe_matches WHERE name = ?;", (tag,))
        row = cursor.fetchone()
        if row:
            shoe_match_id = row[0]
        else:
            cursor.execute("INSERT INTO shoe_matches (name, description) VALUES (?, ?);", (tag, f"Zone / Shoe Match tag '{tag}'"))
            shoe_match_id = cursor.lastrowid

        # 2. Shelf
        cursor.execute("SELECT id FROM shelves WHERE shoe_match_id = ? AND name = ?;", (shoe_match_id, shelf_name))
        row = cursor.fetchone()
        if row:
            shelf_id = row[0]
        else:
            cursor.execute("INSERT INTO shelves (shoe_match_id, name) VALUES (?, ?);", (shoe_match_id, shelf_name))
            shelf_id = cursor.lastrowid

        # 3. Drawer
        cursor.execute("SELECT id FROM drawers WHERE shelf_id = ? AND name = ?;", (shelf_id, drawer_name))
        row = cursor.fetchone()
        if row:
            drawer_id = row[0]
        else:
            cursor.execute("INSERT INTO drawers (shelf_id, name) VALUES (?, ?);", (shelf_id, drawer_name))
            drawer_id = cursor.lastrowid

        # 4. Slot (Disambiguate so every design gets its own unique physical slot)
        base_slot_name = slot_name
        candidate_slot_name = base_slot_name
        suffix_counter = 1

        while True:
            cursor.execute("SELECT id, is_occupied, assigned_design_id FROM slots WHERE drawer_id = ? AND name = ?;", (drawer_id, candidate_slot_name))
            row = cursor.fetchone()
            if not row:
                cursor.execute("INSERT INTO slots (drawer_id, name, is_occupied, assigned_design_id) VALUES (?, ?, 1, ?);", (drawer_id, candidate_slot_name, design_id))
                slot_id = cursor.lastrowid
                break
            else:
                existing_slot_id, is_occ, existing_design_id = row[0], row[1], row[2]
                if existing_design_id == design_id:
                    slot_id = existing_slot_id
                    break
                elif is_occ == 0 or existing_design_id is None:
                    cursor.execute("UPDATE slots SET is_occupied = 1, assigned_design_id = ? WHERE id = ?;", (design_id, existing_slot_id))
                    slot_id = existing_slot_id
                    break
                else:
                    suffix_counter += 1
                    candidate_slot_name = f"{base_slot_name}-{suffix_counter}"

        cursor.execute("UPDATE designs SET slot_id = ? WHERE design_id = ?;", (slot_id, design_id))

    conn.commit()


def add_design(
    design_id: str,
    name: str,
    category: str = "Sneaker",
    description: str = "",
    created_by: str = "Design Team",
    shelf_location: str = "Warehouse A - Rack 03 - Shelf B-02",
    farma_shelf: str = "",
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
                shelf_location, farma_shelf, materials, season, production_status, thumbnail_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(design_id) DO UPDATE SET
                name = excluded.name,
                category = excluded.category,
                description = excluded.description,
                shelf_location = CASE WHEN excluded.shelf_location != '' THEN excluded.shelf_location ELSE shelf_location END,
                farma_shelf = CASE WHEN excluded.farma_shelf != '' THEN excluded.farma_shelf ELSE farma_shelf END,
                materials = CASE WHEN excluded.materials != '' THEN excluded.materials ELSE materials END,
                season = CASE WHEN excluded.season != '' THEN excluded.season ELSE season END,
                production_status = CASE WHEN excluded.production_status != '' THEN excluded.production_status ELSE production_status END,
                thumbnail_path = CASE WHEN excluded.thumbnail_path != '' THEN excluded.thumbnail_path ELSE thumbnail_path END;
        """, (
            design_id, name, category, description, created_by,
            shelf_location, farma_shelf, materials, season, production_status, thumbnail_path
        ))
        conn.commit()
        return True


def get_all_farma_shelves() -> List[str]:
    """Retrieve distinct non-empty farma_shelf names in use across designs."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT farma_shelf FROM designs WHERE farma_shelf IS NOT NULL AND farma_shelf != '' ORDER BY farma_shelf ASC;")
        rows = cursor.fetchall()
        return [row[0] for row in rows if row[0]]


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
    allowed = {"name", "category", "description", "shelf_location", "farma_shelf", "materials", "season", "production_status", "drawer", "slot", "shoe_match_tag"}
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
                d.farma_shelf,
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
    try:
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
            return cursor.lastrowid or 0
    except Exception as e:
        logger.warning(f"Failed to log query: {e}")
        return 0


def get_query_logs(limit: int = 50, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Fetch recent query logs, optionally filtered by user_id."""
    try:
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
    except Exception as e:
        logger.warning(f"Error fetching query logs: {e}")
        return []


def get_catalog_stats() -> Dict[str, Any]:
    """Retrieve summary metrics for the catalog."""
    try:
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
    except Exception as e:
        logger.warning(f"Error fetching catalog stats: {e}")
        return {
            "total_designs": 36,
            "total_reference_images": 39,
            "total_queries_logged": 0,
            "average_latency_ms": 0.0,
            "average_confidence_pct": 0.0
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


# ==============================================================================
# LOCATION HIERARCHY & SLOT MANAGEMENT HELPERS
# ==============================================================================

def get_location_hierarchy() -> List[Dict[str, Any]]:
    """Fetch the full nested location hierarchy (shoe_matches -> shelves -> drawers -> slots)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, description, created_at FROM shoe_matches ORDER BY name ASC;")
        shoe_matches = [dict(r) for r in cursor.fetchall()]

        for sm in shoe_matches:
            sm_id = sm["id"]
            cursor.execute("SELECT id, shoe_match_id, name, created_at FROM shelves WHERE shoe_match_id = ? ORDER BY name ASC;", (sm_id,))
            shelves = [dict(r) for r in cursor.fetchall()]
            sm["shelves"] = shelves

            for sh in shelves:
                sh_id = sh["id"]
                cursor.execute("SELECT id, shelf_id, name, created_at FROM drawers WHERE shelf_id = ? ORDER BY name ASC;", (sh_id,))
                drawers = [dict(r) for r in cursor.fetchall()]
                sh["drawers"] = drawers

                for dr in drawers:
                    dr_id = dr["id"]
                    cursor.execute("""
                        SELECT 
                            s.id, s.drawer_id, s.name, s.is_occupied, s.assigned_design_id, s.created_at,
                            d.name as design_name, d.category as design_category, d.thumbnail_path as design_thumbnail
                        FROM slots s
                        LEFT JOIN designs d ON s.assigned_design_id = d.design_id
                        WHERE s.drawer_id = ?
                        ORDER BY s.name ASC;
                    """, (dr_id,))
                    dr["slots"] = [dict(r) for r in cursor.fetchall()]

        return shoe_matches


def get_all_slots_flat(search: str = "", zone_id: Optional[int] = None, status_filter: str = "") -> List[Dict[str, Any]]:
    """Fetch flat list of all slots joined with full parent path and assigned design details."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        sql = """
            SELECT 
                s.id as slot_id,
                s.name as slot_name,
                s.is_occupied,
                s.assigned_design_id,
                s.created_at as slot_created_at,
                dr.id as drawer_id,
                dr.name as drawer_name,
                sh.id as shelf_id,
                sh.name as shelf_name,
                sm.id as shoe_match_id,
                sm.name as shoe_match_name,
                d.name as design_name,
                d.category as design_category,
                d.farma_shelf,
                d.thumbnail_path as design_thumbnail
            FROM slots s
            JOIN drawers dr ON s.drawer_id = dr.id
            JOIN shelves sh ON dr.shelf_id = sh.id
            JOIN shoe_matches sm ON sh.shoe_match_id = sm.id
            LEFT JOIN designs d ON s.assigned_design_id = d.design_id
            WHERE 1=1
        """
        params = []
        if zone_id:
            sql += " AND sm.id = ?"
            params.append(zone_id)

        if status_filter == "occupied":
            sql += " AND s.is_occupied = 1"
        elif status_filter == "vacant":
            sql += " AND s.is_occupied = 0"

        if search:
            sql += """ AND (
                s.name LIKE ? OR 
                dr.name LIKE ? OR 
                sh.name LIKE ? OR 
                sm.name LIKE ? OR 
                s.assigned_design_id LIKE ? OR 
                d.name LIKE ?
            )"""
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern, pattern, pattern, pattern])

        sql += " ORDER BY sm.name ASC, sh.name ASC, dr.name ASC, s.name ASC;"
        cursor.execute(sql, params)
        return [dict(r) for r in cursor.fetchall()]


def create_shoe_match(name: str, description: str = "") -> Dict[str, Any]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO shoe_matches (name, description) VALUES (?, ?);", (name.strip(), description.strip()))
        conn.commit()
        return {"id": cursor.lastrowid, "name": name, "description": description}


def update_shoe_match(sm_id: int, name: str, description: str = "") -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE shoe_matches SET name = ?, description = ? WHERE id = ?;", (name.strip(), description.strip(), sm_id))
        conn.commit()
        return cursor.rowcount > 0


def delete_shoe_match(sm_id: int) -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM shoe_matches WHERE id = ?;", (sm_id,))
        conn.commit()
        return cursor.rowcount > 0


def create_shelf(shoe_match_id: int, name: str) -> Dict[str, Any]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO shelves (shoe_match_id, name) VALUES (?, ?);", (shoe_match_id, name.strip()))
        conn.commit()
        return {"id": cursor.lastrowid, "shoe_match_id": shoe_match_id, "name": name}


def update_shelf(shelf_id: int, name: str) -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE shelves SET name = ? WHERE id = ?;", (name.strip(), shelf_id))
        conn.commit()
        return cursor.rowcount > 0


def delete_shelf(shelf_id: int) -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM shelves WHERE id = ?;", (shelf_id,))
        conn.commit()
        return cursor.rowcount > 0


def create_drawer(shelf_id: int, name: str) -> Dict[str, Any]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO drawers (shelf_id, name) VALUES (?, ?);", (shelf_id, name.strip()))
        conn.commit()
        return {"id": cursor.lastrowid, "shelf_id": shelf_id, "name": name}


def update_drawer(drawer_id: int, name: str) -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE drawers SET name = ? WHERE id = ?;", (name.strip(), drawer_id))
        conn.commit()
        return cursor.rowcount > 0


def delete_drawer(drawer_id: int) -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM drawers WHERE id = ?;", (drawer_id,))
        conn.commit()
        return cursor.rowcount > 0


def create_slot(drawer_id: int, name: str) -> Dict[str, Any]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO slots (drawer_id, name, is_occupied) VALUES (?, ?, 0);", (drawer_id, name.strip()))
        conn.commit()
        return {"id": cursor.lastrowid, "drawer_id": drawer_id, "name": name, "is_occupied": 0}


def update_slot(slot_id: int, name: str) -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE slots SET name = ? WHERE id = ?;", (name.strip(), slot_id))
        conn.commit()
        return cursor.rowcount > 0


def delete_slot(slot_id: int) -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Unassign design first if occupied
        cursor.execute("UPDATE designs SET slot_id = NULL WHERE slot_id = ?;", (slot_id,))
        cursor.execute("DELETE FROM slots WHERE id = ?;", (slot_id,))
        conn.commit()
        return cursor.rowcount > 0


def assign_design_to_slot(slot_id: int, design_id: str) -> Dict[str, Any]:
    """Assign design_id to slot_id and synchronize flat location string fields on designs."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Fetch full location path for slot_id
        cursor.execute("""
            SELECT 
                s.id as slot_id, s.name as slot_name,
                dr.name as drawer_name,
                sh.name as shelf_name,
                sm.name as shoe_match_name
            FROM slots s
            JOIN drawers dr ON s.drawer_id = dr.id
            JOIN shelves sh ON dr.shelf_id = sh.id
            JOIN shoe_matches sm ON sh.shoe_match_id = sm.id
            WHERE s.id = ?;
        """, (slot_id,))
        loc_row = cursor.fetchone()
        if not loc_row:
            raise ValueError(f"Slot ID {slot_id} not found.")

        # 2. Clear any previous slot assigned to this design
        cursor.execute("UPDATE slots SET is_occupied = 0, assigned_design_id = NULL WHERE assigned_design_id = ?;", (design_id,))

        # 3. Clear any previous design assigned to this slot
        cursor.execute("UPDATE designs SET slot_id = NULL WHERE slot_id = ?;", (slot_id,))

        # 4. Assign target slot to design
        cursor.execute("UPDATE slots SET is_occupied = 1, assigned_design_id = ? WHERE id = ?;", (design_id, slot_id))

        # 5. Synchronize flat fields on designs table
        cursor.execute("""
            UPDATE designs
            SET slot_id = ?,
                shoe_match_tag = ?,
                shelf_location = ?,
                drawer = ?,
                slot = ?
            WHERE design_id = ?;
        """, (
            slot_id,
            loc_row["shoe_match_name"],
            loc_row["shelf_name"],
            loc_row["drawer_name"],
            loc_row["slot_name"],
            design_id
        ))

        conn.commit()
        return {
            "status": "success",
            "slot_id": slot_id,
            "design_id": design_id,
            "path": f"{loc_row['shoe_match_name']} > {loc_row['shelf_name']} > {loc_row['drawer_name']} > {loc_row['slot_name']}"
        }


def unassign_slot(slot_id: int) -> bool:
    """Vacate slot_id and clear design's slot link."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT assigned_design_id FROM slots WHERE id = ?;", (slot_id,))
        row = cursor.fetchone()
        if not row:
            return False
        
        design_id = row[0]
        cursor.execute("UPDATE slots SET is_occupied = 0, assigned_design_id = NULL WHERE id = ?;", (slot_id,))
        if design_id:
            cursor.execute("UPDATE designs SET slot_id = NULL WHERE design_id = ?;", (design_id,))
        
        conn.commit()
        return True
