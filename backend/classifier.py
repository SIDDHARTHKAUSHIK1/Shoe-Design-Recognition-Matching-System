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
    or 'none' (non-footwear) using DINOv2 visual manifold metrics and k-NN consensus.
    """
    _instance: Optional["ZeroShotCategoryClassifier"] = None

    def __init__(self):
        logger.info("Initializing Low-RAM DINOv2 Visual Classifier...")
        t0 = time.time()
        logger.info(f"Zero-extra-RAM Classifier initialized in {time.time() - t0:.2f}s")

    @classmethod
    def get_instance(cls) -> "ZeroShotCategoryClassifier":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def classify_category(
        self,
        image_input: Union[str, Path, bytes, io.BytesIO, Image.Image],
        precomputed_embedding: Optional[np.ndarray] = None
    ) -> Tuple[str, float]:
        """
        Classify input image into 'shoe', 'slipper', or 'none' (non-footwear).

        Returns:
            Tuple[str, float]: (detected_category, confidence_probability)
        """
        from backend.engine import EmbeddingEngine
        from backend.vector_store import VectorStore
        from backend import database as db

        engine = EmbeddingEngine.get_instance()
        vs = VectorStore.get_instance()

        if precomputed_embedding is not None:
            emb = precomputed_embedding
        else:
            emb = engine.get_embedding(image_input)

        if vs.total_vectors == 0:
            return "shoe", 0.95

        # Query top nearest neighbors in FAISS
        k = min(10, vs.total_vectors)
        scores, ids = vs.search(emb, top_k=k)
        
        raw_scores = scores[0] if len(scores) > 0 else []
        raw_ids = ids[0] if len(ids) > 0 else []
        
        max_sim = float(raw_scores[0]) if len(raw_scores) > 0 else 0.0

        # 1. Non-Footwear Rejection:
        # If visual cosine similarity to the closest footwear in the catalog is < 0.28,
        # it is recognized as a random non-footwear object (car, face, tree, pizza, noise, etc.)
        if max_sim < 0.28:
            conf = max(0.0, min(1.0, 1.0 - max_sim))
            return "none", round(conf, 4)

        # 2. Weighted Rank Voting between Shoes and Slippers
        shoe_score = 0.0
        slipper_score = 0.0

        for idx, (s, fid) in enumerate(zip(raw_scores[:5], raw_ids[:5])):
            if fid < 0:
                continue
            meta = db.get_reference_image_by_faiss_id(int(fid))
            if not meta:
                continue
            norm_cat = db.normalize_category(meta.get("category", ""))
            rank_weight = (1.0 / (idx + 1)) * float(s)
            if norm_cat == "shoe":
                shoe_score += rank_weight
            elif norm_cat == "slipper":
                slipper_score += rank_weight

        if slipper_score > shoe_score:
            prob = slipper_score / (shoe_score + slipper_score + 1e-9)
            return "slipper", round(float(prob), 4)
        else:
            prob = shoe_score / (shoe_score + slipper_score + 1e-9)
            return "shoe", round(float(prob), 4)
