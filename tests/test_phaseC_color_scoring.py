import os
import sys
import time
from PIL import Image, ImageDraw
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.color_extractor import ColorExtractor, TOTAL_COLOR_BINS
from backend.matcher import ShoeMatcher
from backend import database as db

def run_tests():
    print("=== 1. Testing ColorExtractor HSV Histogram & Palettes ===")
    # Red test image
    red_img = Image.new("RGB", (200, 200), color=(220, 20, 20))
    red_hist = ColorExtractor.extract_hsv_histogram(red_img)
    red_dom = ColorExtractor.extract_dominant_colors(red_img, k=3)
    
    assert len(red_hist) == TOTAL_COLOR_BINS
    assert np.isclose(np.sum(red_hist), 1.0)
    print(f"Red image dominant color: {red_dom[0]['hex']} ({red_dom[0]['percentage']}%)")

    # Blue test image
    blue_img = Image.new("RGB", (200, 200), color=(20, 20, 220))
    blue_hist = ColorExtractor.extract_hsv_histogram(blue_img)
    blue_dom = ColorExtractor.extract_dominant_colors(blue_img, k=3)
    print(f"Blue image dominant color: {blue_dom[0]['hex']} ({blue_dom[0]['percentage']}%)")

    # Color similarities
    sim_red_red = ColorExtractor.compute_color_similarity(red_hist, red_hist)
    sim_red_blue = ColorExtractor.compute_color_similarity(red_hist, blue_hist)
    print(f"Color Sim (Red vs Red): {sim_red_red:.4f}")
    print(f"Color Sim (Red vs Blue): {sim_red_blue:.4f}")

    assert sim_red_red > 0.98, f"Expected identical colors ~1.0, got {sim_red_red}"
    assert sim_red_blue < 0.20, f"Expected distinct colors < 0.20, got {sim_red_blue}"

    print("\n=== 2. Testing End-to-End Matcher with Color-Aware Scoring ===")
    test_shoe_path = "storage/debug_user_shoe.jpg"
    shoe_img = Image.open(test_shoe_path)

    matcher = ShoeMatcher()
    res = matcher.match_image(shoe_img)

    assert res["is_footwear_detected"] is True
    assert "query_dominant_colors" in res
    print(f"Query Dominant Colors: {res['query_dominant_colors']}")

    top_match = res["matches"][0]
    print(f"Top Match: {top_match['design_name']}")
    print(f"  - Design/Silhouette Cosine: {top_match['cosine_similarity']:.4f}")
    print(f"  - Color Similarity: {top_match.get('color_similarity', 1.0):.4f}")
    print(f"  - Combined Score: {top_match.get('combined_score', 0.0):.4f}")
    print(f"  - Calibrated Confidence: {top_match['confidence_pct']}% ({top_match['match_level']})")
    print(f"  - Catalog Dominant Colors: {top_match.get('dominant_colors', [])}")

    assert top_match["confidence_pct"] >= 80.0
    assert "combined_score" in top_match

    print("\n>>> ALL PHASE C COLOR-AWARE SCORING TESTS PASSED! <<<")

if __name__ == "__main__":
    run_tests()
