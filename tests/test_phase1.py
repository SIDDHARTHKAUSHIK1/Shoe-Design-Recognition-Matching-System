import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image
import numpy as np

from backend.matcher import ShoeMatcher

def run_tests():
    print("Initializing ShoeMatcher...")
    matcher = ShoeMatcher()

    # 1. Valid Shoe Test
    shoe_path = "storage/debug_user_shoe.jpg"
    if os.path.exists(shoe_path):
        res_shoe = matcher.match_image(shoe_path)
        print("=== 1. Valid Footwear Query ===")
        print(f"Detected Category: {res_shoe['detected_category']}")
        print(f"Match Reason: {res_shoe['reason']}")
        print(f"Score Margin: {res_shoe['score_margin']}")
        print(f"Neighborhood Density: {res_shoe['neighborhood_density']}")
        top_match = res_shoe['matches'][0]
        print(f"Top 1 Match: {top_match['design_name']} ({top_match['confidence_pct']}%)")
        assert res_shoe["is_footwear_detected"] is True
        assert res_shoe["reason"] == "matched"
        assert len(res_shoe["matches"]) > 0

    # 2. Blank Image Fallback Test
    blank_img = Image.new("RGB", (300, 300), (255, 255, 255))
    res_blank = matcher.match_image(blank_img)
    print("\n=== 2. Blank Image Fallback ===")
    print(f"Reason: {res_blank['reason']}")
    print(f"Footwear Detected: {res_blank['is_footwear_detected']}")
    assert res_blank["reason"] == "no_clear_object"
    assert res_blank["is_footwear_detected"] is False

    # 3. Pure Noise/Uniform Non-Footwear Test (with auto-crop disabled to test classifier threshold & density)
    from backend.classifier import ZeroShotCategoryClassifier
    classifier = ZeroShotCategoryClassifier.get_instance()
    
    # Synthetic random embedding vector (simulating non-footwear embedding in empty space)
    rng = np.random.RandomState(42)
    fake_random_emb = rng.randn(384).astype(np.float32)
    fake_random_emb /= np.linalg.norm(fake_random_emb)

    cat, prob, reason, diag = classifier.classify_category_detailed(
        image_input=blank_img,
        precomputed_embedding=fake_random_emb
    )
    print("\n=== 3. Non-Footwear / Synthetic Query ===")
    print(f"Detected Category: {cat}")
    print(f"Rejection Reason: {reason}")
    print(f"Diagnostics: {diag}")
    assert cat == "none"
    assert reason in ("below_threshold", "ambiguous_density")

    print("\n>>> ALL PHASE 1 TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    run_tests()
