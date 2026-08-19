"""Audit script: find all slipper-category entries in catalog."""
import sqlite3
import sys
sys.path.insert(0, ".")

conn = sqlite3.connect("storage/catalog.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== All catalog designs ===")
cur.execute("SELECT design_id, name, category FROM designs ORDER BY category")
rows = cur.fetchall()
for r in rows:
    print(dict(r))

slipper_kws = ["slipper", "slide", "sandal", "flip", "flop", "mule", "clog", "thong", "chappal", "croc"]
clauses = " OR ".join([f"LOWER(category) LIKE '%{k}%'" for k in slipper_kws])

print("\n=== Slipper-category designs ===")
cur.execute(f"SELECT design_id, name, category FROM designs WHERE {clauses}")
slipper_designs = cur.fetchall()
for r in slipper_designs:
    print(dict(r))
print(f"Total: {len(slipper_designs)}")

print("\n=== Slipper FAISS vectors (reference_images) ===")
cur.execute(f"""
    SELECT ri.faiss_id, ri.image_path, d.design_id, d.category
    FROM reference_images ri
    JOIN designs d ON ri.design_id = d.design_id
    WHERE {clauses}
    ORDER BY ri.faiss_id
""")
slipper_refs = cur.fetchall()
for r in slipper_refs:
    print(dict(r))
print(f"Total slipper vectors in FAISS: {len(slipper_refs)}")

print("\n=== Total catalog summary ===")
cur.execute("SELECT COUNT(*) FROM designs")
print("Total designs:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM reference_images")
print("Total reference images/vectors:", cur.fetchone()[0])
