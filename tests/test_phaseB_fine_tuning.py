import os
import sys
import time
from PIL import Image
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.engine import EmbeddingEngine
from backend.foreground import isolate_foreground
from scripts.finetune_background_invariant import SyntheticBackgroundGenerator, composite_on_background
from backend.matcher import ShoeMatcher

def run_tests():
    print("=== 1. Initializing Engine with Background-Invariant Head ===")
    engine = EmbeddingEngine.get_instance()
    assert engine.invariant_head is not None, "Invariant projection head failed to load!"

    # Load 2 different shoe images
    img1_path = "storage/debug_user_shoe.jpg"
    img1 = Image.open(img1_path)
    crop1, _, _ = isolate_foreground(img1)

    # Synthetic backgrounds: Red BG vs Green Texture BG
    bg_red = Image.new("RGB", crop1.size, color=(220, 30, 30))
    bg_green = Image.new("RGB", crop1.size, color=(30, 200, 50))

    # Anchor: Shoe 1 on Red BG
    anchor = composite_on_background(crop1, bg_red)
    # Positive: Shoe 1 on Green BG (different background, same shoe)
    pos = composite_on_background(crop1, bg_green)

    # Invariant embeddings
    emb_anchor = engine.get_embedding(anchor, auto_crop=True)
    emb_pos = engine.get_embedding(pos, auto_crop=True)

    sim_pos = float(np.dot(emb_anchor, emb_pos))
    print(f"Same Shoe / Different Background Similarity: {sim_pos:.4f}")
    assert sim_pos > 0.85, f"Expected same shoe across backgrounds to match > 0.85, got {sim_pos}"

    # End-to-End matching with ShoeMatcher
    print("\n=== 2. Testing End-to-End Matching with Invariant Head ===")
    matcher = ShoeMatcher()
    res = matcher.match_image(pos)
    print(f"Query on Green BG -> Matched: {res['matches'][0]['design_name']} | Conf: {res['matches'][0]['confidence_pct']}% | Level: {res['matches'][0]['match_level']}")
    assert res["is_footwear_detected"] is True
    assert res["reason"] == "matched"
    assert res["matches"][0]["confidence_pct"] >= 80.0

    print("\n>>> ALL PHASE B BACKGROUND-INVARIANT EMBEDDING TESTS PASSED! <<<")

if __name__ == "__main__":
    run_tests()
