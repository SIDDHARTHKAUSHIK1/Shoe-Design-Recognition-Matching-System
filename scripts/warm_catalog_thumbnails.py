"""
Comprehensive Offline Pre-generation Script for Catalog WebP Thumbnails.
Warms all thumbnails in storage/thumbnails/ for ALL catalog designs and angles
so every search result (Rank #1, #2, #3) hits a warm fast-path instantly.
"""
import sys
import time
import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.main import db, _resolve_catalog_image_path, _get_or_create_thumbnail, CATALOG_IMAGES_DIR, THUMBNAILS_DIR

def warm_all_catalog_thumbnails():
    start_time = time.time()
    
    # 1. Fetch all live catalog designs from SQLite
    designs = db.get_all_designs()
    total_designs = len(designs)
    
    print("=" * 70)
    print(f"  ShoeMatch AI: Warming Catalog WebP Thumbnails ({total_designs} Live Designs)")
    print("=" * 70)
    
    # 2. Build index of all reference images across SQLite
    ref_images_by_design = {}
    with db.get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT design_id, image_path FROM reference_images;")
        for row in cursor.fetchall():
            d_id = row["design_id"]
            img_p = row["image_path"]
            if d_id and img_p:
                ref_images_by_design.setdefault(d_id, set()).add(Path(img_p).name)

    warmed_count = 0
    already_cached = 0
    skipped_count = 0

    for i, d in enumerate(designs, 1):
        design_id = d.get("design_id")
        if not design_id:
            continue

        images_to_process = set()

        # Add primary thumbnail_path if present
        thumb_hint = d.get("thumbnail_path")
        if thumb_hint:
            images_to_process.add(Path(thumb_hint).name)

        # Add all reference images recorded in SQLite
        if design_id in ref_images_by_design:
            images_to_process.update(ref_images_by_design[design_id])

        # Also inspect on-disk storage directory for this design
        design_dir = CATALOG_IMAGES_DIR / design_id
        if design_dir.exists() and design_dir.is_dir():
            for f in design_dir.iterdir():
                if f.is_file() and f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp'):
                    images_to_process.add(f.name)

        # If still empty, check standard fallback names
        if not images_to_process:
            for fallback in ["photo_1.jpg", "photo_1.jpeg", "photo_1.png", "photo_1.webp"]:
                resolved = _resolve_catalog_image_path(design_id, fallback)
                if resolved:
                    images_to_process.add(fallback)
                    break

        if not images_to_process:
            print(f"  [{i}/{total_designs}] {design_id} — no images found, skipping")
            skipped_count += 1
            continue

        # Warm each image
        for filename in sorted(images_to_process):
            resolved = _resolve_catalog_image_path(design_id, filename)
            if not resolved:
                continue

            orig_p = Path(resolved)
            thumb_p = THUMBNAILS_DIR / design_id / f"{orig_p.stem}_480.webp"

            if thumb_p.exists() and thumb_p.stat().st_size > 0:
                already_cached += 1
            else:
                _get_or_create_thumbnail(resolved, design_id)
                warmed_count += 1

        if i % 15 == 0 or i == total_designs:
            print(f"  [{i}/{total_designs}] {design_id} checked (new: {warmed_count}, cached: {already_cached})")

    elapsed = time.time() - start_time
    print("-" * 70)
    print(f"Summary: {warmed_count} newly generated, {already_cached} already warm, {skipped_count} skipped.")
    print(f"Completed in {elapsed:.2f} seconds.")
    print("=" * 70)

if __name__ == "__main__":
    warm_all_catalog_thumbnails()
