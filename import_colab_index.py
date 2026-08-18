"""
Colab Index & Metadata Importer for Shoe Design Matching System.
Imports `index.faiss` and `metadata.json` generated from Google Colab notebook into the project.
"""
import os
import json
import shutil
import logging
from pathlib import Path
import faiss

from backend.config import BASE_DIR, STORAGE_DIR, CATALOG_IMAGES_DIR, DB_PATH, FAISS_INDEX_PATH
from backend import database as db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def find_file(filename: str, search_dirs: list) -> Path:
    """Find a file in given directories."""
    for d in search_dirs:
        p = Path(d) / filename
        if p.exists():
            return p
    return None


def import_colab_artifacts(
    index_file_path: str = None,
    metadata_file_path: str = None,
    dataset_dir_path: str = None
):
    """
    Import external index.faiss and metadata.json from Google Colab.
    """
    search_dirs = [
        STORAGE_DIR,
        BASE_DIR,
        BASE_DIR / "dataset",
        Path.home() / "Downloads"
    ]

    # 1. Locate index.faiss
    if index_file_path:
        faiss_src = Path(index_file_path)
    else:
        faiss_src = find_file("index.faiss", search_dirs) or find_file("shoe_index.faiss", search_dirs)

    # 2. Locate metadata.json
    if metadata_file_path:
        meta_src = Path(metadata_file_path)
    else:
        meta_src = find_file("metadata.json", search_dirs)

    if not faiss_src or not faiss_src.exists():
        logger.error("Could not find 'index.faiss'. Please place 'index.faiss' in the 'storage/' folder or project root.")
        return False

    if not meta_src or not meta_src.exists():
        logger.error("Could not find 'metadata.json'. Please place 'metadata.json' in the 'storage/' folder or project root.")
        return False

    logger.info(f"Found FAISS index at: {faiss_src}")
    logger.info(f"Found metadata at: {meta_src}")

    # Inspect FAISS index
    index = faiss.read_index(str(faiss_src))
    vector_dim = index.d
    total_vectors = index.ntotal
    logger.info(f"FAISS Index Info: {total_vectors} vectors, Dimension: {vector_dim}")

    # Copy index to storage/shoe_index.faiss
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    dest_faiss = STORAGE_DIR / "shoe_index.faiss"
    if faiss_src.resolve() != dest_faiss.resolve():
        shutil.copy2(faiss_src, dest_faiss)
        logger.info(f"Copied {faiss_src.name} -> {dest_faiss}")

    # Copy metadata.json to storage/metadata.json
    dest_meta = STORAGE_DIR / "metadata.json"
    if meta_src.resolve() != dest_meta.resolve():
        shutil.copy2(meta_src, dest_meta)
        logger.info(f"Copied {meta_src.name} -> {dest_meta}")

    # Read metadata JSON
    with open(dest_meta, "r", encoding="utf-8") as f:
        metadata_list = json.load(f)

    logger.info(f"Loaded {len(metadata_list)} records from metadata.json")

    # Reset SQLite database and populate with imported catalog
    db.init_db()
    
    # Check dataset folder for actual source images
    dataset_dir = Path(dataset_dir_path) if dataset_dir_path else (BASE_DIR / "dataset")
    
    designs_created = set()
    
    with db.get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Clear existing tables for fresh import
        cursor.execute("DELETE FROM reference_images;")
        cursor.execute("DELETE FROM designs;")
        conn.commit()

        for faiss_id, item in enumerate(metadata_list):
            # Parse Colab metadata format: {'design_name': ..., 'source_image': ...}
            # or {'design_id': ..., 'name': ..., 'image_path': ...}
            design_name = item.get("design_name") or item.get("name") or f"Design_{faiss_id+1:03d}"
            source_img = item.get("source_image") or item.get("image_path") or item.get("filename") or ""
            design_id = item.get("design_id") or design_name.replace(" ", "_").upper()
            angle = item.get("angle", "side")
            category = item.get("category", "Sneaker")

            # Format clean design name
            clean_name = design_name.replace("_", " ").title()

            # Ensure design directory exists in storage
            design_storage_dir = CATALOG_IMAGES_DIR / design_id
            design_storage_dir.mkdir(parents=True, exist_ok=True)

            # Locate and copy source image if available
            rel_image_path = f"/catalog_images/{design_id}/photo_{faiss_id+1}.jpg"
            dest_img_path = design_storage_dir / f"photo_{faiss_id+1}.jpg"

            # Search for source image across dataset and storage
            found_img = False
            if source_img:
                possible_paths = [
                    dataset_dir / source_img,
                    dataset_dir / design_name / source_img,
                    dataset_dir / Path(source_img).name,
                    STORAGE_DIR / "catalog_images" / source_img,
                    Path(source_img)
                ]
                for p in possible_paths:
                    if p.exists() and p.is_file():
                        shutil.copy2(p, dest_img_path)
                        found_img = True
                        break
                        
            if not found_img:
                # Search all existing images in storage/catalog_images
                all_existing = sorted(list(STORAGE_DIR.glob("catalog_images/*/*.jpg")) + list(STORAGE_DIR.glob("catalog_images/*/*.jpeg")))
                if faiss_id < len(all_existing):
                    shutil.copy2(all_existing[faiss_id], dest_img_path)
                    found_img = True

            if not found_img and not dest_img_path.exists():
                # Create a placeholder if image file is missing
                rel_image_path = "/static/placeholder.jpg"

            # Insert Design if not already created
            if design_id not in designs_created:
                cursor.execute("""
                    INSERT INTO designs (design_id, name, category, description, created_by, thumbnail_path)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(design_id) DO UPDATE SET
                        thumbnail_path = CASE WHEN thumbnail_path = '' THEN excluded.thumbnail_path ELSE thumbnail_path END;
                """, (
                    design_id,
                    clean_name,
                    category,
                    f"Imported from Colab training catalog ({clean_name}).",
                    "Colab Training",
                    rel_image_path
                ))
                designs_created.add(design_id)

            # Insert Reference Image
            cursor.execute("""
                INSERT INTO reference_images (design_id, image_path, angle, faiss_id)
                VALUES (?, ?, ?, ?);
            """, (design_id, rel_image_path, angle, faiss_id))

        conn.commit()

    # Update model configuration if dimension is 512 (CLIP ViT-B/32)
    if vector_dim == 512:
        logger.info("Detected 512-dimension vectors from Colab (CLIP ViT-B/32). Updating model configuration...")
        update_model_config(model_name="sentence-transformers/clip-ViT-B-32", dim=512)
    elif vector_dim == 384:
        logger.info("Detected 384-dimension vectors from Colab (DINOv2-small).")
        update_model_config(model_name="facebook/dinov2-small", dim=384)

    stats = db.get_catalog_stats()
    logger.info("=" * 60)
    logger.info("   COLAB INDEX & METADATA IMPORT SUCCESSFUL!   ")
    logger.info("=" * 60)
    logger.info(f"Total Unique Designs Imported : {stats['total_designs']}")
    logger.info(f"Total Vectors in FAISS Index  : {stats['total_reference_images']}")
    logger.info(f"Vector Dimension              : {vector_dim}")
    logger.info(f"Index File Location           : {dest_faiss}")
    logger.info(f"Database File Location        : {DB_PATH}")
    logger.info("=" * 60)
    return True


def update_model_config(model_name: str, dim: int):
    """Update backend/config.py to match the imported index model and dimension."""
    config_path = BASE_DIR / "backend" / "config.py"
    if not config_path.exists():
        return

    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    import re
    content = re.sub(
        r'MODEL_NAME\s*=\s*os\.getenv\("EMBEDDING_MODEL",\s*"[^"]+"\)',
        f'MODEL_NAME = os.getenv("EMBEDDING_MODEL", "{model_name}")',
        content
    )
    content = re.sub(
        r'EMBEDDING_DIM\s*=\s*\d+',
        f'EMBEDDING_DIM = {dim}',
        content
    )

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"Updated backend/config.py with MODEL_NAME='{model_name}' and EMBEDDING_DIM={dim}")


if __name__ == "__main__":
    import sys
    idx_p = sys.argv[1] if len(sys.argv) > 1 else None
    meta_p = sys.argv[2] if len(sys.argv) > 2 else None
    import_colab_artifacts(idx_p, meta_p)
