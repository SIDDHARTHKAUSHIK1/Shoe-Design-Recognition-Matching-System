# Master Prompt — Make Top-1 Catalog Matching Reliably Correct

Paste this whole prompt into your coding assistant (or use it as your own implementation checklist) inside the `Shoe_Design_Detection` repo.

---

## Context (confirmed with the project owner — read this first)

- The **real, live catalog is 36 designs / 39 reference photos**, currently indexed in `storage/catalog.db` + `storage/shoe_index.faiss`. This is limited stock on purpose.
- `data/catalog` and `storage/catalog_images` on disk also contain ~139 additional folders (`DESIGN_001`–`DESIGN_048`, most even-numbered `SHOE-XXX`, etc.). **These are confirmed old test/sample data, not real stock. Do not index them. Do not run `scripts/reindex_missing_designs.py`.** Any change in this task must leave the catalog at exactly the same 36 designs it has today, unless the task is explicitly "add more reference photos of an *existing* design" (see Lever 4 below — that's adding photos, not designs).
- The project owner has already trained a custom model component on ~1500 photos: `storage/models/background_invariant_head.pt` (a small residual projection head on top of DINOv2, defined in `backend/engine.py`'s `InvariantProjectionHead`, trained via `scripts/finetune_background_invariant.py` / `scripts/train_kaggle_metric_learning.py`). There are three checkpoints sitting side by side in `storage/models/`: `background_invariant_head.pt` (current), `background_invariant_head_v1_backup.pt`, and `background_invariant_head_v2.pt`. Nothing in the repo currently proves which one is actually best on the real 36-design catalog — that needs to be checked, not assumed.
- A prior pass on this repo already fixed two real bugs, both already committed: (1) `backend/ingestion.py` now computes and stores `color_histogram`/`dominant_colors` at ingest time — previously dead code, meaning `backend/matcher.py`'s documented 75% design / 25% color blend (`WEIGHT_DESIGN` / `WEIGHT_COLOR` in `backend/config.py`) was silently 100% design-only; (2) an angle-classification typo (`elif "back" or "heel" in lower:`) that mislabeled nearly every image's angle as "heel". `scripts/backfill_reference_colors.py` exists to catch up any reference photo still missing color data (currently 2 of 39).

## Goal

Given **any new photo** of a shoe that is genuinely one of the 36 real catalog designs — taken with a different camera, background, lighting, or angle than the clean reference photos already in the catalog — the app's `POST /api/match` should return that design ranked **#1**, with a confidence score that honestly reflects how sure the match is.

**Hard requirement — exact catalog photo re-uploads:** if the uploaded file *is* (or is a near-identical copy of) one of the 39 reference photos already stored in the catalog, that design **must** come back at #1, every single time, with a high confidence score. This is not a "similar design is fine" case — there's zero ambiguity when the query is a copy of a photo the system already has, so anything other than a #1, high-confidence hit here is a real bug that needs to be found and fixed before moving on to anything else. Cover this with a dedicated, unmodified-file test in the harness below (not the perturbed versions) and require 100% Top-1 on it as a gate.

**What counts as failure for genuinely new/different photos:** the correct design landing at #1 is the target. If it lands at #2 or #3 instead, that is *not* a failure — the app already presents Top-3 as a ranked set of similar designs from the catalog, so the correct shoe still showed up as one of the "similar designs we have." Only two things count as real failures worth fixing: (a) a genuinely different, unrelated design occupying the #1 spot while the correct one is still #2/#3 or absent, and (b) the correct design missing from the Top-3 entirely. Don't chase #2-vs-#1 ordering between two legitimately similar designs as if it were a bug — that's the system working as intended.

## Why the currently-published accuracy numbers can't be trusted for this goal

`evaluate.py` runs Leave-One-Out on the catalog's own reference photos using `engine.get_embedding()` and **raw cosine similarity only** — it never calls `backend.matcher.ShoeMatcher.match_image()`, so it doesn't exercise color-aware scoring, category bonus, the rejection threshold, or the visual-duplicate dedup logic that real queries go through. It also measures "does one catalog photo retrieve another catalog photo of the same design" — a much easier task than "does a fresh phone photo, taken under different conditions, retrieve the right design." Treat its 97%+ number as an optimistic upper bound, not a field accuracy measurement. **Do not report a fix as "done" based on `evaluate.py` alone.**

## The work, in order

### 1. Build an honest, field-realistic evaluation harness

Create `scripts/evaluate_field_accuracy.py` (or extend `evaluate.py` behind a flag) that:
- Calls `backend.matcher.ShoeMatcher().match_image()` directly — the exact same code path `POST /api/match` uses — not raw cosine similarity.
- **Test 0 — exact-copy gate (run first, must be 100%):** re-upload every one of the 39 stored reference photos completely unmodified as the query. Every single one must return its own design at #1. Report this as a pass/fail count on its own, separate from everything else below — if this isn't 100%, stop and fix that before evaluating anything perturbed or field-realistic, since it means something more basic than "generalization to new photos" is broken (e.g. embedding nondeterminism, a stale/out-of-sync index, or a threshold rejecting a near-1.0 similarity).
- **Test 1 — field-realistic perturbed queries:** for each of the 36 designs' reference photos, generate 2-3 *perturbed* copies to stand in for a real customer photo: JPEG re-compression at a lower quality, a random ±5-10% crop, a brightness/white-balance shift, and a small rotation (±5°). Use these perturbed images as queries, not the literal original file — querying with the byte-identical file is close to a trivial self-match and won't reveal real weaknesses.
- **Test 2 — leave-one-out across angles:** for designs with 2+ reference photos, exclude one reference photo's vector from the FAISS index for that query, and confirm the design still comes back at rank 1 from its *other* angle photos alone.
- Reports Test 0's pass rate separately (must be 100%), plus for Tests 1-2: Top-1 accuracy (correct design is rank #1), Top-3 "still surfaced" rate (correct design is rank #2 or #3 — logged separately as "shown as a similar design," not a failure), and true miss rate (correct design absent from Top-3, or a different design occupies #1). Only Test 0 failures and Test 1-2 true-miss cases count as failures.
- **Lists every individual true-miss case** (query, expected design, what was actually returned at #1, confidence) so they can be inspected one by one, not just summarized as a percentage. Do not list #2/#3-ranked correct matches as failures.
- Run this now, before making further changes, to get a real baseline. Then re-run it after each change below and compare — the number to move is the true-miss rate and Top-1 rate, not the Top-3 "still surfaced" rate.

### 2. Validate the trained background-invariant head instead of assuming it helps

`ENABLE_INVARIANT_HEAD` in `backend/config.py` gates whether `InvariantProjectionHead` (in `backend/engine.py`) is applied on top of every DINOv2 embedding. Using the harness from step 1:
- Run the full field-accuracy eval with `ENABLE_INVARIANT_HEAD=true` (current) vs. `ENABLE_INVARIANT_HEAD=false` (raw DINOv2 only).
- If `true` wins, also swap in `background_invariant_head_v1_backup.pt` and `background_invariant_head_v2.pt` (temporarily point `INVARIANT_HEAD_PATH` at each) and compare all three. Keep whichever checkpoint actually scores best on the field-realistic harness — don't assume the newest file is the best-trained one.
- Delete or clearly archive the checkpoint(s) that lose, so nobody accidentally loads a worse one later.

### 3. Recalibrate scoring weights and thresholds against the fixed pipeline

Color-aware scoring only became a real (non-constant) signal once the ingestion fix landed — the current `WEIGHT_DESIGN=0.75` / `WEIGHT_COLOR=0.25` split in `backend/config.py` and the per-category values in `config/thresholds.json` (`rejection_threshold`, `margin_threshold`, `min_density`, `platt_scaling.a/b`) were tuned (or hand-picked) before that fix existed. Re-run `scripts/calibrate_thresholds.py` against the current 36-design catalog, and specifically check with the field-accuracy harness from step 1 whether 75/25 is actually optimal for this catalog or whether a different split (try 60/40, 85/15 as bracketing points) does better — don't leave it at its current value just because that's what's there.

### 4. Strengthen the 36 existing designs with more reference angles (not more designs)

Pull each design's `reference_images` count via `backend.database.get_design(design_id)`. Any design with only 1 reference photo is far more fragile to real-world angle/lighting variation than one with 3+. This is **not** catalog growth in the sense the owner ruled out — it's making the *existing* 36 shoes more recognizable from more angles, using the existing `POST /api/designs` endpoint (`backend.database.add_design` is an upsert on `design_id`, so posting more photos against an existing design_id correctly adds reference images without creating a duplicate design). Recommend: for any of the 36 designs with fewer than 3 reference angles, capture 2-3 more photos under conditions closer to how customers will actually photograph the shoe (not just a clean studio background), and add them via the existing endpoint. Re-run the field-accuracy harness after each batch to confirm it actually helps before doing all 36.

### 5. Sanity-check the footwear/category gate isn't silently rejecting good queries

`backend/footwear_gate.py` and `backend/classifier.py` run before the FAISS search and can reject a query outright (`reason: "out_of_distribution"` / `"ambiguous_category"`) or misclassify shoe vs. slipper. Using the same perturbed test images from step 1, confirm none of them are being wrongly gated out before they even reach the matcher — a false rejection here looks identical to "low accuracy" from the user's side but has nothing to do with ranking quality.

## Explicit boundaries

- Do not add any of the ~139 non-stock folders to the index.
- Do not change the total design count of 36 as a side effect of any step above — only reference-photo counts within existing designs may grow (step 4), and only for designs that need it.
- Any threshold, weight, or checkpoint change must be justified by a before/after number from the step-1 harness, not intuition.
- **Do not run `git commit` (or any other git write command — `git add` staged for a later commit is fine to leave staged, but do not commit, push, tag, or amend) at any point during this work.** Make all file changes as plain edits on disk. Leave committing to the project owner, who will review and commit manually.
- **Run the server on port 8001, not 8000** — port 8000 is already in use on this machine. `backend/config.py` reads `PORT = int(os.getenv("PORT", "8000"))`, so start it with the `PORT` environment variable set to `8001` instead of editing the default in code:
  - Windows PowerShell: `$env:PORT=8001; python run_server.py`
  - Windows cmd: `set PORT=8001 && python run_server.py`
  - macOS/Linux: `PORT=8001 python run_server.py`
  
  After starting, confirm the app is reachable at `http://localhost:8001/app` (not port 8000) before running any of the evaluation scripts against it.

## Deliverable

- `scripts/evaluate_field_accuracy.py` (new).
- A short before/after report: Test 0's exact-copy pass rate (must reach 100% — call this out explicitly, don't bury it in an average), plus Top-1 rate, Top-3 "still surfaced" rate, and true-miss rate for Tests 1-2, at the start vs. after steps 2-5. Include which checkpoint and weight values won and why, and a list of any designs still in the true-miss bucket along with a hypothesis for each (e.g. "only 1 reference angle", "near-identical color/shape to design X").
