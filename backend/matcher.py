"""
Shoe Design Matching and Top-3 Scoring Engine.
"""
import time
import logging
from typing import Union, List, Dict, Any, Optional, Tuple
from pathlib import Path
from PIL import Image
import numpy as np

from backend.config import (
    TOP_K_MATCHES,
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_MODERATE_THRESHOLD,
)
from backend.engine import EmbeddingEngine
from backend.classifier import ZeroShotCategoryClassifier
from backend.vector_store import VectorStore
from backend import database as db

logger = logging.getLogger(__name__)


def classify_match_level(confidence_pct: float) -> Tuple[str, str, str]:
    """
    Classify confidence percentage into human-readable factory alert level and color.
    
    Returns:
        Tuple[str, str, str]: (level_code, level_label, color_code)
    """
    if confidence_pct >= CONFIDENCE_HIGH_THRESHOLD:
        return "HIGH", "High Confidence Match", "green"
    elif confidence_pct >= CONFIDENCE_MODERATE_THRESHOLD:
        return "MODERATE", "Moderate Similarity / Variant", "yellow"
    else:
        return "LOW", "Low Similarity / Distinct Design", "red"


class ShoeMatcher:
    """
    Coordinates feature extraction, zero-shot category classification (shoe vs. slipper),
    FAISS vector search, metadata enrichment, and Top-3 category-filtered ranked results.
    """

    def __init__(self):
        self.engine = EmbeddingEngine.get_instance()
        self.classifier = ZeroShotCategoryClassifier.get_instance()
        self.vector_store = VectorStore.get_instance()

    def match_image(
        self,
        query_image_input: Union[str, Path, bytes, Image.Image],
        query_image_save_path: Optional[str] = None,
        top_k: int = TOP_K_MATCHES
    ) -> Dict[str, Any]:
        """
        Execute end-to-end visual matching with automatic shoe vs. slipper differentiation.
        
        Args:
            query_image_input: Image filepath, bytes, or PIL Image.
            query_image_save_path: Relative URL/path where the query image is saved for logging.
            top_k: Number of ranked design matches to return (default 3).
            
        Returns:
            Dict containing detected category, confidence, top_k matches ranked best to third-best, and latency.
        """
        t0 = time.time()
        
        # 1. Extract visual embedding
        query_embedding = self.engine.get_embedding(query_image_input)
        
        # 2. Run zero-shot category classification (invisible to user, automatic differentiation)
        detected_category, cat_prob = self.classifier.classify_category(query_image_input)
        category_confidence_pct = round(cat_prob * 100.0, 1)

        # 3. Guard against non-footwear images (e.g. random pictures, faces, objects, animals)
        if detected_category == "none":
            latency_ms = (time.time() - t0) * 1000
            stats = db.get_catalog_stats()
            
            if query_image_save_path:
                db.log_query(
                    query_image_path=query_image_save_path,
                    top_match_id="NO_FOOTWEAR",
                    top_match_name="No Shoe or Slipper Detected",
                    confidence_pct=0.0,
                    latency_ms=latency_ms,
                    results=[],
                    detected_category="none"
                )
            
            return {
                "success": True,
                "query_image_path": query_image_save_path,
                "detected_category": "none",
                "is_footwear_detected": False,
                "category_confidence_pct": category_confidence_pct,
                "total_catalog_designs": stats.get("total_designs", 0),
                "total_catalog_vectors": self.vector_store.total_vectors,
                "matches": [],
                "latency_ms": round(latency_ms, 2),
                "message": "No shoe or slipper detected in the uploaded image. Please upload a clear photo of footwear."
            }
        
        # 4. Check if catalog has vectors
        if self.vector_store.total_vectors == 0:
            latency_ms = (time.time() - t0) * 1000
            return {
                "success": True,
                "query_image_path": query_image_save_path,
                "detected_category": detected_category,
                "is_footwear_detected": True,
                "category_confidence_pct": category_confidence_pct,
                "total_catalog_designs": 0,
                "total_catalog_vectors": 0,
                "matches": [],
                "latency_ms": round(latency_ms, 2),
                "message": "Catalog is currently empty. Please add reference designs first."
            }

        # 5. Retrieve a wide candidate pool from FAISS to allow complete category filtering
        raw_k = min(max(top_k * 50, 500), self.vector_store.total_vectors)
        scores, faiss_ids = self.vector_store.search(query_embedding, top_k=raw_k)
        
        raw_scores = scores[0] if len(scores) > 0 else []
        raw_ids = faiss_ids[0] if len(faiss_ids) > 0 else []
        
        # 5. Filter candidates strictly to the detected category and group by design ID
        seen_designs = {}
        for score, faiss_id in zip(raw_scores, raw_ids):
            if faiss_id < 0:
                continue
            
            ref_meta = db.get_reference_image_by_faiss_id(int(faiss_id))
            if not ref_meta:
                continue

            ref_category = ref_meta.get("category", "")
            # Filter strictly: only designs whose normalized category matches detected category
            if db.normalize_category(ref_category) != detected_category:
                continue
                
            design_id = ref_meta["design_id"]
            cosine_score = float(score)
            confidence_pct = max(0.0, min(100.0, cosine_score * 100.0))
            
            if design_id not in seen_designs or cosine_score > seen_designs[design_id]["cosine_similarity"]:
                seen_designs[design_id] = {
                    "design_id": design_id,
                    "design_name": ref_meta["name"],
                    "category": ref_meta["category"],
                    "description": ref_meta["description"],
                    "cosine_similarity": round(cosine_score, 4),
                    "confidence_pct": round(confidence_pct, 2),
                    "best_matching_angle": ref_meta["angle"],
                    "best_matching_image_path": ref_meta["image_path"],
                    "faiss_id": int(faiss_id)
                }

        # 6. Sort distinct same-category designs by similarity descending and pick top_k
        sorted_matches = sorted(
            seen_designs.values(),
            key=lambda x: x["cosine_similarity"],
            reverse=True
        )[:top_k]

        # 7. Format top matches with rankings, alert levels, and complete reference photos
        ranked_matches = []
        for rank_idx, match in enumerate(sorted_matches, start=1):
            level_code, level_label, color_code = classify_match_level(match["confidence_pct"])
            
            full_design = db.get_design(match["design_id"]) or {}
            all_refs = full_design.get("reference_images", [])
            
            ranked_matches.append({
                "rank": rank_idx,
                "design_id": match["design_id"],
                "design_name": match["design_name"],
                "category": match["category"],
                "description": match["description"],
                "shelf_location": full_design.get("shelf_location", "Warehouse A - Rack 03 - Shelf B-02"),
                "materials": full_design.get("materials", "Full Grain Leather / Rubber Sole"),
                "season": full_design.get("season", "Collection 2026"),
                "production_status": full_design.get("production_status", "Sample Archive"),
                "confidence_pct": match["confidence_pct"],
                "cosine_similarity": match["cosine_similarity"],
                "match_level": level_code,
                "match_level_label": level_label,
                "match_color": color_code,
                "best_matching_angle": match["best_matching_angle"],
                "best_matching_image_url": match["best_matching_image_path"],
                "all_angles": all_refs
            })

        latency_ms = (time.time() - t0) * 1000
        
        # 8. Audit log to SQLite with detected category
        top_match = ranked_matches[0] if ranked_matches else None
        db.log_query(
            query_image_path=query_image_save_path or "memory_query.jpg",
            top_match_id=top_match["design_id"] if top_match else None,
            top_match_name=top_match["design_name"] if top_match else None,
            confidence_pct=top_match["confidence_pct"] if top_match else 0.0,
            latency_ms=latency_ms,
            results=ranked_matches,
            detected_category=detected_category
        )
        
        catalog_stats = db.get_catalog_stats()
        
        message = None
        if len(ranked_matches) == 0:
            message = f"Detected category '{detected_category}' ({category_confidence_pct}%), but no matching reference designs exist in the catalog for this category."
        
        return {
            "success": True,
            "query_image_path": query_image_save_path,
            "detected_category": detected_category,
            "is_footwear_detected": True,
            "category_confidence_pct": category_confidence_pct,
            "total_catalog_designs": catalog_stats["total_designs"],
            "total_catalog_vectors": self.vector_store.total_vectors,
            "matches": ranked_matches,
            "latency_ms": round(latency_ms, 2),
            "message": message
        }
