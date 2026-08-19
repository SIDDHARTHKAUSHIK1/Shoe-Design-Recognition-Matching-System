"""
Fine-tuning and Metric Learning for Background-Invariant Footwear Embeddings.

Synthesizes multiple background variations for every shoe design (solid colors, gradients, textures),
pairs them with same-background hard negatives (different shoe on same background),
and trains a background-invariant projection head with Triplet Margin Loss.

Usage:
    python scripts/finetune_background_invariant.py [--epochs 25] [--batch_size 16] [--lr 1e-3]
"""
import os
import sys
import time
import random
import argparse
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Any

from PIL import Image, ImageFilter, ImageDraw
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend import database as db
from backend.config import STORAGE_DIR, EMBEDDING_DIM
from backend.foreground import isolate_foreground
from backend.engine import EmbeddingEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MODELS_DIR = STORAGE_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
HEAD_SAVE_PATH = MODELS_DIR / "background_invariant_head.pt"


# ==========================================
# 1. Synthetic Background Generator
# ==========================================
class SyntheticBackgroundGenerator:
    """Generates synthetic backgrounds: solid colors, gradients, textures, noise."""
    @staticmethod
    def generate(size: Tuple[int, int]) -> Image.Image:
        w, h = size
        mode = random.choice(["solid", "linear_gradient", "radial_gradient", "tile_texture", "noise"])
        
        if mode == "solid":
            color = (random.randint(20, 240), random.randint(20, 240), random.randint(20, 240))
            return Image.new("RGB", (w, h), color=color)

        elif mode == "linear_gradient":
            c1 = np.array([random.randint(30, 230), random.randint(30, 230), random.randint(30, 230)])
            c2 = np.array([random.randint(30, 230), random.randint(30, 230), random.randint(30, 230)])
            grad = np.zeros((h, w, 3), dtype=np.uint8)
            for y in range(h):
                alpha = y / float(h)
                grad[y, :, :] = (1.0 - alpha) * c1 + alpha * c2
            return Image.fromarray(grad)

        elif mode == "radial_gradient":
            cx, cy = w // 2, h // 2
            max_r = np.sqrt(cx**2 + cy**2)
            c_center = np.array([random.randint(40, 240), random.randint(40, 240), random.randint(40, 240)])
            c_edge = np.array([random.randint(20, 200), random.randint(20, 200), random.randint(20, 200)])
            
            y_coords, x_coords = np.ogrid[:h, :w]
            dist = np.sqrt((x_coords - cx)**2 + (y_coords - cy)**2) / max_r
            dist = np.clip(dist, 0.0, 1.0)[:, :, None]
            grad = (1.0 - dist) * c_center + dist * c_edge
            return Image.fromarray(grad.astype(np.uint8))

        elif mode == "tile_texture":
            tile_size = random.randint(20, 40)
            c1 = (random.randint(40, 220), random.randint(40, 220), random.randint(40, 220))
            c2 = (random.randint(30, 200), random.randint(30, 200), random.randint(30, 200))
            img = Image.new("RGB", (w, h), color=c1)
            draw = ImageDraw.Draw(img)
            for x in range(0, w, tile_size * 2):
                for y in range(0, h, tile_size * 2):
                    draw.rectangle([x, y, x + tile_size, y + tile_size], fill=c2)
                    draw.rectangle([x + tile_size, y + tile_size, x + 2*tile_size, y + 2*tile_size], fill=c2)
            return img.filter(ImageFilter.GaussianBlur(radius=1.5))

        else:
            noise = np.random.randint(60, 200, (h, w, 3), dtype=np.uint8)
            img = Image.fromarray(noise)
            return img.filter(ImageFilter.GaussianBlur(radius=random.uniform(2.0, 5.0)))


def composite_on_background(foreground_crop: Image.Image, bg: Image.Image) -> Image.Image:
    """Composite a cropped footwear onto a given background."""
    bg_resized = bg.resize(foreground_crop.size, Image.BILINEAR)
    return Image.blend(bg_resized, foreground_crop, alpha=0.85)


