"""
Test script for Shoe vs. Slipper vs. Non-Footwear Automatic Differentiation & Filtering.
"""
import glob
from PIL import Image, ImageDraw
import numpy as np
from backend.classifier import ZeroShotCategoryClassifier
from backend.matcher import ShoeMatcher
from backend import database as db

def create_test_images():
    """Create synthetic shoe, slipper, and random non-footwear test images."""
    # 1. Closed Shoe mockup
    shoe_img = Image.new("RGB", (224, 224), (245, 245, 245))
    draw = ImageDraw.Draw(shoe_img)
    draw.polygon([(30, 150), (60, 110), (120, 100), (170, 120), (200, 150), (195, 175), (30, 175)], fill=(40, 30, 20), outline=(20, 15, 10))
    draw.rectangle([30, 165, 195, 175], fill=(200, 200, 200))
    
    # 2. Open Slipper mockup
    slipper_img = Image.new("RGB", (224, 224), (245, 245, 245))
    draw = ImageDraw.Draw(slipper_img)
    draw.rectangle([30, 155, 195, 175], fill=(50, 120, 220))
    draw.arc([70, 110, 140, 160], start=180, end=360, fill=(30, 30, 30), width=12)
    
    # 3. Random Non-Footwear image (Car/Vehicle)
    car_img = Image.new("RGB", (224, 224), (210, 210, 210))
    draw = ImageDraw.Draw(car_img)
    draw.rectangle([30, 80, 190, 140], fill=(220, 30, 30))
    draw.ellipse([50, 130, 90, 170], fill=(10, 10, 10))
    draw.ellipse([130, 130, 170, 170], fill=(10, 10, 10))
    
    # 4. Random Noise image
    noise_img = Image.fromarray(np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))
    
    return shoe_img, slipper_img, car_img, noise_img

def run_tests():
    print("=" * 65)
    print("RUNNING SHOE / SLIPPER / NON-FOOTWEAR DETECTION TESTS")
    print("=" * 65)
    
    matcher = ShoeMatcher()
    classifier = ZeroShotCategoryClassifier.get_instance()
    
    sample_shoes = glob.glob("storage/catalog_images/SHOE-*/*.jpg") + glob.glob("storage/catalog_images/SHOE-*/*.jpeg")
    sample_slippers = glob.glob("storage/Slippers/*.jpeg") + glob.glob("storage/Slippers/*.jpg")
    
    shoe_synth, slipper_synth, car_img, noise_img = create_test_images()

    print("\n--- 1. Testing Zero-Shot Category Classification ---")
    if sample_shoes:
        cat_shoe, prob_shoe = classifier.classify_category(sample_shoes[0])
        print(f"Real Shoe ({sample_shoes[0]}): Detected='{cat_shoe}' (Conf: {prob_shoe*100:.1f}%)")
        assert cat_shoe == "shoe", f"Expected shoe, got {cat_shoe}"

    if sample_slippers:
        cat_slip, prob_slip = classifier.classify_category(sample_slippers[0])
        print(f"Real Slipper ({sample_slippers[0]}): Detected='{cat_slip}' (Conf: {prob_slip*100:.1f}%)")
        assert cat_slip == "slipper", f"Expected slipper, got {cat_slip}"

    cat_car, prob_car = classifier.classify_category(car_img)
    print(f"Random Car Image: Detected='{cat_car}' (Conf: {prob_car*100:.1f}%)")
    assert cat_car == "none", f"Expected 'none' for car image, got {cat_car}"

    cat_noise, prob_noise = classifier.classify_category(noise_img)
    print(f"Random Noise Image: Detected='{cat_noise}' (Conf: {prob_noise*100:.1f}%)")
    assert cat_noise == "none", f"Expected 'none' for noise image, got {cat_noise}"

    print("\n--- 2. Testing End-to-End Matcher with Category Filtering ---")
    
    # Test Query with a Real Shoe
    res_shoe = matcher.match_image(sample_shoes[0] if sample_shoes else shoe_synth, top_k=3)
    print(f"\n[Shoe Query Result]")
    print(f"  Detected Category: {res_shoe.get('detected_category')} (Footwear: {res_shoe.get('is_footwear_detected')})")
    print(f"  Matches Returned:  {len(res_shoe['matches'])}")
    assert res_shoe["is_footwear_detected"] is True
    assert len(res_shoe["matches"]) > 0
    for m in res_shoe["matches"]:
        norm_cat = db.normalize_category(m["category"])
        print(f"    #{m['rank']}: {m['design_id']} '{m['design_name']}' - Category: {m['category']} ({m['confidence_pct']}%)")
        assert norm_cat == "shoe", f"Expected shoe result, got {norm_cat}"

    # Test Query with a Real Slipper
    res_slipper = matcher.match_image(sample_slippers[0] if sample_slippers else slipper_synth, top_k=3)
    print(f"\n[Slipper Query Result]")
    print(f"  Detected Category: {res_slipper.get('detected_category')} (Footwear: {res_slipper.get('is_footwear_detected')})")
    print(f"  Matches Returned:  {len(res_slipper['matches'])}")
    assert res_slipper["is_footwear_detected"] is True
    assert len(res_slipper["matches"]) > 0
    for m in res_slipper["matches"]:
        norm_cat = db.normalize_category(m["category"])
        print(f"    #{m['rank']}: {m['design_id']} '{m['design_name']}' - Category: {m['category']} ({m['confidence_pct']}%)")
        assert norm_cat == "slipper", f"Expected slipper result, got {norm_cat}"

    # Test Query with a Random Non-Footwear Image
    res_random = matcher.match_image(car_img, top_k=3)
    print(f"\n[Random Non-Footwear Query Result]")
    print(f"  Detected Category: {res_random.get('detected_category')} (Footwear: {res_random.get('is_footwear_detected')})")
    print(f"  Matches Returned:  {len(res_random['matches'])}")
    print(f"  System Message:    {res_random.get('message')}")
    assert res_random["is_footwear_detected"] is False
    assert res_random["detected_category"] == "none"
    assert len(res_random["matches"]) == 0
    assert "No shoe or slipper detected" in res_random["message"]

    print("\n" + "=" * 65)
    print("ALL SHOE, SLIPPER & NON-FOOTWEAR REJECTION TESTS PASSED!")
    print("=" * 65)

if __name__ == "__main__":
    run_tests()
