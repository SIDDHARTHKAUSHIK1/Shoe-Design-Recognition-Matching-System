"""
Field-realistic accuracy evaluation harness for ShoeMatch AI.

WHY THIS SCRIPT EXISTS
-----------------------
evaluate.py runs Leave-One-Out on raw cosine similarity only (engine.get_embedding()
+ np.dot). It never calls backend.matcher.ShoeMatcher.match_image(), so it never
exercises color-aware scoring, the category bonus, the rejection threshold, or the
near-duplicate dedup logic that a real POST /api/match query goes through. It also
measures "does one catalog photo retrieve another catalog photo of the same
design" -- an easier task than "does a fresh phone photo, taken under different
conditions, retrieve the right design." Its ~97% number is an optimistic upper
bound, not a field accuracy measurement.

This script calls ShoeMatcher.match_image() directly -- the exact same code path
POST /api/match uses -- and runs three tests:

  Test 0 -- Exact-copy gate (must be 100%, checked first, gates everything else):
      Re-upload every stored reference photo completely unmodified as the query.
      Every single one must return its own design at #1. If this isn't 100%,
      something more basic than "generalization to new photos" is broken
      (embedding nondeterminism, a stale/out-of-sync index, a threshold rejecting
      a near-1.0 similarity) -- fix that before trusting Test 1/2 numbers at all.

  Test 1 -- Field-realistic perturbed queries:
      For each reference photo, generate perturbed copies standing in for a real
      customer photo (JPEG re-compression, a crop, a brightness/white-balance
      shift, a small rotation) and query with those, never the byte-identical
      original.

  Test 2 -- Leave-one-out across angles (full scoring pipeline, not raw cosine):
      For designs with 2+ reference photos, exclude one reference photo's own
      vector from the candidate pool when querying with it, and confirm the
      design is still found via its OTHER angle photo(s) alone -- using the same
      combined_score formula (WEIGHT_DESIGN * cosine + WEIGHT_COLOR * color_sim +
      category bonus) that backend/matcher.py uses, not just raw cosine.
      Implemented WITHOUT touching the live FAISS index/SQLite catalog: vectors
      are reconstructed from the existing index and scored in memory, so the
      running server's index is never mutated and nothing is written back to
      storage/catalog.db or storage/shoe_index.faiss by this script.

FAILURE DEFINITIONS (confirmed with the project owner -- do not change these)
-------------------------------------------------------------------------------
- Test 0: ANY non-#1 result on an exact re-upload is a failure. Gate requires 100%.
- Test 1 / Test 2: only two things count as real failures:
    (a) a genuinely different design occupies #1 while the correct design is
        #2/#3 or absent entirely, or
    (b) the correct design is missing from the Top-3 entirely.
  Landing at #2 or #3 is NOT a failure -- it is logged separately as "shown as a
  similar design," because the app already presents Top-3 as a ranked set of
  similar catalog designs. Do not chase #2-vs-#1 ordering between two
  legitimately similar designs as if it were a bug.

BOUNDARIES
----------
- This script only READS the catalog (db.get_all_designs / get_all_reference_images
  / get_reference_image_by_faiss_id) and reconstructs vectors already stored in the
  live FAISS index. It never adds, deletes, or re-indexes anything, and never
  touches the ~139 non-stock data/catalog folders that are explicitly excluded
  from the searchable catalog.
- Query images used here are re-derived in memory from the catalog's own stored
  reference photos (which are real stock photos already indexed) -- no new images
  are added to the catalog by running this script.

USAGE
-----
    python scripts/evaluate_field_accuracy.py                  # run Test 0, 1, 2
    python scripts/evaluate_field_accuracy.py --test 0         # exact-copy gate only
    python scripts/evaluate_field_accuracy.py --test 1
    python scripts/evaluate_field_accuracy.py --test 2
    python scripts/evaluate_field_accuracy.py --json report.json   # also dump machine-readable report

Run this from the project root (same place you run run_server.py), with your
normal Python environment (the one with torch/transformers/faiss installed) --
NOT a plain `python` with only the base project dependencies missing.
"""
import sys
import io
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageEnhance

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import BASE_DIR as CFG_BASE_DIR, STORAGE_DIR, WEIGHT_DESIGN, WEIGHT_COLOR, ENABLE_COLOR_AWARE_SCORING
from backend import database as db
from backend.engine import EmbeddingEngine
from backend.vector_store import VectorStore
from backend.matcher import ShoeMatcher
from backend.color_extractor import ColorExtractor

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ==============================================================================
# Shared helpers
# ==============================================================================

