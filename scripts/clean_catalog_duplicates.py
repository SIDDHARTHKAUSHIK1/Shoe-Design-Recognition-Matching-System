import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
import numpy as np
import faiss
from backend import database as db
from backend.vector_store import VectorStore
from backend.config import DB_PATH, FAISS_INDEX_PATH

vs = VectorStore.get_instance()
print(f"Initial FAISS vectors: {vs.total_vectors}")

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
        if j not in visited and sim_mat[i, j] > 0.985: # Identical or near-identical image
            cluster.append(j)
            visited.add(j)
    clusters.append(cluster)

print(f"Total unique visual styles: {len(clusters)}")

# Identify which reference_image and design IDs to keep vs delete
fids_to_keep = [c[0] for c in clusters]
fids_to_delete = []
for c in clusters:
    for fid in c[1:]:
        fids_to_delete.append(fid)

print(f"Keeping {len(fids_to_keep)} unique reference images, removing {len(fids_to_delete)} duplicate reference images.")

# Map what we keep
kept_ref_ids = set()
kept_design_ids = set()

for fid in fids_to_keep:
    meta = db.get_reference_image_by_faiss_id(fid)
    if meta:
        kept_ref_ids.add(meta["ref_id"])
        kept_design_ids.add(meta["design_id"])

print(f"Unique designs to keep: {len(kept_design_ids)} (Shoe + Slipper)")

with db.get_db_connection() as conn:
    cursor = conn.cursor()
    
    # 1. Get all designs in DB
    cursor.execute("SELECT design_id FROM designs")
    all_db_designs = cursor.fetchall()
    
    deleted_designs = 0
    for row in all_db_designs:
        did = row["design_id"]
        if did not in kept_design_ids:
            cursor.execute("DELETE FROM reference_images WHERE design_id = ?", (did,))
            cursor.execute("DELETE FROM designs WHERE design_id = ?", (did,))
            deleted_designs += 1
            
    # 2. Also delete any duplicate reference images of kept designs that were in fids_to_delete
    for fid in fids_to_delete:
        meta = db.get_reference_image_by_faiss_id(fid)
        if meta and meta["ref_id"] not in kept_ref_ids:
            cursor.execute("DELETE FROM reference_images WHERE id = ?", (meta["ref_id"],))

    print(f"Deleted {deleted_designs} redundant duplicate design entries from SQLite.")

    # 3. Rebuild FAISS index from scratch with remaining unique reference images
    new_index = faiss.IndexFlatIP(384)
    new_vectors = []

    cursor.execute("SELECT id, design_id, image_path FROM reference_images ORDER BY id ASC")
    remaining_refs = cursor.fetchall()

    print(f"Total remaining distinct reference images: {len(remaining_refs)}")

    from backend.engine import EmbeddingEngine
    engine = EmbeddingEngine.get_instance()

    def resolve_local(p):
        if os.path.exists(p):
            return p
        clean = p.lstrip("/\\")
        p1 = os.path.join("storage", clean)
        if os.path.exists(p1):
            return p1
        for root, dirs, files in os.walk("storage"):
            if os.path.basename(p) in files:
                return os.path.join(root, os.path.basename(p))
        return p1

    for new_fid, ref in enumerate(remaining_refs):
        ref_id = ref["id"]
        img_p = ref["image_path"]
        actual_path = resolve_local(img_p)
        
        # Extract clean normalized embedding
        emb = engine.get_embedding(actual_path)
        new_vectors.append(emb)
        
        # Update SQLite faiss_id
        cursor.execute("UPDATE reference_images SET faiss_id = ? WHERE id = ?", (new_fid, ref_id))

    if new_vectors:
        matrix = np.array(new_vectors, dtype=np.float32)
        faiss.normalize_L2(matrix)
        new_index.add(matrix)

    faiss.write_index(new_index, str(FAISS_INDEX_PATH))
    print(f"Saved rebuilt FAISS index to {FAISS_INDEX_PATH} with {new_index.ntotal} distinct vectors.")

# Checkpoint database
with db.get_db_connection() as conn:
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")

print("Catalog deduplication and re-indexing completed successfully!")
