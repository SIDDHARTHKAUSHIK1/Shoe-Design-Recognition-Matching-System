"""
Step 3 helper: check whether the current WEIGHT_DESIGN=0.75 / WEIGHT_COLOR=0.25
split (backend/config.py) is actually optimal for the current 36-design catalog,
now that color-aware scoring is a real (non-constant) signal.

WHY THIS SCRIPT EXISTS
-----------------------
Color-aware scoring only became meaningful once backend/ingestion.py started
actually calling backend.database.update_reference_image_color() at ingest
time. The 75/25 split predates that fix and was never re-validated against it.
This script brackets it: it runs scripts/evaluate_field_accuracy.py once per
weight split, each in its own subprocess with WEIGHT_DESIGN / WEIGHT_COLOR set
as environment variables (backend/config.py reads both from os.getenv(), and
those are module-level constants read once per process -- a fresh subprocess
per split is what makes this safe and correct, not a monkeypatch).

It does NOT modify backend/config.py or config/thresholds.json. It only
reports which split scored best on the field-realistic harness; applying the
winning split (by exporting WEIGHT_DESIGN / WEIGHT_COLOR before starting the
server, or editing the defaults in backend/config.py) is a manual decision for
you, per the master prompt's boundary that any weight change must be
justified by a before/after number from this harness.

USAGE
-----
    python scripts/tune_score_weights.py
    python scripts/tune_score_weights.py --splits 0.60,0.40 0.75,0.25 0.85,0.15
    python scripts/tune_score_weights.py --test 1   # skip Test 0/2, just perturbed-query comparison
"""
import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Current default (0.75/0.25) plus the two bracketing points the master prompt calls out.
DEFAULT_SPLITS = [(0.60, 0.40), (0.75, 0.25), (0.85, 0.15)]


def parse_splits(raw: list) -> list:
    out = []
    for s in raw:
        design_s, color_s = s.split(",")
        out.append((float(design_s), float(color_s)))
    return out


def run_one(design_w: float, color_w: float, test_arg: str) -> dict:
    env = os.environ.copy()
    env["WEIGHT_DESIGN"] = str(design_w)
    env["WEIGHT_COLOR"] = str(color_w)

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        json_out = tf.name

    cmd = [sys.executable, str(BASE_DIR / "scripts" / "evaluate_field_accuracy.py"),
           "--test", test_arg, "--json", json_out]

    label = f"WEIGHT_DESIGN={design_w} / WEIGHT_COLOR={color_w}"
    logger.info(f"Running: {label}")
    proc = subprocess.run(cmd, cwd=str(BASE_DIR), env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.error(f"Run failed for '{label}':\n{proc.stderr[-4000:]}")
        return {"label": label, "design_w": design_w, "color_w": color_w, "error": proc.stderr[-2000:]}

    with open(json_out, "r", encoding="utf-8") as f:
        report = json.load(f)
    os.unlink(json_out)
    return {"label": label, "design_w": design_w, "color_w": color_w, "report": report}


def summarize(results: list):
    print("\n" + "=" * 96)
    print("   WEIGHT_DESIGN / WEIGHT_COLOR SPLIT COMPARISON (via scripts/evaluate_field_accuracy.py)   ")
    print("=" * 96)
    header = f"{'Split':<28} | {'Test0 pass%':>11} | {'T1 Top1%':>9} | {'T1 miss%':>9} | {'T2 Top1%':>9} | {'T2 miss%':>9}"
    print(header)
    print("-" * len(header))
    best = None
    for r in results:
        if r.get("error"):
            print(f"{r['label']:<28} | {'ERROR':>11}")
            continue
        rep = r["report"]
        t0 = rep.get("test0", {}).get("pass_rate_pct", None)
        t1_top1 = rep.get("test1", {}).get("top1_rate_pct", None)
        t1_miss = rep.get("test1", {}).get("true_miss_rate_pct", None)
        t2_top1 = rep.get("test2", {}).get("top1_rate_pct", None)
        t2_miss = rep.get("test2", {}).get("true_miss_rate_pct", None)
        print(f"{r['label']:<28} | {str(t0):>11} | {str(t1_top1):>9} | {str(t1_miss):>9} | {str(t2_top1):>9} | {str(t2_miss):>9}")

        # Rank candidates: require Test0 == 100 if it was run, then minimize combined true-miss rate.
        if t0 is not None and t0 < 100.0:
            continue
        miss_signal = sum(x for x in (t1_miss, t2_miss) if x is not None)
        if best is None or miss_signal < best[0]:
            best = (miss_signal, r["label"])

    print("=" * 96)
    if best:
        print(f"Lowest combined true-miss rate among splits passing Test 0 at 100%%: {best[1]}\n")
    else:
        print("No split reached 100%% on Test 0 (or Test 0 wasn't run) -- inspect Test 0 failures before picking a split.\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--splits", nargs="+", default=None,
                         help="Space-separated design,color pairs, e.g. --splits 0.60,0.40 0.75,0.25 0.85,0.15")
    parser.add_argument("--test", choices=["0", "1", "2", "all"], default="all",
                         help="Which evaluate_field_accuracy.py test(s) to run per split (default: all)")
    args = parser.parse_args()

    splits = parse_splits(args.splits) if args.splits else DEFAULT_SPLITS
    results = [run_one(d, c, args.test) for d, c in splits]
    summarize(results)


if __name__ == "__main__":
    main()
