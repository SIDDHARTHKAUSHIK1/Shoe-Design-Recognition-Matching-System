"""
Ultra-Lightweight Footwear Category Classifier & Dual-Signal Verification Ensemble.
Combines DINOv2 visual manifold embeddings with independent structural and geometric
contour analysis to reliably detect 'shoe', 'slipper', or 'none' (non-footwear).
"""
import io
import time
import logging
from pathlib import Path
from typing import Union, Tuple, Optional, Dict, Any
from PIL import Image, ImageOps
import numpy as np
import cv2

logger = logging.getLogger(__name__)


class ZeroShotCategoryClassifier:
    """
    Dual-Signal Category Classifier providing an independent second verification signal
    (structural geometry, grid/document density, and contour solidity) combined with
    DINOv2 manifold metrics to eliminate false positives and false negatives.
    """
    _instance: Optional["ZeroShotCategoryClassifier"] = None

    def __init__(self):
        logger.info("Initializing Dual-Signal Footwear Category Classifier...")

    @classmethod
    def get_instance(cls) -> "ZeroShotCategoryClassifier":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def verify_structural_footwear(
        self,
        image_input: Union[str, Path, bytes, io.BytesIO, Image.Image]
    ) -> Tuple[bool, float, str, Dict[str, Any]]:
        """
        Independent Signal 2: Geometric, structural, and line-density analysis.
        Detects whether an image has the physical contours of footwear vs. UI screenshots,
        scanned documents, or abstract graphics.
        """
        try:
            if isinstance(image_input, (str, Path)):
                pil_img = Image.open(str(image_input)).convert("RGB")
            elif isinstance(image_input, (bytes, bytearray)):
                pil_img = Image.open(io.BytesIO(image_input)).convert("RGB")
            elif isinstance(image_input, io.BytesIO):
                pil_img = Image.open(image_input).convert("RGB")
            elif isinstance(image_input, Image.Image):
                pil_img = image_input.convert("RGB")
            else:
                return True, 0.75, "unknown_input_type", {}

            img_np = np.array(pil_img)
            h, w = img_np.shape[:2]
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

            # 1. Check for pure solid / blank images
            std_dev = float(np.std(gray))
            if std_dev < 5.0:
                return False, 0.0, "solid_blank_image", {"std_dev": std_dev}

            # 2. Check for high-density horizontal/vertical orthogonal grid lines (UI windows, spreadsheets, screenshots)
            h_len = max(12, w // 15)
            v_len = max(12, h // 15)
            h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_len, 1))
            v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_len))

            edges = cv2.Canny(gray, 50, 150)
            h_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, h_kernel)
            v_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, v_kernel)

            h_ratio = float(np.mean(h_lines > 0))
            v_ratio = float(np.mean(v_lines > 0))
            grid_score = (h_ratio + v_ratio) * 1000.0

            # UI screenshots typically have long straight horizontal/vertical layout bars
            if grid_score > 35.0 or (h_ratio > 0.025 and v_ratio > 0.015):
                return False, 0.10, "ui_document_or_grid_detected", {
                    "grid_score": round(grid_score, 2),
                    "h_ratio": round(h_ratio, 4),
                    "v_ratio": round(v_ratio, 4)
                }

            # 3. Extreme Aspect Ratio Check (tall narrow banners or ultra-wide strips)
            aspect_ratio = float(w) / float(max(1, h))
            if aspect_ratio < 0.26 or aspect_ratio > 4.0:
                return False, 0.05, "extreme_aspect_ratio_non_shoe", {
                    "aspect_ratio": round(aspect_ratio, 3),
                    "grid_score": round(grid_score, 2)
                }

            # 4. Structural Solidity & Contour Symmetry Check
            # Threshold to find dominant silhouette
            blur = cv2.GaussianBlur(gray, (5, 5), 0)
            _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            solidity = 0.70
            if contours:
                largest = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(largest)
                hull = cv2.convexHull(largest)
                hull_area = cv2.contourArea(hull)
                if hull_area > 0:
                    solidity = float(area / hull_area)

            structural_prob = 0.85
            if 0.35 <= solidity <= 0.98:
                structural_prob = 0.92
            else:
                structural_prob = 0.65

            diag = {
                "std_dev": round(std_dev, 2),
                "grid_score": round(grid_score, 2),
                "solidity": round(solidity, 4),
                "aspect_ratio": round(aspect_ratio, 3)
            }

            return True, round(structural_prob, 4), "valid_footwear_structure", diag
        except Exception as e:
            logger.debug(f"Structural verification error: {e}")
            return True, 0.80, "structural_check_bypassed", {}

    def compute_neighborhood_density(self, fids: list) -> float:
        """
        Compute mutual pairwise cosine coherence among the query's top-k nearest neighbors.
        Returns float in [0, 1] where high values indicate a dense, coherent cluster.
        """
        from backend.vector_store import VectorStore
        vs = VectorStore.get_instance()
        if vs.total_vectors < 2 or not fids:
            return 1.0

        vecs = []
        for fid in fids:
            if 0 <= fid < vs.total_vectors:
                try:
                    v = vs.index.reconstruct(int(fid))
                    vecs.append(v)
                except Exception:
                    pass

        if len(vecs) < 2:
            return 1.0

        nv = np.array(vecs)
        pairwise = np.dot(nv, nv.T)
        np.fill_diagonal(pairwise, 0)
        mean_coherence = float(pairwise.sum() / (len(nv) * (len(nv) - 1)))
        return max(0.0, min(1.0, mean_coherence))

    def classify_category(
        self,
        image_input: Union[str, Path, bytes, io.BytesIO, Image.Image],
        precomputed_embedding: Optional[np.ndarray] = None
    ) -> Tuple[str, float]:
        """
        Standard classification interface returning (category, confidence_prob).
        """
        cat, prob, _, _ = self.classify_category_detailed(image_input, precomputed_embedding)
        return cat, prob

    def classify_category_detailed(
        self,
        image_input: Union[str, Path, bytes, io.BytesIO, Image.Image],
        precomputed_embedding: Optional[np.ndarray] = None
    ) -> Tuple[str, float, str, dict]:
        """
        Dual-Engine Ensemble Classification:
        Signal 1: DINOv2 metric learning prototype bank (BinaryFootwearGate)
        Signal 2: Independent structural geometry & grid density (verify_structural_footwear)

        Returns:
            Tuple of:
                - detected_category: 'shoe', 'slipper', or 'none'
                - confidence_prob: float in [0.0, 1.0]
                - rejection_reason: 'matched', 'closer_to_non_footwear', 'ui_document_detected', etc.
                - diagnostics: combined dictionary of all metrics
        """
        from backend.engine import EmbeddingEngine
        from backend.vector_store import VectorStore
        from backend.footwear_gate import BinaryFootwearGate

        engine = EmbeddingEngine.get_instance()
        vs = VectorStore.get_instance()
        gate = BinaryFootwearGate.get_instance()

        if precomputed_embedding is not None:
            emb = precomputed_embedding
        else:
            emb = engine.get_embedding(image_input)

        # 1. Signal 1: Binary Footwear Gate (Metric Learning & Prototype Manifold)
        is_fw_1, prob_1, reason_1, diag_1 = gate.verify_footwear(emb, raw_image=image_input)

        # 2. Signal 2: Independent Structural & Grid Density Analysis
        is_fw_2, prob_2, reason_2, diag_2 = self.verify_structural_footwear(image_input)

        combined_diag = {
            **diag_1,
            **{f"struct_{k}": v for k, v in diag_2.items()},
            "signal1_prob": prob_1,
            "signal2_prob": prob_2,
            "signal1_reason": reason_1,
            "signal2_reason": reason_2
        }

        # 3. Ensemble Decision Rule
        is_confirmed_footwear = False
        ensemble_reason = "closer_to_non_footwear"
        ensemble_prob = 0.0

        if not is_fw_1 and not is_fw_2:
            # Dual Rejection
            is_confirmed_footwear = False
            ensemble_reason = reason_1 if reason_1 != "confirmed_footwear" else reason_2
            ensemble_prob = min(prob_1, prob_2)

        elif is_fw_1 and is_fw_2:
            # Dual Confirmation
            is_confirmed_footwear = True
            ensemble_reason = "confirmed_footwear"
            ensemble_prob = round(0.65 * prob_1 + 0.35 * prob_2, 4)

        elif is_fw_1 and not is_fw_2:
            # Signal 1 passed, but Signal 2 flagged non-footwear
            if reason_2 in ("ui_document_or_grid_detected", "solid_blank_image", "extreme_aspect_ratio_non_shoe"):
                # UI / Document / Blank / Extreme Aspect Ratio vetoes embedding match
                is_confirmed_footwear = False
                ensemble_reason = reason_2
                ensemble_prob = prob_2
            elif prob_1 >= 0.92 and diag_1.get("margin", 0) >= 0.20:
                # Strong embedding advantage overrides conservative geometry
                is_confirmed_footwear = True
                ensemble_reason = "confirmed_footwear"
                ensemble_prob = round(prob_1 * 0.90, 4)
            else:
                is_confirmed_footwear = False
                ensemble_reason = reason_2
                ensemble_prob = prob_2

        elif not is_fw_1 and is_fw_2:
            # Signal 2 passed, but Signal 1 failed
            # Only recover if positive similarity strictly exceeds negative similarity and prob is reasonable
            max_pos = diag_1.get("max_pos_sim", 0)
            max_neg = diag_1.get("max_neg_sim", 0)
            if max_pos > max_neg and prob_1 >= 0.45 and prob_2 >= 0.85:
                # Near-boundary edge case shoe recovered by structural confirmation
                is_confirmed_footwear = True
                ensemble_reason = "confirmed_footwear"
                ensemble_prob = round(0.50 * prob_1 + 0.50 * prob_2, 4)
            else:
                is_confirmed_footwear = False
                ensemble_reason = reason_1
                ensemble_prob = prob_1

        if not is_confirmed_footwear:
            return "none", round(ensemble_prob, 4), ensemble_reason, combined_diag

        if vs.total_vectors == 0:
            return "shoe", ensemble_prob, "matched", combined_diag

        # 4. Query top nearest neighbors in FAISS
        k = min(10, vs.total_vectors)
        scores, ids = vs.search(emb, top_k=k)
        
        raw_scores = [float(s) for s in (scores[0] if len(scores) > 0 else [])]
        raw_ids = [int(i) for i in (ids[0] if len(ids) > 0 else [])]
        
        max_sim = float(raw_scores[0]) if len(raw_scores) > 0 else 0.0
        second_sim = float(raw_scores[1]) if len(raw_scores) > 1 else 0.0
        top_margin = max_sim - second_sim

        density_score = self.compute_neighborhood_density(raw_ids[:5])

        combined_diag.update({
            "max_sim": round(max_sim, 4),
            "second_sim": round(second_sim, 4),
            "margin": round(top_margin, 4),
            "density_score": round(density_score, 4),
            "top_ids": raw_ids[:5]
        })

        # 5. Prototype-Based Shoe vs. Slipper Classification
        shoe_slipper_cat, shoe_slipper_conf = gate.classify_shoe_vs_slipper(emb)
        if shoe_slipper_cat == "slipper":
            return "slipper", round(float(shoe_slipper_conf), 4), "slippers_not_supported", combined_diag
        else:
            return "shoe", round(float(shoe_slipper_conf), 4), "matched", combined_diag
