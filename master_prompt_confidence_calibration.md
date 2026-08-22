# Master Prompt — Fix Low "Certitude" / Confidence Percentages and Confirm Rank 1/2/3 Ordering

Paste this whole prompt into your coding assistant (or use it as your own implementation checklist) inside the `Shoe_Design_Detection` repo.

---

## Context (read this first — grounded in the actual current code)

You asked for two things: (1) genuine matches should show a high confidence percentage instead of "Low Certitude", and (2) matched products should be shown at rank #1, then #2, then #3 in true accuracy order.

**Rank ordering is already correct end-to-end — no code change needed there.** `backend/matcher.py` sorts every candidate by `combined_score` before assigning ranks:
```python
sorted_matches = sorted(seen_designs.values(), key=lambda x: x["combined_score"], reverse=True)
...
for rank_idx, match in enumerate(sorted_matches, start=1):
    ...
    ranked_matches.append({"rank": rank_idx, ...})
```
and `frontend/app.js`'s `renderMatchResults()` renders that array as-is, in order, with no client-side re-sort:
```js
data.matches.forEach((m) => {
  const rankLabels = ["#1 Best Match", "#2 Second Best", "#3 Third Best"];
  const rankLabel = rankLabels[m.rank - 1] || `#${m.rank} Match`;
  ...
});
```
So #1/#2/#3 already reflects true accuracy order as computed by the backend. Nothing to fix here — just verify it visually once you've made the confidence fixes below, since a percentage that finally reads correctly makes it easier to eyeball that #1 really is the best score.

**The low-confidence-percentage symptom has three separate, stackable causes. All three need fixing together, or the number will still read low even after fixing the others.**

**1. Platt scaling's `a`/`b` are hardcoded per category, not actually fit from real score data.**
`scripts/calibrate_thresholds.py`'s `fit_platt_and_thresholds()` (lines 109-163) does compute a real, data-driven `rejection_threshold` via Youden's J statistic on the `pos_scores`/`neg_scores` arrays it collects from the live FAISS index — that part is genuine. But right after, at lines 134-144, it throws that real data away and hardcodes the logistic-mapping parameters instead:
```python
# Platt Scaling parameters tailored for cosine embedding manifolds
if category_name == "shoe":
    a = 15.2
    b = -8.8
    high_th = 85.0
    mod_th = 70.0
else:
    a = 14.6
    b = -8.2
    high_th = 82.0
    mod_th = 68.0
```
These constants were tuned at some point for some past scoring distribution and never actually adapt. `backend/database.py`'s `calculate_calibrated_confidence()` reads whatever `a`/`b` currently sit in `config/thresholds.json` and maps `combined_score` through `prob = sigmoid(a*s + b)` — if `a`/`b` don't match the real current distribution of scores, the resulting percentage is wrong (usually too low for genuine matches), no matter how good the underlying match actually is.

**2. There's a second, independent hardcoded "floor" in `backend/database.py` that's also disconnected from config.**
`calculate_calibrated_confidence()` (lines 47-78), right after the Platt calculation:
```python
# High Certitude calibration: matching catalog shoes (s >= 0.42) report 85%+ confidence
if s >= 0.42:
    conf_pct = max(conf_pct, 85.0 + (s - 0.42) * 40.0)
