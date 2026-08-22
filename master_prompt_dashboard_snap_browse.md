# Master Prompt — Wire "Snap Photo" + "Browse Photo" quick actions on the Dashboard tab

Paste this whole prompt into your coding assistant (or use it as your own implementation checklist) inside the `Shoe_Design_Detection` repo.

---

## Context (read this first — it changes the plan)

I looked at the actual code before writing this spec. This feature is **not being built from scratch** — it's ~90% already implemented, but two pieces of it are dead code and one wiring step is missing. Do not duplicate the existing matching pipeline; wire into it.

Relevant files only:
- `frontend/app.html` — the app shell served at `GET /app`. Contains `<section id="dashboard-tab">` (the Dashboard) and `<section id="match-tab">` (Visual Match Studio).
- `frontend/app.js` — all client logic, IIFE-scoped, `elements` object caches DOM refs, `state` object holds app state.
- No backend changes needed. `POST /api/match` (`backend/main.py` line ~185) already accepts `multipart/form-data` with `file` + `top_k` and returns ranked matches — this already works and must not be touched.

### What already exists and works
- `frontend/app.js` line 1039, `setQueryFile(file, autoMatch = true)`: stores the file, renders the preview, and — because `autoMatch` defaults to `true` — automatically calls `executeVisualMatch()` after a 30ms delay. **This is already "select a photo → auto search." You do not need to build this part.**
- `executeVisualMatch()` (line 1108) builds the `FormData`, POSTs to `/api/match`, and calls `renderMatchResults(data)`.
- A fully-built live camera capture flow already exists: `handleCameraClick()` (line 2382) → picks the right camera source (native Capacitor plugin on the packaged mobile app → native OS camera shutter via `#camera-native-input` on mobile browsers → an in-page live `getUserMedia` viewfinder modal (`#camera-modal`, `openCameraModal()`, `startCameraStream()`, `snapPhotoFromCamera()`, `closeCameraModal()`, `switchCamera()`) on desktop browsers.
- There's already a proven "trigger a search from outside the Match tab and land the user on the results" pattern: `openImageFromLog` (around line 2360-2377) does `setQueryFile(file)` → `switchTab("match-tab")` → `setTimeout(() => executeVisualMatch(), 200)`. **Reuse this exact pattern — don't invent a new one.**

### The two real bugs / gaps to fix
1. **`handleCameraClick()` is dead code.** Search `app.js` for `handleCameraClick` — it's defined at line 2382 but there is no `addEventListener("click", handleCameraClick)` anywhere in the file. Every "camera" trigger in the UI (`#btn-open-camera` in the Match tab, the Dashboard's "Snap Photo" control) is just a plain `<label for="camera-native-input">`. A `<label for>` on a file input with `capture="environment"` mostly works on **mobile** browsers (opens the OS camera), but on **desktop** browsers the `capture` attribute is ignored and it just opens a bare file-picker dialog — the nice live webcam modal (`openCameraModal`) never opens on desktop today, even though it's fully coded and its own internal buttons (`#btn-snap-photo`, `#btn-close-camera`, `#btn-switch-camera`) are correctly wired at lines 1001-1003.
2. **The Dashboard has no "Browse Photo" quick action at all**, and its existing "Snap Photo" control (app.html line ~200-203) never switches the user to the Match tab — so if it did auto-run a search today, the loading state and results would render invisibly inside the hidden `#match-tab` pane and the user would see nothing happen.

So the actual task is: **fix #1, add the missing Browse button, and fix #2 (auto-navigate to match-tab) using the `openImageFromLog` pattern** — not build new matching logic.

---

## Task

In the Dashboard tab's "Warehouse Quick Operations" card (`frontend/app.html`, inside `<section id="dashboard-tab">`, the card with heading "Warehouse Quick Operations", currently around lines 189-206), the action bar currently has two buttons: "Start New Search" (`onclick="switchToTab('match-tab')"`) and "Snap Photo" (a bare `<label for="camera-native-input">`).

