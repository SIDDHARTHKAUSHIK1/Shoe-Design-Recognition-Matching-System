"""
Step 5 helper: sanity-check that the footwear/category gate (backend/footwear_gate.py,
backend/classifier.py) isn't silently rejecting good queries before they ever reach
the matcher -- which looks identical to "low accuracy" from the user's side but has
nothing to do with ranking quality.

WHY THIS SCRIPT EXISTS
-----------------------
backend.matcher.ShoeMatcher.match_image() can reject a query outright, before any
FAISS search happens, for two reasons unrelated to ranking:
  - "no_clear_object": the foreground isolator (backend/foreground.py) found no
    confident subject in the frame.
  - "out_of_distribution" / "ambiguous_category": the zero-shot classifier
    (backend/classifier.py) couldn't confidently place the image as a shoe.
  - "slipper_rejected": the shoe-only catalog explicitly rejects slipper uploads.
A false rejection in any of these categories means a genuine, correct-design photo
never even gets a chance to be ranked -- so it's worth ruling out separately from
Test 1/2's ranking-quality numbers.

This reuses the exact same perturbation recipes as scripts/evaluate_field_accuracy.py
Test 1 (JPEG re-compression, crop, brightness shift, rotation) applied to the
catalog's own real reference photos, and reports the rejection reason breakdown.
It does NOT touch the catalog, index, or any config file.

USAGE
-----
    python scripts/check_gate_false_rejections.py
"""
import sys
import logging
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import BASE_DIR, STORAGE_DIR
from backend import database as db
from backend.vector_store import VectorStore
from backend.matcher import ShoeMatcher

# Reuse the exact same perturbation recipes and path resolution as the main harness,
# so gate behavior is checked against the same query images Test 1 uses.
from evaluate_field_accuracy import (
    resolve_image_path,
    load_all_reference_rows,
    PERTURBATION_RECIPES,
    recipes_for_index,
)
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    db.init_db()
    vs = VectorStore.get_instance()
    if vs.total_vectors == 0:
        logger.error("Catalog index is empty. Nothing to check.")
        sys.exit(1)

    matcher = ShoeMatcher()
    ref_rows = load_all_reference_rows()

    rejection_reasons = Counter()
    false_rejections = []
    total = 0

    for idx, r in enumerate(ref_rows):
        full_path = resolve_image_path(r["image_path"], r["design_id"])
        if not full_path.exists():
            continue
        try:
            base_img = Image.open(full_path).convert("RGB")
        except Exception:
            continue

        for recipe_name, recipe_fn in recipes_for_index(idx, count=3):
            try:
                perturbed = recipe_fn(base_img)
            except Exception:
                continue

            total += 1
            result = matcher.match_image(
                perturbed,
                query_image_save_path=f"__eval__/gate_check/{r['design_id']}/{full_path.stem}__{recipe_name}"
            )

            is_footwear = result.get("is_footwear_detected", True)
            reason = result.get("reason")

            if not is_footwear or reason in ("no_clear_object", "out_of_distribution", "ambiguous_category", "slipper_rejected"):
                rejection_reasons[reason or "unknown"] += 1
                false_rejections.append({
                    "expected_design_id": r["design_id"],
                    "source_image": r["image_path"],
                    "perturbation": recipe_name,
                    "reason": reason,
                    "category_confidence_pct": result.get("category_confidence_pct"),
                })

    print("\n" + "=" * 88)
    print("   FOOTWEAR GATE FALSE-REJECTION CHECK   ")
    print("=" * 88)
    print(f"Total perturbed queries tested: {total}")
    print(f"Rejected before reaching the matcher: {len(false_rejections)} "
          f"({round(len(false_rejections)/total*100.0, 2) if total else 0.0}%)")
    if rejection_reasons:
        print("\nBreakdown by reason:")
        for reason, count in rejection_reasons.most_common():
            print(f"  {reason:<25} {count}")
    if false_rejections:
        print("\nIndividual false rejections (these are genuine catalog photos -- every one of these\n"
              "is a query that never got a chance to be ranked, which looks like 'low accuracy' but\n"
              "is actually a gate problem):")
        for f in false_rejections[:40]:
            print(f"  design={f['expected_design_id']:<16} perturbation={f['perturbation']:<24} "
                  f"reason={f['reason']:<22} source={f['source_image']}")
    else:
        print("\nNo false rejections found -- the gate is not the source of any accuracy issues seen here.")
    print("=" * 88 + "\n")


if __name__ == "__main__":
    main()
