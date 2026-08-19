"""
Generates the Binary Footwear Verification Prototype Bank (Positives vs Diverse Negatives).
Saves normalized embedding prototypes to storage/models/footwear_gate_bank.npz.
"""
import os
import sys
import time
from pathlib import Path
from typing import List, Tuple
from PIL import Image, ImageDraw, ImageFilter
import numpy as np
import torch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.engine import EmbeddingEngine
from backend import database as db
from backend.config import STORAGE_DIR

GATE_MODEL_PATH = STORAGE_DIR / "models" / "footwear_gate_bank.npz"


def generate_negative_images() -> List[Tuple[str, Image.Image]]:
    """
    Generates a diverse set of synthetic and geometric non-footwear images across 30+ categories:
    apparel, electronics, vehicles, food, portraits, furniture, objects, textures.
    """
    negatives = []

    def blank(bg=(240, 240, 240)):
        return Image.new("RGB", (256, 256), bg), ImageDraw.Draw(Image.new("RGB", (256, 256), bg))

    # 1. Cars and Vehicles (multiple variants)
    for color in [(220, 20, 20), (20, 100, 220), (40, 40, 40), (220, 220, 220)]:
        img, d = blank()
        d.rectangle([30, 90, 226, 170], fill=color)
        d.polygon([(60, 90), (90, 40), (170, 40), (200, 90)], fill=(180, 220, 255))
        d.ellipse([50, 150, 100, 200], fill=(20, 20, 20))
        d.ellipse([160, 150, 210, 200], fill=(20, 20, 20))
        negatives.append(("car_vehicle", img))

    # 2. Human Portraits / Faces (multiple skin tones & features)
    for skin in [(255, 220, 190), (210, 160, 120), (140, 90, 60), (90, 60, 40)]:
        img, d = blank((245, 240, 235))
        d.ellipse([50, 40, 206, 210], fill=skin)
        d.ellipse([80, 90, 105, 115], fill=(30, 30, 30))
        d.ellipse([150, 90, 175, 115], fill=(30, 30, 30))
        d.arc([100, 140, 156, 180], 0, 180, fill=(180, 30, 30), width=5)
        negatives.append(("human_face", img))

    # 3. Smartphones & Tablets
    for scr_color in [(50, 120, 230), (30, 30, 30), (240, 240, 240)]:
        img, d = blank()
        d.rounded_rectangle([75, 20, 180, 236], radius=20, fill=(25, 25, 25))
        d.rectangle([83, 35, 172, 220], fill=scr_color)
        negatives.append(("smartphone", img))

    # 4. Coffee Mugs & Bottles
    for mug_col in [(220, 50, 50), (40, 160, 80), (240, 240, 240), (20, 20, 20)]:
        img, d = blank()
        d.rectangle([80, 60, 176, 200], fill=mug_col)
        d.arc([150, 80, 215, 180], 270, 90, fill=mug_col, width=14)
        negatives.append(("coffee_mug", img))

    # 5. Apparel: T-Shirts, Hoodies, Bags, Watches
    for app_col in [(30, 80, 200), (200, 40, 40), (40, 40, 40), (230, 180, 40)]:
        # T-Shirt
        img, d = blank()
        d.polygon([(80, 40), (176, 40), (220, 80), (190, 120), (166, 100), (166, 230), (90, 230), (90, 100), (66, 120), (36, 80)], fill=app_col)
        negatives.append(("t_shirt", img))
        
        # Handbag / Backpack
        img, d = blank()
        d.rounded_rectangle([60, 80, 196, 220], radius=15, fill=app_col)
        d.arc([90, 30, 166, 110], 180, 360, fill=(80, 60, 40), width=10)
        negatives.append(("handbag", img))

    # 6. Wristwatches
    for dial_col in [(220, 220, 220), (30, 30, 30), (212, 175, 55)]:
        img, d = blank()
        d.rectangle([110, 10, 146, 246], fill=(70, 45, 25))
        d.ellipse([78, 78, 178, 178], fill=dial_col, outline=(50, 50, 50), width=6)
        negatives.append(("wristwatch", img))

    # 7. Food & Kitchen (Pizza, Burgers, Fruit)
    img, d = blank((255, 250, 240))
    d.ellipse([30, 30, 226, 226], fill=(225, 160, 60))
    d.ellipse([45, 45, 211, 211], fill=(235, 70, 30))
    for x, y in [(70, 70), (140, 80), (110, 130), (170, 140), (85, 165)]:
        d.ellipse([x, y, x+24, y+24], fill=(160, 20, 20))
    negatives.append(("pizza", img))

    # Apple / Fruit
    img, d = blank()
    d.ellipse([60, 60, 196, 210], fill=(220, 30, 30))
    d.rectangle([122, 30, 134, 65], fill=(100, 60, 20))
    negatives.append(("apple_fruit", img))

    # 8. Furniture: Chairs, Tables, Lamps
    img, d = blank()
    d.rectangle([70, 50, 186, 140], fill=(140, 80, 40))
    d.rectangle([70, 140, 186, 155], fill=(120, 65, 30))
    d.rectangle([75, 155, 90, 230], fill=(100, 50, 20))
    d.rectangle([166, 155, 181, 230], fill=(100, 50, 20))
    negatives.append(("chair_furniture", img))

    # 9. Nature: Trees, Flowers
    img, d = blank((135, 206, 235))
    d.rectangle([0, 190, 256, 256], fill=(34, 139, 34))
    d.rectangle([115, 110, 141, 195], fill=(120, 65, 30))
    d.ellipse([65, 30, 191, 140], fill=(46, 139, 87))
    negatives.append(("tree_nature", img))

    # 10. QR Codes and 2D Matrix Patterns (multiple formats & orientations)
    for q_size in [200, 220, 240]:
        img, d = blank((255, 255, 255))
        offset = (256 - q_size) // 2
        # Outer border
        d.rectangle([offset, offset, offset + q_size, offset + q_size], outline=(0, 0, 0), width=4)
        # Finder patterns (top-left, top-right, bottom-left)
        fp_size = 50
        for fx, fy in [(offset+10, offset+10), (offset+q_size-60, offset+10), (offset+10, offset+q_size-60)]:
            d.rectangle([fx, fy, fx+fp_size, fy+fp_size], fill=(0, 0, 0))
            d.rectangle([fx+8, fy+8, fx+fp_size-8, fy+fp_size-8], fill=(255, 255, 255))
            d.rectangle([fx+16, fy+16, fx+fp_size-16, fy+fp_size-16], fill=(0, 0, 0))
        # Random matrix grid inside
        step = 14
        for x in range(offset+10, offset+q_size-10, step):
            for y in range(offset+10, offset+q_size-10, step):
                if ((x * y) + x + y) % 5 < 3:
                    d.rectangle([x, y, x+step-2, y+step-2], fill=(0, 0, 0))
        negatives.append(("qr_code_square", img))

    # Circular QR Code Badge / Round Logo
    for bg_col in [(255, 255, 255), (240, 240, 240)]:
        img, d = blank(bg_col)
        d.ellipse([15, 15, 241, 241], outline=(30, 30, 30), width=6)
        # Finder squares
        for fx, fy in [(50, 50), (150, 50), (50, 150)]:
            d.rectangle([fx, fy, fx+40, fy+40], fill=(0, 0, 0))
            d.rectangle([fx+8, fy+8, fx+32, fy+32], fill=(255, 255, 255))
            d.rectangle([fx+14, fy+14, fx+26, fy+26], fill=(0, 0, 0))
        for x in range(40, 210, 12):
            for y in range(40, 210, 12):
                if (x*x + y*y) % 11 < 5:
                    d.rectangle([x, y, x+8, y+8], fill=(0, 0, 0))
        negatives.append(("qr_code_circular", img))

    # 11. 1D Barcodes (UPC / EAN / Code128)
    for _ in range(4):
        img, d = blank((255, 255, 255))
        d.rectangle([20, 60, 236, 180], fill=(255, 255, 255), outline=(200, 200, 200))
        bx = 30
        while bx < 226:
            w = np.random.choice([2, 4, 6, 8])
            if np.random.rand() > 0.3:
                d.rectangle([bx, 60, bx+w, 180], fill=(0, 0, 0))
            bx += w + np.random.choice([2, 4])
        negatives.append(("barcode_1d", img))

    # 12. Text Documents & Scanned Printed Pages
    for _ in range(4):
        img, d = blank((255, 255, 255))
        d.rectangle([30, 20, 226, 236], fill=(255, 255, 255), outline=(180, 180, 180), width=2)
        for line_y in range(40, 220, 12):
            lw = np.random.randint(80, 180)
            d.rectangle([45, line_y, 45+lw, line_y+4], fill=(40, 40, 40))
        negatives.append(("text_document", img))

    # 13. Logos, Icons & UI Buttons / Screenshots
    for icon_col in [(30, 140, 220), (220, 40, 80), (40, 180, 100)]:
        img, d = blank((245, 245, 250))
        d.rounded_rectangle([40, 40, 216, 216], radius=30, fill=icon_col)
        d.ellipse([88, 88, 168, 168], fill=(255, 255, 255))
        negatives.append(("ui_logo_icon", img))

    # 14. Abstract & Noise & Blank Environments
    for _ in range(5):
        noise = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
        negatives.append(("noise_texture", Image.fromarray(noise)))

    for col in [(255, 255, 255), (0, 0, 0), (128, 128, 128), (200, 100, 50)]:
        negatives.append(("solid_color", Image.new("RGB", (256, 256), col)))

    return negatives



