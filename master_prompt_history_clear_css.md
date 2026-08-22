# Master Prompt — Fix "View Full History →" + Color the "Clear" Button

Paste this whole prompt into your coding assistant (or use it as your own implementation checklist) inside the `Shoe_Design_Detection` repo.

---

## Context (read this first — grounded in the actual current code)

Two separate small asks, one shared root cause for the first one:

**1. "View Full History →" button does nothing when clicked.**
It's a Dashboard button (`frontend/app.html`, inside the "Recent Employee Searches" card, currently around line 216):
```html
<button class="btn-text-sm" onclick="switchToTab('logs-tab')">View Full History &rarr;</button>
```
`frontend/app.js` never defines a function called `switchToTab` anywhere in the file — grep confirms zero matches. What the file actually defines and exposes globally is `switchTab` (no "To"), assigned via `window.switchTab = switchTab;` at line ~809, inside the main app IIFE. Clicking the button currently throws a silent `ReferenceError: switchToTab is not defined` in the console — nothing visible happens.

The good news: the actual `logs-tab` destination is already a fully built "Audit Inspection History" view — table, thumbnails, pagination bar, per-page selector, a "Refresh Logs" button — and the real `switchTab(tabId)` function (`frontend/app.js` lines 787-808) already calls `fetchLogs()` itself whenever `tabId === "logs-tab"` (line 805), and already updates the topbar title/description via `tabTitles[tabId]`. **There is no missing "show full history" logic to build — this is purely a one-word naming fix**: the button needs to call the function that actually exists.

(Side note, out of scope for this task: the Dashboard's "Start New Search" button, right above this one in the same card, has the exact same bug — `onclick="switchToTab('match-tab')"`. Not part of this request; mentioned so whoever picks this up isn't confused why a nearly-identical bug exists two lines away. Leave it alone unless separately asked.)

**2. Both this button and the "Clear" button have no real styling.**
`View Full History →` uses `class="btn-text-sm"`. So does the Query Photo tab's "Clear" button (`frontend/app.html`, around line 235, inside the "1. Query Photo" card header):
```html
<button class="btn-text-sm" id="btn-clear-query" style="display: none;">Clear</button>
```
(It's hidden by default and shown via JS — `frontend/app.js`'s `setQueryFile()` — once a query image is selected; that logic is unrelated and must not be touched.)

`.btn-text-sm` is never defined anywhere in `frontend/styles.css` — grep confirms zero matches. Both buttons currently render as bare, unstyled default browser buttons: no brand color, no hover state, visually inconsistent with every other control in the app (`.btn`, `.btn-primary`, `.btn-secondary`, `.btn-sm`, `.btn-danger` are all properly defined and used elsewhere in `styles.css`).

**The project's color system** (`frontend/styles.css`, lines ~5-120): all colors are CSS custom properties defined once on `:root` for light mode and re-overridden in a `[data-theme="dark"]`-scoped block for dark mode — nothing is ever hardcoded as a raw hex value in component styles. The relevant tokens already available to reuse:
- `--brand-accent` (`#D97706` light / `#F59E0B` dark) and `--brand-accent-hover` — the app's primary accent color, used for `.btn-primary`.
- `--text-primary`, `--text-muted` — standard text colors.
- `--status-danger` (`#DC2626` light / driven by `--status-danger-text` `#FCA5A5` dark), `--status-danger-bg`, `--status-danger-border` — the app's existing red/danger palette, already used elsewhere for destructive states.
- `--border-subtle`, `--radius-sm`, `--transition-fast` — shared structural tokens.

Use these variables, not new hardcoded hex codes — that's what keeps every other button correct automatically in both light and dark mode, and these two buttons must behave the same way.

## Task

1. Fix "View Full History →" so it actually navigates to the Audit Inspection History tab.
2. Give `.btn-text-sm` real styling based on the existing brand-accent color, so "View Full History →" looks like an intentional, on-brand text-link-style action instead of a bare unstyled button.
3. Give the "Clear" button (`#btn-clear-query`) its own distinct color treatment — it's a destructive/reset action (it wipes the selected query photo and resets the match studio via `resetQueryStudio()`), so it should read as a **warning/danger-toned** action, visually distinct from "View Full History →", using the app's existing `--status-danger*` tokens rather than sharing identical styling with a plain navigational text button.

## Step 1 — `frontend/app.html`: fix the broken function name

Find (around line 216):
```html
<button class="btn-text-sm" onclick="switchToTab('logs-tab')">View Full History &rarr;</button>
```
Change `switchToTab` to `switchTab` (the function that actually exists and is exposed on `window`):
```html
<button class="btn-text-sm" onclick="switchTab('logs-tab')">View Full History &rarr;</button>
```
That's the entire functional fix. Do not add any new JS function, do not touch `fetchLogs()`, the logs table rendering, or pagination — all of that already works correctly once this button can actually call `switchTab`.

