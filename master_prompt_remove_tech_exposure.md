# Master Prompt — Remove Demo/Technology Exposure from the Landing Page and Search Loading Screen

Paste this whole prompt into your coding assistant (or use it as your own implementation checklist) inside the `Shoe_Design_Detection` repo.

---

## Context (read this first — grounded in the actual current code)

Three separate, unrelated pieces of UI currently expose internal implementation details (fake demo numbers and AI/tech-stack names) that should not be customer-facing. All three are pure frontend — no backend or matching-pipeline changes needed for any of them.

**1. The floating "Top-1 Visual Match / LOCATION: SHELF A-03 • 38ms" card is a fake, hardcoded demo widget that sits on the landing page permanently.**
It's `frontend/index.html`, the `<div id="confidence-chip">` block, currently lines 159-171:
```html
<!-- Live Ticking Confidence Score Chip -->
<div id="confidence-chip" class="fixed bottom-6 right-6 md:bottom-10 md:right-10 z-30 hidden sm:flex items-center gap-3 bg-white/85 backdrop-blur-md border border-[#1B133C]/10 rounded-2xl p-3.5 shadow-xl transition-all duration-500 hover:scale-105 animate-chip-pulse">
  <div class="w-11 h-11 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-600 font-mono font-bold text-xs shadow-inner">
    <span id="chip-score-display">0.0%</span>
  </div>
  <div class="text-left">
    <div class="text-xs font-semibold text-[#1B133C] flex items-center gap-1.5">
      <span>Top-1 Visual Match</span>
      <span class="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-ping"></span>
    </div>
    <div class="text-[11px] font-mono text-[#1B133C]/60 mt-0.5">LOCATION: SHELF A-03 &bull; 38ms</div>
  </div>
</div>
```
This is not connected to any real search — "SHELF A-03", "38ms", and the 98.4% it counts up to are all hardcoded. The counting-up animation is a separate, self-contained script block further down the same file, `frontend/index.html` lines 631-655:
```html
// Live Ticking Score Motion Effect for Signature Confidence Chip
document.addEventListener("DOMContentLoaded", () => {
  const display = document.getElementById("chip-score-display");
  if (!display) return;
  ... (counts up to a hardcoded target = 98.4) ...
});
```
Nothing else on the page references `#confidence-chip` or `#chip-score-display` — this widget and its animation script are fully self-contained and safe to delete as a unit.

**2. The landing page has an entire "AI Technology Under the Hood" section that names the exact tech stack (DINOv2, FAISS, U2-Netp).**
`frontend/index.html`, `<section id="tech-specs">`, currently lines 455-482:
```html
<!-- SECTION 7: TECH UNDER THE HOOD (SUPPLEMENTARY & SIMPLIFIED) -->
<section id="tech-specs" class="relative z-10 py-16 md:py-24 px-4 sm:px-6 max-w-6xl mx-auto border-t border-[#1B133C]/10">
  ...
  <h4 class="font-bold text-base text-[#1B133C] mb-1">DINOv2 Neural Network</h4>
  ...
  <h4 class="font-bold text-base text-[#1B133C] mb-1">U2-Netp Cutout Model</h4>
  ...
  <h4 class="font-bold text-base text-[#1B133C] mb-1">FAISS Indexing</h4>
  ...
</section>
```
It's a clean, self-contained `<section>...</section>` sitting between "SECTION 6" (ends line 453) and "SECTION 8: FAQ" (starts line 485) — deletable as one block. It's also linked from the top nav bar, `frontend/index.html` line 102:
```html
<a href="#tech-specs" class="hover:text-[#1B133C] transition-colors nav-item-link">AI System</a>
```
That nav link must be removed too, or it becomes a dead link to a section that no longer exists.

**3. The actual app's search-in-progress screen names "FAISS" (and shows other internal pipeline-stage jargon) while a real search is running.**
This is in the real Match Studio app, not the landing page — `frontend/app.html`, inside `<div id="results-loading">`, currently lines 345-357:
```html
<!-- Pipeline Loading State -->
<div class="results-loading" id="results-loading" style="display: none;">
  <div class="pipeline-progress-box">
    <div style="display: flex; align-items: center; justify-content: center; gap: 10px; margin-bottom: 14px;">
      <div class="stage-icon-spinner"></div>
      <h4 style="font-size: 0.95rem; font-weight: 700; color: var(--text-primary);" id="loading-stage-header">Running Match Pipeline...</h4>
    </div>
    <div class="pipeline-stage-item active" id="stage-1"><span style="font-family: var(--font-mono); font-size: 0.75rem;">[1/4]</span> Image Preprocessing & Contrast Normalization</div>
    <div class="pipeline-stage-item" id="stage-2"><span style="font-family: var(--font-mono); font-size: 0.75rem;">[2/4]</span> Foreground Saliency Isolation</div>
    <div class="pipeline-stage-item" id="stage-3"><span style="font-family: var(--font-mono); font-size: 0.75rem;">[3/4]</span> Invariant Feature Projection</div>
    <div class="pipeline-stage-item" id="stage-4"><span style="font-family: var(--font-mono); font-size: 0.75rem;">[4/4]</span> FAISS Vector Space Cosine Search</div>
  </div>
</div>
```
This 4-line technical breakdown is driven by a purely cosmetic, fake-progress `setTimeout` chain in `frontend/app.js`'s `executeVisualMatch()` function, lines 1144-1171 (arms the 4 stages on fixed 180ms/420ms/650ms timers, unrelated to how long the real request actually takes) and lines 1186-1193 (marks all 4 "completed" once the real `/api/match` response actually comes back). None of this timing is real — it's decorative.

## Task

