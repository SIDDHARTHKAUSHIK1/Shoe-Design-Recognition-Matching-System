# Master Prompt — Make Matching Ignore Color, Rank on Design/Texture/Stitching Only

Paste this whole prompt into your coding assistant (or use it as your own implementation checklist) inside the `Shoe_Design_Detection` repo.

---

## Context (read this first — grounded in the actual current code)

Two independent things currently let color influence which design ranks #1, and both need to be addressed together or the fix will be incomplete.

**1. There's an explicit, engineered color-similarity term in the ranking formula.**
`backend/matcher.py`'s `match_image()` (around line 233-245) blends a raw HSV color-histogram similarity into every candidate's score:
```python
color_sim = 1.0
if ENABLE_COLOR_AWARE_SCORING and ref_meta.get("color_histogram"):
    cand_hist = json.loads(ref_meta["color_histogram"])
    color_sim = ColorExtractor.compute_color_similarity(query_hist, cand_hist)

if ENABLE_COLOR_AWARE_SCORING:
    combined_score = WEIGHT_DESIGN * cosine_score + WEIGHT_COLOR * color_sim + cat_bonus
```
`WEIGHT_DESIGN=0.75` / `WEIGHT_COLOR=0.25` / `ENABLE_COLOR_AWARE_SCORING=true` are set in `backend/config.py`. Right now, up to 25% of every match's ranking score is driven purely by how close the query's color histogram is to a candidate's — this is the most direct way color currently affects results, and it's a simple flag flip to remove.

**2. The DINOv2 embedding itself is computed from a full-color image, so it can carry some residual color-correlated signal even with the term above turned off.**
`backend/engine.py`'s `EmbeddingEngine._compute_embedding()` is the single function that turns an image into the 384-d vector used for the actual similarity search (`cosine_score` above) — every caller in the codebase (`match_image()`, `ingest_single_design()`, `evaluate.py`, `scripts/build_footwear_gate.py`, etc.) ultimately routes through it. It currently feeds the isolated foreground crop straight into DINOv2 in full RGB. DINOv2's own pretraining used aggressive color-jitter augmentation, so it's already fairly color-robust — but "fairly robust" isn't "ignores color," and you were explicit that color must not matter at all, only design/shape/texture/stitching. The fix that actually delivers that: strip the color (hue/saturation) out of the image right before it reaches the model, so the embedding is computed from luminance/shape/texture only. This does **not** lose stitching detail — stitch pattern, spacing, and thread contrast against the material are geometric/luminance features, fully visible in grayscale; only hue information (red shoe vs. blue shoe of the same design) is removed, which is exactly what you asked for.

**Important consequence of fix #2 — read before starting:** every one of the 36 designs' 39 reference photos already has a vector sitting in `storage/shoe_index.faiss`, computed the *old* (full-color) way. If you change what `_compute_embedding()` does but don't recompute those 39 existing vectors, every future query (now grayscale-based) will be compared against a stale, inconsistently-computed catalog — this will make matching noticeably *worse*, not better. Re-embedding the existing catalog after the code change is not optional cleanup, it's a required part of this fix (Step 3 below).

The footwear/slipper classification gate (`backend/footwear_gate.py`, `backend/classifier.py`) also reuses this exact same embedding function for its own prototype-matching logic (`scripts/build_footwear_gate.py` builds `storage/models/footwear_gate_bank.npz` by calling `engine.get_embedding()` on sample images) — so it has the identical "must be recomputed after the code change" requirement (Step 4 below).

## Task

1. Turn off the explicit color-histogram scoring term.
2. Make the embedding function itself color-blind (grayscale-in, before DINOv2).
3. Re-embed the existing 36-design catalog so it's consistent with the new embedding function (required, not optional).
4. Rebuild the footwear-gate prototype bank for the same reason (required, not optional).

## Step 1 — `backend/config.py`: disable color-aware scoring

Find:
```python
ENABLE_COLOR_AWARE_SCORING = os.getenv("ENABLE_COLOR_AWARE_SCORING", "true").lower() in ("true", "1", "t")
```
Change the default to `"false"`:
```python
ENABLE_COLOR_AWARE_SCORING = os.getenv("ENABLE_COLOR_AWARE_SCORING", "false").lower() in ("true", "1", "t")
```
Leave `WEIGHT_DESIGN` / `WEIGHT_COLOR` and the `ColorExtractor` class exactly as they are — `backend/matcher.py`'s existing `if ENABLE_COLOR_AWARE_SCORING: ... else: combined_score = cosine_score + cat_bonus` branch already does the right thing once this flag is off; no other line in `matcher.py` needs to change. Do not delete `ColorExtractor` or the `color_histogram`/`dominant_colors` columns/extraction in `backend/ingestion.py` — leave that data being computed and stored (it's harmless, and may still be useful for a future "dominant color" display in the UI even though it no longer affects ranking).

## Step 2 — `backend/engine.py`: make the embedding itself color-blind

In `EmbeddingEngine._compute_embedding(self, img, use_tta=None)`, add a grayscale conversion as the very first thing done to `img`, before any TTA crop generation or processor call. This is the single point every embedding in the app goes through, so this one change covers ingestion, live queries, `evaluate.py`, and the footwear gate consistently — do not duplicate this conversion at each call site instead.

