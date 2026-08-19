import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import database as db
from scripts.export_hard_negatives import export_hard_negatives

def run_tests():
    print("=== 1. Initializing Database & Logging Query ===")
    db.init_db()
    
    # 1. Log a dummy query
    qid = db.log_query(
        query_image_path="storage/debug_user_shoe.jpg",
        top_match_id="SHOE_001",
        top_match_name="UrbanGlide Street Low",
        confidence_pct=95.4,
        latency_ms=210.5,
        results=[],
        detected_category="shoe"
    )
    print(f"Logged Test Query ID: {qid}")
    assert qid > 0

    # 2. Record feedback for this query
    fb1 = db.record_feedback(
        query_id=qid,
        user_verdict="wrong_match",
        correct_design_id="SHOE_002",
        notes="Actual shoe had rubber toe bumper"
    )
    print("Recorded Feedback 1:", fb1)
    assert fb1["user_verdict"] == "wrong_match"
    assert fb1["status"] == "recorded"

    fb2 = db.record_feedback(
        query_id=qid,
        user_verdict="not_in_catalog",
        correct_design_id=None,
        notes="Sample prototype from 2027 line"
    )
    print("Recorded Feedback 2:", fb2)
    assert fb2["user_verdict"] == "not_in_catalog"

    # 3. Retrieve feedback logs
    fb_logs = db.get_feedback_logs(limit=10)
    print(f"Retrieved {len(fb_logs)} feedback records.")
    assert len(fb_logs) >= 2
    assert fb_logs[0]["user_verdict"] in ("wrong_match", "not_in_catalog")

    # 4. Test hard negative export script
    test_export_dir = "storage/test_hard_negatives"
    manifest = export_hard_negatives(output_dir=test_export_dir)
    print("Export Manifest:", manifest["verdict_distribution"])
    assert manifest["total_exported"] >= 2
    assert os.path.exists(os.path.join(test_export_dir, "manifest.json"))

    print("\n>>> ALL PHASE 4 FEEDBACK LOOP TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    run_tests()
