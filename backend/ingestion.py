"""
Catalog Ingestion and Incremental Indexing Pipeline.
"""
import os
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from PIL import Image
import numpy as np

from backend.config import (
    DATASET_DIR,
    CATALOG_IMAGES_DIR,
    DB_PATH,
    FAISS_INDEX_PATH
)
from backend import database as db
from backend.engine import EmbeddingEngine
from backend.vector_store import VectorStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Shoe categories for realistic catalog indexing
SAMPLE_CATEGORIES = [
    "Sneaker", "Running Shoe", "Casual Trainer", "High-Top Basketball",
    "Slip-On Loafer", "Classic Oxford", "Athletic Cross-Trainer", "Hiking Boot"
]

SAMPLE_DESIGN_NAMES = [
    "AeroStride Pro Runner",
    "UrbanGlide Street Low",
    "Vortex Cushion Speed",
    "Apex Trail Master",
    "Zenith Minimalist Trainer",
    "RetroFlex Classic Court",
    "HyperSprint Track Racer",
    "EchoWave Air Mesh",
    "TitanShield Heavy Trek",
    "CloudPace Lightweight Sneaker",
    "Monarch Leather Casual",
    "Velocity Knit Sock-Fit",
    "PulseBoost Endurance",
    "Phantom Stealth Low-Top",
    "Quantum Dynamic Sneaker",
    "Summit Grip Outdoor",
    "DriftWave Canvas Slip-On",
    "NovaEdge Sport Edition",
    "TerraForm Cross-Country",
    "ApexFlow Streetwear Edition",
    "StrideCraft Heritage Leather"
]


def classify_angle_from_filename(filename: str, index_in_group: int = 0) -> str:
    """Infer angle label from filename or relative position."""
    lower = filename.lower()
    if "side" in lower:
        return "side"
    elif "top" in lower:
        return "top"
    elif "sole" in lower or "bottom" in lower:
        return "sole"
    elif "34" in lower or "3_4" in lower or "three_quarter" in lower:
        return "angle_34"
    elif "front" in lower:
        return "front"
    elif "back" or "heel" in lower:
        return "heel"
    
    # Fallback based on sequence in design group
    angle_sequence = ["side", "angle_34", "top", "sole", "perspective", "heel"]
    return angle_sequence[index_in_group % len(angle_sequence)]