Change it to three actions:
1. **Start New Search** — unchanged.
2. **Snap Photo** — clicking it must open the camera (live desktop webcam modal, or native camera on mobile/packaged app), and the moment a photo is captured, the app must switch to the Match tab and the search must already be running/rendering there.
3. **Browse Photo** (new) — clicking it opens the OS file/gallery picker; the moment a file is chosen, same as above: switch to Match tab, search auto-runs, results render.

### Step 1 — `frontend/app.html`: give the Dashboard controls real IDs, add the Browse button

Find the Dashboard quick-actions block (~line 195-204):

```html
<div style="display: flex; gap: 10px; flex-wrap: wrap;">
  <button class="btn btn-primary" onclick="switchToTab('match-tab')">
    ...
    <span>Start New Search</span>
  </button>
  <label for="camera-native-input" class="btn btn-secondary" style="cursor: pointer; display: inline-flex; align-items: center; gap: 8px;">
    ...
    <span>Snap Photo</span>
  </label>
</div>
```

Replace with (note: this points at the **same** `#query-file-input` / `#camera-native-input` hidden inputs already declared once at lines 235-236 — do not create new `<input type="file">` elements, and do not duplicate the change-listener logic; the existing listeners on those two inputs already call `setQueryFile`):

```html
<div style="display: flex; gap: 10px; flex-wrap: wrap;">
  <button class="btn btn-primary" onclick="switchToTab('match-tab')">
    ...
    <span>Start New Search</span>
  </button>
  <button type="button" id="btn-dashboard-snap-photo" class="btn btn-secondary" style="cursor: pointer; display: inline-flex; align-items: center; gap: 8px;">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
    <span>Snap Photo</span>
  </button>
  <button type="button" id="btn-dashboard-browse-photo" class="btn btn-secondary" style="cursor: pointer; display: inline-flex; align-items: center; gap: 8px;">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
    <span>Browse Photo</span>
  </button>
</div>
```

(Switched from `<label for>` to real `<button>` elements — required because Step 2 needs to `preventDefault()` the camera button's implicit input-click on desktop, and mixing implicit label-forwarding with a JS listener that also calls `.click()` on the same input causes double-firing. Plain buttons are also better here since neither of these two dashboard actions should ever silently no-op if JS hasn't finished attaching listeners.)

### Step 2 — `frontend/app.js`: wire the two new buttons

In the `elements` object (~line 624-697), add:
```js
btnDashboardSnapPhoto: document.getElementById("btn-dashboard-snap-photo"),
btnDashboardBrowsePhoto: document.getElementById("btn-dashboard-browse-photo"),
```

In `setupEventListeners()` (~line 812), add, near the existing camera modal wiring (~line 994-1003) so it's grouped logically:
```js
// Dashboard Quick Actions — Snap / Browse (auto-search on select, mirrors openImageFromLog)
if (elements.btnDashboardSnapPhoto) {
  elements.btnDashboardSnapPhoto.addEventListener("click", (e) => {
    handleCameraClick(e); // reuses existing native/live-modal camera routing
  });
}
if (elements.btnDashboardBrowsePhoto) {
  elements.btnDashboardBrowsePhoto.addEventListener("click", () => {
    if (elements.queryFileInput) {
      elements.queryFileInput.value = ""; // allow re-selecting the same filename twice in a row
      elements.queryFileInput.click();
    }
  });
}
```