Add right at the top of the function body (after the `use_st` early-return branch, before the `if use_tta:` block):
```python
def _compute_embedding(self, img: Image.Image, use_tta: Optional[bool] = None) -> np.ndarray:
    """Internal computation of normalized DINOv2 embedding with optional batched TTA."""
    if getattr(self, "use_st", False):
        emb = self.st_model.encode(img, convert_to_numpy=True, normalize_embeddings=True)
        return emb.astype(np.float32)

    # Strip hue/saturation before the model ever sees the image — shape, texture, and
    # stitching detail are luminance/geometric features and are fully preserved; only
    # color is removed. Converting via 'L' then back to 'RGB' keeps 3 channels (R=G=B)
    # so the image processor / patch embedding still gets the input shape it expects.
    img = img.convert("L").convert("RGB")

    if use_tta is None:
        use_tta = ENABLE_TTA
    ...
```
Everything after that (`if use_tta:` and below) stays exactly as it is today — the TTA mirror-crop logic, the invariant-head projection, all of it operates on the now-grayscale image without any further changes needed.

Do **not** apply this grayscale conversion earlier in the pipeline (e.g., inside `preprocess_image()` or `isolate_image_foreground()`). Foreground isolation (`backend/foreground.py`'s U2-Netp segmentation) and the color histogram extraction that still runs in `matcher.py` for informational purposes should keep working from the original color image — only the final step that feeds DINOv2 needs to be grayscale.

## Step 3 — Re-embed the existing catalog (REQUIRED, do this before anything else)

There is already an existing script in this repo, `scripts/rebuild_shoe_only_index.py`, that shows the correct, safe pattern for fully rebuilding the FAISS index in place: `VectorStore.reset()`, recompute every reference image's embedding via `engine._compute_embedding()`, `vs.add_vectors()` in the same order, then write the new FAISS IDs back into `reference_images.faiss_id` in SQLite. Model a new script on it — the only real difference is you want **all** reference images re-embedded (not just shoes), since this is a full re-index, not a category filter:

Create `scripts/rebuild_index_grayscale.py`:
- Call `db.init_db()`, then `db.get_all_reference_images()` (not the shoe-only variant) to get every reference row.
- `VectorStore.get_instance().reset()`.
- For each reference row, resolve its image file on disk (mirror the path resolution already used in `scripts/rebuild_shoe_only_index.py` / `scripts/backfill_reference_colors.py`), open it, and call `engine._compute_embedding(Image.open(path).convert("RGB"))` — note: pass the plain opened image the same way `rebuild_shoe_only_index.py` does (not through `isolate_image_foreground` again if the stored file is already the isolated/cropped version — check `CATALOG_IMAGES_DIR` contents to confirm whether stored reference photos are pre-isolated or raw; match whatever `rebuild_shoe_only_index.py` already assumes, since that script is the known-working reference for this exact catalog).
- Collect embeddings in the same order as the reference rows, `vs.add_vectors()` them, and write the returned FAISS IDs back to `reference_images.faiss_id` for each row (`UPDATE reference_images SET faiss_id = ? WHERE id = ?`) — copy this part directly from `rebuild_shoe_only_index.py`, it's already correct.
- Log a final count confirming `vs.total_vectors` matches the number of reference rows re-embedded (should be 39, or however many currently exist).

Run this script once, immediately after Steps 1-2 are in place, before doing anything else with the app. Restart the server afterward so it loads the freshly-rebuilt `storage/shoe_index.faiss` from disk rather than an old in-memory copy.

## Step 4 — Rebuild the footwear-gate prototype bank (REQUIRED, same reason as Step 3)

`scripts/build_footwear_gate.py` already exists and does exactly what's needed — it calls `engine.get_embedding()` (which now routes through the grayscale-aware `_compute_embedding()`) on all its positive/negative sample images and regenerates `storage/models/footwear_gate_bank.npz`. Just re-run it:
```
python scripts/build_footwear_gate.py
```
Run this after Step 3, then restart the server so `BinaryFootwearGate._load_prototype_bank()` picks up the freshly-rebuilt bank instead of the stale one.

## Explicit boundaries

- No new evaluation/testing scripts — you're handling verification yourself. Just make the code changes and run the two required rebuild steps (3 and 4) so the app is in a consistent, working state when you start testing it.
- Do not touch `ColorExtractor`, the `color_histogram`/`dominant_colors` columns, or the color extraction calls in `backend/ingestion.py` and `backend/matcher.py` — leave that data being computed and stored, just no longer weighted into the ranking (Step 1 already achieves that).
- Do not change `backend/foreground.py` (U2-Netp segmentation) — it should keep working from the full-color image; only the final embedding step goes grayscale.
- Do not change the 36-design catalog count, add any of the previously-discussed ~139 non-stock folders, or touch anything in `data/catalog`/`storage/catalog_images` beyond what Step 3's re-embedding script reads.
- No git commits — leave all changes as plain file edits for review.

## What changes for you, practically

Two shoes that are the same design/shape/texture/stitching but different colors should now score close to identically and be much more likely to swap #1/#2/#3 rank based on shape/texture alone rather than one of them "winning" because its color histogram happened to match the query more closely. A single-color design shouldn't get an artificial boost or penalty just because the query photo was taken under different lighting or against a differently-colored background remnant. Since you're testing manually, the most useful check is: take two catalog designs that are visually similar in shape but clearly different in color, and confirm color is no longer the deciding factor between them.
