import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageOps
import numpy as np

from backend.engine import EmbeddingEngine
from backend.matcher import ShoeMatcher

def run_tests():
    print("=== 1. Initializing Engine for Phase 3 TTA Verification ===")
    engine = EmbeddingEngine.get_instance()
    img_path = "storage/debug_user_shoe.jpg"
    img = Image.open(img_path)

    # 1. Single forward pass (TTA disabled)
    t0 = time.time()
    emb_no_tta = engine._compute_embedding(img, use_tta=False)
    lat_no_tta = (time.time() - t0) * 1000
    norm_no_tta = np.linalg.norm(emb_no_tta)
    print(f"No TTA Embedding -> Latency: {lat_no_tta:.2f}ms | Norm: {norm_no_tta:.4f}")
    assert abs(norm_no_tta - 1.0) < 1e-4

    # 2. TTA forward pass (2-crop batched)
    t0 = time.time()
    emb_tta = engine._compute_embedding(img, use_tta=True)
    lat_tta = (time.time() - t0) * 1000
    norm_tta = np.linalg.norm(emb_tta)
    print(f"TTA Batched (2-crop) -> Latency: {lat_tta:.2f}ms | Norm: {norm_tta:.4f}")
    assert abs(norm_tta - 1.0) < 1e-4
    assert lat_tta < 350.0  # Latency within acceptable CPU threshold

    # 3. Mirror invariance check
    # Query a flipped version of the shoe
    img_flipped = ImageOps.mirror(img)
    emb_flipped_tta = engine._compute_embedding(img_flipped, use_tta=True)
    
    # Cosine alignment between normal and flipped query embeddings with TTA
    sim_alignment = float(np.dot(emb_tta, emb_flipped_tta))
    print(f"Mirror Invariance Cosine Alignment: {sim_alignment:.4f}")
    assert sim_alignment > 0.95  # Highly robust against horizontal orientation changes

    # 4. End-to-End matching test with TTA enabled
    matcher = ShoeMatcher()
    res = matcher.match_image(img_flipped)
    top_m = res["matches"][0]
    print(f"Flipped Query Top Match: {top_m['design_name']} | Calibrated Conf: {top_m['confidence_pct']}% | Level: {top_m['match_level']}")
    assert res["is_footwear_detected"] is True
    assert res["reason"] == "matched"
    assert top_m["confidence_pct"] > 70.0

    print("\n>>> ALL PHASE 3 TTA TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    run_tests()
