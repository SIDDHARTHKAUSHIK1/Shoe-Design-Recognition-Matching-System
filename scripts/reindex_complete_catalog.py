"""
Reindex Complete Unified Catalog: 25 Shoe Designs + 20 Colab Slipper Designs.
"""
import os
import sys
import glob
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import STORAGE_DIR, CATALOG_IMAGES_DIR, DB_PATH, FAISS_INDEX_PATH
from backend import database as db
from backend.engine import EmbeddingEngine
from backend.vector_store import VectorStore
from backend.ingestion import ingest_single_design

def reindex_complete_catalog():
    print("=" * 65)
    print(">> REINDEXING UNIFIED CATALOG: SHOES + COLAB SLIPPERS")
    print("=" * 65)

    db.init_db()
    engine = EmbeddingEngine.get_instance()
    
    # 1. Reset database tables and FAISS index
    VectorStore._instance = None
    if FAISS_INDEX_PATH.exists():
        try:
            FAISS_INDEX_PATH.unlink()
        except Exception:
            pass
    
    vstore = VectorStore.get_instance()
    
    with db.get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM reference_images;")
        cursor.execute("DELETE FROM designs;")
        conn.commit()

    # 2. Index Shoes (SHOE-001 through SHOE-025)
    shoe_categories = [
        "Sneaker", "Running Shoe", "Casual Trainer", "Classic Oxford",
        "Slip-On Loafer", "Hiking Boot", "High-Top Basketball", "Athletic Cross-Trainer"
    ]
    shoe_names = [
        "AeroStride Pro Runner", "UrbanGlide Street Low", "Vortex Cushion Speed",
        "Apex Trail Master", "Zenith Minimalist Trainer", "RetroFlex Classic Court",
        "HyperSprint Track Racer", "EchoWave Air Mesh", "TitanShield Heavy Trek",
        "CloudPace Lightweight Sneaker", "Monarch Leather Casual", "Velocity Knit Sock-Fit",
        "PulseBoost Endurance", "Phantom Stealth Low-Top", "Quantum Dynamic Sneaker",
        "Summit Grip Outdoor", "DriftWave Canvas Slip-On", "NovaEdge Sport Edition",
        "TerraForm Cross-Country", "ApexFlow Streetwear Edition", "StrideCraft Heritage Leather",
        "ShadowRacer Carbon Spec", "Heritage Wingtip Oxford", "Heritage Brogue Oxford",
        "Imperial Monk Strap Sample"
    ]

    shoe_folders = sorted(list(CATALOG_IMAGES_DIR.glob("SHOE-*")) + list(CATALOG_IMAGES_DIR.glob("DESIGN_*")))
    indexed_shoes = 0

    for idx, sdir in enumerate(shoe_folders, start=1):
        if not sdir.is_dir():
            continue
        design_id = f"SHOE-{idx:03d}"
        name = shoe_names[(idx - 1) % len(shoe_names)]
        category = shoe_categories[(idx - 1) % len(shoe_categories)]
        shelf = f"Building A - Section {(idx%3)+1} - Rack A-{(idx%8)+1:02d} - Shelf {(idx%4)+1}"
        
        img_files = []
        for img_p in sdir.glob("*.*"):
            if img_p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                img_files.append({"filepath": str(img_p), "filename": img_p.name})
                
        if img_files:
            ingest_single_design(
                design_id=design_id,
                name=name,
                category=category,
                description=f"Authentic production shoe design: {name} with factory verified multi-angle photos.",
                created_by="Footwear Design Studio",
                shelf_location=shelf,
                materials="Italian Nappa Leather / Cushioned EVA Midsole / Rubber Outsole",
                season="Spring/Summer 2026",
                production_status="Active Sample Room",
                image_files=img_files
            )
            indexed_shoes += 1

    print(f"[OK] Indexed {indexed_shoes} Shoe reference designs.")

    # -----------------------------------------------------------------------
    # SLIPPER INDEXING — PERMANENTLY DISABLED
    # This system is shoe-only. Slippers are excluded from FAISS index and DB catalog.
    # -----------------------------------------------------------------------
    indexed_slippers = 0

    stats = db.get_catalog_stats()
    print("\n" + "=" * 65)
    print(">> SHOE-ONLY CATALOG REINDEXING COMPLETED!")
    print("=" * 65)
    print(f"Shoe Designs Indexed    : {indexed_shoes}")
    print(f"Slipper Designs Skipped : {indexed_slippers}")
    print(f"Total Catalog Designs   : {stats['total_designs']}")
    print(f"Total FAISS Vectors     : {stats['total_reference_images']}")
    print("=" * 65)

    print("=" * 65)
    print(f"Shoe Designs Indexed    : {indexed_shoes}")
    print(f"Slipper Designs Indexed : {indexed_slippers}")
    print(f"Total Catalog Designs   : {stats['total_designs']}")
    print(f"Total FAISS Vectors     : {stats['total_reference_images']}")
    print("=" * 65)



if __name__ == "__main__":
    reindex_complete_catalog()
