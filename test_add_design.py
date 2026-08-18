"""
Test Incremental Add Design & Immediate Search Matching Race.
"""
import requests
import glob
from pathlib import Path

def test_incremental_addition_and_search():
    print("=" * 60)
    print("Testing Add New Design & Immediate Search Matching...")
    print("=" * 60)

    # 1. Fetch initial catalog stats
    r_stats1 = requests.get("http://127.0.0.1:8000/api/stats").json()
    init_designs = r_stats1["total_designs"]
    init_vectors = r_stats1["total_reference_images"]
    print(f"Initial Catalog: {init_designs} designs, {init_vectors} vector embeddings.")

    # 2. Pick a sample test image
    sample_imgs = glob.glob("storage/catalog_images/*/*.jpg") + glob.glob("storage/catalog_images/*/*.jpeg")
    assert sample_imgs, "No catalog images found for testing"
    test_img_path = sample_imgs[0]
    
    new_sku = f"SHOE-{init_designs + 1:03d}"
    print(f"\nAdding New Design: {new_sku} ('Imperial Monk Strap Sample')...")

    # 3. Post to /api/designs
    with open(test_img_path, "rb") as f:
        files = [("files", ("side_angle.jpg", f.read(), "image/jpeg"))]
        
    data = {
        "design_id": new_sku,
        "name": "Imperial Monk Strap Sample",
        "category": "Slip-On Loafer",
        "created_by": "Senior Design Master",
        "shelf_location": "Building A - Section 1 - Rack B-01 - Shelf 1",
        "production_status": "Master Craftsman Vault",
        "materials": "Full Grain Crust Calfskin / Blake Stitch Sole",
        "season": "Autumn/Winter 2026",
        "description": "Newly registered luxury factory prototype design."
    }

    r_add = requests.post("http://127.0.0.1:8000/api/designs", data=data, files=files)
    print("Add Design Response:", r_add.status_code, r_add.json())
    assert r_add.status_code == 200, "Failed to add new design"

    # 4. Verify stats increased
    r_stats2 = requests.get("http://127.0.0.1:8000/api/stats").json()
    print(f"Updated Catalog: {r_stats2['total_designs']} designs (+1), {r_stats2['total_reference_images']} vector embeddings (+1).")
    assert r_stats2["total_designs"] == init_designs + 1

    # 5. Query matching with this exact shoe image to test if it wins the matching race!
    print(f"\nQuerying visual matcher with photo of {new_sku}...")
    with open(test_img_path, "rb") as f:
        r_match = requests.post("http://127.0.0.1:8000/api/match", files={"file": ("query.jpg", f, "image/jpeg")})
    
    m_data = r_match.json()
    print(f"Match Query Latency: {m_data['latency_ms']} ms")
    top_matches = m_data.get("matches", [])
    print(f"Top Matches count: {len(top_matches)}")
    for m in top_matches:
        print(f"  Rank #{m['rank']}: {m['design_id']} '{m['design_name']}' -> {m['confidence_pct']}% ({m['match_level_label']})")
        print(f"    Shelf Location: {m.get('shelf_location')}")
        print(f"    Image: {m.get('best_matching_image_url')}")

    # Check that the newly added SKU is immediately in the top matches!
    matched_skus = [m["design_id"] for m in top_matches]
    print(f"\nMatched SKUs in Top-3: {matched_skus}")
    assert new_sku in matched_skus, f"Newly added design {new_sku} was not found in match results!"
    print(f"\nSUCCESS: Newly indexed design {new_sku} successfully entered the search race and matched!")

if __name__ == "__main__":
    test_incremental_addition_and_search()