```
`0.42`, `85.0`, and `40.0` are all bare Python literals — not read from `config/thresholds.json`, not touched by `calibrate_thresholds.py` at all. This floor exists specifically to push genuine matches up into "High Certitude" territory, but it was tuned for whatever `combined_score` distribution existed when someone wrote it. `combined_score` is `WEIGHT_DESIGN * cosine_score + WEIGHT_COLOR * color_sim + cat_bonus` (`backend/matcher.py` line 243) — if you've since turned off color-aware scoring or changed the embedding, `combined_score` values shift, and a floor keyed to a fixed `0.42` cutoff stops firing for scores that used to clear it.

**3. The frontend independently re-derives its own confidence label using different hardcoded thresholds than the backend — so even a genuinely "High Confidence" match from the backend can still display as "Low Certitude" in the UI.**
The backend already computes the correct label per match, using the real calibrated thresholds from `config/thresholds.json` (currently `confidence_high_threshold: 80.0` / `confidence_moderate_threshold: 60.0` for the `shoe` category) via `classify_match_level()` in `backend/matcher.py` (lines 31-48), and returns it on every match object:
```python
level_code, level_label, color_code = classify_match_level(match["confidence_pct"], category=match["category"])
...
ranked_matches.append({
    ...
    "match_level": level_code,
    "match_level_label": level_label,   # e.g. "High Confidence Match"
    "match_color": color_code,          # e.g. "green"
    ...
})
```
But `frontend/app.js`'s `renderMatchResults()` (line 1288-1289) ignores those two fields entirely and recomputes its own label from a *different*, hardcoded pair of thresholds:
```js
const confLevel = m.confidence_pct >= 85 ? "high" : (m.confidence_pct >= 70 ? "medium" : "low");
const levelLabel = m.confidence_pct >= 85 ? "Strong Match" : (m.confidence_pct >= 70 ? "Variant" : "Low Certitude");
```
Since the backend's real threshold (80.0) is *lower* than the frontend's hardcoded one (85), a match the backend correctly calls "High Confidence Match" at, say, 82% still gets labeled "Low Certitude" by the frontend just because 82 < 85. This exact same duplicated-and-mismatched pattern also appears at lines 325, 356, 1660-1661, and 2344 in `frontend/app.js` (dashboard accuracy stat, recent-searches pill, image-preview modal, and the logs table) — all of them should read the backend's own label instead of re-deriving one.

## Task

1. Make Platt scaling `a`/`b` genuinely fit from the real `pos_scores`/`neg_scores` data `calibrate_thresholds.py` already collects, instead of hardcoding them.
2. Make the "High Certitude" floor in `backend/database.py` read its cutoff/boost parameters from `config/thresholds.json` instead of bare literals, and derive sensible values for those parameters from real score statistics inside the calibration script.
3. Make the frontend use the backend's own `match_level_label` / `match_color` per match instead of re-deriving a label from a second, mismatched pair of hardcoded thresholds.
4. Re-run calibration once, after any embedding/scoring changes you've already made, so the new numbers reflect the current real scoring distribution.

## Step 1 — `scripts/calibrate_thresholds.py`: fit Platt scaling for real

Replace the hardcoded branch in `fit_platt_and_thresholds()` (currently lines 134-144) with an actual logistic regression fit on `pos_scores` (label 1) and `neg_scores` (label 0). `scikit-learn` is already a project dependency (`backend/ingestion.py` already imports `from sklearn.cluster import DBSCAN`), so `sklearn.linear_model.LogisticRegression` needs no new install.

```python
from sklearn.linear_model import LogisticRegression

# Fit Platt scaling (a, b) from the real collected score distributions instead of
# hardcoding it. X = raw similarity scores, y = 1 for genuine same-design pairs,
# 0 for cross-design/cross-category/OOD negatives.
X = np.array(list(pos_scores) + list(neg_scores)).reshape(-1, 1)
y = np.array([1] * len(pos_scores) + [0] * len(neg_scores))

if len(set(y.tolist())) < 2:
    # Degenerate case (e.g. catalog too small to have both classes yet) — fall back
    # to a conservative default rather than crashing calibration.
    a, b = 20.0, -8.0
else:
    clf = LogisticRegression(C=1.0, class_weight="balanced")
    clf.fit(X, y)
    a = float(clf.coef_[0][0])
    b = float(clf.intercept_[0])

# Derive the "high confidence" and "moderate confidence" percentage thresholds from
# the real positive-score distribution instead of hardcoding them: high = the
# calibrated confidence at the 10th percentile of genuine-match scores (so ~90% of
# real matches clear "high"), moderate = the calibrated confidence at the rejection
# threshold itself (anything scoring above the accept/reject line is at least
# "moderate"). Fall back to the old defaults if there aren't enough positive samples
# to compute a stable percentile.
def _sigmoid_pct(s, a, b):
    logit = max(-50.0, min(50.0, a * s + b))
    return 100.0 / (1.0 + np.exp(-logit))

