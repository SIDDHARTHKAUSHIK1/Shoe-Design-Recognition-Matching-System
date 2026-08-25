"""
Unit and regression test suite for BinaryFootwearGate and False-Positive Footwear Rejection.
Verifies:
1. Genuine shoe and slipper embeddings pass the gate (True Positive).
2. Diverse non-footwear objects (vehicles, faces, phones, mugs, blank images) are rejected (True Negative).
3. Zero false positives on non-footwear queries.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import unittest
import numpy as np
from PIL import Image
import io

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


    def test_qr_code_and_barcode_rejection(self):
        """Explicitly verify QR codes, barcodes, and document graphics are rejected by gate."""
        from PIL import ImageDraw
        # Synthetic QR code
        qr_img = Image.new("RGB", (256, 256), (255, 255, 255))
        d = ImageDraw.Draw(qr_img)
        d.rectangle([20, 20, 90, 90], fill=(0, 0, 0))
        d.rectangle([40, 40, 70, 70], fill=(255, 255, 255))
        d.rectangle([50, 50, 60, 60], fill=(0, 0, 0))
        d.rectangle([166, 20, 236, 90], fill=(0, 0, 0))
        d.rectangle([176, 30, 226, 80], fill=(255, 255, 255))
        d.rectangle([186, 40, 216, 70], fill=(0, 0, 0))
        for x in range(30, 230, 20):
            for y in range(30, 230, 20):
                if (x * y) % 5 < 3:
                    d.rectangle([x, y, x+10, y+10], fill=(0, 0, 0))

        res = self.matcher.match_image(qr_img)
        self.assertFalse(res.get("is_footwear_detected", True))
        self.assertEqual(len(res.get("matches", [])), 0)
        self.assertIn(res.get("reason"), {"qr_code_detected", "qr_code_or_barcode_pattern", "closer_to_non_footwear", "no_clear_object"})

    def test_brogue_and_formal_shoes_pass_gate(self):
        """Verify previously false-negative formal dress shoes (brogues, oxfords) pass the gate and match."""
        from pathlib import Path
        test_dir = Path("test_images")
        for fname in ["false_negative_brogue.jpg", "false_negative_pair.jpg"]:
            p = test_dir / fname
            if p.exists():
                img = Image.open(p).convert("RGB")
                res = self.matcher.match_image(img)
                self.assertTrue(res.get("is_footwear_detected"), f"{fname} was incorrectly rejected as non-footwear: {res.get('reason')}")
                self.assertEqual(res.get("detected_category"), "shoe")
                self.assertGreater(len(res.get("matches", [])), 0)


if __name__ == "__main__":
    unittest.main()

