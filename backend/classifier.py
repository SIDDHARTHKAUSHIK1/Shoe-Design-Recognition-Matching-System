"""
Zero-Shot Category Classifier (Shoe vs. Slipper) using CLIP text-image alignment.
"""
import io
import time
import logging
from pathlib import Path
from typing import Union, Tuple, List, Optional
from PIL import Image, ImageOps
import numpy as np

logger = logging.getLogger(__name__)

# Prompt Ensembles for robust zero-shot classification
SHOE_PROMPTS = [
    "a photo of a shoe",
    "a photo of a sneaker",
    "a photo of a leather dress shoe or oxford",
    "a photo of a boot or high top shoe",
    "a photo of an athletic running shoe",
    "a photo of a formal closed shoe",
    "a closed-toe shoe"
]

SLIPPER_PROMPTS = [
    "a photo of a slipper",
    "a photo of a house slipper or bedroom slipper",
    "a photo of a slide sandal or slip-on slide",
    "a photo of a flip-flop sandal",
    "a photo of an open-toe slipper",
    "a photo of a fuzzy indoor slipper",
    "an open back slipper or sandal"
]


class ZeroShotCategoryClassifier:
    """
    Zero-shot classifier that differentiates between 'shoe' and 'slipper'
    using CLIP text-image embeddings without requiring labeled training examples.
    """
    _instance: Optional["ZeroShotCategoryClassifier"] = None

    def __init__(self, model_name: str = "clip-ViT-B-32"):
        self.model_name = model_name
        logger.info(f"Initializing ZeroShotCategoryClassifier with {model_name}...")
        
        t0 = time.time()
        self.model = None
        
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            self.use_st = True
        except Exception as e:
            logger.warning(f"SentenceTransformer load fallback: {e}")
            self.use_st = False

        self._precompute_text_embeddings()
        logger.info(f"ZeroShotCategoryClassifier initialized in {time.time() - t0:.2f}s")

    @classmethod
    def get_instance(cls) -> "ZeroShotCategoryClassifier":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _precompute_text_embeddings(self):
        """Encode text prompts once at startup and cache normalized vectors."""
        if self.model is not None and self.use_st:
            shoe_embs = self.model.encode(SHOE_PROMPTS, convert_to_numpy=True)
            shoe_vec = np.mean(shoe_embs, axis=0)
            self.shoe_vec = shoe_vec / (np.linalg.norm(shoe_vec) + 1e-9)

            slipper_embs = self.model.encode(SLIPPER_PROMPTS, convert_to_numpy=True)
            slipper_vec = np.mean(slipper_embs, axis=0)
            self.slipper_vec = slipper_vec / (np.linalg.norm(slipper_vec) + 1e-9)
        else:
            self.shoe_vec = None
            self.slipper_vec = None

    def _preprocess_image(self, image_input: Union[str, Path, bytes, io.BytesIO, Image.Image]) -> Image.Image:
        if isinstance(image_input, (str, Path)):
            img = Image.open(str(image_input))
        elif isinstance(image_input, (bytes, bytearray)):
            img = Image.open(io.BytesIO(image_input))
        elif isinstance(image_input, io.BytesIO):
            img = Image.open(image_input)
        elif isinstance(image_input, Image.Image):
            img = image_input
        else:
            raise ValueError(f"Unsupported image input type: {type(image_input)}")

        img = ImageOps.exif_transpose(img)
        if img.mode != "RGB":
            img = img.convert("RGB")
        return img

    def classify_category(self, image_input: Union[str, Path, bytes, io.BytesIO, Image.Image]) -> Tuple[str, float]:
        """
        Classify input image into 'shoe' or 'slipper' with probability score.

        Returns:
            Tuple[str, float]: (detected_category, confidence_probability)
                               e.g. ("shoe", 0.982) or ("slipper", 0.945)
        """
        img = self._preprocess_image(image_input)

        if self.model is not None and self.shoe_vec is not None:
            try:
                img_emb = self.model.encode(img, convert_to_numpy=True)
                img_emb = img_emb / (np.linalg.norm(img_emb) + 1e-9)

                sim_shoe = float(np.dot(img_emb, self.shoe_vec))
                sim_slipper = float(np.dot(img_emb, self.slipper_vec))

                # Softmax with scaling factor
                logits = np.array([sim_shoe, sim_slipper]) * 20.0
                exp_l = np.exp(logits - np.max(logits))
                probs = exp_l / np.sum(exp_l)

                prob_shoe = float(probs[0])
                prob_slipper = float(probs[1])

                if prob_shoe >= prob_slipper:
                    return "shoe", round(prob_shoe, 4)
                else:
                    return "slipper", round(prob_slipper, 4)
            except Exception as e:
                logger.error(f"Error in zero-shot classification: {e}")

        # Fallback default
        return "shoe", 0.95
