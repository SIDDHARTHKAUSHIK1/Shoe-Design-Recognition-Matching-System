"""
Dataset Ingestion and Automated Label Generation for Custom 1,500 Shoe Dataset.
Copies and validates images from Large_dataset/ to data/training/custom_1500/images/
and generates data/training/custom_1500/labels.csv.
"""
import os
import sys
import csv
import shutil
import logging
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import TRAINING_DATA_DIR, assert_catalog_image_path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SOURCE_DIR = BASE_DIR / "Large_dataset"
TARGET_DATASET_DIR = TRAINING_DATA_DIR / "custom_1500"
TARGET_IMAGES_DIR = TARGET_DATASET_DIR / "images"
LABELS_CSV_PATH = TARGET_DATASET_DIR / "labels.csv"

CATEGORY_MAPPING = {
    "boat": "boat",
    "brogue": "brogue",
    "sneaker": "sneaker"
}


def prepare_custom_1500_dataset():
    logger.info("=== Preparing Custom 1,500-Image Training Dataset ===")
    logger.info(f"Source Directory: {SOURCE_DIR}")
    logger.info(f"Target Directory: {TARGET_DATASET_DIR}")

    if not SOURCE_DIR.exists():
        raise FileNotFoundError(f"Source folder not found at {SOURCE_DIR}")

    TARGET_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    for cat in CATEGORY_MAPPING.values():
        (TARGET_IMAGES_DIR / cat).mkdir(parents=True, exist_ok=True)

    records = []
    skipped_count = 0
    total_found = 0

    # Scan subdirectories
    for src_sub in sorted(SOURCE_DIR.iterdir()):
        if not src_sub.is_dir():
            continue
        
        raw_name = src_sub.name.lower()
        if raw_name not in CATEGORY_MAPPING:
            logger.warning(f"Skipping unknown category folder: {src_sub.name}")
            continue
        
        cat = CATEGORY_MAPPING[raw_name]
        dest_cat_dir = TARGET_IMAGES_DIR / cat

        image_files = sorted([
            f for f in src_sub.iterdir() 
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".bmp")
        ])
        logger.info(f"Processing category '{cat}': found {len(image_files)} raw images in {src_sub}...")

        for idx, img_file in enumerate(image_files, start=1):
            total_found += 1
            # Validate image with PIL
            try:
                with Image.open(img_file) as im:
                    im.verify()
                with Image.open(img_file) as im:
                    im.convert("RGB")
            except Exception as e:
                logger.warning(f"Corrupt or unreadable image skipped: {img_file} ({e})")
                skipped_count += 1
                continue

            # Standardized filename
            dest_filename = f"{cat}_{idx:04d}{img_file.suffix.lower()}"
            dest_path = dest_cat_dir / dest_filename

            # Copy file if not already present or different size
            if not dest_path.exists() or dest_path.stat().st_size != img_file.stat().st_size:
                shutil.copy2(img_file, dest_path)

            rel_path = dest_path.relative_to(BASE_DIR).as_posix()
            records.append({
                "image_path": rel_path,
                "design_group": cat
            })

    # Write labels.csv
    with open(LABELS_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["image_path", "design_group"])
        writer.writeheader()
        writer.writerows(records)

    logger.info(f"Successfully generated {LABELS_CSV_PATH} with {len(records)} entries.")
    
    # Category summary
    summary = {}
    for r in records:
        summary[r["design_group"]] = summary.get(r["design_group"], 0) + 1

    print("\n" + "=" * 60)
    print(">> CUSTOM 1,500 DATASET INGESTION SUMMARY")
    print("=" * 60)
    print(f"Total Source Images Found : {total_found}")
    print(f"Total Validated Images    : {len(records)}")
    print(f"Total Corrupt / Skipped   : {skipped_count}")
    print("Breakdown by Coarse Group :")
    for grp, count in sorted(summary.items()):
        print(f"  - {grp:10s} : {count:4d} images")
    print(f"Labels Manifest Saved At  : {LABELS_CSV_PATH}")
    print("=" * 60 + "\n")

    return records


if __name__ == "__main__":
    prepare_custom_1500_dataset()
