import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import glob
import numpy as np
from PIL import Image, ImageDraw
from backend.engine import EmbeddingEngine
from backend import database as db
from backend.vector_store import VectorStore

engine = EmbeddingEngine.get_instance()
vs = VectorStore.get_instance()

shoe_embs = []
slipper_embs = []

for fid in range(vs.total_vectors):
    meta = db.get_reference_image_by_faiss_id(fid)
    if not meta: continue
    vec = vs.index.reconstruct(fid)
    norm_cat = db.normalize_category(meta.get("category", ""))
    if norm_cat == "shoe":
        shoe_embs.append(vec)
    elif norm_cat == "slipper":
        slipper_embs.append(vec)

shoe_centroid = np.mean(shoe_embs, axis=0)
shoe_centroid = shoe_centroid / (np.linalg.norm(shoe_centroid) + 1e-9)

slipper_centroid = np.mean(slipper_embs, axis=0)
slipper_centroid = slipper_centroid / (np.linalg.norm(slipper_centroid) + 1e-9)

print(f"Centroids computed: {len(shoe_embs)} shoe vectors, {len(slipper_embs)} slipper vectors")

def classify_with_dinov2(img):
    emb = engine.get_embedding(img)
    scores, ids = vs.search(emb, top_k=7)
    max_sim = float(scores[0][0])
    
    sim_shoe = float(np.dot(emb, shoe_centroid))
    sim_slipper = float(np.dot(emb, slipper_centroid))
    
    # 1. Non-footwear rejection: If similarity to catalog is below threshold
    if max_sim < 0.28:
        return "none", round(1.0 - max_sim, 4)
    
    # 2. k-NN category voting
    shoe_votes = 0.0
    slipper_votes = 0.0
    for s, fid in zip(scores[0], ids[0]):
        if fid < 0: continue
        meta = db.get_reference_image_by_faiss_id(int(fid))
        if not meta: continue
        cat = db.normalize_category(meta.get("category", ""))
        weight = float(s)
        if cat == "shoe":
            shoe_votes += weight
        elif cat == "slipper":
            slipper_votes += weight
            
    # Softmax probabilities between shoe and slipper
    logits = np.array([sim_shoe * 6.0 + shoe_votes, sim_slipper * 6.0 + slipper_votes])
    exp_l = np.exp(logits - np.max(logits))
    probs = exp_l / np.sum(exp_l)
    
    if probs[0] >= probs[1]:
        return "shoe", round(float(probs[0]), 4)
    else:
        return "slipper", round(float(probs[1]), 4)

# Test on 10 shoes
print("\n--- Testing 10 Shoes ---")
shoe_files = sorted(glob.glob("storage/catalog_images/SHOE-*/*.jpg") + glob.glob("storage/catalog_images/SHOE-*/*.jpeg"))
for p in shoe_files[:10]:
    c, prob = classify_with_dinov2(p)
    print(f"Shoe ({p.split('/')[-1]}): Cat = {c} (Prob: {prob:.2f})")

# Test on all 20 slippers
print("\n--- Testing All 20 Slippers ---")
slipper_files = sorted(glob.glob("storage/Slippers/*.jpeg") + glob.glob("storage/Slippers/*.jpg"))
correct_slippers = 0
for p in slipper_files:
    c, prob = classify_with_dinov2(p)
    if c == "slipper": correct_slippers += 1
    print(f"Slipper ({p.split('/')[-1]}): Cat = {c} (Prob: {prob:.2f})")
print(f"Slippers accuracy: {correct_slippers}/{len(slipper_files)}")

# Test on Non-Footwear images
print("\n--- Testing Non-Footwear Images ---")
non_fws = [
    ("Car", Image.new("RGB", (224, 224), (200, 50, 50))),
    ("Face", Image.new("RGB", (224, 224), (255, 220, 190))),
    ("Tree", Image.new("RGB", (224, 224), (34, 139, 34))),
    ("Noise", Image.fromarray(np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))),
    ("Solid White", Image.new("RGB", (224, 224), (255, 255, 255))),
    ("Solid Black", Image.new("RGB", (224, 224), (0, 0, 0)))
]

for name, img in non_fws:
    c, prob = classify_with_dinov2(img)
    status = "REJECTED (Correct)" if c == "none" else f"FAILED ({c})"
    print(f"{name:15s} -> Cat: {c:8s} | {status}")
