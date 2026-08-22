"""
Zip dist/ into a Hostinger-uploadable archive.

    python scripts/package_frontend.py        (or: npm run build:zip)

The archive extracts AS the web root — index.html sits at the top level, not
nested inside a folder — which is what hPanel's File Manager and the Hostinger
static-site deploy both expect.
"""
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
OUT = os.path.join(ROOT, "deploy", "hostinger", "shoematch-frontend.zip")

if not os.path.isdir(DIST):
    sys.exit("ERROR: dist/ not found. Run `npm run build` first.")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
if os.path.exists(OUT):
    os.remove(OUT)

count = 0
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for root, _dirs, files in os.walk(DIST):
        for name in sorted(files):
            full = os.path.join(root, name)
            arc = os.path.relpath(full, DIST).replace("\\", "/")
            z.write(full, arc)
            count += 1

if count == 0:
    sys.exit("ERROR: dist/ is empty. Run `npm run build` first.")

print("packaged %d files -> %s (%.1f KB)"
      % (count, os.path.relpath(OUT, ROOT).replace("\\", "/"), os.path.getsize(OUT) / 1024))
