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

# Load all shoes and slippers embeddings
shoes_paths = glob.glob("storage/catalog_images/SHOE-*/*.jpg") + glob.glob("storage/catalog_images/SHOE-*/*.jpeg")
slippers_paths = glob.glob("storage/Slippers/*.jpeg") + glob.glob("storage/Slippers/*.jpg")

print(f"Catalog: {len(shoes_paths)} shoe images, {len(slippers_paths)} slipper images")

# Generate test non-footwear images
test_non_fw = []
# 1. Car
img_car = Image.new("RGB", (224, 224), (230, 230, 230))
d = ImageDraw.Draw(img_car)
d.rectangle([20, 80, 200, 150], fill=(200, 30, 30))
d.ellipse([40, 135, 85, 180], fill=(20, 20, 20))
d.ellipse([135, 135, 180, 180], fill=(20, 20, 20))
test_non_fw.append(("Car", img_car))

# 2. Face
img_face = Image.new("RGB", (224, 224), (245, 235, 220))
d = ImageDraw.Draw(img_face)
d.ellipse([50, 40, 170, 180], fill=(255, 215, 180))
test_non_fw.append(("Face", img_face))

# 3. Phone
img_phone = Image.new("RGB", (224, 224), (240, 240, 240))
d = ImageDraw.Draw(img_phone)
d.rounded_rectangle([70, 20, 150, 200], radius=15, fill=(40, 40, 40))
test_non_fw.append(("Smartphone", img_phone))

# 4. Pizza
img_pizza = Image.new("RGB", (224, 224), (250, 245, 235))
d = ImageDraw.Draw(img_pizza)
d.ellipse([30, 30, 190, 190], fill=(220, 160, 60))
test_non_fw.append(("Pizza", img_pizza))

# 5. Tree
img_tree = Image.new("RGB", (224, 224), (135, 206, 235))
d = ImageDraw.Draw(img_tree)
d.rectangle([0, 160, 224, 224], fill=(34, 139, 34))
test_non_fw.append(("Tree", img_tree))

# 6. Noise
img_noise = Image.fromarray(np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))
test_non_fw.append(("Noise", img_noise))

# Test max similarity in FAISS for footwear vs non-footwear
print("\n--- FAISS Max Similarity for Real Footwear vs Non-Footwear ---")

# Sample 5 real shoes
for p in shoes_paths[:5]:
    emb = engine.get_embedding(p)
    scores, ids = vs.search(emb, top_k=5)
    max_score = float(scores[0][0])
    top_meta = db.get_reference_image_by_faiss_id(int(ids[0][0]))
    cat = top_meta.get("category", "unknown") if top_meta else "none"
    print(f"Shoe ({p.split('/')[-1]}): Max Sim = {max_score:.4f} | Top Match Cat = {cat}")

# Sample 5 real slippers
for p in slippers_paths[:5]:
    emb = engine.get_embedding(p)
    scores, ids = vs.search(emb, top_k=5)
    max_score = float(scores[0][0])
    top_meta = db.get_reference_image_by_faiss_id(int(ids[0][0]))
    cat = top_meta.get("category", "unknown") if top_meta else "none"
    print(f"Slipper ({p.split('/')[-1]}): Max Sim = {max_score:.4f} | Top Match Cat = {cat}")

# Test Non-Footwear images
for name, img in test_non_fw:
    emb = engine.get_embedding(img)
    scores, ids = vs.search(emb, top_k=5)
    max_score = float(scores[0][0])
    top_meta = db.get_reference_image_by_faiss_id(int(ids[0][0]))
    cat = top_meta.get("category", "unknown") if top_meta else "none"
    print(f"Non-Footwear [{name:10s}]: Max Sim = {max_score:.4f} | Top Match Cat = {cat}")
