import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import database as db
from backend.vector_store import VectorStore
import numpy as np

vs = VectorStore.get_instance()
print("Scanning unique clusters in FAISS index...")

all_vecs = np.array([vs.index.reconstruct(i) for i in range(vs.total_vectors)])
sim_mat = np.dot(all_vecs, all_vecs.T)

visited = set()
clusters = []

for i in range(vs.total_vectors):
    if i in visited:
        continue
    cluster = [i]
    visited.add(i)
    for j in range(i + 1, vs.total_vectors):
        if j not in visited and sim_mat[i, j] > 0.990: # Visually identical / near-duplicate image
            cluster.append(j)
            visited.add(j)
    clusters.append(cluster)

print(f"Total FAISS vectors: {vs.total_vectors}")
print(f"Total UNIQUE visual clusters: {len(clusters)}")

shoe_clusters = 0
slipper_clusters = 0

for c in clusters:
    meta = db.get_reference_image_by_faiss_id(c[0])
    cat = db.normalize_category(meta.get("category", ""))
    if cat == "slipper":
        slipper_clusters += 1
    else:
        shoe_clusters += 1

print(f"Unique shoe visual styles: {shoe_clusters}")
print(f"Unique slipper visual styles: {slipper_clusters}")
