"""
Incrementally index catalog design folders that exist on disk but were never
actually registered in the FAISS index / SQLite database.

WHY THIS SCRIPT EXISTS
-----------------------
`python -m backend.ingestion` (backend.ingestion.ingest_catalog_from_dataset)
is all-or-nothing: it checks "does the catalog already have ANY designs?" and,
if so, does nothing at all -- see the early-return in ingest_catalog_from_dataset().
That means any design folder added to data/catalog *after* the very first
ingestion run is silently never indexed, even though its photos are sitting
right there on disk in data/catalog/ and storage/catalog_images/. Those
designs can never be matched by the app -- if a user uploads a real photo of
one of them, the system has no choice but to return some other, wrong design
as the closest match, which looks like "low accuracy".

On this catalog, as of the day this script was written, 140 of 176 on-disk
design folders (about 80%) were missing from the database for exactly this
reason. Run this script any time you add new folders to data/catalog and want
them to actually become searchable.

WHAT IT DOES
------------
- Scans CATALOG_DATA_DIR (data/catalog) for design folders.
- Skips any folder whose name is already a design_id in the database.
- For every remaining folder, calls backend.ingestion.ingest_single_design()
  -- the same incremental, single-design ingestion function used by the
  POST /api/designs endpoint -- so newly indexed designs go through the exact
  same code path (embedding, foreground isolation, color feature extraction,
  FAISS add, DB insert) as a design added by hand through the app.
- Safe to re-run: already-registered design_ids are always skipped, so running
  this twice in a row is a no-op the second time.

USAGE
-----
    python scripts/reindex_missing_designs.py --dry-run   # see what would be added, no writes
    python scripts/reindex_missing_designs.py              # actually index the missing designs

Run this from the project root (same place you run run_server.py).
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import CATALOG_DATA_DIR
from backend import database as db
# NOTE: backend.ingestion (and the EmbeddingEngine/torch chain it pulls in) is
# imported lazily inside main(), only when actually indexing, so `--dry-run`
# works even in an environment that doesn't have torch installed yet.

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def infer_category(folder_name: str) -> str:
    """Mirror the shoe/slipper heuristic already used in ingest_catalog_from_dataset()."""
    return "Slide Sandal" if db.normalize_category(folder_name) == "slipper" else "Sneaker"


def find_missing_designs():
    db.init_db()
    existing_ids = {d["design_id"] for d in db.get_all_designs()}

    if not CATALOG_DATA_DIR.exists():
        logger.error(f"Catalog source directory does not exist: {CATALOG_DATA_DIR}")
        return [], existing_ids

    on_disk = sorted([d for d in CATALOG_DATA_DIR.iterdir() if d.is_dir()], key=lambda p: p.name)
    missing = [d for d in on_disk if d.name not in existing_ids]
    return missing, existing_ids


def main(dry_run: bool = False):
    missing, existing_ids = find_missing_designs()

    print("=" * 70)
    print(f"Catalog source: {CATALOG_DATA_DIR}")
    print(f"Design folders on disk found under data/catalog: {len(missing) + len(existing_ids)}")
    print(f"Already indexed in the database: {len(existing_ids)}")
    print(f"NOT yet indexed (about to fix): {len(missing)}")
    print("=" * 70)

    if not missing:
        print("Nothing to do -- every on-disk design folder is already indexed.")
        return

    if dry_run:
        print("\n--dry-run: no changes will be made. Designs that WOULD be indexed:\n")
        for d in missing:
            n_imgs = len([f for f in d.iterdir() if f.suffix.lower() in IMAGE_EXTS])
            print(f"  {d.name:20s} ({n_imgs} image file(s))")
        return

    # Imported lazily so `--dry-run` never requires torch/transformers to be installed.
    from backend.ingestion import ingest_single_design

    added, failed, skipped_empty = 0, 0, 0
    for i, d in enumerate(missing, start=1):
        img_files = [
            {"filepath": str(f), "filename": f.name}
            for f in sorted(d.iterdir())
            if f.is_file() and f.suffix.lower() in IMAGE_EXTS
        ]
        if not img_files:
            logger.warning(f"[{i}/{len(missing)}] Skipping {d.name}: no image files found.")
            skipped_empty += 1
            continue

        category = infer_category(d.name)
        name = d.name.replace("_", " ").replace("-", " ").title()

        try:
            result = ingest_single_design(
                design_id=d.name,
                name=name,
                category=category,
                description=f"Catalog design {d.name}, indexed by reindex_missing_designs.py.",
                created_by="Reindex Script",
                image_files=img_files,
            )
            if result.get("success"):
                added += 1
                print(f"[{i}/{len(missing)}] Indexed {d.name} ({result.get('images_indexed')} images)")
            else:
                failed += 1
                logger.error(f"[{i}/{len(missing)}] Failed {d.name}: {result.get('message')}")
        except Exception as e:
            failed += 1
            logger.error(f"[{i}/{len(missing)}] Exception indexing {d.name}: {e}")

    print("=" * 70)
    print(f"Done. Added: {added}  Failed: {failed}  Skipped (no images): {skipped_empty}  Total attempted: {len(missing)}")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. python scripts/calibrate_thresholds.py   # score distribution changed, recalibrate")
    print("  2. python evaluate.py                        # confirm accuracy on the full catalog")
    print("  3. Restart the server (python run_server.py) so the new FAISS index is loaded fresh")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="List what would be indexed without writing anything.")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
