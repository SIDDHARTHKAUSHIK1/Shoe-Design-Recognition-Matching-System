import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collections import defaultdict
from backend import database as db
import hashlib

def file_hash(filepath):
    if not os.path.exists(filepath):
        return None
    with open(filepath, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

designs = db.get_all_designs()
print(f"Total designs in DB: {len(designs)}")

img_hash_to_designs = defaultdict(list)
for d in designs:
    for img in d.get("reference_images", []):
        p = img.get("image_path")
        h = file_hash(p)
        if h:
            img_hash_to_designs[h].append((d["design_id"], d["name"], p))

duplicates = {h: items for h, items in img_hash_to_designs.items() if len(items) > 1}
print(f"Total duplicate image content hashes: {len(duplicates)}")

for h, items in list(duplicates.items())[:10]:
    print(f"\nHash: {h} (Used by {len(items)} entries):")
    for did, name, p in items:
        print(f"  - {did}: '{name}' -> {p}")
