import os, sys
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

def classify_fast(img_or_path, precomputed_emb=None):
    if precomputed_emb is not None:
        emb = precomputed_emb
    else:
        emb = engine.get_embedding(img_or_path)
        
    scores, ids = vs.search(emb, top_k=5)
    raw_scores = scores[0] if len(scores) > 0 else []
    raw_ids = ids[0] if len(ids) > 0 else []
    
    max_sim = float(raw_scores[0]) if len(raw_scores) > 0 else 0.0
    
    # 1. Non-Footwear Rejection:
    # Max similarity to catalog footwear is below 0.28
    if max_sim < 0.28:
        conf = max(0.0, min(1.0, 1.0 - max_sim))
        return "none", round(conf, 4)
        
    # 2. Check top match and top 3 nearest neighbors
    top_meta = db.get_reference_image_by_faiss_id(int(raw_ids[0]))
    top_cat = db.normalize_category(top_meta.get("category", "")) if top_meta else "shoe"
    
    # Vote across top 3 with exponential decay
    shoe_score = 0.0
    slipper_score = 0.0
    for idx, (s, fid) in enumerate(zip(raw_scores[:3], raw_ids[:3])):
        if fid < 0: continue
        meta = db.get_reference_image_by_faiss_id(int(fid))
        if not meta: continue
        cat = db.normalize_category(meta.get("category", ""))
        rank_weight = (1.0 / (idx + 1)) * float(s)
        if cat == "shoe":
            shoe_score += rank_weight
        elif cat == "slipper":
            slipper_score += rank_weight
            
    if slipper_score > shoe_score:
        prob = slipper_score / (shoe_score + slipper_score + 1e-9)
        return "slipper", round(float(prob), 4)
    else:
        prob = shoe_score / (shoe_score + slipper_score + 1e-9)
        return "shoe", round(float(prob), 4)

print("--- Testing Shoes ---")
shoe_files = sorted(glob.glob("storage/catalog_images/SHOE-*/*.jpg") + glob.glob("storage/catalog_images/SHOE-*/*.jpeg"))
correct_shoes = 0
for p in shoe_files[:20]:
    c, prob = classify_fast(p)
    if c == "shoe": correct_shoes += 1
    print(f"Shoe ({p.split('/')[-1]}): Cat = {c} ({prob:.2f})")
print(f"Shoes accuracy: {correct_shoes}/20")

print("\n--- Testing All 20 Slippers ---")
slipper_files = sorted(glob.glob("storage/Slippers/*.jpeg") + glob.glob("storage/Slippers/*.jpg"))
correct_slippers = 0
for p in slipper_files:
    c, prob = classify_fast(p)
    if c == "slipper": correct_slippers += 1
    print(f"Slipper ({p.split('/')[-1]}): Cat = {c} ({prob:.2f})")
print(f"Slippers accuracy: {correct_slippers}/{len(slipper_files)}")

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
    c, prob = classify_fast(img)
    status = "REJECTED (Correct)" if c == "none" else f"FAILED ({c})"
    print(f"{name:15s} -> Cat: {c:8s} | {status}")
