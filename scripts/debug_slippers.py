import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import glob
from backend.matcher import ShoeMatcher
from backend.classifier import ZeroShotCategoryClassifier
from backend import database as db

matcher = ShoeMatcher()
classifier = ZeroShotCategoryClassifier.get_instance()
slipper_files = sorted(glob.glob('storage/Slippers/*.jpeg') + glob.glob('storage/Slippers/*.jpg'))
print(f'Testing all {len(slipper_files)} slippers in storage/Slippers:')

for idx, s_path in enumerate(slipper_files):
    cat, prob = classifier.classify_category(s_path)
    res = matcher.match_image(s_path, top_k=3)
    detected_cat = res.get('detected_category')
    fw = res.get('is_footwear_detected')
    matches = res.get('matches', [])
    print(f'[{idx+1:02d}] {s_path:35s} -> Classifier: {cat} ({prob:.2f}) | Matcher Cat: {detected_cat} (FW: {fw}) | Matches: {len(matches)}')
    if matches:
        print(f'     Top #1: {matches[0]["design_id"]} "{matches[0]["design_name"]}" ({matches[0]["confidence_pct"]}%) Category: {matches[0]["category"]}')
    else:
        print(f'     Msg: {res.get("message")}')