def resolve_image_path(image_path: str, design_id: str) -> Path:
    """Mirror the path resolution already used in evaluate.py / backfill_reference_colors.py."""
    rel_path = image_path.lstrip("/")
    full_path = BASE_DIR / "storage" / rel_path
    if not full_path.exists():
        full_path = STORAGE_DIR / "catalog_images" / design_id / Path(image_path).name
    return full_path


def load_all_reference_rows() -> List[Dict[str, Any]]:
    """
    Full per-reference-image metadata including color data, keyed by walking every
    faiss_id currently in the index (get_all_reference_images() doesn't include
    color columns, get_reference_image_by_faiss_id() does).
    """
    vs = VectorStore.get_instance()
    rows = []
    for fid in range(vs.total_vectors):
        meta = db.get_reference_image_by_faiss_id(fid)
        if meta:
            rows.append(meta)
    return rows


def rank_of_design_in_matches(matches: List[Dict[str, Any]], expected_design_id: str) -> Optional[int]:
    """Return the 1-indexed rank of expected_design_id within `matches`, or None if absent."""
    for m in matches:
        if m.get("design_id") == expected_design_id:
            return m.get("rank")
    return None


def classify_outcome(rank: Optional[int], matches: List[Dict[str, Any]]) -> str:
    """
    Classify a Test 1 / Test 2 query outcome per the project owner's rules:
      - 'top1'        : correct design at #1 (success)
      - 'shown_as_similar' : correct design at #2 or #3 (NOT a failure)
      - 'wrong_top1'  : a different design occupies #1 and correct design is #2/#3/absent (FAILURE)
      - 'missing'     : correct design absent from Top-3 entirely (FAILURE)
      - 'no_match'    : matcher returned no matches at all / rejected the query (FAILURE, logged distinctly)
    """
    if not matches:
        return "no_match"
    if rank == 1:
        return "top1"
    if rank in (2, 3):
        return "shown_as_similar"
    return "missing" if rank is None else "wrong_top1"


# ==============================================================================
# Perturbation recipes for Test 1
# ==============================================================================

def _perturb_jpeg_recompress(img: Image.Image, quality: int = 40) -> Image.Image:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def _perturb_crop(img: Image.Image, frac: float, corner: str) -> Image.Image:
    w, h = img.size
    cw, ch = int(w * frac), int(h * frac)
    if corner == "topleft":
        box = (0, 0, cw, ch)
    elif corner == "bottomright":
        box = (w - cw, h - ch, w, h)
    else:  # center
        left = (w - cw) // 2
        top = (h - ch) // 2
        box = (left, top, left + cw, top + ch)
    return img.crop(box)


def _perturb_brightness(img: Image.Image, factor: float) -> Image.Image:
    return ImageEnhance.Brightness(img).enhance(factor)


def _perturb_rotate(img: Image.Image, degrees: float) -> Image.Image:
    return img.convert("RGB").rotate(degrees, expand=True, fillcolor=(245, 245, 245))


# Fixed, deterministic recipe set (not random) so repeated runs are comparable
# before/after a change, per the master prompt's "compare after each step" requirement.
PERTURBATION_RECIPES = [
    ("jpeg_q40", lambda img: _perturb_jpeg_recompress(img, quality=40)),
    ("crop_92pct_topleft", lambda img: _perturb_crop(img, 0.92, "topleft")),
    ("crop_90pct_bottomright", lambda img: _perturb_crop(img, 0.90, "bottomright")),
    ("brightness_1.15", lambda img: _perturb_brightness(img, 1.15)),
    ("brightness_0.85", lambda img: _perturb_brightness(img, 0.85)),
    ("rotate_plus5", lambda img: _perturb_rotate(img, 5)),
    ("rotate_minus5", lambda img: _perturb_rotate(img, -5)),
]


