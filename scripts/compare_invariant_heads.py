"""
Step 2 helper: validate the trained background-invariant head checkpoints
instead of assuming any of them helps.

WHY THIS SCRIPT EXISTS
-----------------------
storage/models/ has three checkpoints sitting side by side:
  - background_invariant_head.pt          (current, loaded by default)
  - background_invariant_head_v1_backup.pt
  - background_invariant_head_v2.pt
Nothing in the repo proves which one is actually best on the real 36-design
catalog. This script runs scripts/evaluate_field_accuracy.py once per
checkpoint (plus once with the head disabled entirely, as a raw-DINOv2
baseline) via a fresh subprocess per run -- each with different
ENABLE_INVARIANT_HEAD / INVARIANT_HEAD_PATH environment variables -- so
backend/config.py picks up a genuinely different setting each time (module-
level config constants are only read once per process, so this can't be done
safely by importing and re-importing backend.config in one process).

It does NOT modify backend/config.py, storage/models/, or any checkpoint file.
It only reports which configuration scored best; deciding to delete/archive a
losing checkpoint is a manual step for you, per the master prompt's boundary
that any checkpoint change must be justified by a before/after number from
this harness, not intuition.

USAGE
-----
    python scripts/compare_invariant_heads.py
    python scripts/compare_invariant_heads.py --test 0    # just the exact-copy gate, faster
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

CHECKPOINTS_DIR = BASE_DIR / "storage" / "models"

CONFIGS = [
    {"label": "invariant_head_DISABLED (raw DINOv2 baseline)", "env": {"ENABLE_INVARIANT_HEAD": "false"}},
    {"label": "background_invariant_head.pt (current)", "env": {"ENABLE_INVARIANT_HEAD": "true",
        "INVARIANT_HEAD_PATH": str(CHECKPOINTS_DIR / "background_invariant_head.pt")}},
    {"label": "background_invariant_head_v1_backup.pt", "env": {"ENABLE_INVARIANT_HEAD": "true",
        "INVARIANT_HEAD_PATH": str(CHECKPOINTS_DIR / "background_invariant_head_v1_backup.pt")}},
    {"label": "background_invariant_head_v2.pt", "env": {"ENABLE_INVARIANT_HEAD": "true",
        "INVARIANT_HEAD_PATH": str(CHECKPOINTS_DIR / "background_invariant_head_v2.pt")}},
]


def run_one(label: str, env_overrides: dict, test_arg: str) -> dict:
    ckpt_path = env_overrides.get("INVARIANT_HEAD_PATH")
    if ckpt_path and not Path(ckpt_path).exists():
        logger.warning(f"Skipping '{label}': checkpoint file not found at {ckpt_path}")
        return {"label": label, "skipped": True, "reason": "checkpoint_missing"}

    env = os.environ.copy()
    env.update(env_overrides)

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        json_out = tf.name

    cmd = [sys.executable, str(BASE_DIR / "scripts" / "evaluate_field_accuracy.py"),
           "--test", test_arg, "--json", json_out]

    logger.info(f"Running: {label}  (env: {env_overrides})")
    proc = subprocess.run(cmd, cwd=str(BASE_DIR), env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.error(f"Run failed for '{label}':\n{proc.stderr[-4000:]}")
        return {"label": label, "error": proc.stderr[-2000:]}

    with open(json_out, "r", encoding="utf-8") as f:
        report = json.load(f)
    os.unlink(json_out)
    return {"label": label, "report": report}


def summarize(results: list):
    print("\n" + "=" * 90)
    print("   INVARIANT HEAD CHECKPOINT COMPARISON (via scripts/evaluate_field_accuracy.py)   ")
    print("=" * 90)
    header = f"{'Configuration':<45} | {'Test0 pass%':>11} | {'T1 Top1%':>9} | {'T1 miss%':>9} | {'T2 Top1%':>9} | {'T2 miss%':>9}"
    print(header)
    print("-" * len(header))
    for r in results:
        if r.get("skipped") or r.get("error"):
            print(f"{r['label']:<45} | {'SKIPPED/ERROR':>11}")
            continue
        rep = r["report"]
        t0 = rep.get("test0", {}).get("pass_rate_pct", "-")
        t1_top1 = rep.get("test1", {}).get("top1_rate_pct", "-")
        t1_miss = rep.get("test1", {}).get("true_miss_rate_pct", "-")
        t2_top1 = rep.get("test2", {}).get("top1_rate_pct", "-")
        t2_miss = rep.get("test2", {}).get("true_miss_rate_pct", "-")
        print(f"{r['label']:<45} | {str(t0):>11} | {str(t1_top1):>9} | {str(t1_miss):>9} | {str(t2_top1):>9} | {str(t2_miss):>9}")
    print("=" * 90)
    print("Pick the configuration with the highest Test0 pass%% (must be 100 to even consider it),")
    print("then the highest Top-1%% / lowest true-miss%% on Test 1 and Test 2. Do not switch checkpoints")
    print("based on Test0 alone -- Test1/2 measure generalization, which is the point of this head.\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--test", choices=["0", "1", "2", "all"], default="all",
                         help="Which evaluate_field_accuracy.py test(s) to run per configuration (default: all)")
    args = parser.parse_args()

    results = [run_one(c["label"], c["env"], args.test) for c in CONFIGS]
    summarize(results)


if __name__ == "__main__":
    main()