if len(pos_scores) >= 5:
    p10 = float(np.percentile(pos_scores, 10))
    high_th = round(_sigmoid_pct(p10, a, b), 1)
    mod_th = round(_sigmoid_pct(best_thresh, a, b), 1)
    # Keep the two thresholds sane relative to each other regardless of what the fit produced.
    high_th = max(high_th, mod_th + 5.0)
    high_th = min(high_th, 95.0)
    mod_th = max(mod_th, 40.0)
else:
    high_th = 85.0 if category_name == "shoe" else 82.0
    mod_th = 70.0 if category_name == "shoe" else 68.0
```

Keep everything else in the function (the Youden's J threshold loop above this, and the returned dict shape below it) exactly as it is — only the block that previously hardcoded `a`/`b`/`high_th`/`mod_th` changes. The returned dict already includes `"platt_scaling": {"a": ..., "b": ...}` and `"confidence_high_threshold"` / `"confidence_moderate_threshold"` — those now carry real fitted/derived values instead of constants.

## Step 2 — `backend/database.py`: make the "High Certitude" floor config-driven

In `calculate_calibrated_confidence()` (lines 47-78), the floor currently reads:
```python
# High Certitude calibration: matching catalog shoes (s >= 0.42) report 85%+ confidence
if s >= 0.42:
    conf_pct = max(conf_pct, 85.0 + (s - 0.42) * 40.0)
```
Change it to pull its breakpoint and target percentage from the same `cat_config` dict already loaded a few lines above (from `load_thresholds_config()`), with the current literals kept only as the fallback when a category's config doesn't define this yet:
```python
try:
    thresholds = load_thresholds_config()
    cat_config = thresholds.get(normalize_category(category), thresholds.get("global", {}))
    platt = cat_config.get("platt_scaling", {"a": 25.0, "b": -9.5})
    a = platt.get("a", 25.0)
    b = platt.get("b", -9.5)
    floor_breakpoint = cat_config.get("confidence_floor_breakpoint", 0.42)
    floor_target = cat_config.get("confidence_floor_target_pct", 85.0)
    floor_slope = cat_config.get("confidence_floor_slope", 40.0)
except Exception:
    floor_breakpoint, floor_target, floor_slope = 0.42, 85.0, 40.0

logit = a * s + b
logit = max(-50.0, min(50.0, logit))
prob = 1.0 / (1.0 + math.exp(-logit))
conf_pct = prob * 100.0

if s >= floor_breakpoint:
    conf_pct = max(conf_pct, floor_target + (s - floor_breakpoint) * floor_slope)
```
(This needs `floor_breakpoint`/`floor_target`/`floor_slope` to be initialized before the `try` block too, same pattern as `a`/`b` already use above them, so an exception in the `try` still leaves valid fallback values.)

Then in `scripts/calibrate_thresholds.py`'s `fit_platt_and_thresholds()`, add these three keys to the returned dict, derived from the real positive scores rather than guessed:
```python
# Floor breakpoint: a similarity score comfortably inside the genuine-match
# distribution (25th percentile of real positive scores) — above this, force
# the displayed confidence up to at least floor_target regardless of what the
# raw Platt sigmoid alone would produce.
floor_breakpoint = round(float(np.percentile(pos_scores, 25)), 4) if len(pos_scores) >= 5 else 0.42
floor_target = high_th  # tie the floor to the same "high confidence" threshold computed above
floor_slope = 40.0
```
and add `"confidence_floor_breakpoint": floor_breakpoint, "confidence_floor_target_pct": floor_target, "confidence_floor_slope": floor_slope,` to the dict returned at the bottom of the function (same dict that already has `"rejection_threshold"`, `"confidence_high_threshold"`, etc.).

## Step 3 — `frontend/app.js`: use the backend's own confidence label everywhere, stop re-deriving it

Replace the re-derivation at lines 1288-1289 (inside `renderMatchResults()`):
```js
// Before:
const confLevel = m.confidence_pct >= 85 ? "high" : (m.confidence_pct >= 70 ? "medium" : "low");
const levelLabel = m.confidence_pct >= 85 ? "Strong Match" : (m.confidence_pct >= 70 ? "Variant" : "Low Certitude");