def recipes_for_index(idx: int, count: int = 3) -> List[Tuple[str, Any]]:
    """Deterministically pick `count` distinct recipes for reference photo #idx,
    cycling through the fixed recipe list so every image gets a varied but
    reproducible set of perturbations across runs."""
    n = len(PERTURBATION_RECIPES)
    return [PERTURBATION_RECIPES[(idx + i) % n] for i in range(count)]


# ==============================================================================
# Test 0 -- exact-copy gate
# ==============================================================================

def run_test0(matcher: ShoeMatcher, ref_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    logger.info(f"Test 0 (exact-copy gate): {len(ref_rows)} reference photos...")
    failures = []
    passed = 0

    for r in ref_rows:
        full_path = resolve_image_path(r["image_path"], r["design_id"])
        if not full_path.exists():
            failures.append({
                "image_path": r["image_path"], "design_id": r["design_id"],
                "problem": "file_missing_on_disk", "expected": r["design_id"], "actual_top1": None
            })
            continue

        result = matcher.match_image(full_path, query_image_save_path=f"__eval__/test0/{r['design_id']}/{full_path.name}")
        matches = result.get("matches", [])
        top1 = matches[0]["design_id"] if matches else None
        top1_conf = matches[0]["confidence_pct"] if matches else None

        if top1 == r["design_id"]:
            passed += 1
        else:
            failures.append({
                "image_path": r["image_path"],
                "expected": r["design_id"],
                "actual_top1": top1,
                "actual_top1_confidence": top1_conf,
                "matcher_reason": result.get("reason"),
                "is_footwear_detected": result.get("is_footwear_detected"),
            })

    total = len(ref_rows)
    pass_rate = round((passed / total) * 100.0, 2) if total else 0.0
    return {
        "total": total,
        "passed": passed,
        "failed": len(failures),
        "pass_rate_pct": pass_rate,
        "is_100_pct": len(failures) == 0,
        "failures": failures,
    }


# ==============================================================================
# Test 1 -- field-realistic perturbed queries
# ==============================================================================

def run_test1(matcher: ShoeMatcher, ref_rows: List[Dict[str, Any]], n_perturbations: int = 3) -> Dict[str, Any]:
    logger.info(f"Test 1 (perturbed field queries): {len(ref_rows)} reference photos x {n_perturbations} perturbations...")
    outcomes = {"top1": 0, "shown_as_similar": 0, "wrong_top1": 0, "missing": 0, "no_match": 0}
    true_misses = []
    total = 0

    for idx, r in enumerate(ref_rows):
        full_path = resolve_image_path(r["image_path"], r["design_id"])
        if not full_path.exists():
            continue
        try:
            base_img = Image.open(full_path).convert("RGB")
        except Exception as e:
            logger.warning(f"Could not open {full_path}: {e}")
            continue

        for recipe_name, recipe_fn in recipes_for_index(idx, n_perturbations):
            try:
                perturbed = recipe_fn(base_img)
            except Exception as e:
                logger.warning(f"Perturbation '{recipe_name}' failed on {full_path.name}: {e}")
                continue

            total += 1
            result = matcher.match_image(
                perturbed,
                query_image_save_path=f"__eval__/test1/{r['design_id']}/{full_path.stem}__{recipe_name}"
            )
            matches = result.get("matches", [])
            rank = rank_of_design_in_matches(matches, r["design_id"])
            outcome = classify_outcome(rank, matches)
            outcomes[outcome] += 1

            if outcome in ("wrong_top1", "missing", "no_match"):
                true_misses.append({
                    "expected_design_id": r["design_id"],
                    "source_image": r["image_path"],
                    "perturbation": recipe_name,
                    "actual_top1": matches[0]["design_id"] if matches else None,
                    "actual_top1_confidence": matches[0]["confidence_pct"] if matches else None,
                    "outcome": outcome,
                    "matcher_reason": result.get("reason"),
                })

    true_miss_count = outcomes["wrong_top1"] + outcomes["missing"] + outcomes["no_match"]
    return {
        "total_queries": total,
        "top1_count": outcomes["top1"],
        "shown_as_similar_count": outcomes["shown_as_similar"],
        "true_miss_count": true_miss_count,
        "outcome_breakdown": outcomes,
        "top1_rate_pct": round((outcomes["top1"] / total) * 100.0, 2) if total else 0.0,
        "still_surfaced_rate_pct": round(((outcomes["top1"] + outcomes["shown_as_similar"]) / total) * 100.0, 2) if total else 0.0,
        "true_miss_rate_pct": round((true_miss_count / total) * 100.0, 2) if total else 0.0,
        "true_misses": true_misses,
    }


# ==============================================================================
# Test 2 -- leave-one-out across angles, through the FULL scoring pipeline
# ==============================================================================

def build_candidate_index(ref_rows: List[Dict[str, Any]], vs: VectorStore):
    """Reconstruct every vector currently in the live FAISS index (read-only) and
    pair it with its full metadata, keyed by faiss_id. Never mutates the index."""
    vectors: Dict[int, np.ndarray] = {}
    meta: Dict[int, Dict[str, Any]] = {}
    for r in ref_rows:
        fid = int(r["faiss_id"])
        vectors[fid] = vs.index.reconstruct(fid)
        hist = None
        dominant = None
        if r.get("color_histogram"):
            try:
                hist = json.loads(r["color_histogram"])
            except Exception:
                hist = None
        if r.get("dominant_colors"):
            try:
                dominant = json.loads(r["dominant_colors"])
            except Exception:
                dominant = None
        meta[fid] = {**r, "color_histogram_parsed": hist, "dominant_colors_parsed": dominant}
    return vectors, meta


def score_candidates(
    query_vec: np.ndarray,
    query_hist: Optional[List[float]],
    query_category: str,
    candidate_faiss_ids: List[int],
    vectors: Dict[int, np.ndarray],
    meta: Dict[int, Dict[str, Any]],
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """
    Replicates backend/matcher.py's ShoeMatcher.match_image() steps 5-6 exactly
    (per-design best combined_score, sort, near-duplicate-vector dedup to top_k)
    over an explicit candidate pool, so Test 2 can hold out one vector without
    touching the live FAISS index.
    """
    seen_designs: Dict[str, Dict[str, Any]] = {}

    for fid in candidate_faiss_ids:
        cand_meta = meta[fid]
        cand_vec = vectors[fid]
        cosine_score = float(np.dot(query_vec, cand_vec))

        color_sim = 1.0
        if ENABLE_COLOR_AWARE_SCORING and query_hist is not None and cand_meta.get("color_histogram_parsed"):
            try:
                color_sim = ColorExtractor.compute_color_similarity(query_hist, cand_meta["color_histogram_parsed"])
            except Exception:
                color_sim = 1.0

        cat_bonus = 0.05 if db.normalize_category(cand_meta.get("category", "")) == query_category else 0.0

        if ENABLE_COLOR_AWARE_SCORING:
            combined_score = WEIGHT_DESIGN * cosine_score + WEIGHT_COLOR * color_sim + cat_bonus
        else:
            combined_score = cosine_score + cat_bonus

        design_id = cand_meta["design_id"]
        if design_id not in seen_designs or combined_score > seen_designs[design_id]["combined_score"]:
            seen_designs[design_id] = {
                "design_id": design_id,
                "combined_score": combined_score,
                "faiss_id": fid,
            }

    sorted_candidates = sorted(seen_designs.values(), key=lambda x: x["combined_score"], reverse=True)

    sorted_matches = []
    selected_vectors = []
    for cand in sorted_candidates:
        vec = vectors[cand["faiss_id"]]
        is_dup = any(float(np.dot(vec, sv)) > 0.980 for sv in selected_vectors)
        if not is_dup:
            sorted_matches.append(cand)
            selected_vectors.append(vec)
            if len(sorted_matches) >= top_k:
                break

    for rank_idx, m in enumerate(sorted_matches, start=1):
        m["rank"] = rank_idx
    return sorted_matches


def run_test2(ref_rows: List[Dict[str, Any]], vs: VectorStore) -> Dict[str, Any]:
    # Only designs with 2+ reference photos are eligible -- a design with a single
    # photo can't have "its other angle photos" by definition.
    by_design: Dict[str, List[Dict[str, Any]]] = {}
    for r in ref_rows:
        by_design.setdefault(r["design_id"], []).append(r)
    eligible = {d: rs for d, rs in by_design.items() if len(rs) >= 2}
    skipped_single_photo = [d for d, rs in by_design.items() if len(rs) < 2]

    logger.info(
        f"Test 2 (leave-one-out across angles): {len(eligible)} designs eligible "
        f"(2+ reference photos), {len(skipped_single_photo)} designs skipped (only 1 photo)."
    )

    vectors, meta = build_candidate_index(ref_rows, vs)
    all_faiss_ids = list(vectors.keys())

    outcomes = {"top1": 0, "shown_as_similar": 0, "wrong_top1": 0, "missing": 0}
    true_misses = []
    total = 0

    for design_id, rows in eligible.items():
        for held_out in rows:
            fid = int(held_out["faiss_id"])
            query_vec = vectors[fid]
            query_hist = meta[fid].get("color_histogram_parsed")
            query_category = db.normalize_category(meta[fid].get("category", ""))

            candidate_ids = [f for f in all_faiss_ids if f != fid]
            matches = score_candidates(query_vec, query_hist, query_category, candidate_ids, vectors, meta, top_k=3)

            rank = None
            for m in matches:
                if m["design_id"] == design_id:
                    rank = m["rank"]
                    break

            outcome = classify_outcome(rank, matches)
            total += 1
            outcomes[outcome] = outcomes.get(outcome, 0) + 1

            if outcome in ("wrong_top1", "missing"):
                true_misses.append({
                    "expected_design_id": design_id,
                    "held_out_image": held_out["image_path"],
                    "actual_top1": matches[0]["design_id"] if matches else None,
                    "outcome": outcome,
                    "other_angles_available": len(rows) - 1,
                })

    true_miss_count = outcomes.get("wrong_top1", 0) + outcomes.get("missing", 0)
    return {
        "eligible_designs": len(eligible),
        "skipped_single_photo_designs": skipped_single_photo,
        "total_queries": total,
        "outcome_breakdown": outcomes,
        "top1_rate_pct": round((outcomes.get("top1", 0) / total) * 100.0, 2) if total else 0.0,
        "still_surfaced_rate_pct": round(((outcomes.get("top1", 0) + outcomes.get("shown_as_similar", 0)) / total) * 100.0, 2) if total else 0.0,
        "true_miss_rate_pct": round((true_miss_count / total) * 100.0, 2) if total else 0.0,
        "true_misses": true_misses,
    }


# ==============================================================================
# Report printing
# ==============================================================================

def print_report(report: Dict[str, Any]):
    print("\n" + "=" * 78)
    print("      SHOEMATCH AI — FIELD-REALISTIC ACCURACY REPORT (full pipeline)      ")
    print("=" * 78)
    print(f"WEIGHT_DESIGN={WEIGHT_DESIGN}  WEIGHT_COLOR={WEIGHT_COLOR}  ENABLE_COLOR_AWARE_SCORING={ENABLE_COLOR_AWARE_SCORING}")
    print("-" * 78)

    if "test0" in report:
        t0 = report["test0"]
        flag = "PASS" if t0["is_100_pct"] else "*** FAIL — FIX BEFORE TRUSTING TEST 1/2 ***"
        print(f"TEST 0 — Exact-copy gate (must be 100%): {t0['pass_rate_pct']}% "
              f"({t0['passed']}/{t0['total']})  [{flag}]")
        if not t0["is_100_pct"]:
            for f in t0["failures"][:20]:
                print(f"    MISS: expected={f['expected']}  got_top1={f.get('actual_top1')}  "
                      f"image={f['image_path']}")
        print("-" * 78)

    if "test1" in report:
        t1 = report["test1"]
        print(f"TEST 1 — Perturbed field queries ({t1['total_queries']} queries):")
        print(f"    Top-1 rate:                {t1['top1_rate_pct']}%")
        print(f"    Still surfaced (#1-#3):    {t1['still_surfaced_rate_pct']}%  "
              f"(shown_as_similar={t1['shown_as_similar_count']}, not counted as failure)")
        print(f"    TRUE MISS rate:            {t1['true_miss_rate_pct']}%  ({t1['true_miss_count']} cases)")
        for m in t1["true_misses"][:30]:
            print(f"    TRUE MISS: expected={m['expected_design_id']}  got_top1={m['actual_top1']}  "
                  f"({m['outcome']}, perturbation={m['perturbation']}, source={m['source_image']})")
        print("-" * 78)

    if "test2" in report:
        t2 = report["test2"]
        print(f"TEST 2 — Leave-one-out across angles ({t2['total_queries']} queries, "
              f"{t2['eligible_designs']} eligible designs):")
        print(f"    Top-1 rate:                {t2['top1_rate_pct']}%")
        print(f"    Still surfaced (#1-#3):    {t2['still_surfaced_rate_pct']}%")
        print(f"    TRUE MISS rate:            {t2['true_miss_rate_pct']}%")
        if t2["skipped_single_photo_designs"]:
            print(f"    Skipped (only 1 reference photo, {len(t2['skipped_single_photo_designs'])} designs): "
                  f"{', '.join(t2['skipped_single_photo_designs'][:15])}"
                  f"{' ...' if len(t2['skipped_single_photo_designs']) > 15 else ''}")
        for m in t2["true_misses"][:30]:
            print(f"    TRUE MISS: expected={m['expected_design_id']}  got_top1={m['actual_top1']}  "
                  f"({m['outcome']}, held_out={m['held_out_image']})")
        print("-" * 78)

    print("=" * 78 + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--test", choices=["0", "1", "2", "all"], default="all",
                         help="Which test to run (default: all)")
    parser.add_argument("--perturbations", type=int, default=3,
                         help="Number of perturbed variants per reference photo for Test 1 (default 3)")
    parser.add_argument("--json", type=str, default=None,
                         help="Optional path to also write the full machine-readable report as JSON")
    args = parser.parse_args()

    db.init_db()
    vs = VectorStore.get_instance()
    matcher = ShoeMatcher()

    if vs.total_vectors == 0:
        logger.error("Catalog index is empty (0 vectors). Nothing to evaluate.")
        sys.exit(1)

    ref_rows = load_all_reference_rows()
    logger.info(f"Loaded {len(ref_rows)} reference images across "
                f"{len(set(r['design_id'] for r in ref_rows))} designs from the live catalog.")

    report: Dict[str, Any] = {}

    run0 = args.test in ("0", "all")
    run1 = args.test in ("1", "all")
    run2 = args.test in ("2", "all")

    if run0:
        report["test0"] = run_test0(matcher, ref_rows)
        if args.test == "all" and not report["test0"]["is_100_pct"]:
            logger.warning(
                "Test 0 did NOT reach 100%%. Per the harness spec, this should be fixed "
                "before trusting Test 1/2 numbers -- continuing anyway since --test=all was requested, "
                "but treat the Test 1/2 results below as provisional."
            )

    if run1:
        report["test1"] = run_test1(matcher, ref_rows, n_perturbations=args.perturbations)

    if run2:
        report["test2"] = run_test2(ref_rows, vs)

    print_report(report)

    if args.json:
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        logger.info(f"Full JSON report written to {out_path}")


if __name__ == "__main__":
    main()
