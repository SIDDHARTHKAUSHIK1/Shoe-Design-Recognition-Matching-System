"""
Foreground Isolation and Auto-Cropping Module for ShoeMatch AI.
Uses lightweight U2-Netp (~4.7MB) running on CPU to segment footwear from background clutter.
"""
import os
import io
import time
import logging
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from PIL import Image, ImageOps
import numpy as np
import cv2

try:
    import onnxruntime as ort
except ImportError:
    ort = None

from backend.config import STORAGE_DIR

logger = logging.getLogger(__name__)

MODELS_DIR = STORAGE_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
U2NETP_PATH = MODELS_DIR / "u2netp.onnx"
U2NETP_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx"


class ForegroundIsolator:
    """
    Singleton class managing the lightweight U2-Netp ONNX session for foreground extraction.
    """
    _instance: Optional["ForegroundIsolator"] = None

    def __init__(self, model_path: Path = U2NETP_PATH):
        self.model_path = model_path
        self.session = None
        self._enabled = os.getenv("ENABLE_AUTO_CROP", "true").lower() in ("true", "1", "t", "yes")
        
        if self._enabled:
            self._ensure_model_and_session()

    @classmethod
    def get_instance(cls) -> "ForegroundIsolator":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _ensure_model_and_session(self):
        """Download model if missing and initialize ONNX session with 1 CPU thread."""
        if not self._enabled or ort is None:
            return

        if not self.model_path.exists():
            try:
                import urllib.request
                logger.info(f"Downloading lightweight U2-Netp model (~4.7MB) to {self.model_path}...")
                urllib.request.urlretrieve(U2NETP_URL, str(self.model_path))
                logger.info("U2-Netp model download complete.")
            except Exception as e:
                logger.warning(f"Failed to download U2-Netp ONNX model: {e}. Auto-crop will fall back to original image.")
                return

        try:
            sess_opts = ort.SessionOptions()
            sess_opts.intra_op_num_threads = 1
            sess_opts.inter_op_num_threads = 1
            sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.session = ort.InferenceSession(str(self.model_path), sess_opts, providers=["CPUExecutionProvider"])
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            logger.info("ForegroundIsolator initialized successfully with U2-Netp on CPU.")
        except Exception as e:
            logger.warning(f"Could not initialize ONNXRuntime session for U2-Netp: {e}")
            self.session = None

    def isolate(
        self,
        image: Image.Image,
        padding_ratio: float = 0.08,
        min_coverage: float = 0.03,
        max_coverage: float = 0.96,
    ) -> Tuple[Image.Image, Optional[str], Dict[str, Any]]:
        """
        Isolate foreground shoe/slipper from background clutter and crop with padding.

        Args:
            image: PIL Image.
            padding_ratio: Margin to add around bounding box (default 8%).
            min_coverage: Minimum mask area ratio (below this = 'no_clear_object').
            max_coverage: Maximum mask area ratio (above this = full frame / no distinct crop).

        Returns:
            Tuple of:
                - Cropped PIL Image (or original if no crop applied).
                - Rejection reason string (e.g. 'no_clear_object') or None if valid.
                - Metadata dict with crop details, coverage, bounding box, and latency.
        """
        if not self._enabled or self.session is None:
            return image, None, {"cropped": False, "reason": "disabled_or_unavailable"}

        t0 = time.time()
        orig_w, orig_h = image.size

        # Preprocess for U2-Netp: 320x320 normalized tensor
        resized = image.convert("RGB").resize((320, 320), Image.BILINEAR)
        img_np = np.array(resized).astype(np.float32) / 255.0
        # ImageNet normalization
        img_np = (img_np - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
        img_np = img_np.transpose((2, 0, 1))
        input_tensor = np.expand_dims(img_np, axis=0).astype(np.float32)

        try:
            pred = self.session.run([self.output_name], {self.input_name: input_tensor})[0]
            mask_320 = pred[0, 0]
            mask_320 = (mask_320 - mask_320.min()) / (mask_320.max() - mask_320.min() + 1e-8)
        except Exception as e:
            logger.warning(f"Foreground segmentation inference failed: {e}")
            return image, None, {"cropped": False, "reason": "inference_error"}

        # Upsample soft mask to original image resolution with linear interpolation
        full_mask = cv2.resize(mask_320, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
        full_mask = np.clip(full_mask, 0.0, 1.0)

        # Binarize mask for coverage and bbox computation
        bin_mask = (full_mask > 0.40).astype(np.uint8)
        coverage = float(bin_mask.mean())

        latency_ms = (time.time() - t0) * 1000

        # Fallback 1: Less than 3% foreground -> No clear dominant object
        if coverage < min_coverage:
            return image, "no_clear_object", {
                "cropped": False,
                "reason": "no_clear_object",
                "coverage": round(coverage, 4),
                "latency_ms": round(latency_ms, 2)
            }

        # Fallback 2: Over 96% foreground -> Object fills entire frame or background is non-distinguishable
        if coverage > max_coverage:
            return image, None, {
                "cropped": False,
                "reason": "full_frame_object",
                "coverage": round(coverage, 4),
                "latency_ms": round(latency_ms, 2)
            }

        # Alpha composite footwear onto neutral studio background (248, 248, 248)
        # This completely zeroes out background texture, floor reflections, carpets, and shadows
        orig_arr = np.array(image.convert("RGB")).astype(np.float32)
        mask_3d = np.repeat(np.expand_dims(full_mask, axis=2), 3, axis=2)
        neutral_bg = np.array([248.0, 248.0, 248.0], dtype=np.float32)
        neutral_img_arr = orig_arr * mask_3d + neutral_bg * (1.0 - mask_3d)
        neutral_img_arr = np.clip(neutral_img_arr, 0, 255).astype(np.uint8)
        neutral_pil = Image.fromarray(neutral_img_arr)

        # Find foreground bounding box
        y_indices, x_indices = np.where(bin_mask > 0)
        if len(x_indices) == 0 or len(y_indices) == 0:
            return image, "no_clear_object", {
                "cropped": False,
                "reason": "no_clear_object",
                "coverage": 0.0,
                "latency_ms": round(latency_ms, 2)
            }

        x_min, x_max = int(x_indices.min()), int(x_indices.max())
        y_min, y_max = int(y_indices.min()), int(y_indices.max())

        # Add padding margin
        box_w = x_max - x_min
        box_h = y_max - y_min
        pad_w = int(padding_ratio * box_w)
        pad_h = int(padding_ratio * box_h)

        x_min = max(0, x_min - pad_w)
        y_min = max(0, y_min - pad_h)
        x_max = min(orig_w, x_max + pad_w)
        y_max = min(orig_h, y_max + pad_h)

        # Ensure valid crop dimension (at least 32x32)
        if (x_max - x_min) < 32 or (y_max - y_min) < 32:
            return image, None, {
                "cropped": False,
                "reason": "box_too_small",
                "coverage": round(coverage, 4),
                "latency_ms": round(latency_ms, 2)
            }

        # Crop neutral-filled image to bounding box
        cropped_img = neutral_pil.crop((x_min, y_min, x_max, y_max))

        meta = {
            "cropped": True,
            "segmented": True,
            "bbox": [x_min, y_min, x_max, y_max],
            "original_size": [orig_w, orig_h],
            "cropped_size": [x_max - x_min, y_max - y_min],
            "coverage": round(coverage, 4),
            "latency_ms": round(latency_ms, 2)
        }

        return cropped_img, None, meta


def isolate_foreground(
    image: Image.Image,
    padding_ratio: float = 0.08,
) -> Tuple[Image.Image, Optional[str], Dict[str, Any]]:
    """
    Discrete, testable helper function to isolate foreground footwear with neutral studio fill.
    """
    return ForegroundIsolator.get_instance().isolate(image, padding_ratio=padding_ratio)