1. Remove the fake "Top-1 Visual Match" floating chip from the landing page entirely.
2. Remove the "AI Technology Under the Hood" section (and its nav link) from the landing page entirely.
3. Replace the 4-stage technical pipeline breakdown on the search loading screen with a single plain "Searching in progress…" message — no stage names, no technology names.

## Step 1 — `frontend/index.html`: delete the floating confidence chip

Delete the entire `<div id="confidence-chip">...</div>` block (lines 159-171, shown in full above).

Delete the entire "Live Ticking Score Motion Effect" script block (lines 631-655, shown in full above) — it only exists to animate this chip and has no other purpose.

## Step 2 — `frontend/index.html`: delete the technology section

Delete the entire `<section id="tech-specs">...</section>` block (lines 455-482, shown in full above).

Delete its nav bar link, line 102:
```html
<a href="#tech-specs" class="hover:text-[#1B133C] transition-colors nav-item-link">AI System</a>
```

## Step 3 — `frontend/app.html` + `frontend/app.js`: simplify the search loading screen

In `frontend/app.html`, replace the pipeline block (lines 345-357) with a single generic status line — keep the existing spinner and keep the `id="results-loading"` wrapper exactly as-is (other code toggles its visibility by that id):
```html
<!-- Pipeline Loading State -->
<div class="results-loading" id="results-loading" style="display: none;">
  <div class="pipeline-progress-box">
    <div style="display: flex; align-items: center; justify-content: center; gap: 10px;">
      <div class="stage-icon-spinner"></div>
      <h4 style="font-size: 0.95rem; font-weight: 700; color: var(--text-primary);" id="loading-stage-header">Searching in progress…</h4>
    </div>
  </div>
</div>
```
(This removes the four `id="stage-1"` through `id="stage-4"` divs entirely. Keep `id="loading-stage-header"` — nothing else needs to change on it, but leaving the id in place is harmless and future-proof.)

In `frontend/app.js`'s `executeVisualMatch()`, remove the now-dead stage-timer logic that referenced those four ids:
- Delete lines 1144-1171 (the "Reset pipeline stage items" loop, the `stageTimer1`/`stageTimer2`/`stageTimer3` `setTimeout` calls, and the `stage-1` activation — all of it operated on elements you just deleted in Step 3's HTML change).
- Delete the corresponding cleanup at lines 1186-1193 (`clearTimeout(stageTimer1/2/3)` and the loop that marks `stage-1..4` as `"completed"`). Since the `stageTimer*` variables no longer exist after removing the block above, these `clearTimeout` calls must go too — leaving them in would throw a `ReferenceError` the moment a real search runs.

After this change, `results-loading` should simply show the spinner + "Searching in progress…" for as long as the real `fetch("/api/match")` call takes, with no fake per-stage timing and no technology names anywhere in it.

## Explicit boundaries

- Do not touch anything else inside `executeVisualMatch()` — the actual `fetch("/api/match")` call, `renderMatchResults(data)`, error handling, and `fetchStats()` are all correct and out of scope.
- Do not touch the "Sub-Second Speed (~38ms)" feature card elsewhere on the landing page (`frontend/index.html`, in the "why choose us" grid) — it's a marketing speed claim, not a fake match result or a technology name, and wasn't part of this request.
- There is one more place that names a technology on the frontend, found while investigating this: the admin "Add New Reference Design" modal (`frontend/app.html`, line ~874) has the help text "Indexes reference photos with sub-second incremental FAISS vector ingestion." That's admin-only catalog-management UI, not the landing page or the search screen, so it's out of scope for this change — flag it in your summary for a possible future pass rather than editing it now.
- No backend changes anywhere. This is a 3-file change: `frontend/index.html`, `frontend/app.html`, `frontend/app.js`.

## Acceptance criteria

1. Loading the landing page (`/`) never shows the "Top-1 Visual Match / SHELF A-03 / 38ms" chip, at any scroll position, in any viewport size.
2. The landing page has no "AI Technology Under the Hood" section and no "AI System" nav link; scrolling/clicking through the rest of the nav (How it works, Catalog Variety, Accuracy, Warehouses, FAQ) still works.
3. Running a real search in the Match Studio app shows a spinner and "Searching in progress…" only — no `[1/4]`, `[2/4]`, `[3/4]`, `[4/4]` labels, no mention of FAISS, DINOv2, or any other model/library name — until real results render.
4. No JS console errors on either page (particularly no `ReferenceError` from the removed `stageTimer*` variables).
5. Everything else on both pages — hero section, "How it works" steps, other feature cards, FAQ, the actual match results rendering — is pixel-identical to before this change.

## Manual QA checklist

- [ ] Load `/` (landing page): confirm no floating chip appears bottom-right, ever.
- [ ] Load `/`: confirm "AI Technology Under the Hood" section is gone and the "AI System" nav pill is gone; other nav links still scroll to the right section.
- [ ] Open browser devtools console on `/`: no errors on load or on scroll.
- [ ] Load `/app`, upload a real query photo, click "Find Matches in Catalog": confirm the loading screen shows only a spinner + "Searching in progress…", then real results render normally afterward.
- [ ] Open browser devtools console on `/app` while running a search: no errors (specifically confirm no `ReferenceError: stageTimer1 is not defined` or similar).
- [ ] Confirm the "Sub-Second Speed (~38ms)" feature card elsewhere on the landing page is untouched (left as-is, not part of this change).

## Deliverable

A diff touching `frontend/index.html`, `frontend/app.html`, and `frontend/app.js` only, plus a one-paragraph summary confirming the QA checklist passed and separately flagging the "Add New Reference Design" modal's FAISS mention as a related, out-of-scope item for later.
