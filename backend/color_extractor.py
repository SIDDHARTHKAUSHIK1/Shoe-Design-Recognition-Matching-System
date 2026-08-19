"""
Color Extraction and Color-Aware Similarity Scoring for Footwear.

Extracts normalized HSV color histograms and dominant color palettes
strictly from the isolated footwear foreground (excluding background pixels).
"""
import logging
from typing import List, Tuple, Dict, Any, Optional
from PIL import Image
import numpy as np
import cv2

logger = logging.getLogger(__name__)

# Standard 64-bin HSV quantization (16 Hue bins, 2 Saturation bins, 2 Value bins)
H_BINS = 16
S_BINS = 2
V_BINS = 2
TOTAL_COLOR_BINS = H_BINS * S_BINS * V_BINS  # 64 bins


class ColorExtractor:
    """
    Extracts foreground-isolated color representations for color-aware product matching.
    """

    @staticmethod
    def extract_hsv_histogram(img: Image.Image, mask: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Extract a normalized 64-bin HSV color histogram from the footwear image.
        If a mask is provided, only pixels where mask > 0.5 are included.
        If no mask is provided, filters out near-white/neutral background (RGB > 240).
        
        Returns:
            np.ndarray: L1-normalized 64-dimensional float32 vector (sums to 1.0).
        """
        rgb_arr = np.array(img.convert("RGB"))
        hsv_arr = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2HSV)

        if mask is not None:
            if mask.shape != rgb_arr.shape[:2]:
                mask_resized = cv2.resize(mask.astype(np.float32), (rgb_arr.shape[1], rgb_arr.shape[0]))
            else:
                mask_resized = mask.astype(np.float32)
            valid_mask = (mask_resized > 0.4).astype(np.uint8) * 255
        else:
            # Mask out neutral studio background (R, G, B all > 242)
            is_bg = (rgb_arr[:, :, 0] > 242) & (rgb_arr[:, :, 1] > 242) & (rgb_arr[:, :, 2] > 242)
            valid_mask = (~is_bg).astype(np.uint8) * 255

        # If foreground mask is empty, fallback to entire image
        if np.count_nonzero(valid_mask) < 50:
            valid_mask = np.ones(rgb_arr.shape[:2], dtype=np.uint8) * 255

        # Calculate 3D histogram in HSV space
        hist = cv2.calcHist(
            [hsv_arr], 
            [0, 1, 2], 
            valid_mask, 
            [H_BINS, S_BINS, V_BINS], 
            [0, 180, 0, 256, 0, 256]
        )
        hist = hist.flatten().astype(np.float32)
        total = np.sum(hist)
        if total > 0:
            hist /= total
        else:
            hist = np.ones(TOTAL_COLOR_BINS, dtype=np.float32) / float(TOTAL_COLOR_BINS)

        return hist

    @staticmethod
    def compute_color_similarity(hist_a: np.ndarray, hist_b: np.ndarray) -> float:
        """
        Compute histogram intersection similarity between two normalized histograms.
        Returns a float in [0.0, 1.0], where 1.0 indicates identical color distributions.
        """
        if hist_a is None or hist_b is None or len(hist_a) == 0 or len(hist_b) == 0:
            return 0.5  # Neutral fallback
        
        hist_a = np.asarray(hist_a, dtype=np.float32)
        hist_b = np.asarray(hist_b, dtype=np.float32)

        # Histogram intersection similarity: sum(min(a_i, b_i))
        intersection = float(np.sum(np.minimum(hist_a, hist_b)))
        return float(np.clip(intersection, 0.0, 1.0))

    @staticmethod
    def extract_dominant_colors(img: Image.Image, k: int = 3, mask: Optional[np.ndarray] = None) -> List[Dict[str, Any]]:
        """
        Extract top-k dominant colors from the shoe with hex codes and percentages using k-means.
        """
        rgb_arr = np.array(img.convert("RGB"))
        if mask is not None:
            if mask.shape != rgb_arr.shape[:2]:
                mask_resized = cv2.resize(mask.astype(np.float32), (rgb_arr.shape[1], rgb_arr.shape[0]))
            else:
                mask_resized = mask.astype(np.float32)
            valid_pixels = rgb_arr[mask_resized > 0.4]
        else:
            is_bg = (rgb_arr[:, :, 0] > 242) & (rgb_arr[:, :, 1] > 242) & (rgb_arr[:, :, 2] > 242)
            valid_pixels = rgb_arr[~is_bg]

        if len(valid_pixels) < 100:
            valid_pixels = rgb_arr.reshape(-1, 3)

        # Subsample for fast k-means
        if len(valid_pixels) > 5000:
            idx = np.random.choice(len(valid_pixels), 5000, replace=False)
            valid_pixels = valid_pixels[idx]

        pixels = np.float32(valid_pixels)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        flags = cv2.KMEANS_RANDOM_CENTERS

        try:
            _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 5, flags)
            counts = np.bincount(labels.flatten())
            total = np.sum(counts)

            dominant = []
            for count, center in sorted(zip(counts, centers), key=lambda x: x[0], reverse=True):
                r, g, b = int(center[0]), int(center[1]), int(center[2])
                hex_code = f"#{r:02x}{g:02x}{b:02x}"
                dominant.append({
                    "hex": hex_code,
                    "rgb": [r, g, b],
                    "percentage": float(round(float(count) / float(total) * 100.0, 1))
                })
            return dominant
        except Exception as e:
            logger.warning(f"K-means dominant color extraction failed: {e}")
            return [{"hex": "#808080", "rgb": [128, 128, 128], "percentage": 100.0}]
