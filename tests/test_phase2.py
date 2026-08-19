import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import load_thresholds_config
from backend import database as db
from backend.matcher import ShoeMatcher, classify_match_level

def run_tests():
    print("=== 1. Testing Thresholds Config Loading ===")
    cfg = load_thresholds_config()
    print("Loaded Config Categories:", list(cfg.keys()))
    assert "shoe" in cfg
    assert "slipper" in cfg
    assert "platt_scaling" in cfg["shoe"]

    print("\n=== 2. Testing Calibrated Confidence (Platt Scaling) ===")
    # High similarity (>0.80) should yield high confidence (>90%)
    conf_high = db.calculate_calibrated_confidence(0.85, category="shoe")
    print(f"Similarity 0.85 -> Calibrated Confidence: {conf_high}%")
    assert conf_high > 90.0

    # Moderate similarity (0.65 - 0.75) should yield moderate confidence (65% - 90%)
    conf_mod = db.calculate_calibrated_confidence(0.70, category="shoe")
    print(f"Similarity 0.70 -> Calibrated Confidence: {conf_mod}%")
    assert 60.0 <= conf_mod <= 90.0

    # Low similarity (<0.45) should yield low confidence (<15%)
    conf_low = db.calculate_calibrated_confidence(0.40, category="shoe")
    print(f"Similarity 0.40 -> Calibrated Confidence: {conf_low}%")
    assert conf_low < 20.0

    print("\n=== 3. Testing Per-Category Match Level Classification ===")
    lvl_code, lvl_label, color = classify_match_level(conf_high, category="shoe")
    print(f"Confidence {conf_high}% -> Level: {lvl_code} ({lvl_label}, {color})")
    assert lvl_code == "HIGH"
    assert color == "green"

    print("\n=== 4. Testing End-to-End Shoe Matcher with Calibrated Scores ===")
    matcher = ShoeMatcher()
    res = matcher.match_image("storage/debug_user_shoe.jpg")
    print(f"Detected Category: {res['detected_category']}")
    print(f"Reason: {res['reason']}")
    top_m = res["matches"][0]
    print(f"Top 1 Match: {top_m['design_name']} | Cosine: {top_m['cosine_similarity']} | Calibrated Conf: {top_m['confidence_pct']}% | Match Level: {top_m['match_level']}")
    assert res["is_footwear_detected"] is True
    assert top_m["confidence_pct"] > 50.0

    print("\n>>> ALL PHASE 2 TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    run_tests()
