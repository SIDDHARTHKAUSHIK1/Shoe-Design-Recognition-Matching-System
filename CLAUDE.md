# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

Use the existing `.venv` (Python 3.11). System `python3` is 3.13 and **cannot** install this project: `requirements.txt` caps `torch<2.3.0` (no wheels past 3.11), a pin kept for Intel macOS. Never raise the torch pin without also changing the Dockerfile base image.

```bash
.venv/bin/python -m pip install -r requirements.txt
```

## Commands

```bash
# Run the API + web UI. HOST defaults to the production VPS IP (195.35.6.176)
# in backend/config.py, so bind explicitly or uvicorn fails to start locally.
HOST=127.0.0.1 .venv/bin/python run_server.py     # http://127.0.0.1:8000

.venv/bin/python -m backend.ingestion             # (re)ingest data/catalog into SQLite + FAISS
.venv/bin/python evaluate.py                      # leave-one-out accuracy benchmark
node scripts/build-frontend.mjs                   # full static bundle -> dist/ (fails on missing asset)
npm run build                                     # DIFFERENT: mobile-only copy -> dist/ + cap sync android
```

### Tests

No pytest config and no shared runner — every test file is a standalone script with a `__main__` block. Run one at a time:

```bash
.venv/bin/python tests/test_phase1.py             # plain assert scripts (tests/test_phase*.py)
.venv/bin/python -m unittest tests.test_auth      # unittest-based: test_auth, test_data_guardrails,
                                                  # test_footwear_gate, test_slipper_exclusion, test_upload_security
.venv/bin/python test_api.py                      # root-level test_*.py hit a LIVE server on :8000 — start it first
```

Tests load the real models and the real `storage/catalog.db`; several also depend on images in `storage/` that may not exist locally, so they skip or fail on a fresh checkout rather than being hermetic.

## Architecture

FastAPI backend (`backend/`) + three thin frontends over one REST API. Everything heavy is a lazily-built singleton (`X.get_instance()`) warmed in `main.py`'s `lifespan`: `EmbeddingEngine`, `VectorStore`, `ZeroShotCategoryClassifier`, `BinaryFootwearGate`, `ForegroundIsolator`, `ImageQualityEnhancer`.

### Query pipeline (`ShoeMatcher.match_image`, backend/matcher.py)

Each stage can short-circuit and return `matches: []` with a `reason` — the endpoint still returns HTTP 200, so callers must branch on `reason`/`matched`, not status code.

1. `preprocess_image` — EXIF transpose, RGB, then `preprocessor.enhance_image` (upscale, CLAHE, denoise, white balance).
2. `foreground.isolate_foreground` — U2-Netp ONNX, **auto-downloaded on first use** to `storage/models/u2netp.onnx`; degrades to the raw image if onnxruntime or the download is unavailable. Exits early on `no_clear_object`.
3. `EmbeddingEngine._compute_embedding` — DINOv2-small, 384-d L2-normalized. On CPU the model is dynamically INT8-quantized and pinned to `TORCH_THREADS` (default 1, tuned for 512MB hosts — raise it on a dev box). TTA averages 2 crops. An optional `InvariantProjectionHead` is applied if `storage/models/background_invariant_head.pt` exists.
4. `ZeroShotCategoryClassifier.classify_category_detailed` — two independent signals, ensembled: the `BinaryFootwearGate` prototype bank (embedding-space, from `storage/models/footwear_gate_bank.npz`) and `verify_structural_footwear` (pure OpenCV — grid/line density, aspect ratio, contour solidity, which is what rejects screenshots and documents). UI/blank/extreme-aspect verdicts veto the embedding signal outright. Then a prototype classifier splits shoe vs slipper.
5. **Slippers are rejected** (`slipper_rejected`) — this is a shoe-only catalog despite slipper support existing throughout the code.
6. FAISS search over a deliberately wide pool (`top_k * 50`, min 500), then filtered to the detected category, because category filtering happens *after* retrieval.
7. Scoring: `0.75 * cosine + 0.25 * HSV-histogram color similarity`, then per-category Platt calibration into a confidence %, then de-duplication of candidates whose vectors exceed 0.98 similarity, then top-3.
8. Every query — including rejections — is written to `query_logs`.

### The faiss_id contract

`VectorStore` is a `faiss.IndexFlatIP`, which has **no delete-by-id**. A vector's `faiss_id` is simply its insertion position, and `reference_images.faiss_id` in SQLite is the only link back to metadata (`db.get_reference_image_by_faiss_id`). Consequences:

- Adding is O(1) (`add_vectors`) and persists the whole index to disk atomically on every call.
- Deleting a design (`DELETE /api/designs/{id}`) resets the index, re-embeds every remaining reference image, and rewrites all `faiss_id` values in SQLite.
- Any code that mutates the index must keep that mapping in sync, or matches silently resolve to the wrong design.

`ingest_single_design` also rebuilds the footwear gate prototype bank after each add.

### Thresholds and calibration

`config/thresholds.json` (per-category: `rejection_threshold`, confidence bands, `platt_scaling`) overrides `DEFAULT_THRESHOLDS` in `backend/config.py` and is re-read on every call. Tune matching behavior there — not by editing scoring code. `scripts/calibrate_thresholds.py` regenerates it.

### Data segregation guardrail

`config.assert_catalog_image_path` raises if any path under `data/training/` (Kaggle data) reaches catalog indexing. Training data must never enter FAISS or the catalog. Enforced by `tests/test_data_guardrails.py`.

### Storage

`storage/` is **committed to git**, including `catalog.db` and ~all of `catalog_images/`. Re-ingesting or rebuilding the index dirties tracked files, so check `git status` before assuming a change is yours. Live artifacts are `storage/catalog.db` and `storage/shoe_index.faiss`; `storage/index.faiss` and `storage/shoematch.db` are stale leftovers that nothing reads.

### Auth

`backend/auth.py` is hand-rolled: PBKDF2-HMAC-SHA256 password hashing and an HMAC-SHA256 JWT signed with `SECRET_KEY`, accepted via HttpOnly cookie or Bearer header. Routes gate on the `require_authenticated_user` / `require_admin_user` dependencies; users with `must_change_password` are blocked from everything but the password-change endpoint. `SECURITY.md` documents the intended controls — keep it in sync when touching auth, uploads, or rate limits.

### Frontends

All three call the same API; `window.SHOEMATCH_API_BASE` in the relevant `config.js` is the single host knob (a localStorage value set in the Settings screen overrides it).

- `frontend/` — landing (`index.html`) + web studio (`app.html` + `app.js`); FastAPI mounts this at `/static`, so HTML uses absolute `/static/...` paths.
- `frontend/mobile/` — self-contained relative-path bundle; Capacitor packages it from `dist/` into `android/`. Needs an absolute API base since there is no same-origin server.
- `src-tauri/` — desktop shell.

## Deployment

Production is a **systemd service** (`deploy/backend.service`, `deploy/vps_install.sh`) running uvicorn from a venv at `/var/www/shoematch` behind Nginx, on the Hostinger VPS. Deploying = sync files + `systemctl restart`. Do not pip-install into that venv casually; the torch pin above applies there too.

Note the repo contains three *other* deployment paths that no longer describe production: `.github/workflows/deploy.yml` (docker compose in `/var/www/Shoe_Design_Detection`), `docker-compose.yml`, and `vercel.json` / `render.yaml`. Treat systemd as the source of truth and don't "fix" code to match the stale ones.
