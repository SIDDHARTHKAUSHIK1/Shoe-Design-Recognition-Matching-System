"""
Step 4 helper: identify which of the 36 existing designs are most fragile to
real-world angle/lighting variation because they only have 1 reference photo,
so you know which designs to prioritize when capturing 2-3 more angles.

WHY THIS SCRIPT EXISTS
-----------------------
This is NOT catalog growth in the sense the project owner ruled out (adding
the ~139 non-stock test-data folders as new designs). It's the opposite: it
helps you strengthen the EXISTING 36 designs by pointing out which ones are
thinnest on reference angles, so photographing 2-3 more angles of just those
designs and adding them via the existing POST /api/designs endpoint (which is
an upsert on design_id -- see backend.database.add_design's
ON CONFLICT(design_id) DO UPDATE -- so this correctly adds reference images
without creating a duplicate design) gets the most benefit for the least
photography effort.

This script only READS the catalog (backend.database.get_all_designs /
get_design). It makes no changes.

USAGE
-----
    python scripts/report_thin_designs.py
    python scripts/report_thin_designs.py --threshold 3   # flag designs with fewer than N ref photos
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import database as db

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--threshold", type=int, default=3,
                         help="Flag designs with fewer than this many reference photos (default: 3)")
    args = parser.parse_args()

    db.init_db()
    designs = db.get_all_designs()

    if not designs:
        print("No designs found in the catalog.")
        return

    rows = []
    for d in designs:
        full = db.get_design(d["design_id"]) or {}
        angles = sorted(set(r.get("angle", "") for r in full.get("reference_images", [])))
        rows.append({
            "design_id": d["design_id"],
            "name": d["name"],
            "category": d.get("category", ""),
            "image_count": d.get("image_count", 0),
            "angles_covered": angles,
        })

    rows.sort(key=lambda r: r["image_count"])
    thin = [r for r in rows if r["image_count"] < args.threshold]

    print("\n" + "=" * 92)
    print(f"   REFERENCE-ANGLE COVERAGE REPORT — {len(designs)} designs, "
          f"threshold = {args.threshold} photo(s)   ")
    print("=" * 92)
    print(f"{'Design ID':<16} | {'Name':<28} | {'Category':<12} | {'#Photos':>7} | Angles covered")
    print("-" * 92)
    for r in rows:
        flag = "  <-- add more angles" if r["image_count"] < args.threshold else ""
        print(f"{r['design_id']:<16} | {r['name'][:28]:<28} | {r['category']:<12} | "
              f"{r['image_count']:>7} | {', '.join(r['angles_covered']) or '(none)'}{flag}")
    print("-" * 92)
    print(f"{len(thin)} of {len(designs)} designs have fewer than {args.threshold} reference photos.")
    if thin:
        print("Priority order for new photos (thinnest first):")
        for r in thin:
            print(f"  - {r['design_id']} ({r['name']}): currently {r['image_count']} photo(s), "
                  f"covering [{', '.join(r['angles_covered']) or 'none'}]. "
                  f"Capture angles NOT already covered (e.g. side/angle_34/top/sole/front/heel), "
                  f"under conditions closer to a real customer photo (not just a clean studio background), "
                  f"then add via POST /api/designs with this same design_id.")
    print("=" * 92 + "\n")
    print("After adding photos for a batch of these designs, re-run "
          "scripts/evaluate_field_accuracy.py --test 1 (and --test 2, once a design has 2+ photos) "
          "and compare against the prior baseline before doing the rest.\n")


if __name__ == "__main__":
    main()
