"""
Test matching on user's query photo.
"""
import glob
from backend.matcher import ShoeMatcher

def test_query():
    matcher = ShoeMatcher()
    queries = sorted(glob.glob("storage/uploads/*.jpg") + glob.glob("storage/uploads/*.jpeg"))
    print(f"Total uploaded queries found: {len(queries)}")
    for q in queries[-3:]:
        print(f"\n--- Testing Query: {q} ---")
        res = matcher.match_image(q)
        print(f"Latency: {res['latency_ms']} ms")
        for m in res['matches']:
            print(f"  Rank #{m['rank']}: {m['design_id']} '{m['design_name']}' -> {m['confidence_pct']}% ({m['match_level_label']})")
            print(f"    Image: {m['best_matching_image_url']}")

if __name__ == "__main__":
    test_query()
