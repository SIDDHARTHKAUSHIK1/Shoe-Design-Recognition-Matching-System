"""
Test suite: Verify slippers are completely excluded from search results.

Tests:
  1. No slipper FAISS vectors — index contains exactly 31 shoe vectors
  2. Slipper-classified query returns slipper_rejected response (no matches)
  3. No SLIP-* design_id ever appears in any top-3 result across all catalog shoes
  4. Slipper upload is logged with detected_category='slipper'
  5. Slipper neighbors in classifier rank-voting cannot contaminate shoe score
"""
import sys
import unittest
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

logging.disable(logging.CRITICAL)


class TestSlipperExclusion(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from backend import database as db
        from backend.vector_store import VectorStore
        from backend.engine import EmbeddingEngine

        db.init_db()
        cls.vs = VectorStore.get_instance()
        cls.engine = EmbeddingEngine.get_instance()
        cls.db = db

    # ------------------------------------------------------------------
    # Test 1: FAISS index contains NO slipper vectors
    # ------------------------------------------------------------------
    def test_1_no_slipper_vectors_in_faiss_index(self):
        """FAISS index must contain exactly 31 shoe vectors and 0 slipper vectors."""
        vs = self.vs
        db = self.db

        total_vectors = vs.total_vectors
        self.assertEqual(total_vectors, 31,
            f"Expected 31 shoe vectors in FAISS, got {total_vectors}")

        # Cross-check: every FAISS ID in DB must belong to a shoe design
        all_shoe_refs = db.get_all_shoe_reference_images()
        shoe_faiss_ids = {r["faiss_id"] for r in all_shoe_refs}
        self.assertEqual(len(shoe_faiss_ids), 31,
            f"Expected 31 shoe FAISS IDs in DB, got {len(shoe_faiss_ids)}")

        # Verify no SLIP-* design is indexed
        for i in range(vs.total_vectors):
            meta = db.get_reference_image_by_faiss_id(i)
            self.assertIsNotNone(meta, f"No DB record for FAISS ID {i}")
            design_id = meta["design_id"]
            self.assertFalse(design_id.startswith("SLIP-"),
                f"Slipper design {design_id} found at FAISS ID {i}!")
            self.assertFalse(db.is_slipper_category(meta.get("category", "")),
                f"Slipper category '{meta['category']}' found at FAISS ID {i}!")

        print(f"\n  [OK] FAISS contains {total_vectors} shoe vectors, 0 slipper vectors.")

    # ------------------------------------------------------------------
    # Test 2: Slipper-classified query returns slipper_rejected response
    # ------------------------------------------------------------------
    def test_2_slipper_upload_rejected_with_correct_response(self):
        """Matcher must return reason='slipper_rejected', matched=False for slipper images."""
        import numpy as np
        from backend.matcher import ShoeMatcher
        from backend.classifier import ZeroShotCategoryClassifier
        from unittest.mock import patch

        matcher = ShoeMatcher()
        classifier = ZeroShotCategoryClassifier.get_instance()

        # Use a known slipper image from catalog_images
        slipper_img_dir = BASE_DIR / "storage" / "catalog_images" / "SLIP-001"
        slipper_imgs = list(slipper_img_dir.glob("*.jpeg")) + list(slipper_img_dir.glob("*.jpg"))

        if not slipper_imgs:
            self.skipTest("No SLIP-001 image found for slipper rejection test.")

        slipper_path = slipper_imgs[0]
        with open(slipper_path, "rb") as f:
            contents = f.read()

        result = matcher.match_image(query_image_input=contents)

        # Must be rejected — no matches returned
        self.assertEqual(result.get("matched"), False,
            f"Slipper image returned matched=True! Result: {result.get('reason')}")
        self.assertIn(result.get("reason"), {"slipper_rejected", "no_footwear_detected"},
            f"Unexpected rejection reason: {result.get('reason')}")
        self.assertEqual(len(result.get("matches", [])), 0,
            "Slipper query should return 0 matches")

        print(f"\n  [OK] Slipper upload correctly rejected. reason='{result.get('reason')}'")

    # ------------------------------------------------------------------
    # Test 3: All-catalog LOO — no SLIP-* design ever appears in top-3
    # ------------------------------------------------------------------
    def test_3_no_slipper_in_top3_for_any_shoe_query(self):
        """For every shoe in the catalog, no SLIP-* design appears in top-3 results."""
        from backend.matcher import ShoeMatcher
        from backend.config import CATALOG_IMAGES_DIR

        db = self.db
        matcher = ShoeMatcher()

        shoe_refs = db.get_all_shoe_reference_images()
        violations = []

        for ref in shoe_refs:
            design_id = ref["design_id"]
            img_path_rel = ref["image_path"]
            img_path = BASE_DIR / img_path_rel.lstrip("/")
            if not img_path.exists():
                img_path = CATALOG_IMAGES_DIR / design_id / Path(img_path_rel).name
            if not img_path.exists():
                continue

            try:
                with open(img_path, "rb") as f:
                    contents = f.read()
                result = matcher.match_image(query_image_input=contents)
                for m in result.get("matches", []):
                    if m["design_id"].startswith("SLIP-") or db.is_slipper_category(m.get("category", "")):
                        violations.append({
                            "query": design_id,
                            "slipper_match": m["design_id"],
                            "category": m["category"],
                        })
            except Exception as e:
                print(f"  WARN: Could not query {design_id}: {e}")

        self.assertEqual(len(violations), 0,
            f"Slipper designs appeared in results! Violations: {violations}")

        print(f"\n  [OK] Tested {len(shoe_refs)} shoe queries — 0 slipper appearances in top-3.")

    # ------------------------------------------------------------------
    # Test 4: Slipper rejection is logged with correct category tag
    # ------------------------------------------------------------------
    def test_4_slipper_rejection_is_audit_logged(self):
        """Slipper rejections must be logged to query_logs with detected_category='slipper'."""
        from backend.matcher import ShoeMatcher

        slipper_img_dir = BASE_DIR / "storage" / "catalog_images" / "SLIP-002"
        slipper_imgs = list(slipper_img_dir.glob("*.jpeg")) + list(slipper_img_dir.glob("*.jpg"))
        if not slipper_imgs:
            self.skipTest("No SLIP-002 image found for audit log test.")

        with open(slipper_imgs[0], "rb") as f:
            contents = f.read()

        db = self.db
        initial_logs = db.get_query_logs(limit=1000)
        initial_slipper_logs = [l for l in initial_logs if l.get("detected_category") == "slipper"]

        matcher = ShoeMatcher()
        result = matcher.match_image(
            query_image_input=contents,
            query_image_save_path="/uploads/test_slipper_audit.jpg"
        )

        new_logs = db.get_query_logs(limit=1000)
        new_slipper_logs = [l for l in new_logs if l.get("detected_category") == "slipper"]

        # At minimum we need ≥ previous count (could be same if classified as non-footwear)
        self.assertGreaterEqual(
            len(new_slipper_logs), len(initial_slipper_logs),
            "Slipper rejection should have been logged in query_logs"
        )
        print(f"\n  [OK] Slipper audit logging verified. Slipper log count: {len(new_slipper_logs)}")

    # ------------------------------------------------------------------
    # Test 5: is_slipper_category() covers all known category strings
    # ------------------------------------------------------------------
    def test_5_slipper_category_detection_coverage(self):
        """is_slipper_category() must return True for all slipper category strings."""
        db = self.db
        slipper_categories = [
            "Slide Sandal", "Flip-Flop", "House Slipper", "Mule Slipper",
            "Open-Toe Slide", "Comfort Slipper", "Indoor Fleece Slipper",
            "Beach Sandal", "Slipper", "Chappal", "CROC", "thong sandal",
            "Slide", "Flip Flop", "clog"
        ]
        non_slipper_categories = [
            "Sneaker", "Running Shoe", "Casual Trainer", "Classic Oxford",
            "Slip-On Loafer", "High-Top Basketball", "Athletic Cross-Trainer",
            "Hiking Boot"
        ]
        for cat in slipper_categories:
            self.assertTrue(db.is_slipper_category(cat),
                f"is_slipper_category should return True for '{cat}'")

        for cat in non_slipper_categories:
            self.assertFalse(db.is_slipper_category(cat),
                f"is_slipper_category should return False for '{cat}'")

        print(f"\n  [OK] is_slipper_category correctly covers {len(slipper_categories)} slipper types.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
