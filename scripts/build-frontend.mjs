/**
 * ShoeMatch AI — static frontend build.
 *
 *   node scripts/build-frontend.mjs        (or: npm run build)
 *
 * Source of truth is frontend/. Output is dist/, laid out as the web root
 * expects it: the HTML files reference /static/... absolute paths (matching how
 * FastAPI mounts frontend/ at /static), so this build is a copy + folder remap,
 * not a rewrite.
 *
 * The build FAILS if an asset referenced by the HTML is missing, so a broken
 * bundle is caught here rather than discovered live on the domain.
 */
import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const FRONTEND = path.join(ROOT, "frontend");
const DIST = path.join(ROOT, "dist");
const CATALOG_SRC = path.join(ROOT, "storage", "catalog_images");
const HTACCESS_SRC = path.join(ROOT, "deploy", "hostinger", "htaccess.conf");

// HTML entry points -> dist root.
const PAGES = ["index.html", "app.html"];

// Everything the HTML loads from /static/.
const STATIC_ASSETS = [
  "app.js",
  "config.js",
  "styles.css",
  "index.css",
  "tailwind.min.css",
  "hero_shoe.png",
  "placeholder.jpg",
  "placeholder.png",
];

// frontend/mobile/ ships as a self-contained folder (its refs are relative).
const MOBILE_FILES = ["index.html", "mobile.js", "mobile.css"];

const say = (...a) => console.log(...a);
let copied = 0;
const problems = [];

async function exists(p) {
  try { await fs.access(p); return true; } catch { return false; }
}

async function copy(src, dest, label) {
  if (!(await exists(src))) {
    problems.push(`missing source: ${path.relative(ROOT, src)}`);
    return false;
  }
  await fs.mkdir(path.dirname(dest), { recursive: true });
  await fs.copyFile(src, dest);
  const { size } = await fs.stat(dest);
  say(`  ${label.padEnd(38)} ${(size / 1024).toFixed(1).padStart(8)} KB`);
  copied++;
  return true;
}

// ---------------------------------------------------------------- clean
say("\nShoeMatch AI — building static frontend\n" + "=".repeat(62));
await fs.rm(DIST, { recursive: true, force: true });
await fs.mkdir(DIST, { recursive: true });
say(`\ncleaned  ${path.relative(ROOT, DIST)}/`);

// ---------------------------------------------------------------- pages
say("\npages -> dist/");
for (const p of PAGES) await copy(path.join(FRONTEND, p), path.join(DIST, p), p);

// --------------------------------------------------------------- static
say("\nassets -> dist/static/");
for (const a of STATIC_ASSETS) {
  await copy(path.join(FRONTEND, a), path.join(DIST, "static", a), `static/${a}`);
}

// --------------------------------------------------------------- mobile
say("\nmobile -> dist/mobile/");
for (const m of MOBILE_FILES) {
  await copy(path.join(FRONTEND, "mobile", m), path.join(DIST, "mobile", m), `mobile/${m}`);
}
// The mobile UI needs the same backend config as the desktop one.
await copy(path.join(FRONTEND, "config.js"), path.join(DIST, "mobile", "config.js"), "mobile/config.js");

// ------------------------------------------------- catalog images (auto)
// Discovered from the built HTML so the list can never drift from the markup.
const refs = new Set();
for (const p of PAGES) {
  const f = path.join(DIST, p);
  if (!(await exists(f))) continue;
  const html = await fs.readFile(f, "utf8");
  for (const m of html.matchAll(/\/catalog_images\/([^"'\s)>]+)/g)) refs.add(m[1]);
}

if (refs.size) {
  say(`\ncatalog images -> dist/catalog_images/   (${refs.size} referenced by the HTML)`);
  for (const rel of [...refs].sort()) {
    await copy(path.join(CATALOG_SRC, rel), path.join(DIST, "catalog_images", rel), `catalog_images/${rel}`);
  }
} else {
  say("\ncatalog images -> none referenced");
}

// ------------------------------------------------------------- .htaccess
say("\nserver config -> dist/");
await copy(HTACCESS_SRC, path.join(DIST, ".htaccess"), ".htaccess");

// ------------------------------------------------- verify /static/ refs
for (const p of PAGES) {
  const f = path.join(DIST, p);
  if (!(await exists(f))) continue;
  const html = await fs.readFile(f, "utf8");
  for (const m of html.matchAll(/["'](\/static\/[^"'?]+)/g)) {
    const rel = m[1].replace(/^\//, "");
    if (!(await exists(path.join(DIST, rel)))) {
      problems.push(`${p} references ${m[1]} but it is not in the bundle`);
    }
  }
}

// ---------------------------------------------------------------- report
say("\n" + "=".repeat(62));
if (problems.length) {
  say(`BUILD FAILED — ${problems.length} problem(s):`);
  for (const p of [...new Set(problems)]) say(`  - ${p}`);
  say("=".repeat(62) + "\n");
  process.exit(1);
}
say(`build ok — ${copied} files in ${path.relative(ROOT, DIST)}/`);
say("=".repeat(62) + "\n");
