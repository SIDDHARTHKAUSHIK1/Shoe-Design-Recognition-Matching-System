"""
Vision Embedding Engine using DINOv2 / CLIP with PyTorch & HuggingFace.
"""
import io
import time
import logging
from pathlib import Path
from typing import Union, List, Optional, Tuple, Dict, Any
from PIL import Image, ImageOps
import numpy as np
import torch
import torch.nn as nn
from transformers import AutoImageProcessor, AutoModel

from backend.config import MODEL_NAME, EMBEDDING_DIM, ENABLE_TTA, TTA_CROPS, ENABLE_INVARIANT_HEAD, INVARIANT_HEAD_PATH

logger = logging.getLogger(__name__)


class InvariantProjectionHead(nn.Module):
    """
    Residual projection head that refines DINOv2 embeddings into a background-invariant metric space.
    f(x) = L2_Normalize(x + W2(GELU(W1(x))))
    """
    def __init__(self, in_dim: int = 384, hidden_dim: int = 512):
        super().__init__()
        self.mlp = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, in_dim)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        res = self.mlp(x)
        out = x + res
        return torch.nn.functional.normalize(out, p=2, dim=-1)


class EmbeddingEngine:
    """
    Singleton Embedding Engine for extracting deterministic visual embeddings.
    Loaded once at application startup to ensure sub-second query latency.
    """
    _instance: Optional["EmbeddingEngine"] = None

    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Initializing EmbeddingEngine with {model_name} on device: {self.device} (TTA={ENABLE_TTA}, crops={TTA_CROPS})")
        
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
            
            # Low-memory CPU optimization for Render 512MB RAM instances
            if self.device == "cpu":
                torch.set_num_threads(1)
                try:
                    self.model = torch.quantization.quantize_dynamic(
                        self.model, {torch.nn.Linear}, dtype=torch.qint8
                    )
                    logger.info("DINOv2 dynamically quantized to INT8 (reduced RAM footprint).")
                except Exception as qe:
                    logger.warning(f"Quantization note: {qe}")

        # Initialize Background-Invariant Projection Head if available
        self.invariant_head = None
        if ENABLE_INVARIANT_HEAD and INVARIANT_HEAD_PATH.exists():
            try:
                self.invariant_head = InvariantProjectionHead(in_dim=EMBEDDING_DIM).to(self.device)
                self.invariant_head.load_state_dict(torch.load(str(INVARIANT_HEAD_PATH), map_location=self.device))
                self.invariant_head.eval()
                logger.info("Loaded background-invariant projection head weights.")
            except Exception as e:
                logger.warning(f"Could not load background-invariant head: {e}")
            
        # Warmup model
        self._warmup()
        import gc
        gc.collect()
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

    def isolate_image_foreground(
        self,
        image_input: Union[str, Path, bytes, io.BytesIO, Image.Image]
    ) -> Tuple[Image.Image, Optional[str], dict]:
        """
        Discrete, testable helper to isolate footwear from background clutter.
        Runs before resizing/normalization.
        """
        from backend.foreground import isolate_foreground
        img = self.preprocess_image(image_input)
        return isolate_foreground(img)

    def extract_query_features(
        self,
        image_input: Union[str, Path, bytes, io.BytesIO, Image.Image],
        auto_crop: bool = True
    ) -> Tuple[np.ndarray, Optional[str], dict]:
        """
        Extract L2-normalized visual embedding with optional foreground auto-cropping.
        
        Returns:
            Tuple of:
                - L2-normalized 1D float32 vector (384-d).
                - Rejection reason string (e.g. 'no_clear_object') if no clear object found.
                - Foreground crop metadata dict.
        """
        img = self.preprocess_image(image_input)
        rejection_reason = None
        crop_meta = {"cropped": False}

        if auto_crop:
            img, rejection_reason, crop_meta = self.isolate_image_foreground(img)

        # If no clear object found, still compute embedding for fallback, but return rejection reason
        emb = self._compute_embedding(img)
        return emb, rejection_reason, crop_meta

    def _compute_embedding(self, img: Image.Image, use_tta: Optional[bool] = None) -> np.ndarray:
        """Internal computation of normalized DINOv2 embedding with optional batched TTA."""
        if getattr(self, "use_st", False):
            emb = self.st_model.encode(img, convert_to_numpy=True, normalize_embeddings=True)
            return emb.astype(np.float32)
            
        if use_tta is None:
            use_tta = ENABLE_TTA

        if use_tta:
            # Multi-crop augmentation: original + horizontal mirror
            crops = [img, ImageOps.mirror(img)]
            if TTA_CROPS >= 3:
                w, h = img.size
                crop_box = (int(w * 0.05), int(h * 0.05), int(w * 0.95), int(h * 0.95))
                crops.append(img.crop(crop_box))
            
            inputs = self.processor(images=crops, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
                    embs = outputs.pooler_output
                else:
                    embs = outputs.last_hidden_state[:, 0, :]
                
                # Normalize each crop embedding
                embs = torch.nn.functional.normalize(embs, p=2, dim=1)
                # Mean pool across augmented views and re-normalize to unit length
                mean_emb = torch.nn.functional.normalize(embs.mean(dim=0, keepdim=True), p=2, dim=1)
                
                # Apply background-invariant projection if available
                if self.invariant_head is not None:
                    mean_emb = self.invariant_head(mean_emb)
                
            return mean_emb.cpu().numpy()[0].astype(np.float32)

        inputs = self.processor(images=img, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            # Use CLS token representation from last hidden state
            if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
                emb = outputs.pooler_output
            else:
                emb = outputs.last_hidden_state[:, 0, :]
                
            # L2 Normalize the vector so cosine similarity == dot product
            emb = torch.nn.functional.normalize(emb, p=2, dim=1)
            
            # Apply background-invariant projection if available
            if self.invariant_head is not None:
                emb = self.invariant_head(emb)
            
        return emb.cpu().numpy()[0].astype(np.float32)

    def get_embedding(
        self, 
        image_input: Union[str, Path, bytes, io.BytesIO, Image.Image],
        auto_crop: bool = True
    ) -> np.ndarray:
        """
        Compute an L2-normalized 1D visual embedding vector for a single image.
        
        Args:
            image_input: Filepath, bytes, or PIL Image.
            auto_crop: Whether to auto-crop the foreground object before embedding (default True).
            
        Returns:
            np.ndarray: L2-normalized 1D float32 vector.
        """
        img = self.preprocess_image(image_input)
        if auto_crop:
            from backend.foreground import isolate_foreground
            img, _, _ = isolate_foreground(img)
            
        return self._compute_embedding(img)

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
                
                if self.invariant_head is not None:
                    emb = self.invariant_head(emb)
                    
                all_embeddings.append(emb.cpu().numpy().astype(np.float32))
                
        if all_embeddings:
            return np.vstack(all_embeddings)
        return np.empty((0, EMBEDDING_DIM), dtype=np.float32)


# Global helper functions
def get_embedding(image_input: Union[str, Path, bytes, io.BytesIO, Image.Image]) -> np.ndarray:
    """Convenience helper to extract embedding using the singleton engine."""
    return EmbeddingEngine.get_instance().get_embedding(image_input)
