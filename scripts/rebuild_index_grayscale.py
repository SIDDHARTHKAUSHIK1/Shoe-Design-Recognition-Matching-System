"""
Rebuild FAISS index by re-embedding all catalog reference photos through the grayscale-aware EmbeddingEngine.
Updates reference_images.faiss_id in SQLite to match contiguous IDs.
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
from backend.config import CATALOG_IMAGES_DIR, assert_catalog_image_path, STORAGE_DIR
from backend.engine import EmbeddingEngine
from backend.vector_store import VectorStore

def rebuild_index_grayscale():
    logger.info("=== Rebuilding FAISS Index — Grayscale Embeddings ===")
    db.init_db()

    all_refs = db.get_all_reference_images()
    logger.info(f"Total reference images to re-embed: {len(all_refs)}")

    engine = EmbeddingEngine.get_instance()
    vs = VectorStore.get_instance()
    vs.reset()

    processed_refs = []
    embeddings_list = []

    for ref in all_refs:
        design_id = ref["design_id"]
        rel_path = ref["image_path"]

        img_path = Path(rel_path) if Path(rel_path).is_absolute() else BASE_DIR / rel_path.lstrip("/")
        if not img_path.exists():
            img_path = CATALOG_IMAGES_DIR / design_id / Path(rel_path).name
        if not img_path.exists():
            img_path = STORAGE_DIR / rel_path.lstrip("/")

        if not img_path.exists():
            logger.warning(f"  SKIP — image not found: {img_path}")
            continue

        assert_catalog_image_path(img_path)

        try:
            img = engine.preprocess_image(img_path)
            iso, _, _ = engine.isolate_image_foreground(img)
            emb = engine._compute_embedding(iso)
            embeddings_list.append(emb)
            processed_refs.append(ref)
            logger.info(f"  [OK] {design_id} — {ref.get('image_path', '')} — old_faiss_id={ref.get('faiss_id')}")
        except Exception as e:
            logger.error(f"  [FAIL] Failed to embed {img_path}: {e}")

    if not embeddings_list:
        logger.error("No embeddings generated. Aborting index write.")
        sys.exit(1)

    arr = np.array(embeddings_list, dtype=np.float32)
    assigned_ids = vs.add_vectors(arr)
    vs.save()

    with db.get_db_connection() as conn:
        for ref, new_fid in zip(processed_refs, assigned_ids):
            conn.execute(
                "UPDATE reference_images SET faiss_id = ? WHERE id = ?",
                (int(new_fid), int(ref["id"]))
            )
        conn.commit()

    logger.info(f"=== SUCCESSFULLY REBUILT INDEX: {vs.total_vectors} vectors indexed ===")

if __name__ == "__main__":
    rebuild_index_grayscale()
