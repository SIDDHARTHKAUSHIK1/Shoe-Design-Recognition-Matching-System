"""
Live API Verification Test Script.
"""
import requests
import time
import glob

def test_api():
    print("Testing Shoe Design Matching API...")
    
    # 1. Test Stats
    r_stats = requests.get("http://127.0.0.1:8000/api/stats", timeout=5)
    print("1. GET /api/stats -> Status:", r_stats.status_code)
    print("   Data:", r_stats.json())
    assert r_stats.status_code == 200, "Stats endpoint failed"

    # 2. Test Designs List
    r_designs = requests.get("http://127.0.0.1:8000/api/designs", timeout=5)
    print("2. GET /api/designs -> Status:", r_designs.status_code)
    d_data = r_designs.json()
    print(f"   Total Designs: {d_data.get('total')}")
    assert r_designs.status_code == 200, "Designs endpoint failed"

    # 3. Test Match Query
    imgs = glob.glob("dataset/*.jpeg") + glob.glob("storage/catalog_images/*/*.jpg") + glob.glob("storage/catalog_images/*/*.jpeg")
    if imgs:
        test_img = imgs[0]
        print(f"3. Testing POST /api/match with {test_img}...")
        with open(test_img, "rb") as f:
            r_match = requests.post("http://127.0.0.1:8000/api/match", files={"file": ("shoe.jpg", f, "image/jpeg")}, data={"top_k": 3}, timeout=10)
        print("   Status:", r_match.status_code)
        m_data = r_match.json()
        print(f"   Inference Latency: {m_data.get('latency_ms')} ms")
        print(f"   Matches Returned: {len(m_data.get('matches', []))}")
        for m in m_data.get("matches", []):
            print(f"   - Rank #{m['rank']}: {m['design_id']} '{m['design_name']}' -> {m['confidence_pct']}% ({m['match_level_label']})")
            img_url = m['best_matching_image_url']
            r_img = requests.get(f"http://127.0.0.1:8000{img_url}")
            print(f"     Image URL: {img_url} -> Status: {r_img.status_code} ({len(r_img.content)} bytes)")
            assert r_img.status_code == 200, f"Image {img_url} failed to load"
            assert "placeholder" not in img_url, f"Image is still showing placeholder"

    # 4. Test Single Design Details & Warehouse Shelf Location
    r_detail = requests.get("http://127.0.0.1:8000/api/designs/SHOE-001", timeout=5)
    print("4. GET /api/designs/SHOE-001 -> Status:", r_detail.status_code)
    detail_data = r_detail.json()
    print(f"   Shelf Location: {detail_data.get('shelf_location')}")
    print(f"   Materials: {detail_data.get('materials')}")
    print(f"   Angles Count: {len(detail_data.get('reference_images', []))}")
    assert r_detail.status_code == 200, "Design detail endpoint failed"
    assert detail_data.get("shelf_location"), "Missing shelf location in detail response"

    # 5. Test Shelf Location Update API
    r_update = requests.put(
        "http://127.0.0.1:8000/api/designs/SHOE-001/location",
        data={"shelf_location": "Building A - Section 2 - Rack A-01 - Shelf 1", "production_status": "Active Sample Room"},
        timeout=5
    )
    print("5. PUT /api/designs/SHOE-001/location -> Status:", r_update.status_code)
    assert r_update.status_code == 200, "Shelf location update failed"

    # 6. Test Logs
    r_logs = requests.get("http://127.0.0.1:8000/api/logs?limit=5", timeout=5)
    print("6. GET /api/logs -> Status:", r_logs.status_code)
    print(f"   Total Logs Count: {r_logs.json().get('total')}")
    assert r_logs.status_code == 200, "Logs endpoint failed"

    print("\nALL API ENDPOINT VERIFICATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_api()
