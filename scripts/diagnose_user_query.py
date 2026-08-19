import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
import numpy as np
from backend.engine import EmbeddingEngine
from backend.classifier import ZeroShotCategoryClassifier
from backend.matcher import ShoeMatcher
from backend.vector_store import VectorStore
from backend import database as db

img_path = r"C:/Users/Siddharth Kaushik/.gemini/antigravity/brain/0fc6c58f-7dec-43ea-9262-04d4d2c0a5c8/.user_uploaded/media_1787118555504.png"
img_full = Image.open(img_path)
print("Screenshot size:", img_full.size)

# Crop the query shoe thumbnail from the screenshot:
# In the screenshot, the left panel has the query shoe photo
# Let's crop around [60, 280, 315, 640]
w, h = img_full.size
# Let's crop the actual shoe photo area from the left preview box
# Shoe photo is around x=[63, 318], y=[215, 365]
crop_box = (63, 215, 318, 365)
cropped_shoe = img_full.crop(crop_box).convert("RGB")
cropped_shoe.save("storage/debug_user_shoe.jpg")
print("Saved cropped query shoe to storage/debug_user_shoe.jpg")

engine = EmbeddingEngine.get_instance()
vs = VectorStore.get_instance()
clf = ZeroShotCategoryClassifier.get_instance()
matcher = ShoeMatcher()

emb = engine.get_embedding(cropped_shoe)
scores, ids = vs.search(emb, top_k=10)

print("\n--- FAISS Search Results on Cropped User Shoe ---")
for idx, (s, fid) in enumerate(zip(scores[0], ids[0])):
    meta = db.get_reference_image_by_faiss_id(int(fid))
    name = meta.get("name") if meta else "None"
    cat = meta.get("category") if meta else "None"
    print(f"Rank #{idx+1}: FAISS_ID={fid} | Score={s:.4f} | Name='{name}' | Cat='{cat}'")

cat, prob = clf.classify_category(cropped_shoe, precomputed_embedding=emb)
print(f"\nClassifier Result: Category='{cat}', Prob={prob:.4f}")

res = matcher.match_image(cropped_shoe)
print("\nMatcher Result:")
print("  Success:", res.get("success"))
print("  Detected Cat:", res.get("detected_category"))
print("  Footwear Detected:", res.get("is_footwear_detected"))
print("  Matches count:", len(res.get("matches", [])))
print("  Message:", res.get("message"))
