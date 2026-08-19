import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import database as db
from backend.vector_store import VectorStore
import numpy as np

vs = VectorStore.get_instance()

ids_to_check = [226, 186, 126, 86, 26]
for fid in ids_to_check:
    meta = db.get_reference_image_by_faiss_id(fid)
    print(f"FAISS ID {fid}:")
    print(f"  Design: {meta.get('design_id')} - {meta.get('name')}")
    print(f"  Image: {meta.get('image_path')}")
    print(f"  Size: {os.path.getsize(meta.get('image_path')) if os.path.exists(meta.get('image_path')) else 'Missing'}")

# Also check pairwise cosine similarity between all 247 vectors in FAISS to find duplicate visual vectors!
print("\n--- Scanning for duplicate visual embeddings (similarity > 0.999) ---")
all_vecs = []
for i in range(vs.total_vectors):
    all_vecs.append(vs.index.reconstruct(i))
all_vecs = np.array(all_vecs)

# Compute similarity matrix
sim_mat = np.dot(all_vecs, all_vecs.T)
np.fill_diagonal(sim_mat, 0)

dup_pairs = []
for i in range(vs.total_vectors):
    for j in range(i + 1, vs.total_vectors):
        if sim_mat[i, j] > 0.995:
            meta_i = db.get_reference_image_by_faiss_id(i)
            meta_j = db.get_reference_image_by_faiss_id(j)
            dup_pairs.append((i, j, sim_mat[i, j], meta_i, meta_j))

print(f"Found {len(dup_pairs)} pairs of visually identical/near-duplicate images!")
for i, j, s, mi, mj in dup_pairs[:20]:
    print(f"FAISS {i} ({mi.get('design_id')}: {mi.get('image_path')}) <-> FAISS {j} ({mj.get('design_id')}: {mj.get('image_path')}) : Sim = {s:.4f}")
