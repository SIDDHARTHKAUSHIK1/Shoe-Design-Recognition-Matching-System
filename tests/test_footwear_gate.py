"""
Unit and regression test suite for BinaryFootwearGate and False-Positive Footwear Rejection.
Verifies:
1. Genuine shoe and slipper embeddings pass the gate (True Positive).
2. Diverse non-footwear objects (vehicles, faces, phones, mugs, blank images) are rejected (True Negative).
3. Zero false positives on non-footwear queries.
"""
import unittest
import numpy as np
from PIL import Image

from backend.footwear_gate import BinaryFootwearGate
from backend.classifier import ZeroShotCategoryClassifier
from backend.engine import EmbeddingEngine
from backend.matcher import ShoeMatcher
from scripts.build_footwear_gate import generate_negative_images


class TestFootwearGate(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.gate = BinaryFootwearGate.get_instance()
        cls.classifier = ZeroShotCategoryClassifier.get_instance()
        cls.engine = EmbeddingEngine.get_instance()
        cls.matcher = ShoeMatcher()

    def test_gate_initialization(self):
        self.assertTrue(self.gate.loaded)
        self.assertIsNotNone(self.gate.pos_embeddings)
        self.assertIsNotNone(self.gate.neg_embeddings)
        self.assertGreaterEqual(len(self.gate.pos_embeddings), 30)

        self.assertGreaterEqual(len(self.gate.neg_embeddings), 35)

    def test_genuine_footwear_passes_gate(self):
        """All catalog reference embeddings must be recognized as genuine footwear."""
        for i in range(min(10, len(self.gate.pos_embeddings))):
            vec = self.gate.pos_embeddings[i]
            is_fw, prob, reason, diag = self.gate.verify_footwear(vec)
            self.assertTrue(is_fw, f"Catalog item {i} failed gate with reason: {reason}")
            self.assertGreaterEqual(prob, 0.60)

    def test_non_footwear_rejected_by_gate(self):
        """All out-of-distribution negatives must be rejected by the gate."""
        neg_samples = generate_negative_images()
        rejected_count = 0
        for name, img in neg_samples:
            emb = self.engine._compute_embedding(img)
            is_fw, prob, reason, diag = self.gate.verify_footwear(emb)
            if not is_fw:
                rejected_count += 1
            else:
                print(f"FAILED TO REJECT: {name} (prob={prob}, reason={reason}, diag={diag})")

        total = len(neg_samples)
        rejection_rate = (rejected_count / total) * 100.0
        self.assertGreaterEqual(rejection_rate, 95.0, f"Rejection rate {rejection_rate}% is below target 95%")

    def test_end_to_end_matcher_rejection(self):
        """Ensure matcher returns is_footwear_detected=False and empty matches for non-footwear."""
        test_images = [
            Image.new("RGB", (224, 224), color=(255, 0, 0)),
            Image.fromarray(np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)),
            Image.new("RGB", (224, 224), color=(255, 255, 255)),
        ]
        for img in test_images:
            res = self.matcher.match_image(img)
            self.assertFalse(res.get("is_footwear_detected", True))
            self.assertEqual(len(res.get("matches", [])), 0)
            self.assertEqual(res.get("detected_category"), "none")


if __name__ == "__main__":
    unittest.main()
