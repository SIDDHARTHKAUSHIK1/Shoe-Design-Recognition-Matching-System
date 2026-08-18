"""
Vision Embedding Engine using DINOv2 / CLIP with PyTorch & HuggingFace.
"""
import io
import time
import logging
from pathlib import Path
from typing import Union, List, Optional
from PIL import Image, ImageOps
import numpy as np
import torch
from transformers import AutoImageProcessor, AutoModel

from backend.config import MODEL_NAME, EMBEDDING_DIM

logger = logging.getLogger(__name__)


class EmbeddingEngine:
    """
    Singleton Embedding Engine for extracting deterministic visual embeddings.
    Loaded once at application startup to ensure sub-second query latency.
    """
    _instance: Optional["EmbeddingEngine"] = None

    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Initializing EmbeddingEngine with {model_name} on device: {self.device}")
        
        t0 = time.time()
        self.use_st = False
        
        if "clip" in model_name.lower():
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading SentenceTransformer model: {model_name}")
                self.st_model = SentenceTransformer(model_name, device=self.device)
                self.use_st = True
            except Exception as e:
                logger.warning(f"Could not load via SentenceTransformer ({e}). Falling back to AutoModel.")
                self.processor = AutoImageProcessor.from_pretrained(model_name)
                self.model = AutoModel.from_pretrained(model_name).to(self.device)
                self.model.eval()
        else:
            self.processor = AutoImageProcessor.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name).to(self.device)
            self.model.eval()
            
        # Warmup model
        self._warmup()
        logger.info(f"Model {model_name} loaded and warmed up in {time.time() - t0:.2f}s")

    @classmethod
    def get_instance(cls) -> "EmbeddingEngine":
        """Get or initialize singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _warmup(self):
        """Run a dummy forward pass to prime CPU/GPU caches and torch kernels."""
        dummy_img = Image.new("RGB", (224, 224), color=(128, 128, 128))
        _ = self.get_embedding(dummy_img)

    def preprocess_image(self, image_input: Union[str, Path, bytes, io.BytesIO, Image.Image]) -> Image.Image:
        """
        Preprocess input into a clean, orientation-corrected RGB PIL image.
        """
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

        # Correct EXIF orientation if present
        img = ImageOps.exif_transpose(img)
        
        # Convert RGBA / Grayscale to RGB with white background if transparent
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[3])
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")
            
        return img

    def get_embedding(self, image_input: Union[str, Path, bytes, io.BytesIO, Image.Image]) -> np.ndarray:
        """
        Compute an L2-normalized 1D visual embedding vector for a single image.
        
        Args:
            image_input: Filepath, bytes, or PIL Image.
            
        Returns:
            np.ndarray: L2-normalized 1D float32 vector.
        """
        img = self.preprocess_image(image_input)
        
        if getattr(self, "use_st", False):
            emb = self.st_model.encode(img, convert_to_numpy=True, normalize_embeddings=True)
            return emb.astype(np.float32)
            
        inputs = self.processor(images=img, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            # Use CLS token representation from last hidden state
            # For DINOv2, outputs.last_hidden_state[:, 0, :] is the global image embedding
            if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
                emb = outputs.pooler_output
            else:
                emb = outputs.last_hidden_state[:, 0, :]
                
            # L2 Normalize the vector so cosine similarity == dot product
            emb = torch.nn.functional.normalize(emb, p=2, dim=1)
            
        return emb.cpu().numpy()[0].astype(np.float32)

    def get_batch_embeddings(
        self, 
        images: List[Union[str, Path, bytes, io.BytesIO, Image.Image]],
        batch_size: int = 16
    ) -> np.ndarray:
        """
        Compute normalized embeddings for a list of images in batches.
        
        Args:
            images: List of image inputs.
            batch_size: Batch size for inference.
            
        Returns:
            np.ndarray: 2D array of shape (N, 384)
        """
        all_embeddings = []
        
        for i in range(0, len(images), batch_size):
            batch_inputs = images[i:i + batch_size]
            pil_images = [self.preprocess_image(img) for img in batch_inputs]
            
            inputs = self.processor(images=pil_images, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
                    emb = outputs.pooler_output
                else:
                    emb = outputs.last_hidden_state[:, 0, :]
                    
                emb = torch.nn.functional.normalize(emb, p=2, dim=1)
                all_embeddings.append(emb.cpu().numpy().astype(np.float32))
                
        if all_embeddings:
            return np.vstack(all_embeddings)
        return np.empty((0, EMBEDDING_DIM), dtype=np.float32)


# Global helper functions
def get_embedding(image_input: Union[str, Path, bytes, io.BytesIO, Image.Image]) -> np.ndarray:
    """Convenience helper to extract embedding using the singleton engine."""
    return EmbeddingEngine.get_instance().get_embedding(image_input)
