# Master Prompt — Replace Confidence Percentage with a Simple "Found" / "Not Found" Result

Paste this whole prompt into your coding assistant (or use it as your own implementation checklist) inside the `Shoe_Design_Detection` repo.

---

## Context (read this first — grounded in the actual current code)

Good news: the backend already has a genuine, data-driven "did we actually find this shoe or not" decision built in — you don't need to invent new logic for "Found"/"Not Found", you just need to stop showing the percentage that currently sits next to it and use that existing decision instead.

**The backend already rejects weak matches before they ever reach the results list.** In `backend/matcher.py` (lines 300-341), after ranking candidates, it compares the top result's score against a calibrated per-category `rejection_threshold` (read from `config/thresholds.json`, default `0.35`):
```python
rejection_th = float(cat_cfg.get("rejection_threshold", 0.35))
top1_sim = sorted_matches[0]["combined_score"] if sorted_matches else 0.0
...
if not sorted_matches or top1_sim < rejection_th:
    ...
    return {
        "success": True,
        "matched": False,
        "matches": [],
        "reason": "no_close_catalog_match",
        "message": "Footwear detected, but no close matching design was found in the catalog."
    }
```
This means: **every single item that ever shows up in `data.matches` has already cleared this bar.** There is no such thing as a "weak" card in the Top-3 list today — if a shoe was too dissimilar to anything in the catalog, the backend already excluded it and returned an empty `matches` array with `matched: false` instead. So "Found" vs "Not Found" isn't a new concept you need to build — it's exactly the difference between `data.matches.length > 0` (Found) and the empty/rejected case (Not Found), which the frontend already branches on.

**Where the percentage currently shows up**, all in `frontend/app.js`:
1. **Main match results card** (`renderMatchResults()`, lines 1288-1289 and 1300-1303) — the badge you're looking at that says e.g. "64.59% Low Similarity / Distinct Design". This is the primary target.
2. **Shoe inspection modal** (`openShoeInspectionModal()`, lines 1714-1725) — opened when you click a match card; shows the same percentage plus a separate "Visual Cosine: X%" line.
3. **Dashboard "Recent Employee Searches" preview pills and the "Match Accuracy" stat tile** (lines 325-327, 342, 356) — these are historical/aggregate views of past searches, not the live search result you're looking at.
4. **Admin Search Logs table** (line 2343-2345) — full audit log, admin-only.

This prompt fixes #1 and #2 (the live search result and the detail view you open from it) since that's what you're describing. #3 and #4 are flagged as a separate, explicit decision at the end rather than changed automatically — they're operational/audit views where an admin may still want the exact number, and changing them wasn't part of what you asked for.

## Task

