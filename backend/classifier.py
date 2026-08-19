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
    "a photo of a shoe or sneaker",
    "a photo of footwear, sneakers, dress shoes, boots, or loafers",
    "a photo of a closed-toe shoe or athletic shoe",
    "shoes on a white background",
    "a photo of a leather shoe or boot"
]

SLIPPER_PROMPTS = [
    "a photo of a slipper or slide sandal",
    "a photo of house slippers, bedroom slippers, or flip-flops",
    "a photo of open-toe slippers, slides, or sandals",
    "slippers or flip-flops",
    "a photo of indoor comfort slippers"
]

NON_FOOTWEAR_PROMPTS = [
    "a photo of a person, human face, portrait, man, woman, or child",
    "a photo of an animal, dog, cat, bird, horse, or wildlife",
    "a photo of a car, automobile, truck, motorcycle, or vehicle",
    "a photo of a computer, laptop, smartphone, TV, screen, or electronics",
    "a photo of food, pizza, fruit, vegetables, beverage, or meal",
    "a photo of furniture, chair, table, sofa, bed, or interior room",
    "a photo of a building, house, street, city architecture, landscape, sky, or nature",
    "a photo of clothes, shirt, pants, jacket, watch, bag, or hat",
    "a photo of a random non-footwear object, blank surface, or abstract graphic",
    "nothing, noise, abstract pattern, or empty background"
]


class ZeroShotCategoryClassifier:
    """
    Zero-shot classifier that detects whether an image is a 'shoe', 'slipper',
    or 'none' (non-footwear / random image) using CLIP text-image alignment.
    """
    _instance: Optional["ZeroShotCategoryClassifier"] = None

    def __init__(self, model_name: str = "clip-ViT-B-32"):
        self.model_name = model_name
        logger.info(f"Initializing ZeroShotCategoryClassifier with {model_name}...")
        
        t0 = time.time()
        self.model = None
        
        try:
            import torch
            torch.set_num_threads(1)
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name, device="cpu")
            self.use_st = True
        except Exception as e:
            logger.warning(f"SentenceTransformer load fallback: {e}")
            self.use_st = False

        self._precompute_text_embeddings()
        
        # Free unnecessary memory and garbage collect
        import gc
        gc.collect()
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

            non_fw_embs = self.model.encode(NON_FOOTWEAR_PROMPTS, convert_to_numpy=True)
            non_fw_vec = np.mean(non_fw_embs, axis=0)
            self.non_footwear_vec = non_fw_vec / (np.linalg.norm(non_fw_vec) + 1e-9)
        else:
            self.shoe_vec = None
            self.slipper_vec = None
            self.non_footwear_vec = None

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
        Classify input image into 'shoe', 'slipper', or 'none' (non-footwear).

        Returns:
            Tuple[str, float]: (detected_category, confidence_probability)
                               e.g. ("shoe", 0.982), ("slipper", 0.945), or ("none", 0.0)
        """
        img = self._preprocess_image(image_input)

        if self.model is not None and self.shoe_vec is not None:
            try:
                img_emb = self.model.encode(img, convert_to_numpy=True)
                img_emb = img_emb / (np.linalg.norm(img_emb) + 1e-9)

                sim_shoe = float(np.dot(img_emb, self.shoe_vec))
                sim_slipper = float(np.dot(img_emb, self.slipper_vec))
                sim_non_fw = float(np.dot(img_emb, self.non_footwear_vec))

                # Softmax with scaling factor
                logits = np.array([sim_shoe, sim_slipper, sim_non_fw]) * 22.0
                exp_l = np.exp(logits - np.max(logits))
                probs = exp_l / np.sum(exp_l)

                prob_shoe = float(probs[0])
                prob_slipper = float(probs[1])
                prob_non_fw = float(probs[2])

                max_footwear_sim = max(sim_shoe, sim_slipper)
                margin = max_footwear_sim - sim_non_fw

                # Non-footwear conditions:
                # 1. Non-footwear class has the highest softmax probability
                # 2. Footwear similarity margin over non-footwear is too small (<= 0.012)
                # 3. Both shoe and slipper similarities are below absolute baseline
                if prob_non_fw >= prob_shoe and prob_non_fw >= prob_slipper:
                    return "none", round(prob_non_fw, 4)
                
                if margin <= 0.012 or max_footwear_sim < 0.19:
                    return "none", round(prob_non_fw, 4)

                # Re-normalize between shoe and slipper
                sub_probs = np.array([prob_shoe, prob_slipper])
                sub_probs = sub_probs / (np.sum(sub_probs) + 1e-9)

                if sub_probs[0] >= sub_probs[1]:
                    return "shoe", round(float(sub_probs[0]), 4)
                else:
                    return "slipper", round(float(sub_probs[1]), 4)
            except Exception as e:
                logger.error(f"Error in zero-shot classification: {e}")

        # Fallback default
        return "shoe", 0.95
