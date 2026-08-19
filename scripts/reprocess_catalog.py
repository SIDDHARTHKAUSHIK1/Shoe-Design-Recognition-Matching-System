"""
Reprocess Catalog Reference Images with Background Segmentation and Neutral Studio Fill.

Iterates over every catalog reference photo, applies high-fidelity foreground segmentation,
composites the isolated footwear onto a neutral studio fill (248, 248, 248),
re-computes background-invariant DINOv2 embeddings with TTA, and rebuilds the FAISS vector index.

Usage:
    python scripts/reprocess_catalog.py
"""
import os
import sys
import time
import logging
from pathlib import Path
from PIL import Image
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend import database as db
from backend.config import STORAGE_DIR, CATALOG_IMAGES_DIR, EMBEDDING_DIM
from backend.foreground import isolate_foreground
from backend.engine import EmbeddingEngine
from backend.vector_store import VectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SEGMENTED_CATALOG_DIR = STORAGE_DIR / "catalog_segmented"
SEGMENTED_CATALOG_DIR.mkdir(parents=True, exist_ok=True)


def reprocess_catalog():
    t0 = time.time()
    logger.info("=== Starting Catalog Background Neutralization & Re-Indexing ===")

    db.init_db()
    all_refs = db.get_all_reference_images()
    if not all_refs:
        logger.warning("No reference images found in catalog database.")
        return

    logger.info(f"Found {len(all_refs)} catalog reference images to reprocess.")

    engine = EmbeddingEngine.get_instance()
    vs = VectorStore.get_instance()
    vs.reset()

    processed_images = []
    processed_metadata = []
    embeddings_list = []

    for idx, ref in enumerate(all_refs, start=1):
        design_id = ref["design_id"]
        rel_img_path = ref["image_path"]
        
        # Resolve source image file
        src_path = Path(rel_img_path)
        if not src_path.is_absolute():
            src_path = BASE_DIR / rel_img_path

        if not src_path.exists():
            # Fallback check under catalog_images
            src_path = CATALOG_IMAGES_DIR / design_id / Path(rel_img_path).name

        if not src_path.exists():
            logger.warning(f"[{idx}/{len(all_refs)}] Image file not found: {src_path}")
            continue

        try:
            raw_img = Image.open(src_path).convert("RGB")
            # Apply foreground isolation with neutral background fill (248, 248, 248)
            neutral_crop, reason, meta = isolate_foreground(raw_img, padding_ratio=0.08)

            # Save segmented reference image
            dest_folder = SEGMENTED_CATALOG_DIR / design_id
            dest_folder.mkdir(parents=True, exist_ok=True)
            dest_path = dest_folder / src_path.name
            neutral_crop.save(dest_path, quality=95)

            # Compute normalized embedding with TTA
            emb = engine._compute_embedding(neutral_crop, use_tta=True)
            embeddings_list.append(emb)
            processed_metadata.append(ref)
            processed_images.append(dest_path)

            if idx % 10 == 0 or idx == len(all_refs):
                logger.info(f"[{idx}/{len(all_refs)}] Processed {design_id} - {ref.get('design_name', '')} (coverage: {meta.get('coverage', 0):.2f})")

        except Exception as e:
            logger.error(f"Error processing image {src_path}: {e}")

    if not embeddings_list:
        logger.error("No valid embeddings were generated.")
        return

    embs_arr = np.vstack(embeddings_list).astype(np.float32)
    logger.info(f"Adding {len(embs_arr)} re-segmented vectors to FAISS index...")
    assigned_faiss_ids = vs.add_vectors(embs_arr)

    # Synchronize FAISS IDs in SQLite reference_images table
    with db.get_db_connection() as conn:
        for ref_meta, new_fid in zip(processed_metadata, assigned_faiss_ids):
            conn.execute(
                "UPDATE reference_images SET faiss_id = ? WHERE id = ?;",
                (new_fid, ref_meta["id"])
            )
        conn.commit()

    total_time = time.time() - t0
    logger.info(f"=== Successfully Reprocessed Catalog in {total_time:.2f}s ===")
    logger.info(f"Total Vectors in FAISS: {vs.total_vectors}")
    logger.info(f"Segmented images saved to: {SEGMENTED_CATALOG_DIR}")

    # Re-run threshold calibration
    try:
        from scripts.calibrate_thresholds import run_calibration
        logger.info("Re-calibrating category thresholds with neutral-filled catalog...")
        run_calibration()
    except Exception as e:
        logger.warning(f"Could not automatically run threshold calibration: {e}")

    print("\nCatalog Reprocessing Summary:")
    print(f"Total Images Reprocessed: {len(embeddings_list)}")
    print(f"FAISS Total Vectors: {vs.total_vectors}")
    print(f"Elapsed Time: {total_time:.2f}s")


if __name__ == "__main__":
    reprocess_catalog()
