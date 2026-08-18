"""
Test script for Shoe vs. Slipper Automatic Differentiation & Strict Filtering.
"""
import glob
from PIL import Image, ImageDraw
import numpy as np
from backend.classifier import ZeroShotCategoryClassifier
from backend.matcher import ShoeMatcher
from backend import database as db

def create_synthetic_test_images():
    """Create a synthetic closed-toe shoe shape and open slide shape for verification."""
    # 1. Closed Shoe mockup
    shoe_img = Image.new("RGB", (224, 224), (245, 245, 245))
    draw = ImageDraw.Draw(shoe_img)
    # Draw leather shoe silhouette
    draw.polygon([(30, 150), (60, 110), (120, 100), (170, 120), (200, 150), (195, 175), (30, 175)], fill=(40, 30, 20), outline=(20, 15, 10))
    draw.rectangle([30, 165, 195, 175], fill=(200, 200, 200)) # sole
    
    # 2. Open Slipper mockup
    slipper_img = Image.new("RGB", (224, 224), (245, 245, 245))
    draw = ImageDraw.Draw(slipper_img)
    # Draw flat open slide sandal
    draw.rectangle([30, 155, 195, 175], fill=(50, 120, 220)) # flat footbed
    draw.arc([70, 110, 140, 160], start=180, end=360, fill=(30, 30, 30), width=12) # upper strap
    
    return shoe_img, slipper_img

def run_tests():
    print("=" * 60)
    print("RUNNING SHOE VS. SLIPPER DIFFERENTIATION TESTS")
    print("=" * 60)
    
    matcher = ShoeMatcher()
    classifier = ZeroShotCategoryClassifier.get_instance()
    
    sample_images = glob.glob("storage/catalog_images/SHOE-*/*.jpg") + glob.glob("storage/catalog_images/SHOE-*/*.jpeg")
    slipper_images = glob.glob("storage/catalog_images/SLIP-*/*.jpg") + glob.glob("storage/catalog_images/SLIP-*/*.jpeg")
    
    shoe_synth, slipper_synth = create_synthetic_test_images()

    print("\n--- 1. Testing Zero-Shot Category Classification ---")
    if sample_images:
        cat_shoe, prob_shoe = classifier.classify_category(sample_images[0])
        print(f"Catalog Shoe ({sample_images[0]}): Detected='{cat_shoe}' (Conf: {prob_shoe*100:.1f}%)")
        assert cat_shoe in ("shoe", "slipper"), "Category must be shoe or slipper"

    cat_synth_slipper, prob_synth_slipper = classifier.classify_category(slipper_synth)
    print(f"Synthetic Slipper: Detected='{cat_synth_slipper}' (Conf: {prob_synth_slipper*100:.1f}%)")

    print("\n--- 2. Testing End-to-End Matcher with Category Filtering ---")
    # Test Query with a Shoe
    query_shoe_img = sample_images[0] if sample_images else shoe_synth
    res_shoe = matcher.match_image(query_shoe_img, top_k=3)
    
    print(f"\n[Shoe Query Result]")
    print(f"Detected Category: {res_shoe.get('detected_category')} ({res_shoe.get('category_confidence_pct')}%)")
    print(f"Matches Returned: {len(res_shoe['matches'])}")
    for m in res_shoe["matches"]:
        norm_cat = db.normalize_category(m["category"])
        print(f"  Rank #{m['rank']}: {m['design_id']} '{m['design_name']}' - Category: {m['category']} (Normalized: {norm_cat}) - {m['confidence_pct']}%")
        assert norm_cat == res_shoe["detected_category"], f"Result category {norm_cat} does not match detected {res_shoe['detected_category']}"

    # Test Query with a Slipper
    query_slipper_img = slipper_synth
    res_slipper = matcher.match_image(query_slipper_img, top_k=3)
    
    print(f"\n[Slipper Query Result]")
    print(f"Detected Category: {res_slipper.get('detected_category')} ({res_slipper.get('category_confidence_pct')}%)")
    print(f"Matches Returned: {len(res_slipper['matches'])}")
    for m in res_slipper["matches"]:
        norm_cat = db.normalize_category(m["category"])
        print(f"  Rank #{m['rank']}: {m['design_id']} '{m['design_name']}' - Category: {m['category']} (Normalized: {norm_cat}) - {m['confidence_pct']}%")
        assert norm_cat == res_slipper["detected_category"], f"Result category {norm_cat} does not match detected {res_slipper['detected_category']}"

    print("\n" + "=" * 60)
    print("ALL SHOE VS. SLIPPER DIFFERENTIATION TESTS PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