// After — trust the backend, which already used the real calibrated per-category
// thresholds from config/thresholds.json via classify_match_level():
const colorToLevel = { green: "high", yellow: "medium", red: "low" };
const confLevel = colorToLevel[m.match_color] || "low";
const levelLabel = m.match_level_label || "Low Certitude";
```
Apply the same fix at the other three places in `frontend/app.js` that independently hardcode `85`/`70` against `confidence_pct` instead of using the match/log object's own label:
- Line ~325 (dashboard "accuracy" stat, `logs.filter(l => (l.confidence_pct || 0) >= 85)`) — if `log.match_level` or `log.match_color` is present on the logged record, filter on that (`l.match_level === "HIGH"` or `l.match_color === "green"`) instead of a raw `>= 85` cutoff. If the logs endpoint doesn't currently return `match_level`/`match_color` per log row, that's a backend gap — flag it rather than leaving the frontend guessing with a hardcoded number, and use `>= (the shoe category's configured confidence_high_threshold, fetched once from a stats/config endpoint if one exists)` as a stopgap only if you don't want to touch the logs endpoint in this pass.
- Line ~356 (`preview-match-pill ${log.confidence_pct >= 85 ? 'high' : log.confidence_pct >= 70 ? 'moderate' : 'low'}`) — same fix, prefer `log.match_color`/`log.match_level` if available on the row.
- Lines ~1660-1661 and ~2344 — same pattern, prefer the object's own `match_color`/`match_level_label` field when present; these two are lower priority since they're modal/table display, not the primary match-card view, but keep them consistent so the same match never shows two different confidence tiers in different parts of the UI.

Do not change the `>= 85` / `>= 70` percentage cutoffs used purely for CSS class selection where no `match_color` field exists on the object at all (e.g., a raw number typed in by hand somewhere unrelated to match results) — only replace cutoffs that are re-deriving a label for something the backend already labeled correctly.

## Step 4 — Re-run calibration

After Steps 1-2 are in place, re-run:
```
python scripts/calibrate_thresholds.py
```
This regenerates `config/thresholds.json` with genuinely fitted `a`/`b` and derived thresholds/floor parameters for both `shoe` and `slipper` categories, based on whatever the current FAISS index and embeddings actually look like. Restart the server afterward so `load_thresholds_config()` picks up the new file rather than a stale cached one.

**If you've already applied a prior change that alters the embedding or scoring pipeline** (for example, disabling color-aware scoring or making the embedding grayscale), re-run this calibration step *after* that pipeline change and its required re-embedding/rebuild steps are done — calibrating against the old score distribution and then changing the scoring underneath it would immediately make the new numbers stale again.

## Explicit boundaries

- No new evaluation/testing scripts — you're handling verification yourself.
- Do not change `classify_match_level()` in `backend/matcher.py` — it already correctly reads calibrated thresholds from config; it just needed those config values to actually be well-calibrated, and it needed the frontend to actually use its output.
- Do not change `backend/matcher.py`'s sorting/ranking logic (`sorted_matches = sorted(...)`, the `for rank_idx, match in enumerate(...)` loop) — ranking order is already correct, as explained in Context above.
- Do not change how `combined_score` itself is computed in `backend/matcher.py` — this prompt only concerns turning a given `combined_score` into an honest confidence percentage and an honest displayed label, not changing the score itself.
- No git commits — leave all changes as plain file edits for review.

## What changes for you, practically

A genuine catalog match should now show a confidence percentage that's actually derived from your real score distribution instead of stale hand-tuned constants, and the "High Confidence" / "Moderate" / "Low Certitude" label shown on each match card will always agree with what the backend itself decided that match's tier is — no more a match being internally classified "High Confidence" by the backend while the card still says "Low Certitude" because the frontend was quietly using a stricter, unrelated cutoff. Rank #1/#2/#3 ordering needs no change — it was already correct — but it'll now be easier to trust at a glance once the percentage next to it is accurate.
