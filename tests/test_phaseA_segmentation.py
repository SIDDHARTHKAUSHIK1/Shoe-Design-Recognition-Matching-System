import os
import sys
import time
from PIL import Image
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.foreground import isolate_foreground
from backend.matcher import ShoeMatcher
from scripts.reprocess_catalog import reprocess_catalog

def run_tests():
    print("=== 1. Testing Neutral Background Fill Segmentation ===")
    img_path = "storage/debug_user_shoe.jpg"
    img = Image.open(img_path)

    neutral_img, reason, meta = isolate_foreground(img, padding_ratio=0.08)
    print(f"Original size: {img.size} -> Processed size: {neutral_img.size}")
    print(f"Crop Meta: {meta}")
    assert reason is None
    assert meta["segmented"] is True
    assert meta["cropped"] is True
    
    # Check that corners of neutral_img are neutral studio fill (close to 248, 248, 248)
    arr = np.array(neutral_img)
    corner_pixel = arr[0, 0]
    print(f"Top-Left Corner Pixel Color (should be ~248 neutral studio): {corner_pixel}")
    # Verify corner is neutral light gray / white (not dark / floor color)
    assert np.all(corner_pixel >= 240)

    # 2. Testing Low Coverage Rejection
    print("\n=== 2. Testing Non-Object Low Coverage Fallback ===")
    blank_img = Image.new("RGB", (300, 300), color=(128, 128, 128))
    _, blank_reason, _ = isolate_foreground(blank_img)
    print(f"Blank Image Rejection Reason: {blank_reason}")
    assert blank_reason == "no_clear_object"

    # 3. Testing Catalog Reprocessing
    print("\n=== 3. Testing Catalog Reprocessing & Vector Store Rebuilding ===")
    reprocess_catalog()

    # 4. Testing End-to-End Query Matching
    print("\n=== 4. Testing End-to-End Matching with Neutral Segmented Catalog ===")
    matcher = ShoeMatcher()
    res = matcher.match_image(img)
    print(f"Query Detected Category: {res['detected_category']} | Reason: {res['reason']}")
    top_m = res["matches"][0]
    print(f"Top 1 Match: {top_m['design_name']} | Calibrated Conf: {top_m['confidence_pct']}% | Level: {top_m['match_level']}")
    assert res["is_footwear_detected"] is True
    assert res["reason"] == "matched"
    assert top_m["confidence_pct"] >= 80.0

    print("\n>>> ALL PHASE A SEGMENTATION & REPROCESSING TESTS PASSED! <<<")

if __name__ == "__main__":
    run_tests()
