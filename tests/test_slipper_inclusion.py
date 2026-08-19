"""
Test suite: Verify slippers are included and searchable in the catalog system.

Tests:
  1. FAISS index contains 51 vectors (31 shoes + 20 slippers)
  2. Slipper-classified query returns matched=True with slipper matches
  3. Category filtering ensures slipper queries match slipper reference designs
"""
import sys
import unittest
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

logging.disable(logging.CRITICAL)


class TestSlipperInclusion(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from backend import database as db
        from backend.vector_store import VectorStore
        from backend.engine import EmbeddingEngine

        db.init_db()
        cls.vs = VectorStore.get_instance()
        cls.engine = EmbeddingEngine.get_instance()
        cls.db = db

    def test_1_faiss_contains_shoes_and_slippers(self):
        """FAISS index must contain 51 total vectors (both shoes and slippers)."""
        vs = self.vs
        db = self.db

        total_vectors = vs.total_vectors
        self.assertEqual(total_vectors, 51,
            f"Expected 51 total vectors in FAISS index, got {total_vectors}")

        slipper_count = 0
        shoe_count = 0
        for i in range(vs.total_vectors):
            meta = db.get_reference_image_by_faiss_id(i)
            self.assertIsNotNone(meta, f"No DB record for FAISS ID {i}")
            if meta["design_id"].startswith("SLIP-"):
                slipper_count += 1
            else:
                shoe_count += 1

        self.assertEqual(shoe_count, 31, f"Expected 31 shoe vectors in FAISS, got {shoe_count}")
        self.assertEqual(slipper_count, 20, f"Expected 20 slipper vectors in FAISS, got {slipper_count}")
        print(f"\n  [OK] FAISS index contains {shoe_count} shoe vectors and {slipper_count} slipper vectors.")

    def test_2_slipper_upload_returns_matched_results(self):
        """Slipper upload must be processed and match catalog slippers."""
        from backend.matcher import ShoeMatcher

        matcher = ShoeMatcher()

        # Use a known slipper image from catalog_images
        slipper_img_dir = BASE_DIR / "storage" / "catalog_images" / "SLIP-001"
        slipper_imgs = list(slipper_img_dir.glob("*.jpeg")) + list(slipper_img_dir.glob("*.jpg"))

        if not slipper_imgs:
            self.skipTest("No SLIP-001 image found for slipper matching test.")

        slipper_path = slipper_imgs[0]
        with open(slipper_path, "rb") as f:
            contents = f.read()

        result = matcher.match_image(query_image_input=contents)

        self.assertTrue(result.get("success"), "Matcher call failed")
        self.assertTrue(result.get("matched"), f"Slipper match returned matched=False! Reason: {result.get('reason')}")
        self.assertEqual(result.get("detected_category"), "slipper", f"Expected slipper category, got {result.get('detected_category')}")
        self.assertGreater(len(result.get("matches", [])), 0, "Expected at least 1 match for slipper query")
        
        top_match = result["matches"][0]
        self.assertTrue(top_match["design_id"].startswith("SLIP-"), f"Top match should be a slipper design, got {top_match['design_id']}")
        print(f"\n  [OK] Slipper query successfully matched {top_match['design_id']} ({top_match['design_name']})")


if __name__ == "__main__":
    unittest.main()
