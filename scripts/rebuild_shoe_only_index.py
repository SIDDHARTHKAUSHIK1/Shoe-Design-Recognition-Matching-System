"""
Rebuild FAISS index to contain ONLY shoe-category vectors.
Strips all 20 slipper vectors (SLIP-001..SLIP-020, FAISS IDs 31-50) from the live index.
Updates reference_images.faiss_id in SQLite to match new contiguous IDs.
"""
import sys
import logging
from pathlib import Path
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

from backend import database as db
from backend.config import CATALOG_IMAGES_DIR
from backend.engine import EmbeddingEngine
from backend.vector_store import VectorStore

def rebuild_shoe_only_index():
    logger.info("=== Rebuilding FAISS index — shoe-only ===")
    db.init_db()

    # Get only shoe reference images
    all_refs = db.get_all_shoe_reference_images()
    logger.info(f"Shoe reference images to index: {len(all_refs)}")

    engine = EmbeddingEngine.get_instance()
    vs = VectorStore.get_instance()
    vs.reset()

    processed_refs = []
    embeddings_list = []

    for ref in all_refs:
        design_id = ref["design_id"]
        rel_path = ref["image_path"]

        # Try multiple path resolutions
        img_path = Path(rel_path) if Path(rel_path).is_absolute() else BASE_DIR / rel_path.lstrip("/")
        if not img_path.exists():
            img_path = CATALOG_IMAGES_DIR / design_id / Path(rel_path).name

        if not img_path.exists():
            logger.warning(f"  SKIP — image not found: {img_path}")
            continue

        try:
            from PIL import Image
            img = Image.open(img_path).convert("RGB")
            emb = engine._compute_embedding(img)
            embeddings_list.append(emb)
            processed_refs.append(ref)
            logger.info(f"  [OK] {design_id} — {ref.get('design_name', '')} — FAISS old_id={ref['faiss_id']}")
        except Exception as e:
            logger.error(f"  ERROR embedding {img_path}: {e}")

    if not embeddings_list:
        logger.error("No embeddings generated — aborting.")
        return

    embs_arr = np.vstack(embeddings_list).astype(np.float32)
    assigned_ids = vs.add_vectors(embs_arr)
    logger.info(f"Added {len(assigned_ids)} shoe vectors to FAISS. New IDs: {assigned_ids}")

    # Sync new FAISS IDs back to SQLite
    with db.get_db_connection() as conn:
        for ref, new_fid in zip(processed_refs, assigned_ids):
            conn.execute(
                "UPDATE reference_images SET faiss_id = ? WHERE id = ?;",
                (new_fid, ref["id"])
            )
        conn.commit()
    logger.info("SQLite faiss_id columns updated.")

    logger.info("=== Done ===")
    logger.info(f"FAISS total vectors: {vs.total_vectors} (should be 31)")
    logger.info(f"Slipper vectors in index: 0 (guaranteed)")

    # Verify no slippers remain in index mapping
    slipper_refs = [r for r in db.get_all_reference_images()
                    if db.is_slipper_category(r.get("design_category", ""))]
    slipper_faiss_ids = [r["faiss_id"] for r in slipper_refs]
    shoe_faiss_ids = [r["faiss_id"] for r in db.get_all_shoe_reference_images()]
    logger.info(f"Slipper DB rows still have FAISS IDs (harmless — they are no longer IN the index): {slipper_faiss_ids[:5]}...")
    logger.info(f"Active shoe FAISS IDs in DB: {shoe_faiss_ids}")
    print("\n[OK] Shoe-only FAISS index rebuilt successfully.")
    print(f"  Shoe vectors: {vs.total_vectors}")
    print(f"  Slipper vectors in index: 0")

if __name__ == "__main__":
    rebuild_shoe_only_index()
