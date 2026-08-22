"""
Shoe Design Matching and Top-3 Scoring Engine.
"""
import time
import logging
from typing import Union, List, Dict, Any, Optional, Tuple
from pathlib import Path
from PIL import Image
import numpy as np
import torch

from backend.config import (
    TOP_K_MATCHES,
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_MODERATE_THRESHOLD,
    ENABLE_COLOR_AWARE_SCORING,
    WEIGHT_DESIGN,
    WEIGHT_COLOR,
    load_thresholds_config,
)
from backend.engine import EmbeddingEngine
from backend.classifier import ZeroShotCategoryClassifier
from backend.vector_store import VectorStore
from backend.color_extractor import ColorExtractor
from backend import database as db
import json

logger = logging.getLogger(__name__)


def classify_match_level(confidence_pct: float, category: str = "shoe") -> Tuple[str, str, str]:
    """
    Classify confidence percentage into human-readable factory alert level and color
    using calibrated per-category thresholds from config.
    """
    thresholds = load_thresholds_config()
    norm_cat = db.normalize_category(category)
    cat_cfg = thresholds.get(norm_cat, thresholds.get("global", {}))

    high_th = float(cat_cfg.get("confidence_high_threshold", CONFIDENCE_HIGH_THRESHOLD))
    mod_th = float(cat_cfg.get("confidence_moderate_threshold", CONFIDENCE_MODERATE_THRESHOLD))

    if confidence_pct >= high_th:
        return "HIGH", "High Confidence Match", "green"
    elif confidence_pct >= mod_th:
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
        """
        t0 = time.time()
        
        with torch.no_grad():
            # 1. Preprocess and isolate foreground
            query_pil = self.engine.preprocess_image(query_image_input)
            isolated_img, fg_reason, crop_meta = self.engine.isolate_image_foreground(query_pil)
            
            # Guard against images with no clear foreground object
            if fg_reason == "no_clear_object":
                latency_ms = (time.time() - t0) * 1000
                stats = db.get_catalog_stats()
                if query_image_save_path:
                    db.log_query(
                        query_image_path=query_image_save_path,
                        top_match_id="NO_OBJECT",
                        top_match_name="No Clear Footwear Object Detected",
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
                    "category_confidence_pct": 0.0,
                    "reason": "no_clear_object",
                    "total_catalog_designs": stats.get("total_designs", 0),
                    "total_catalog_vectors": self.vector_store.total_vectors,
                    "matches": [],
                    "latency_ms": round(latency_ms, 2),
                    "crop_metadata": crop_meta,
                    "message": "No clear footwear object detected in the photo. Please center the shoe or slipper and upload a clearer photo."
                }

            query_embedding = self.engine._compute_embedding(isolated_img)
            query_hist = ColorExtractor.extract_hsv_histogram(isolated_img)
            query_dominant_colors = ColorExtractor.extract_dominant_colors(isolated_img)
            
            # 2. Run zero-shot category classification with density diagnostics
            detected_category, cat_prob, cat_reason, cat_diag = self.classifier.classify_category_detailed(
                query_image_input, precomputed_embedding=query_embedding
            )
            category_confidence_pct = round(cat_prob * 100.0, 1)

        # 3. Handle rejected non-footwear objects
        if detected_category == "none":
            latency_ms = (time.time() - t0) * 1000
            stats = db.get_catalog_stats()
            
            reason_msg = "Non-footwear object detected. Please upload an image of a shoe or slipper."
            if cat_reason == "out_of_distribution":
                reason_msg = "Image does not match any footwear category in the catalog."
            elif cat_reason == "ambiguous_category":
                reason_msg = "Ambiguous object. Could not reliably determine if this is a shoe or slipper."
                
            if query_image_save_path:
                db.log_query(
                    query_image_path=query_image_save_path,
                    top_match_id="REJECTED",
                    top_match_name="Rejected Non-Footwear",
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
                "reason": cat_reason,
                "diagnostics": cat_diag,
                "total_catalog_designs": stats.get("total_designs", 0),
                "total_catalog_vectors": self.vector_store.total_vectors,
                "matches": [],
                "latency_ms": round(latency_ms, 2),
                "crop_metadata": crop_meta,
                "message": reason_msg
            }

        # 3b. Handle slipper uploads — rejected in shoe-only catalog system
        if detected_category == "slipper":
            latency_ms = (time.time() - t0) * 1000
            stats = db.get_catalog_stats()

            if query_image_save_path:
                db.log_query(
                    query_image_path=query_image_save_path,
                    top_match_id="SLIPPER_REJECTED",
                    top_match_name="Slipper Upload — Not Supported",
                    confidence_pct=0.0,
                    latency_ms=latency_ms,
                    results=[],
                    detected_category="slipper"
                )

            return {
                "success": True,
                "query_image_path": query_image_save_path,
                "detected_category": "slipper",
                "is_footwear_detected": True,
                "matched": False,
                "category_confidence_pct": category_confidence_pct,
                "reason": "slipper_rejected",
                "total_catalog_designs": stats.get("total_designs", 0),
                "total_catalog_vectors": self.vector_store.total_vectors,
                "matches": [],
                "latency_ms": round(latency_ms, 2),
                "crop_metadata": crop_meta,
                "message": "Slippers are not supported by this catalog. Please upload a shoe image."
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
                "reason": "empty_catalog",
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
        
        # 5. Filter candidates strictly to the detected category and apply color-aware ranking
        seen_designs = {}
        for score, faiss_id in zip(raw_scores, raw_ids):
            if faiss_id < 0:
                continue
            
            ref_meta = db.get_reference_image_by_faiss_id(int(faiss_id))
            if not ref_meta:
                continue

            ref_category = ref_meta.get("category", "")
            cat_bonus = 0.05 if db.normalize_category(ref_category) == detected_category else 0.00
                
            design_id = ref_meta["design_id"]
            cosine_score = float(score)
            
            # Color-aware similarity scoring
            color_sim = 1.0
            if ENABLE_COLOR_AWARE_SCORING and ref_meta.get("color_histogram"):
                try:
                    cand_hist = json.loads(ref_meta["color_histogram"])
                    color_sim = ColorExtractor.compute_color_similarity(query_hist, cand_hist)
                except Exception:
                    color_sim = 1.0

            if ENABLE_COLOR_AWARE_SCORING:
                combined_score = WEIGHT_DESIGN * cosine_score + WEIGHT_COLOR * color_sim + cat_bonus
            else:
                combined_score = cosine_score + cat_bonus

            confidence_pct = db.calculate_calibrated_confidence(combined_score, category=ref_category)

            cand_dominant = []
            if ref_meta.get("dominant_colors"):
                try:
                    cand_dominant = json.loads(ref_meta["dominant_colors"])
                except Exception:
                    pass
            
            if design_id not in seen_designs or combined_score > seen_designs[design_id]["combined_score"]:
                seen_designs[design_id] = {
                    "design_id": design_id,
                    "design_name": ref_meta["name"],
                    "category": ref_meta["category"],
                    "description": ref_meta["description"],
                    "cosine_similarity": round(cosine_score, 4),
                    "color_similarity": round(color_sim, 4),
                    "combined_score": round(combined_score, 4),
                    "confidence_pct": round(confidence_pct, 2),
                    "dominant_colors": cand_dominant,
                    "best_matching_angle": ref_meta["angle"],
                    "best_matching_image_path": ref_meta["image_path"],
                    "faiss_id": int(faiss_id)
                }

        # 6. Sort candidates and select top_k visually distinct designs (diversity de-duplication)
        sorted_candidates = sorted(
            seen_designs.values(),
            key=lambda x: x["combined_score"],
            reverse=True
        )

        sorted_matches = []
        selected_vectors = []

        for cand in sorted_candidates:
            fid = cand["faiss_id"]
            vec = self.vector_store.index.reconstruct(fid)
            
            # Ensure candidate is not a visual duplicate (> 0.98 similarity) of an already chosen match
            is_dup = False
            for svec in selected_vectors:
                sim = float(np.dot(vec, svec))
                if sim > 0.980:
                    is_dup = True
                    break
            
            if not is_dup:
                sorted_matches.append(cand)
                selected_vectors.append(vec)
                if len(sorted_matches) >= top_k:
                    break

        # Margin and Ambiguity Analysis
        thresholds = load_thresholds_config()
        cat_cfg = thresholds.get(detected_category, thresholds.get("global", {}))
        rejection_th = float(cat_cfg.get("rejection_threshold", 0.35))

        top1_sim = sorted_matches[0]["combined_score"] if sorted_matches else 0.0
        top2_sim = sorted_matches[1]["combined_score"] if len(sorted_matches) > 1 else 0.0
        score_margin = round(top1_sim - top2_sim, 4)

        latency_ms = (time.time() - t0) * 1000
        stats = db.get_catalog_stats()

        # Handle case where footwear is detected, but does not match any catalog design
        if not sorted_matches or top1_sim < rejection_th:
            if query_image_save_path:
                db.log_query(
                    query_image_path=query_image_save_path,
                    top_match_id="NO_MATCH",
                    top_match_name="No Close Catalog Match",
                    confidence_pct=0.0,
                    latency_ms=latency_ms,
                    results=[],
                    detected_category=detected_category
                )
            return {
                "success": True,
                "query_image_path": query_image_save_path,
                "detected_category": detected_category,
                "is_footwear_detected": True,
                "matched": False,
                "category_confidence_pct": category_confidence_pct,
                "reason": "no_close_catalog_match",
                "top_similarity": round(top1_sim, 4),
                "rejection_threshold": rejection_th,
                "total_catalog_designs": stats.get("total_designs", 0),
                "total_catalog_vectors": self.vector_store.total_vectors,
                "matches": [],
                "crop_metadata": crop_meta,
                "query_dominant_colors": query_dominant_colors,
                "latency_ms": round(latency_ms, 2),
                "message": "Footwear detected, but no close matching design was found in the catalog."
            }

        if top1_sim < 0.55 and score_margin < 0.015 and len(sorted_matches) > 1:
            match_reason = "low_margin"
        else:
            match_reason = "matched"

        # 7. Format top matches with rankings, alert levels, and complete reference photos
        ranked_matches = []
        for rank_idx, match in enumerate(sorted_matches, start=1):
            level_code, level_label, color_code = classify_match_level(match["confidence_pct"], category=match["category"])
            
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
                "color_similarity": match.get("color_similarity", 1.0),
                "combined_score": match.get("combined_score", match["cosine_similarity"]),
                "dominant_colors": match.get("dominant_colors", []),
                "match_level": level_code,
                "match_level_label": level_label,
                "match_color": color_code,
                "best_matching_angle": match["best_matching_angle"],
                "best_matching_image_url": match["best_matching_image_path"],
                "all_angles": all_refs
            })
        
        # 8. Audit log to SQLite with detected category
        top_match = ranked_matches[0] if ranked_matches else None
        query_id = db.log_query(
            query_image_path=query_image_save_path or "memory_query.jpg",
            top_match_id=top_match["design_id"] if top_match else None,
            top_match_name=top_match["design_name"] if top_match else None,
            confidence_pct=top_match["confidence_pct"] if top_match else 0.0,
            latency_ms=latency_ms,
            results=ranked_matches,
            detected_category=detected_category
        )
        
        return {
            "success": True,
            "query_id": query_id,
            "query_image_path": query_image_save_path,
            "detected_category": detected_category,
            "is_footwear_detected": True,
            "matched": True,
            "category_confidence_pct": category_confidence_pct,
            "reason": match_reason,
            "score_margin": score_margin,
            "neighborhood_density": cat_diag.get("density_score", 1.0),
            "total_catalog_designs": stats.get("total_designs", 0),
            "total_catalog_vectors": self.vector_store.total_vectors,
            "matches": ranked_matches,
            "crop_metadata": crop_meta,
            "query_dominant_colors": query_dominant_colors,
            "latency_ms": round(latency_ms, 2)
        }
