"""
One-time backfill: compute and store color_histogram + dominant_colors for any
existing catalog reference image that doesn't have them yet.

WHY THIS SCRIPT EXISTS
-----------------------
backend/matcher.py blends cosine similarity (75%) with a color-histogram
similarity (25%) when ranking matches -- see WEIGHT_DESIGN / WEIGHT_COLOR in
backend/config.py. That color similarity is only meaningful if BOTH the query
photo and the catalog reference image have a color_histogram computed the
same way. Until this fix, backend/ingestion.py never called
backend.database.update_reference_image_color(), so newly-added reference
images ended up with an empty color_histogram -- matcher.py then falls back
to a flat color_sim = 1.0 for those rows, which makes color-aware scoring a
no-op for them. ingestion.py has been fixed to populate color data going
forward; this script catches up any rows that were added before the fix.

Safe to re-run -- it only touches rows where color_histogram is empty, and
recomputes deterministically from the stored image file.

USAGE
-----
    python scripts/backfill_reference_colors.py --dry-run
    python scripts/backfill_reference_colors.py
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import BASE_DIR, STORAGE_DIR
from backend import database as db
from backend.engine import EmbeddingEngine
from backend.color_extractor import ColorExtractor

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def resolve_image_path(image_path: str, design_id: str) -> Path:
    """Mirror the path resolution already used in evaluate.py."""
    rel_path = image_path.lstrip("/")
    full_path = BASE_DIR / "storage" / rel_path
    if not full_path.exists():
        full_path = STORAGE_DIR / "catalog_images" / design_id / Path(image_path).name
    return full_path


def rows_missing_color():
    with db.get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, design_id, image_path, faiss_id
            FROM reference_images
            WHERE color_histogram IS NULL OR color_histogram = ''
            ORDER BY id ASC;
        """)
        return [dict(r) for r in cursor.fetchall()]


def main(dry_run: bool = False):
    db.init_db()
    rows = rows_missing_color()

    print("=" * 70)
    print(f"Reference images with no color data: {len(rows)}")
    print("=" * 70)

    if not rows:
        print("Nothing to do -- every reference image already has color data.")
        return

    if dry_run:
        for r in rows:
            print(f"  would backfill: {r['design_id']} / {r['image_path']} (faiss_id={r['faiss_id']})")
        return

    engine = EmbeddingEngine.get_instance()

    updated, failed = 0, 0
    for i, r in enumerate(rows, start=1):
        full_path = resolve_image_path(r["image_path"], r["design_id"])
        if not full_path.exists():
            logger.warning(f"[{i}/{len(rows)}] Image file missing on disk, skipping: {full_path}")
            failed += 1
            continue
        try:
            preprocessed = engine.preprocess_image(full_path)
            isolated, _, _ = engine.isolate_image_foreground(preprocessed)
            color_hist = ColorExtractor.extract_hsv_histogram(isolated)
            dominant_colors = ColorExtractor.extract_dominant_colors(isolated)
            db.update_reference_image_color(
                faiss_id=r["faiss_id"],
                color_histogram=color_hist.tolist(),
                dominant_colors=dominant_colors,
            )
            updated += 1
            print(f"[{i}/{len(rows)}] Updated {r['design_id']} / {Path(r['image_path']).name}")
        except Exception as e:
            failed += 1
            logger.error(f"[{i}/{len(rows)}] Failed on {full_path}: {e}")

    print("=" * 70)
    print(f"Done. Updated: {updated}  Failed: {failed}  Total: {len(rows)}")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="List rows that would be updated without writing anything.")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
