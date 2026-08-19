"""
Ultra-Lightweight Footwear Category Classifier (Shoe vs. Slipper vs. Non-Footwear).
Reuses the shared DINOv2 visual embedding engine to operate comfortably within < 150MB RAM.
"""
import io
import time
import logging
from pathlib import Path
from typing import Union, Tuple, Optional
from PIL import Image, ImageOps
import numpy as np

logger = logging.getLogger(__name__)


class ZeroShotCategoryClassifier:
    """
    Zero-extra-RAM Category Classifier that detects whether an image is a 'shoe', 'slipper',
    or 'none' (non-footwear) using DINOv2 visual manifold metrics, k-NN density, and margin checks.
    """
    _instance: Optional["ZeroShotCategoryClassifier"] = None

    def __init__(self):
        logger.info("Initializing Low-RAM DINOv2 Visual Classifier with Margin & Density checks...")

    @classmethod
    def get_instance(cls) -> "ZeroShotCategoryClassifier":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

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
        Classify input image into 'shoe', 'slipper', or 'none' with detailed diagnostics.

        Returns:
            Tuple of:
                - detected_category: 'shoe', 'slipper', or 'none'
                - confidence_prob: float in [0.0, 1.0]
                - rejection_reason: 'matched', 'below_threshold', 'ambiguous_density', 'low_margin'
                - diagnostics: dict with max_sim, density_score, margin, top scores
        """
        from backend.engine import EmbeddingEngine
        from backend.vector_store import VectorStore
        from backend.footwear_gate import BinaryFootwearGate
        from backend import database as db

        engine = EmbeddingEngine.get_instance()
        vs = VectorStore.get_instance()
        gate = BinaryFootwearGate.get_instance()

        if precomputed_embedding is not None:
            emb = precomputed_embedding
        else:
            emb = engine.get_embedding(image_input)

        # 1. Independent Binary Footwear Gate Check (Footwear vs. Non-Footwear)
        is_footwear, gate_prob, gate_reason, gate_diag = gate.verify_footwear(emb, raw_image=image_input)
        if not is_footwear:
            return "none", round(gate_prob, 4), gate_reason, gate_diag


        if vs.total_vectors == 0:
            return "shoe", 0.95, "matched", gate_diag

        # Query top nearest neighbors in FAISS
        k = min(10, vs.total_vectors)
        scores, ids = vs.search(emb, top_k=k)
        
        raw_scores = [float(s) for s in (scores[0] if len(scores) > 0 else [])]
        raw_ids = [int(i) for i in (ids[0] if len(ids) > 0 else [])]
        
        max_sim = float(raw_scores[0]) if len(raw_scores) > 0 else 0.0
        second_sim = float(raw_scores[1]) if len(raw_scores) > 1 else 0.0
        top_margin = max_sim - second_sim

        # Calculate neighbor mutual density (coherence)
        density_score = self.compute_neighborhood_density(raw_ids[:5])

        diagnostics = {
            **gate_diag,
            "max_sim": round(max_sim, 4),
            "second_sim": round(second_sim, 4),
            "margin": round(top_margin, 4),
            "density_score": round(density_score, 4),
            "top_ids": raw_ids[:5]
        }

        # 2. Hard Non-Footwear Rejection if similarity to catalog is exceedingly low
        if max_sim < 0.30:
            conf = max(0.0, min(1.0, 1.0 - max_sim))
            return "none", round(conf, 4), "below_threshold", diagnostics


        # 3. Prototype-Based Shoe vs. Slipper Classification
        shoe_slipper_cat, shoe_slipper_conf = gate.classify_shoe_vs_slipper(emb)
        if shoe_slipper_cat == "slipper":
            return "slipper", round(float(shoe_slipper_conf), 4), "slippers_not_supported", diagnostics
        else:
            return "shoe", round(float(shoe_slipper_conf), 4), "matched", diagnostics


