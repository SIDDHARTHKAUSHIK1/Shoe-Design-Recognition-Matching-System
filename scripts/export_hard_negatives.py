"""
Export Hard Negatives and Misclassified Queries from ShoeMatch AI Feedback.

Extracts all queries where user verdict was 'wrong_match', 'not_in_catalog', or 'wrong_category',
copies the query image to a target directory, and saves an indexed dataset JSON for future
fine-tuning, metric learning, or threshold calibration.

Usage:
    python scripts/export_hard_negatives.py [--output_dir storage/hard_negatives]
"""
import os
import sys
import json
import shutil
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend import database as db
from backend.config import STORAGE_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def export_hard_negatives(output_dir: str = None) -> dict:
    target_dir = Path(output_dir) if output_dir else STORAGE_DIR / "hard_negatives"
    images_dir = target_dir / "images"
    target_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    feedback_records = db.get_feedback_logs(limit=1000)
    logger.info(f"Retrieved {len(feedback_records)} total feedback records from database.")

    exported_items = []
    category_counts = {}

    for rec in feedback_records:
        verdict = rec.get("user_verdict")
        # Focus on hard negative / rejection failure cases
        if verdict not in ("wrong_match", "not_in_catalog", "wrong_category"):
            continue

        q_img_path = rec.get("query_image_path")
        if not q_img_path:
            continue

        # Resolve image file
        resolved_src = Path(q_img_path)
        if not resolved_src.is_absolute():
            resolved_src = BASE_DIR / q_img_path

        dest_filename = f"feedback_{rec['id']}_{resolved_src.name}"
        dest_path = images_dir / dest_filename

        if resolved_src.exists():
            try:
                shutil.copy2(resolved_src, dest_path)
            except Exception as e:
                logger.warning(f"Could not copy image {resolved_src}: {e}")

        item_meta = {
            "feedback_id": rec["id"],
            "query_id": rec.get("query_id"),
            "user_verdict": verdict,
            "correct_design_id": rec.get("correct_design_id"),
            "notes": rec.get("notes", ""),
            "original_image_path": str(q_img_path),
            "exported_image_path": str(dest_path.relative_to(target_dir)),
            "top_match_id": rec.get("top_match_id"),
            "top_match_name": rec.get("top_match_name"),
            "confidence_pct": rec.get("confidence_pct"),
            "detected_category": rec.get("detected_category"),
            "created_at": rec.get("created_at")
        }
        exported_items.append(item_meta)
        category_counts[verdict] = category_counts.get(verdict, 0) + 1

    manifest = {
        "version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "total_exported": len(exported_items),
        "verdict_distribution": category_counts,
        "records": exported_items
    }

    manifest_path = target_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"Successfully exported {len(exported_items)} hard negative records to: {target_dir}")
    print(f"\nHard Negatives Export Summary:")
    print(f"Total Exported: {len(exported_items)}")
    for k, v in category_counts.items():
        print(f" - {k}: {v}")
    print(f"Manifest written to: {manifest_path}")

    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export hard negatives from user feedback.")
    parser.add_argument("--output_dir", type=str, default=None, help="Target export folder")
    args = parser.parse_args()

    export_hard_negatives(args.output_dir)
