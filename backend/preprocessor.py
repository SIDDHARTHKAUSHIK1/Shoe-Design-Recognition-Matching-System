"""
Adaptive Image Quality Enhancement Preprocessor for ShoeMatch AI.
Runs on CPU before foreground segmentation and visual embedding.
Includes dynamic resolution upscaling, exposure normalization (CLAHE),
edge-preserving bilateral denoising, and white balance correction.
"""
import time
import logging
from typing import Tuple, Dict, Any, Optional
from PIL import Image
import numpy as np
import cv2

logger = logging.getLogger(__name__)


class ImageQualityEnhancer:
    """
    Fast, CPU-optimized image enhancement preprocessor.
    Improves downstream segmentation (U2-Netp), feature extraction (DINOv2),
    and color consistency across diverse lighting and camera qualities.
    """
    _instance: Optional["ImageQualityEnhancer"] = None

    def __init__(
        self,
        min_dim: int = 384,
        enable_upscale: bool = True,
        enable_clahe: bool = True,
        enable_denoise: bool = True,
        enable_white_balance: bool = True
    ):
        self.min_dim = min_dim
        self.enable_upscale = enable_upscale
        self.enable_clahe = enable_clahe
        self.enable_denoise = enable_denoise
        self.enable_white_balance = enable_white_balance
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    @classmethod
    def get_instance(cls) -> "ImageQualityEnhancer":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def upscale_if_needed(self, img: Image.Image) -> Tuple[Image.Image, bool]:
        """Upscale image if smaller than minimum dimension using high-fidelity Lanczos."""
        w, h = img.size
        min_side = min(w, h)
        if min_side < self.min_dim and min_side > 0:
            scale = self.min_dim / float(min_side)
            new_w = int(round(w * scale))
            new_h = int(round(h * scale))
            upscaled = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            return upscaled, True
        return img, False

    def normalize_exposure(self, img_np: np.ndarray) -> Tuple[np.ndarray, bool]:
        """Apply adaptive CLAHE & gamma correction on L-channel in LAB color space."""
        try:
            lab = cv2.cvtColor(img_np, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            l_mean = float(np.mean(l))
            
            # Gamma boost for very dark / underexposed images
            if l_mean < 50:
                gamma = 1.6
                inv_gamma = 1.0 / gamma
                lut = np.array([((i / 255.0) ** inv_gamma) * 255 for i in range(256)]).astype(np.uint8)
                l = cv2.LUT(l, lut)

            # Apply CLAHE if low contrast or uneven lighting
            if l_mean < 90 or l_mean > 190 or np.std(l) < 50:
                l_eq = self.clahe.apply(l)
                l_final = cv2.addWeighted(l_eq, 0.80, l, 0.20, 0)
                lab_eq = cv2.merge((l_final, a, b))
                return cv2.cvtColor(lab_eq, cv2.COLOR_LAB2RGB), True
            return img_np, False
        except Exception:
            return img_np, False

    def denoise(self, img_np: np.ndarray) -> Tuple[np.ndarray, bool]:
        """Lightweight edge-preserving bilateral denoising on CPU."""
        try:
            # Check noise level using Laplacian variance
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            if lap_var > 300:  # High-frequency grain/noise present
                denoised = cv2.bilateralFilter(img_np, d=5, sigmaColor=30, sigmaSpace=30)
                return denoised, True
            return img_np, False
        except Exception:
            return img_np, False

    def auto_white_balance(self, img_np: np.ndarray) -> Tuple[np.ndarray, bool]:
        """Correct color cast using Gray-World / Shades of Gray color constancy."""
        try:
            r_mean = np.mean(img_np[:, :, 0])
            g_mean = np.mean(img_np[:, :, 1])
            b_mean = np.mean(img_np[:, :, 2])
            
            # Check if significant color cast exists (e.g. yellow indoor incandescent)
            if abs(r_mean - g_mean) > 25 or abs(b_mean - g_mean) > 25:
                avg_gray = (r_mean + g_mean + b_mean) / 3.0
                if r_mean > 0 and g_mean > 0 and b_mean > 0:
                    scale_r = avg_gray / r_mean
                    scale_g = avg_gray / g_mean
                    scale_b = avg_gray / b_mean
                    
                    balanced = np.zeros_like(img_np, dtype=np.float32)
                    balanced[:, :, 0] = np.clip(img_np[:, :, 0] * scale_r, 0, 255)
                    balanced[:, :, 1] = np.clip(img_np[:, :, 1] * scale_g, 0, 255)
                    balanced[:, :, 2] = np.clip(img_np[:, :, 2] * scale_b, 0, 255)
                    return balanced.astype(np.uint8), True
            return img_np, False
        except Exception:
            return img_np, False

    def enhance(
        self,
        image: Image.Image,
        return_metadata: bool = True
    ) -> Tuple[Image.Image, Dict[str, Any]]:
        """
        Execute full image enhancement pipeline.

        Returns:
            Tuple of (Enhanced PIL Image, enhancement_metadata_dict)
        """
        t0 = time.time()
        meta = {
            "upscaled": False,
            "exposure_normalized": False,
            "denoised": False,
            "white_balanced": False,
            "original_size": list(image.size),
            "enhanced_size": list(image.size),
            "latency_ms": 0.0
        }

        curr_img = image.convert("RGB")

        # 1. Upscale if below threshold
        if self.enable_upscale:
            curr_img, upscaled = self.upscale_if_needed(curr_img)
            meta["upscaled"] = upscaled
            meta["enhanced_size"] = list(curr_img.size)

        img_np = np.array(curr_img)

        # 2. White Balance Correction
        if self.enable_white_balance:
            img_np, wb_applied = self.auto_white_balance(img_np)
            meta["white_balanced"] = wb_applied

        # 3. Exposure / CLAHE Normalization
        if self.enable_clahe:
            img_np, clahe_applied = self.normalize_exposure(img_np)
            meta["exposure_normalized"] = clahe_applied

        # 4. Bilateral Denoising
        if self.enable_denoise:
            img_np, denoise_applied = self.denoise(img_np)
            meta["denoised"] = denoise_applied

        enhanced_img = Image.fromarray(img_np)
        meta["latency_ms"] = round((time.time() - t0) * 1000, 2)

        return enhanced_img, meta


def enhance_image(image: Image.Image) -> Tuple[Image.Image, Dict[str, Any]]:
    """Convenience helper function to enhance an input image."""
    return ImageQualityEnhancer.get_instance().enhance(image)