# ==========================================
# 2. Residual Background-Invariant Projector
# ==========================================
class InvariantProjectionHead(nn.Module):
    """
    Residual projection head that refines DINOv2 embeddings into a background-invariant space.
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
        # Initialize residual projection to small weights
        nn.init.normal_(self.mlp[0].weight, std=0.01)
        nn.init.zeros_(self.mlp[-1].weight)
        nn.init.zeros_(self.mlp[-1].bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        res = self.mlp(x)
        out = x + res
        return nn.functional.normalize(out, p=2, dim=-1)


# ==========================================
# 3. Training Function with Batched Feature Pre-computation
# ==========================================
def train_background_invariant_head(epochs: int = 25, batch_size: int = 16, lr: float = 1e-3, margin: float = 0.3):
    t0 = time.time()
    logger.info("=== Starting Background-Invariant Metric Learning Fine-Tuning ===")

    db.init_db()
    all_refs = db.get_all_reference_images()
    design_crops = {}

    # Load pre-segmented images
    for r in all_refs:
        d_id = r["design_id"]
        img_name = Path(r["image_path"]).name
        candidates = [
            STORAGE_DIR / "catalog_segmented" / d_id / img_name,
            STORAGE_DIR / "catalog_images" / d_id / img_name,
            BASE_DIR / r["image_path"]
        ]
        for c in candidates:
            if c.exists():
                try:
                    img = Image.open(c).convert("RGB")
                    design_crops.setdefault(d_id, []).append(img)
                    break
                except Exception:
                    pass

    design_ids = list(design_crops.keys())
    if len(design_ids) < 2:
        logger.error(f"Not enough distinct designs found (found {len(design_ids)}).")
        return

    logger.info(f"Loaded {len(design_ids)} distinct designs. Generating synthetic composite triplets...")
    bg_gen = SyntheticBackgroundGenerator()

    anchors_imgs = []
    positives_imgs = []
    negatives_imgs = []

    samples_per_design = 8
    for d_id in design_ids:
        crops = design_crops[d_id]
        for _ in range(samples_per_design):
            crop_a = random.choice(crops)
            crop_p = random.choice(crops)
            
            # Different design for negative
            neg_d_id = random.choice([d for d in design_ids if d != d_id])
            crop_n = random.choice(design_crops[neg_d_id])

            bg_A = bg_gen.generate(crop_a.size)
            bg_B = bg_gen.generate(crop_p.size)

            # Anchor (Shoe X on BG A) & Positive (Shoe X on BG B)
            anchors_imgs.append(composite_on_background(crop_a, bg_A))
            positives_imgs.append(composite_on_background(crop_p, bg_B))
            # Negative (Shoe Y on BG A) - same background as anchor!
            negatives_imgs.append(composite_on_background(crop_n, bg_A))

    total_triplets = len(anchors_imgs)
    logger.info(f"Synthesized {total_triplets} triplets. Computing DINOv2 embeddings in batches...")

    engine = EmbeddingEngine.get_instance()
    all_imgs = anchors_imgs + positives_imgs + negatives_imgs
    all_embs = engine.get_batch_embeddings(all_imgs, batch_size=32)

    emb_anchors = torch.tensor(all_embs[0:total_triplets], dtype=torch.float32)
    emb_positives = torch.tensor(all_embs[total_triplets:2*total_triplets], dtype=torch.float32)
    emb_negatives = torch.tensor(all_embs[2*total_triplets:], dtype=torch.float32)

    # Tensor Dataset & DataLoader
    dataset = torch.utils.data.TensorDataset(emb_anchors, emb_positives, emb_negatives)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = InvariantProjectionHead(in_dim=EMBEDDING_DIM).to(device)
    criterion = nn.TripletMarginLoss(margin=margin, p=2)
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    logger.info(f"Training InvariantProjectionHead for {epochs} epochs on {device}...")
    model.train()

    for epoch in range(1, epochs + 1):
        total_loss = 0.0
        for batch_a, batch_p, batch_n in dataloader:
            batch_a, batch_p, batch_n = batch_a.to(device), batch_p.to(device), batch_n.to(device)

            optimizer.zero_grad()
            out_a = model(batch_a)
            out_p = model(batch_p)
            out_n = model(batch_n)

            loss = criterion(out_a, out_p, out_n)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * batch_a.size(0)

        scheduler.step()
        avg_loss = total_loss / total_triplets
        if epoch % 5 == 0 or epoch == epochs:
            logger.info(f"Epoch [{epoch:02d}/{epochs:02d}] - Triplet Loss: {avg_loss:.4f} (lr: {scheduler.get_last_lr()[0]:.6f})")

    # Save trained head weights
    torch.save(model.state_dict(), str(HEAD_SAVE_PATH))
    logger.info(f"Successfully saved Background-Invariant Head to: {HEAD_SAVE_PATH}")
    logger.info(f"Training completed in {time.time() - t0:.2f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fine-tune background-invariant footwear projection head.")
    parser.add_argument("--epochs", type=int, default=25, help="Training epochs")
    parser.add_argument("--batch_size", type=int, default=16, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    args = parser.parse_args()

    train_background_invariant_head(epochs=args.epochs, batch_size=args.batch_size, lr=args.lr)