## Step 2 — `frontend/styles.css`: define `.btn-text-sm` (base style, used by "View Full History →")

Add a new rule near the other `.btn-*` variants (right after `.btn-sm`, around line 605, is a sensible spot — keep all button-variant rules grouped together):

```css
.btn-text-sm {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 2px;
  background: transparent;
  border: none;
  color: var(--brand-accent);
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: color var(--transition-fast);
}

.btn-text-sm:hover {
  color: var(--brand-accent-hover);
  text-decoration: underline;
}
```

This makes "View Full History →" read as an intentional on-brand text link (same amber/accent color the rest of the app uses for primary actions), not a bare browser button.

## Step 3 — `frontend/styles.css`: give the Clear button its own danger-toned modifier class

Do **not** let `#btn-clear-query` just inherit the same amber `.btn-text-sm` styling from Step 2 — it's a destructive action and should look like one. Add a second, small modifier class right after `.btn-text-sm:hover`:

```css
.btn-text-sm.btn-text-danger {
  color: var(--status-danger);
}

.btn-text-sm.btn-text-danger:hover {
  color: var(--status-danger-text);
  text-decoration: underline;
}
```

Then in `frontend/app.html`, add that second class to the Clear button only (leave its `id` and inline `style="display: none;"` exactly as they are — that inline style is toggled by existing JS and must not be removed):

```html
<button class="btn-text-sm btn-text-danger" id="btn-clear-query" style="display: none;">Clear</button>
```

Result: "View Full History →" is amber/brand-accent (matches primary actions), "Clear" is red/danger-toned (matches the app's existing destructive-action color), and both share the same underlying compact text-button shape from `.btn-text-sm` so they're visually consistent in size and weight with each other and with the rest of the UI.

## Explicit boundaries

- Do not rename or touch `window.switchTab` / `switchTab()` itself, `fetchLogs()`, `renderLogsTable()`, or any pagination logic in `frontend/app.js` — none of it is broken.
- Do not fix the Dashboard's "Start New Search" button in this same change — it has an identical bug but wasn't part of this request. Flag it in your summary so it's not forgotten, but don't silently fix it here.
- Do not remove or alter the inline `style="display: none;"` on `#btn-clear-query`, or the `id="btn-clear-query"` attribute — `frontend/app.js` (`elements.btnClearQuery`, `setQueryFile()`, `resetQueryStudio()`) depends on that exact id and toggles that inline style directly.
- Do not introduce any new hardcoded hex/rgb color values — every color must come from an existing `var(--...)` token already defined in `:root` / the dark-mode block, so both buttons stay correct automatically in light and dark mode without any extra dark-mode-specific CSS.
- No backend changes. This is a 2-file change: `frontend/app.html` and `frontend/styles.css`.

## Acceptance criteria

1. Clicking "View Full History →" on the Dashboard switches to the Audit Inspection History tab (`#logs-tab`), the nav sidebar highlights the correct item, the topbar title/description update, and the logs table refreshes and shows real entries (via the existing `fetchLogs()` call already wired into `switchTab`).
2. "View Full History →" is visibly colored (brand-accent/amber) with a hover state, in both light and dark mode — not a bare default button.
3. The Clear button on the Query Photo card is visibly colored in the app's red/danger tone with its own hover state, distinct from "View Full History →", in both light and dark mode.
4. The Clear button's existing show/hide behavior (hidden until a query photo is selected) and its click behavior (`resetQueryStudio()`) are unchanged.
5. No other button or tab-switch call site in the app regresses — verify "Refresh Logs", sidebar nav items, and any other place that calls `switchTab(...)` directly (not `switchToTab`) still work exactly as before.

## Manual QA checklist

- [ ] Dashboard → click "View Full History →" → lands on Audit Inspection History tab with real log entries visible and pagination controls present.
- [ ] "View Full History →" text is amber/brand-accent colored, underlines on hover, in both light and dark theme.
- [ ] Match tab → select a query photo → "Clear" button appears, is red/danger colored, underlines on hover, in both light and dark theme.
- [ ] Click "Clear" → query photo, preview, and results area reset exactly as before this change.
- [ ] Sidebar navigation and "Refresh Logs" button on the logs tab still work unchanged.
- [ ] Dashboard's "Start New Search" button is confirmed still broken (unchanged, out of scope) — not silently fixed as a side effect.

## Deliverable

A diff touching only `frontend/app.html` (two small edits: the `onclick` fix and the added `btn-text-danger` class) and `frontend/styles.css` (the two new CSS rule blocks), plus a one-paragraph summary confirming the QA checklist passed and separately flagging the identical `switchToTab` bug still present on "Start New Search" for a future fix.
