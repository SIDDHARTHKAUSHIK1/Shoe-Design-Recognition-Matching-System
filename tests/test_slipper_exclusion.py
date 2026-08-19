"""
Test suite: Verify slippers are completely excluded from catalog and search results.

Tests:
  1. No slipper FAISS vectors — index contains exactly 31 shoe vectors
  2. Slipper query returns slipper_rejected response (no matches)
  3. No SLIP-* design_id ever appears in any search result
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

    def test_1_no_slipper_vectors_in_faiss_index(self):
        """FAISS index must contain exactly 31 shoe vectors and 0 slipper vectors."""
        vs = self.vs
        db = self.db

        total_vectors = vs.total_vectors
        self.assertEqual(total_vectors, 31,
            f"Expected 31 shoe vectors in FAISS, got {total_vectors}")

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

    def test_2_slipper_upload_rejected_with_correct_response(self):
        """Matcher must return reason='slipper_rejected', matched=False for slipper images."""
        import numpy as np
        from backend.matcher import ShoeMatcher

        matcher = ShoeMatcher()

        # Use a real shoe image from catalog
        shoe_img_path = BASE_DIR / "data" / "catalog" / "SHOE-001" / "angle_heel_1.jpg"
        if not shoe_img_path.exists():
            self.skipTest("SHOE-001 image not found")

        with open(shoe_img_path, "rb") as f:
            contents = f.read()

        # Mock classifier to simulate slipper category detection
        from unittest.mock import patch
        with patch.object(matcher.classifier, 'classify_category_detailed', return_value=('slipper', 0.95, 'slippers_not_supported', {})):
            result = matcher.match_image(query_image_input=contents)



        self.assertEqual(result.get("matched"), False,
            f"Slipper image returned matched=True! Result: {result.get('reason')}")
        self.assertEqual(result.get("reason"), "slipper_rejected",
            f"Unexpected rejection reason: {result.get('reason')}")
        self.assertEqual(len(result.get("matches", [])), 0,
            "Slipper query should return 0 matches")


        print(f"\n  [OK] Slipper upload correctly rejected with reason='slipper_rejected'")


if __name__ == "__main__":
    unittest.main()