1. Replace the percentage + Low/Moderate/High label badge on each match card with a plain "Found" tag.
2. Do the same in the shoe inspection modal, and drop the separate "Visual Cosine: X%" line there too.
3. Make sure the existing "no match" states read unambiguously as "Not Found" (they already exist and are already driven by the backend's real rejection threshold — just tighten the wording).

## Step 1 — `frontend/app.js`: match result cards

In `renderMatchResults()`, replace lines 1288-1289:
```js
// Before:
const confLevel = m.confidence_pct >= 85 ? "high" : (m.confidence_pct >= 70 ? "medium" : "low");
const levelLabel = m.confidence_pct >= 85 ? "Strong Match" : (m.confidence_pct >= 70 ? "Variant" : "Low Certitude");
```
Delete both lines — they're no longer needed, `m.match_color` (already returned by the backend) still drives the card's border/accent color via `card.className = \`match-item-card ${m.match_color}\`` a few lines above, and that line stays as-is.

Then replace the badge markup at lines 1300-1303:
```html
<!-- Before: -->
<span class="precision-confidence-badge ${confLevel}">
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
  <span>${m.confidence_pct}% ${levelLabel}</span>
</span>

<!-- After: -->
<span class="precision-confidence-badge found">
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>
  <span>Found</span>
</span>
```
Every card that reaches this point came from `data.matches`, which — per the Context section — only ever contains designs that already cleared the backend's `rejection_threshold`. So "Found" is always correct here; there's no per-card threshold logic to add on the frontend.

In `frontend/styles.css`, add a `.found` variant next to the existing `.precision-confidence-badge` color variants (`.high` / `.medium` / `.low` — find them and match the same pattern), using a green/success color from the existing token set (e.g. `var(--status-success)` or whatever the codebase's existing "positive" status color variable is called — check `:root` for the exact token name rather than hardcoding a hex value). You can leave the old `.high` / `.medium` / `.low` rules in the stylesheet even though nothing references them anymore — removing unused CSS isn't necessary for this change.

## Step 2 — `frontend/app.js`: shoe inspection modal

In `openShoeInspectionModal()`, replace the match banner block at lines 1714-1725:
```js
// Before:
if (normalizedMatch && normalizedMatch.confidence_pct !== null) {
  const rankLabels = ["#1 Best Match", "#2 Second Best Match", "#3 Third Best Match"];
  const rankTitle = rankLabels[normalizedMatch.rank - 1] || `#${normalizedMatch.rank} Ranked Match Result`;

  matchBannerHtml = `
    <div class="preview-match-title">
      <span>${rankTitle}</span>
      <span class="preview-match-pill ${normalizedMatch.match_color}">${normalizedMatch.confidence_pct}% (${normalizedMatch.match_level_label})</span>
    </div>
    ${normalizedMatch.cosine_similarity !== undefined ? `
      <span class="preview-cosine-tag mono">Visual Cosine: ${(normalizedMatch.cosine_similarity * 100).toFixed(1)}%</span>
    ` : ''}
  `;
}
```
to:
```js
// After:
if (normalizedMatch && normalizedMatch.confidence_pct !== null) {
  const rankLabels = ["#1 Best Match", "#2 Second Best Match", "#3 Third Best Match"];
  const rankTitle = rankLabels[normalizedMatch.rank - 1] || `#${normalizedMatch.rank} Ranked Match Result`;

  matchBannerHtml = `
    <div class="preview-match-title">
      <span>${rankTitle}</span>
      <span class="preview-match-pill found">Found</span>
    </div>
  `;
}
```
This drops both the percentage pill and the separate cosine-similarity line — the modal is only ever opened on a card that already came from `data.matches`, so the same "already cleared the rejection threshold" reasoning from Step 1 applies here too.

Leave the rest of `openShoeInspectionModal()` (everything building `normalizedMatch` above this block, lines 1642-1713) untouched — you still need `normalizedMatch.rank` and `normalizedMatch !== null` to decide whether to show the banner at all; only the content of the banner itself changes.

## Step 3 — tighten the "no match" wording to explicitly say "Not Found"

Two places already handle the case where nothing matched well enough — you don't need new logic, just clearer copy so it visibly pairs with "Found":

In `renderMatchResults()`, the non-footwear guard (around line 1225):
```js
// Before:
elements.resultsEmpty.querySelector("h4").textContent = "🚫 No Shoe Detected";
// After:
elements.resultsEmpty.querySelector("h4").textContent = "🚫 Not Found — No Shoe Detected";
```
And the no-close-match case (around line 1244), which fires when the backend's `rejection_threshold` check rejected every candidate:
```js
// Before:
const catName = data.detected_category ? data.detected_category.toUpperCase() : "Category";
elements.resultsEmpty.querySelector("h4").textContent = `No ${catName} Matches in Catalog`;
// After:
const catName = data.detected_category ? data.detected_category.toUpperCase() : "Category";
elements.resultsEmpty.querySelector("h4").textContent = `Not Found — No Matching ${catName} in Catalog`;
```

## Explicit boundaries

- Do not touch `backend/matcher.py`'s rejection logic, `rejection_threshold` config, or anything in `config/thresholds.json` — the existing accept/reject decision is already correct and is exactly what "Found"/"Not Found" should be based on. This is a display-only change.
- Do not touch `data.matches` ordering, `m.rank`, or the `"#1 Best Match" / "#2 Second Best" / "#3 Third Best"` rank labels — you're only removing the percentage/label badge, not the rank position.
- Do not change the Dashboard "Recent Employee Searches" pills, the "Match Accuracy" stat tile (lines 325-327), or the admin Search Logs table (line 2343-2345) — these show percentages for historical/aggregate/audit purposes, not as a live search result, and weren't part of this request. If you also want those converted to Found/Not Found, that's a quick follow-up on the same pattern, but decide that separately since it affects admin reporting, not just the search screen.
- Leave `data.category_confidence_pct` (the "Detected: Shoe (95%)" text near the top of results, line 1238) alone — that's the footwear-category detector's own confidence, a different signal from match quality, and wasn't mentioned in your request.
- No backend changes anywhere. This is a `frontend/app.js` (+ a small `frontend/styles.css` addition for the `.found` badge color) change only.
- No git commits — leave all changes as plain file edits for review.

## What changes for you, practically

Every card in your Top-3 results will now just say "Found" instead of a percentage and a Low/Moderate/High label — because by the time a design reaches that list, the backend has already decided it's a real match. If nothing in the catalog is close enough, you'll see the existing empty-results screen, now clearly worded as "Not Found" instead of just the shoe icon and a generic message.
