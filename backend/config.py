"""
System Configuration for Shoe Design Recognition & Matching System.
"""
import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"
STORAGE_DIR = BASE_DIR / "storage"
DATASET_DIR = BASE_DIR / "dataset"
CONFIG_DIR = BASE_DIR / "config"
UPLOADS_DIR = STORAGE_DIR / "uploads"
CATALOG_IMAGES_DIR = STORAGE_DIR / "catalog_images"

# Ensure runtime directories exist
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
CATALOG_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Database & Vector Index paths
DB_PATH = STORAGE_DIR / "catalog.db"
FAISS_INDEX_PATH = STORAGE_DIR / "shoe_index.faiss"
THRESHOLDS_CONFIG_PATH = CONFIG_DIR / "thresholds.json"

# Thresholds and Calibration Configuration Loader
import json

DEFAULT_THRESHOLDS = {
    "shoe": {
        "rejection_threshold": 0.22,
        "confidence_high_threshold": 85.0,
        "confidence_moderate_threshold": 70.0,
        "margin_threshold": 0.015,
        "min_density": 0.20,
        "platt_scaling": {"a": 15.2, "b": -8.8}
    },
    "slipper": {
        "rejection_threshold": 0.20,
        "confidence_high_threshold": 82.0,
        "confidence_moderate_threshold": 68.0,
        "margin_threshold": 0.015,
        "min_density": 0.20,
        "platt_scaling": {"a": 14.6, "b": -8.2}
    },
    "global": {
        "rejection_threshold": 0.22,
        "margin_threshold": 0.015,
        "min_density": 0.20,
        "platt_scaling": {"a": 15.0, "b": -8.5}
    }
}

def load_thresholds_config() -> dict:
    if THRESHOLDS_CONFIG_PATH.exists():
        try:
            with open(THRESHOLDS_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("categories", DEFAULT_THRESHOLDS)
        except Exception:
            pass
    return DEFAULT_THRESHOLDS

# Vision Model Configuration
# DINOv2-small offers 384-d embeddings with ~100ms CPU latency and superior texture/shape representations
MODEL_NAME = os.getenv("EMBEDDING_MODEL", "facebook/dinov2-small")
EMBEDDING_DIM = 384  # DINOv2-small output dimension
IMAGE_SIZE = (224, 224)

# Test-Time Augmentation (TTA) Configuration
ENABLE_TTA = os.getenv("ENABLE_TTA", "true").lower() in ("true", "1", "t")
TTA_CROPS = int(os.getenv("TTA_CROPS", "2"))  # 2 crops (original + horizontal flip) for <250ms latency

# Background-Invariant Projection Head Configuration
ENABLE_INVARIANT_HEAD = os.getenv("ENABLE_INVARIANT_HEAD", "true").lower() in ("true", "1", "t")
INVARIANT_HEAD_PATH = STORAGE_DIR / "models" / "background_invariant_head.pt"

# Color-Aware Multi-Component Scoring Configuration
ENABLE_COLOR_AWARE_SCORING = os.getenv("ENABLE_COLOR_AWARE_SCORING", "true").lower() in ("true", "1", "t")
WEIGHT_DESIGN = float(os.getenv("WEIGHT_DESIGN", "0.75"))  # 75% geometric / texture silhouette match
WEIGHT_COLOR = float(os.getenv("WEIGHT_COLOR", "0.25"))    # 25% foreground dominant color match

# Matching & Confidence Thresholds
CONFIDENCE_HIGH_THRESHOLD = 85.0     # >= 85%: Strong Match (Green)
CONFIDENCE_MODERATE_THRESHOLD = 70.0 # 70% - 84.9%: Moderate Match (Yellow)
# < 70%: Low Similarity / Novel Design (Red)

# Number of top results to return
TOP_K_MATCHES = 3

# Server configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