def ingest_single_design(
    design_id: str,
    name: str,
    category: str = "Sneaker",
    description: str = "",
    created_by: str = "Design Team",
    shelf_location: str = "Warehouse A - Rack 03 - Shelf B-02",
    materials: str = "Full Grain Leather / Rubber Sole",
    season: str = "Collection 2026",
    production_status: str = "Active Production Sample",
    image_files: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Incrementally ingest a single shoe design with multiple angle photos.
    Uses FAISS incremental add() without re-indexing existing catalog items.
    """
    image_files = image_files or []
    design_dir = CATALOG_IMAGES_DIR / design_id
    design_dir.mkdir(parents=True, exist_ok=True)
    
    engine = EmbeddingEngine.get_instance()
    vector_store = VectorStore.get_instance()
    
    # 1. Register design in SQLite
    db.add_design(
        design_id=design_id,
        name=name,
        category=category,
        description=description,
        created_by=created_by,
        shelf_location=shelf_location,
        materials=materials,
        season=season,
        production_status=production_status
    )
    
    embeddings = []
    registered_images = []
    
    # 2. Process each image
    for idx, item in enumerate(image_files):
        angle = item.get("angle") or classify_angle_from_filename(item.get("filename", ""), idx)
        
        # Save image file to persistent storage
        if "content" in item:
            # Uploaded as bytes
            ext = os.path.splitext(item.get("filename", "image.jpg"))[1] or ".jpg"
            dest_filename = f"angle_{angle}_{idx + 1}{ext}"
            dest_path = design_dir / dest_filename
            with open(dest_path, "wb") as f:
                f.write(item["content"])
            img_input = dest_path
        elif "filepath" in item:
            # Existing filepath on disk
            src_path = Path(item["filepath"])
            ext = src_path.suffix or ".jpg"
            dest_filename = f"angle_{angle}_{idx + 1}{ext}"
            dest_path = design_dir / dest_filename
            shutil.copy2(src_path, dest_path)
            img_input = dest_path
        else:
            continue
            
        # Compute normalized embedding
        emb = engine.get_embedding(img_input)
        embeddings.append(emb)
        
        rel_image_path = f"/catalog_images/{design_id}/{dest_filename}"
        registered_images.append({
            "image_path": rel_image_path,
            "angle": angle,
            "dest_path": dest_path
        })

    # 3. Add embeddings incrementally to FAISS
    if embeddings:
        emb_matrix = np.vstack(embeddings).astype(np.float32)
        assigned_faiss_ids = vector_store.add_vectors(emb_matrix)
        
        # 4. Save reference image metadata in database
        for meta, faiss_id in zip(registered_images, assigned_faiss_ids):
            db.add_reference_image(
                design_id=design_id,
                image_path=meta["image_path"],
                angle=meta["angle"],
                faiss_id=faiss_id
            )

        logger.info(f"Successfully ingested design '{name}' ({design_id}) with {len(embeddings)} reference images.")
        
        return {
            "success": True,
            "design_id": design_id,
            "name": name,
            "images_indexed": len(embeddings),
            "faiss_ids": assigned_faiss_ids
        }
        
    return {
        "success": False,
        "design_id": design_id,
        "message": "No valid images provided."
    }


def ingest_catalog_from_dataset():
    """
    Ingest and organize the reference shoe dataset into SQLite and FAISS.
    Handles both structured folders (dataset/design_xxx/...) and flat dataset images.
    """
    db.init_db()
    vector_store = VectorStore.get_instance()
    
    # Check if index is already populated
    if vector_store.total_vectors > 0 and len(db.get_all_designs()) > 0:
        logger.info(f"Catalog is already populated ({len(db.get_all_designs())} designs, {vector_store.total_vectors} vectors).")
        return
        
    logger.info("Scanning dataset directory for ingestion...")
    
    if not DATASET_DIR.exists():
        logger.warning(f"Dataset directory {DATASET_DIR} does not exist.")
        return

    # Check for subdirectories (structured format: dataset/shoes/... and dataset/slippers/...)
    subdirs = [d for d in DATASET_DIR.iterdir() if d.is_dir()]
    
    design_folders = []
    for d in subdirs:
        if d.name.lower() in ("shoes", "shoe"):
            for inner in d.iterdir():
                if inner.is_dir():
                    design_folders.append((inner, "shoe"))
        elif d.name.lower() in ("slippers", "slipper"):
            for inner in d.iterdir():
                if inner.is_dir():
                    design_folders.append((inner, "slipper"))
        else:
            cat = "slipper" if db.normalize_category(d.name) == "slipper" else "shoe"
            design_folders.append((d, cat))
    
    if design_folders:
        logger.info(f"Found {len(design_folders)} structured design folders in dataset.")
        for idx, (sdir, cat_type) in enumerate(design_folders, start=1):
            prefix = "SLIP" if cat_type == "slipper" else "SHOE"
            design_id = f"{prefix}-{idx:03d}"
            name = sdir.name.replace("_", " ").title()
            category = "Slide Sandal" if cat_type == "slipper" else "Sneaker"
            description = f"Factory catalog {cat_type} design: {name} with multi-angle reference photos."
            
            img_files = []
            for img_file in sdir.glob("*.*"):
                if img_file.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                    img_files.append({"filepath": str(img_file), "filename": img_file.name})
                    
            if img_files:
                ingest_single_design(
                    design_id=design_id,
                    name=name,
                    category=category,
                    description=description,
                    created_by="Master Catalog",
                    image_files=img_files
                )
    else:
        # Flat image collection: Cluster using DINOv2 visual similarity
        flat_images = sorted([
            f for f in DATASET_DIR.iterdir() 
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
        ])
        
        if not flat_images:
            logger.warning("No image files found in dataset directory.")
            return
            
        logger.info(f"Discovered {len(flat_images)} raw images. Performing visual clustering...")
        engine = EmbeddingEngine.get_instance()
        
        embeddings = []
        for img_p in flat_images:
            emb = engine.get_embedding(img_p)
            embeddings.append(emb)
            
        emb_matrix = np.array(embeddings)
        
        # DBSCAN clustering with cosine metric
        from sklearn.cluster import DBSCAN
        clustering = DBSCAN(eps=0.22, min_samples=2, metric="cosine").fit(emb_matrix)
        labels = clustering.labels_
        
        clusters = {}
        for idx, lbl in enumerate(labels):
            clusters.setdefault(lbl, []).append(flat_images[idx])
            
        logger.info(f"Formed {len(clusters)} distinct shoe design clusters from {len(flat_images)} images.")
        
        design_idx = 1
        for cluster_id, img_list in clusters.items():
            design_id = f"SHOE-{design_idx:03d}"
            name = SAMPLE_DESIGN_NAMES[(design_idx - 1) % len(SAMPLE_DESIGN_NAMES)]
            category = SAMPLE_CATEGORIES[(design_idx - 1) % len(SAMPLE_CATEGORIES)]
            description = f"Manufactured specification {name}. Multi-angle reference set containing {len(img_list)} catalog images."
            
            img_items = [{"filepath": str(p), "filename": p.name} for p in img_list]
            ingest_single_design(
                design_id=design_id,
                name=name,
                category=category,
                description=description,
                created_by="Factory Production Team",
                image_files=img_items
            )
            design_idx += 1

    stats = db.get_catalog_stats()
    logger.info(f"Ingestion complete! Total Designs: {stats['total_designs']}, Total Vectors in FAISS: {stats['total_reference_images']}")


if __name__ == "__main__":
    ingest_catalog_from_dataset()