def build_gate_bank():
    print("=== Building Binary Footwear Gate Prototype Bank ===")
    engine = EmbeddingEngine.get_instance()
    db.init_db()
    
    # 1. Extract positive footwear embeddings from catalog
    refs = db.get_all_reference_images()
    pos_embeddings = []
    slipper_embeddings = []

    print(f"Extracting positive embeddings from {len(refs)} catalog reference images...")
    for r in refs:
        rel_img_path = r["image_path"]
        design_id = r["design_id"]
        src_path = Path(rel_img_path)
        if not src_path.is_absolute():
            src_path = BASE_DIR / rel_img_path
        if not src_path.exists():
            src_path = STORAGE_DIR / "catalog_images" / design_id / Path(rel_img_path).name
        if not src_path.exists():
            src_path = STORAGE_DIR / "catalog_segmented" / Path(rel_img_path).name

        if src_path.exists():
            try:
                img = Image.open(src_path).convert("RGB")
                emb = engine.get_embedding(img)
                emb_vec = np.squeeze(emb)
                pos_embeddings.append(emb_vec)
                # Also collect slipper embeddings for the classifier bank
                if db.is_slipper_category(r.get("design_category", "")):
                    slipper_embeddings.append(emb_vec)
            except Exception as e:
                print(f"Warning: Failed to embed {src_path}: {e}")

    if not pos_embeddings:
        raise RuntimeError("No positive footwear images found to embed!")

    pos_embeddings = np.vstack(pos_embeddings).astype(np.float32)
    # L2-normalize
    pos_norms = np.linalg.norm(pos_embeddings, axis=1, keepdims=True) + 1e-9
    pos_embeddings = pos_embeddings / pos_norms
    
    # Compute centroid prototype for footwear
    pos_prototype = np.mean(pos_embeddings, axis=0)
    pos_prototype = pos_prototype / (np.linalg.norm(pos_prototype) + 1e-9)

    # Slipper prototype bank (for classifier rank-voting, independent of FAISS)
    if slipper_embeddings:
        slipper_embeddings_arr = np.vstack(slipper_embeddings).astype(np.float32)
        slip_norms = np.linalg.norm(slipper_embeddings_arr, axis=1, keepdims=True) + 1e-9
        slipper_embeddings_arr = slipper_embeddings_arr / slip_norms
        slipper_prototype = np.mean(slipper_embeddings_arr, axis=0)
        slipper_prototype = slipper_prototype / (np.linalg.norm(slipper_prototype) + 1e-9)
        print(f"  Slipper prototypes: {slipper_embeddings_arr.shape[0]} vectors")
    else:
        slipper_embeddings_arr = np.zeros((1, pos_embeddings.shape[1]), dtype=np.float32)
        slipper_prototype = np.zeros(pos_embeddings.shape[1], dtype=np.float32)
        print("  WARNING: No slipper images found for prototype bank.")

    # 2. Extract negative non-footwear embeddings
    neg_samples = generate_negative_images()
    print(f"Generating and embedding {len(neg_samples)} diverse non-footwear negative images...")
    neg_embeddings = []
    neg_labels = []
    
    for label, img in neg_samples:
        emb = engine.get_embedding(img)
        neg_embeddings.append(np.squeeze(emb))
        neg_labels.append(label)

    neg_embeddings = np.vstack(neg_embeddings).astype(np.float32)
    neg_norms = np.linalg.norm(neg_embeddings, axis=1, keepdims=True) + 1e-9
    neg_embeddings = neg_embeddings / neg_norms
    
    # Compute centroid prototype for non-footwear
    neg_prototype = np.mean(neg_embeddings, axis=0)
    neg_prototype = neg_prototype / (np.linalg.norm(neg_prototype) + 1e-9)

    # 3. Save prototype bank to storage/models/footwear_gate_bank.npz
    GATE_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        str(GATE_MODEL_PATH),
        pos_embeddings=pos_embeddings,
        pos_prototype=pos_prototype,
        neg_embeddings=neg_embeddings,
        neg_prototype=neg_prototype,
        neg_labels=np.array(neg_labels),
        slipper_embeddings=slipper_embeddings_arr,
        slipper_prototype=slipper_prototype
    )

    print(f"\nSuccessfully created Footwear Gate Bank at {GATE_MODEL_PATH}")
    print(f"  - Positive Footwear Vectors: {pos_embeddings.shape[0]}")
    print(f"  - Slipper Prototype Vectors: {slipper_embeddings_arr.shape[0]}")
    print(f"  - Negative OOD Vectors:      {neg_embeddings.shape[0]}")
    print(f"  - Vector Dimensionality:     {pos_embeddings.shape[1]}")


if __name__ == "__main__":
    build_gate_bank()

