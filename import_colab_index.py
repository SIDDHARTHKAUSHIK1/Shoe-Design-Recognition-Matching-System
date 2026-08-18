"""
Colab Index & Metadata Importer for Shoe & Slipper Design Matching System.
Automatically unpacks and imports `shoe_matching_colab_export.zip` generated from Google Colab.
"""
import os
import sys
import json
import shutil
import zipfile
import logging
import argparse
from pathlib import Path
import faiss

# Fix Windows UTF-8 stdout
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from backend.config import BASE_DIR, STORAGE_DIR, CATALOG_IMAGES_DIR, DB_PATH, FAISS_INDEX_PATH
from backend import database as db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def find_zip_package(custom_path: str = None) -> Path:
    """Find the exported colab zip file across project and download folders."""
    if custom_path:
        p = Path(custom_path)
        if p.exists():
            return p
        # Check relative to base dir
        if (BASE_DIR / custom_path).exists():
            return BASE_DIR / custom_path

    search_dirs = [
        BASE_DIR,
        STORAGE_DIR,
        Path.home() / "Downloads",
        Path.home() / "Desktop"
    ]

    for d in search_dirs:
        if not d.exists():
            continue
        # Look for matching zip files
        candidates = list(d.glob("*colab_export*.zip")) + list(d.glob("*slipper*export*.zip")) + list(d.glob("*shoe_matching*.zip"))
        if candidates:
            return candidates[0]

    return None


def extract_zip_if_needed(zip_path: Path) -> Path:
    """Extract zip into a temporary staging folder in storage/colab_extracted."""
    extract_dir = STORAGE_DIR / "colab_extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Extracting '{zip_path}' -> '{extract_dir}'...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
        
    return extract_dir


def import_colab_artifacts(
    zip_file_path: str = None,
    index_file_path: str = None,
    metadata_file_path: str = None
):
    """
    Import external FAISS index, metadata.json, and catalog images from Google Colab.
    """
    print("=" * 65)
    print(">> IMPORTING TRAINED GOOGLE COLAB DATASET INTO SHOEMATCH AI")
    print("=" * 65)

    staging_dir = None
    zip_p = find_zip_package(zip_file_path)
    
    if zip_p:
        logger.info(f"Found Colab export package: {zip_p}")
        staging_dir = extract_zip_if_needed(zip_p)

    search_dirs = [
        staging_dir,
        STORAGE_DIR,
        BASE_DIR,
        Path.home() / "Downloads"
    ]
    search_dirs = [d for d in search_dirs if d and d.exists()]

    # 1. Locate index.faiss
    faiss_src = None
    if index_file_path and Path(index_file_path).exists():
        faiss_src = Path(index_file_path)
    else:
        for d in search_dirs:
            for name in ("shoe_index.faiss", "index.faiss"):
                p = d / name
                if p.exists():
                    faiss_src = p
                    break
            if faiss_src:
                break

    # 2. Locate metadata.json
    meta_src = None
    if metadata_file_path and Path(metadata_file_path).exists():
        meta_src = Path(metadata_file_path)
    else:
        for d in search_dirs:
            p = d / "metadata.json"
            if p.exists():
                meta_src = p
                break

    if not faiss_src or not faiss_src.exists():
        logger.error("Could not find 'index.faiss' or 'shoe_index.faiss'.")
        print("\n[!] Please place 'shoe_matching_colab_export.zip' in your project directory:")
        print(f"    {BASE_DIR}")
        return False

    if not meta_src or not meta_src.exists():
        logger.error("Could not find 'metadata.json'.")
        print("\n[!] Please ensure 'metadata.json' is inside your zip or storage folder.")
        return False

    logger.info(f"Using FAISS index: {faiss_src}")
    logger.info(f"Using metadata:    {meta_src}")

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
        logger.info(f"Copied index -> {dest_faiss}")

    # Read metadata JSON
    with open(meta_src, "r", encoding="utf-8") as f:
        metadata_list = json.load(f)

    logger.info(f"Loaded {len(metadata_list)} records from metadata.json")

    # If staging_dir contains catalog_images, copy them to storage/catalog_images
    if staging_dir:
        staged_images = staging_dir / "catalog_images"
        if staged_images.exists():
            for design_f in staged_images.iterdir():
                if design_f.is_dir():
                    dest_design_dir = CATALOG_IMAGES_DIR / design_f.name
                    dest_design_dir.mkdir(parents=True, exist_ok=True)
                    for img_file in design_f.iterdir():
                        if img_file.is_file():
                            shutil.copy2(img_file, dest_design_dir / img_file.name)

    # Reset and populate SQLite database
    db.init_db()
    
    with db.get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Clear existing tables for fresh clean catalog
        cursor.execute("DELETE FROM reference_images;")
        cursor.execute("DELETE FROM designs;")
        conn.commit()

        designs_created = set()

        for faiss_id, item in enumerate(metadata_list):
            design_id = item.get("design_id") or f"DES-{faiss_id+1:03d}"
            name = item.get("name") or item.get("design_name") or f"Design {faiss_id+1:03d}"
            raw_category = item.get("category", "Sneaker")
            angle = item.get("angle", "side")
            image_path = item.get("image_path", "")
            shelf = item.get("shelf_location", "Warehouse A - Rack 01 - Shelf 1")
            materials = item.get("materials", "Standard Footwear Materials")
            season = item.get("season", "Collection 2026")
            status = item.get("production_status", "Active Sample Room")
            desc = item.get("description", f"Catalog model: {name}")

            # Ensure image path has leading slash
            if not image_path.startswith("/"):
                image_path = "/" + image_path

            # Insert Design
            if design_id not in designs_created:
                cursor.execute("""
                    INSERT INTO designs (
                        design_id, name, category, description, created_by,
                        shelf_location, materials, season, production_status, thumbnail_path
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(design_id) DO UPDATE SET
                        thumbnail_path = CASE WHEN thumbnail_path = '' THEN excluded.thumbnail_path ELSE thumbnail_path END;
                """, (
                    design_id, name, raw_category, desc, "Colab GPU Training",
                    shelf, materials, season, status, image_path
                ))
                designs_created.add(design_id)

            # Insert Reference Image
            cursor.execute("""
                INSERT INTO reference_images (design_id, image_path, angle, faiss_id)
                VALUES (?, ?, ?, ?);
            """, (design_id, image_path, angle, int(item.get("faiss_id", faiss_id))))

        conn.commit()

    stats = db.get_catalog_stats()
    print("\n" + "=" * 65)
    print("🎉 COLAB INDEX & METADATA IMPORT SUCCESSFUL!")
    print("=" * 65)
    print(f"📊 Total Unique Designs Imported : {stats['total_designs']}")
    print(f"⚡ Total Vectors in FAISS Index  : {stats['total_reference_images']}")
    print(f"📐 Vector Dimension              : {vector_dim}")
    print(f"📁 Index File Location           : {dest_faiss}")
    print(f"🗄️ Database File Location        : {DB_PATH}")
    print("=" * 65)
    print("\n🚀 Ready! Open http://localhost:8000 to test visual matching.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import Colab-trained FAISS index and metadata into ShoeMatch AI")
    parser.add_argument("--zip", "-z", type=str, default=None, help="Path to shoe_matching_colab_export.zip")
    parser.add_argument("--index", "-i", type=str, default=None, help="Path to index.faiss")
    parser.add_argument("--metadata", "-m", type=str, default=None, help="Path to metadata.json")
    args = parser.parse_args()

    import_colab_artifacts(args.zip, args.index, args.metadata)
