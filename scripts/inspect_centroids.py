import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import database as db
from backend.vector_store import VectorStore
vs = VectorStore.get_instance()
print('Total vectors in FAISS:', vs.total_vectors)
shoes = 0
slippers = 0
for fid in range(vs.total_vectors):
    meta = db.get_reference_image_by_faiss_id(fid)
    if not meta:
        print(f'FAISS ID {fid} has NO metadata in DB!')
        continue
    raw_cat = meta.get('category', '')
    norm_cat = db.normalize_category(raw_cat)
    if norm_cat == 'shoe':
        shoes += 1
    elif norm_cat == 'slipper':
        slippers += 1
        if slippers <= 3:
            print(f'Slipper vector fid={fid}: design={meta.get("design_id")} raw_cat="{raw_cat}"')
print(f'Total: shoes={shoes}, slippers={slippers}')