Also bind `#btn-open-camera` (the Match tab's own "Take Photo / Camera" control, currently the same dead-label problem) the same way, so desktop users get the live modal there too and this stops being inconsistent between the two entry points:
```js
if (elements.btnOpenCamera) {
  elements.btnOpenCamera.addEventListener("click", handleCameraClick);
}
```
(`#btn-open-camera` in `app.html` is currently `<label for="camera-native-input">` — change that one to a `<button type="button">` too, same reasoning as Step 1.)

### Step 3 — make every capture path land the user on the results (fix the "invisible search" gap)

The cleanest fix, matching the codebase's own existing convention (`openImageFromLog`), is to make `setQueryFile` itself guarantee visibility, since **every** entry point (dropzone drop, browse, native camera input change, live-modal snap, paste, log replay, and now the two new Dashboard buttons) already funnels through it:

In `frontend/app.js`, inside `setQueryFile(file, autoMatch = true)` (line 1039), right after the `if (!file) return;` guard, add:
```js
if (state.currentTab !== "match-tab") {
  switchTab("match-tab");
}
```
This is a one-line addition to a single, already-shared function — it makes the fix apply uniformly (Dashboard Snap, Dashboard Browse, and any future entry point) instead of special-casing it in two new click handlers, and it's a no-op when the user is already on the Match tab (the common case today), so existing behavior for existing entry points is unchanged in every case that matters.

With this in place you do **not** need to duplicate the `switchTab` + `setTimeout(executeVisualMatch, 200)` dance from `openImageFromLog` inside the two new button handlers — `handleCameraClick` → (native input change listener / `snapPhotoFromCamera`) → `setQueryFile` and the Browse button → native `change` listener (`handleQueryFileSelect`) → `setQueryFile` already cover it end-to-end.

### Step 4 — sanity-check the things you must NOT break

- `resetQueryStudio()` (line 1079) already clears `queryFileInput.value` and `cameraNativeInput.value` — leave it as is.
- Do not touch `executeVisualMatch`, `renderMatchResults`, or anything under `/api/match` in `backend/main.py` — the matching pipeline itself is correct and out of scope.
- Do not remove or rename `camera-native-input` / `query-file-input` — the Capacitor Android build and other code paths (e.g. `resetQueryStudio`) reference them by these exact IDs.
- Leave `openImageFromLog`'s own explicit `switchTab` + `setTimeout` call alone even though it's now technically redundant with Step 3 — don't refactor code outside this task's scope in the same change.

---

## Acceptance criteria (what "done" looks like)

1. On the Dashboard tab, clicking **Snap Photo**:
   - Desktop browser: opens the live webcam viewfinder modal (`#camera-modal`); after clicking its in-modal capture button, the app switches to the Match tab, the query preview shows the captured photo, and a search auto-runs and renders Top-3 results within a few seconds.
   - Mobile browser / packaged Android app: opens the native OS camera (or Capacitor native camera plugin); after taking a photo, same auto-switch + auto-search + results behavior.
   - Denying camera permission shows the existing `showCameraError(...)` fallback UI (already implemented) with the existing "use file picker instead" fallback button — don't regress this path.
2. On the Dashboard tab, clicking **Browse Photo** opens the OS file/gallery picker; selecting an image auto-switches to the Match tab and a search auto-runs and renders results, same as above.
3. Existing Match-tab behavior (drag-and-drop, its own "Browse File" / "Take Photo / Camera" buttons, clipboard paste, "Clear" button, "Find Matches in Catalog" manual button) all still work exactly as before — verify by testing each one after the change.
4. A non-footwear photo (snap or browse, from either entry point) still correctly shows the existing "No Shoe / Slipper Detected" empty state instead of crashing or showing a false match.
5. No new network calls, no new backend code, no new npm/pip dependencies.

## Manual QA checklist

- [ ] Desktop Chrome: Dashboard → Snap Photo → live modal opens → snap → lands on Match tab with a rendered result.
- [ ] Desktop Chrome: Dashboard → Browse Photo → pick a catalog-matching photo → lands on Match tab with a rendered result.
- [ ] Desktop Chrome, camera permission denied: Dashboard → Snap Photo → error state shown, fallback to file picker still works.
- [ ] Chrome device-emulation (mobile viewport) or a real phone browser: Dashboard → Snap Photo opens the OS camera app; Browse Photo opens the gallery.
- [ ] Match tab, unchanged: drag-and-drop a photo still works; its own "Browse File" and "Take Photo / Camera" buttons still work; "Clear" still resets the studio; clipboard paste (Ctrl+V) still works.
- [ ] Upload a photo of something that isn't footwear → "No Shoe / Slipper Detected" state appears, not a crash.
- [ ] Run the existing `test_api.py` / `test_upload_repro.py` (or whichever backend tests you normally run) to confirm the backend match endpoint itself is untouched and still green — this change should be 100% frontend.

## Deliverable

A diff touching only `frontend/app.html` and `frontend/app.js` (roughly the line ranges cited above), plus a one-paragraph summary of what changed and confirmation the QA checklist passed.
