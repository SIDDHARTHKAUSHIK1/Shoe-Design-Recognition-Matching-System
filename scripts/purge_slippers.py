import shutil
import logging
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend import database as db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def purge_slippers():
    logger.info("=== Purging all Slipper designs from DB and disk ===")
    db.init_db()

    with db.get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT design_id, name, category 
            FROM designs 
            WHERE design_id LIKE 'SLIP-%' OR category LIKE '%Slipper%' OR category LIKE '%Slide%' OR category LIKE '%Flip-Flop%';
        """)
        slippers = cursor.fetchall()
        logger.info(f"Found {len(slippers)} slipper designs to purge from DB.")
        for s in slippers:
            did = s['design_id']
            logger.info(f"  - Purging DB records for: {did} | {s['name']} ({s['category']})")
            cursor.execute("DELETE FROM reference_images WHERE design_id = ?;", (did,))
            cursor.execute("DELETE FROM designs WHERE design_id = ?;", (did,))
        conn.commit()

    # Delete physical folders
    for root in [BASE_DIR / 'data' / 'catalog', BASE_DIR / 'storage' / 'catalog_images']:
        if root.exists():
            for d in root.glob('SLIP-*'):
                logger.info(f"  - Removing directory: {d}")
                shutil.rmtree(d, ignore_errors=True)

    stats = db.get_catalog_stats()
    logger.info(f"Remaining Shoe Catalog Stats: {stats}")

if __name__ == "__main__":
    purge_slippers()
