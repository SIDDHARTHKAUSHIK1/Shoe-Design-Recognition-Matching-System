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
UPLOADS_DIR = STORAGE_DIR / "uploads"
CATALOG_IMAGES_DIR = STORAGE_DIR / "catalog_images"

# Ensure runtime directories exist
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
CATALOG_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Database & Vector Index paths
DB_PATH = STORAGE_DIR / "catalog.db"
FAISS_INDEX_PATH = STORAGE_DIR / "shoe_index.faiss"

# Vision Model Configuration
# DINOv2-small offers 384-d embeddings with ~100ms CPU latency and superior texture/shape representations
MODEL_NAME = os.getenv("EMBEDDING_MODEL", "facebook/dinov2-small")
EMBEDDING_DIM = 384  # DINOv2-small output dimension
IMAGE_SIZE = (224, 224)

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
