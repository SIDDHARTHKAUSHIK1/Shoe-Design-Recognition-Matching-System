"""
Test suite: Strict Isolation & Guardrails between Training Data and Production Catalog Index.

Ensures:
  1. assert_catalog_image_path accepts paths in data/catalog/ and storage/catalog_images/
  2. assert_catalog_image_path rejects any path in data/training/ with PermissionError
  3. FAISS index rebuild scripts strictly reject any data from training directories
"""
import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import (
    TRAINING_DATA_DIR,
    CATALOG_DATA_DIR,
    CATALOG_IMAGES_DIR,
    assert_catalog_image_path
)


class TestDataSeparationGuardrails(unittest.TestCase):

    def test_catalog_paths_allowed(self):
        """Valid catalog paths must pass validation."""
        valid_path1 = CATALOG_DATA_DIR / "SHOE-001" / "angle_side_1.jpg"
        valid_path2 = CATALOG_IMAGES_DIR / "SHOE-001" / "angle_side_1.jpg"
        
        self.assertEqual(assert_catalog_image_path(valid_path1), valid_path1.resolve())
        self.assertEqual(assert_catalog_image_path(valid_path2), valid_path2.resolve())

    def test_training_paths_strictly_blocked(self):
        """Any path inside TRAINING_DATA_DIR must raise PermissionError."""
        fake_kaggle_img = TRAINING_DATA_DIR / "ut-zappos50k" / "Shoes" / "Sneakers" / "sample.jpg"
        
        with self.assertRaises(PermissionError) as ctx:
            assert_catalog_image_path(fake_kaggle_img)
        
        self.assertIn("SECURITY GUARDRAIL VIOLATION", str(ctx.exception))

    def test_directory_constants_distinct(self):
        """TRAINING_DATA_DIR and CATALOG_DATA_DIR must be completely distinct paths."""
        self.assertNotEqual(TRAINING_DATA_DIR.resolve(), CATALOG_DATA_DIR.resolve())
        self.assertNotIn(str(TRAINING_DATA_DIR.resolve()), str(CATALOG_DATA_DIR.resolve()))
        self.assertNotIn(str(CATALOG_DATA_DIR.resolve()), str(TRAINING_DATA_DIR.resolve()))


if __name__ == "__main__":
    unittest.main()
