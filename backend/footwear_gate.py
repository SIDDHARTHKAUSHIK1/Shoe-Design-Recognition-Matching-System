"""
Dedicated Binary Footwear Verification Gate (Footwear vs. Non-Footwear Out-of-Distribution).
Evaluates whether a visual embedding belongs to genuine footwear (shoe/slipper)
before allowing catalog similarity search.
"""
import logging
from pathlib import Path
from typing import Tuple, Dict, Any, Optional
import numpy as np

from backend.config import STORAGE_DIR

logger = logging.getLogger(__name__)
GATE_MODEL_PATH = STORAGE_DIR / "models" / "footwear_gate_bank.npz"


class BinaryFootwearGate:
    """
    High-precision binary gate separating genuine footwear from out-of-distribution non-footwear
    using calibrated positive and negative visual manifold prototypes.
    Also exposes classify_shoe_vs_slipper() — a prototype-based classifier independent of FAISS,
    so slipper uploads are detected even when the FAISS index is shoe-only.
    """
    _instance: Optional["BinaryFootwearGate"] = None

    def __init__(self, bank_path: Path = GATE_MODEL_PATH):
        self.bank_path = bank_path
        self.pos_embeddings = None
        self.neg_embeddings = None
        self.pos_prototype = None
        self.neg_prototype = None
        self.slipper_embeddings = None
        self.slipper_prototype = None
        self.loaded = False
        self._load_prototype_bank()

    @classmethod
    def get_instance(cls) -> "BinaryFootwearGate":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_prototype_bank(self):
        """Loads precomputed positive and negative prototype embeddings from disk."""
        if not self.bank_path.exists():
            logger.warning(f"Footwear gate prototype bank not found at {self.bank_path}. Building now...")
            try:
                from scripts.build_footwear_gate import build_gate_bank
                build_gate_bank()
            except Exception as e:
                logger.error(f"Failed to auto-build footwear gate bank: {e}")
                return

        try:
            data = np.load(str(self.bank_path))
            self.pos_embeddings = data["pos_embeddings"].astype(np.float32)
            self.neg_embeddings = data["neg_embeddings"].astype(np.float32)
            self.pos_prototype = data["pos_prototype"].astype(np.float32)
            self.neg_prototype = data["neg_prototype"].astype(np.float32)
            # Load slipper prototypes if present (added in extended build)
            if "slipper_embeddings" in data and "slipper_prototype" in data:
                self.slipper_embeddings = data["slipper_embeddings"].astype(np.float32)
                self.slipper_prototype = data["slipper_prototype"].astype(np.float32)
                logger.info(f"  Slipper prototypes loaded: {len(self.slipper_embeddings)} vectors")
            self.loaded = True
            logger.info(
                f"BinaryFootwearGate initialized ({len(self.pos_embeddings)} positive vectors, "
                f"{len(self.neg_embeddings)} negative vectors)."
            )
        except Exception as e:
            logger.error(f"Failed to load footwear gate prototype bank: {e}")
            self.loaded = False

    def verify_footwear(
        self,
        query_embedding: np.ndarray,
        min_pos_sim: float = 0.42,
        min_margin: float = 0.03,
        min_probability: float = 0.60
    ) -> Tuple[bool, float, str, Dict[str, Any]]:
        """
        Verify if the given embedding is genuine footwear or non-footwear.

        Returns:
            Tuple of:
                - is_footwear: bool (True only if confirmed footwear)
                - confidence_prob: float [0.0, 1.0]
                - reason: 'confirmed_footwear', 'low_footwear_similarity', 'closer_to_non_footwear', 'low_probability'
                - diagnostics: dict with all comparative metrics
        """
        if not self.loaded or self.pos_embeddings is None:
            # Fallback if bank missing
            return True, 0.90, "gate_disabled", {}

        q_vec = np.squeeze(query_embedding).astype(np.float32)
        norm = np.linalg.norm(q_vec)
        if norm > 0:
            q_vec = q_vec / norm

        # Pairwise cosine similarities to all positives and negatives
        sim_pos = np.dot(self.pos_embeddings, q_vec)
        sim_neg = np.dot(self.neg_embeddings, q_vec)

        max_pos_sim = float(np.max(sim_pos))
        max_neg_sim = float(np.max(sim_neg))

        # Top-3 mean similarities for robust cluster proximity
        top3_pos_mean = float(np.mean(np.sort(sim_pos)[-3:]))
        top3_neg_mean = float(np.mean(np.sort(sim_neg)[-3:]))

        # Prototype similarities
        proto_pos_sim = float(np.dot(self.pos_prototype, q_vec))
        proto_neg_sim = float(np.dot(self.neg_prototype, q_vec))

        # Margin: positive advantage over negative domain
        margin = top3_pos_mean - top3_neg_mean

        # Softmax probability over positive vs negative domain
        tau = 0.08
        pos_logit = top3_pos_mean / tau
        neg_logit = top3_neg_mean / tau
        # Numerically stable softmax
        max_l = max(pos_logit, neg_logit)
        prob_footwear = float(np.exp(pos_logit - max_l) / (np.exp(pos_logit - max_l) + np.exp(neg_logit - max_l)))

        diagnostics = {
            "max_pos_sim": round(max_pos_sim, 4),
            "max_neg_sim": round(max_neg_sim, 4),
            "top3_pos_mean": round(top3_pos_mean, 4),
            "top3_neg_mean": round(top3_neg_mean, 4),
            "proto_pos_sim": round(proto_pos_sim, 4),
            "proto_neg_sim": round(proto_neg_sim, 4),
            "margin": round(margin, 4),
            "prob_footwear": round(prob_footwear, 4)
        }

        # Verification Gate Rules (Default is REJECTION)
        if max_neg_sim >= max_pos_sim:
            return False, round(prob_footwear, 4), "closer_to_non_footwear", diagnostics

        if max_pos_sim < min_pos_sim:
            return False, round(prob_footwear, 4), "low_footwear_similarity", diagnostics

        if margin < min_margin:
            return False, round(prob_footwear, 4), "closer_to_non_footwear", diagnostics

        if prob_footwear < min_probability:
            return False, round(prob_footwear, 4), "low_probability", diagnostics

        # Passed all gate checks -> Confirmed genuine footwear
        return True, round(prob_footwear, 4), "confirmed_footwear", diagnostics


    def classify_shoe_vs_slipper(
        self,
        query_embedding: np.ndarray
    ) -> Tuple[str, float]:
        """
        Classify confirmed footwear as 'shoe' or 'slipper' using prototype bank similarity.
        Operates independently of FAISS — works correctly even when FAISS is shoe-only.

        Returns:
            Tuple of (category: 'shoe' | 'slipper', confidence: float[0.0, 1.0])
        """
        if self.slipper_embeddings is None or self.slipper_prototype is None:
            # No slipper bank available — default to shoe
            return "shoe", 0.70

        q_vec = np.squeeze(query_embedding).astype(np.float32)
        norm = np.linalg.norm(q_vec)
        if norm > 0:
            q_vec = q_vec / norm

        # Similarity to slipper prototype cluster
        sim_to_slipper = np.dot(self.slipper_embeddings, q_vec)
        top3_slipper = float(np.mean(np.sort(sim_to_slipper)[-3:]))
        proto_slipper = float(np.dot(self.slipper_prototype, q_vec))

        # Overall footwear prototype similarity (includes both shoe + slipper)
        proto_footwear = float(np.dot(self.pos_prototype, q_vec))

        # Weighted slipper score
        slipper_score = 0.6 * top3_slipper + 0.4 * proto_slipper
        # Shoe score: footwear affinity adjusted away from slipper domain
        shoe_score = proto_footwear - 0.3 * slipper_score

        if slipper_score > shoe_score:
            conf = max(0.5, min(1.0, slipper_score / (shoe_score + slipper_score + 1e-9)))
            return "slipper", round(conf, 4)
        else:
            conf = max(0.5, min(1.0, shoe_score / (shoe_score + slipper_score + 1e-9)))
            return "shoe", round(conf, 4)
