"""
Catalog Reset Script.
Wipes sample catalog items, reference images, FAISS vector index, and image storage,
leaving a clean, empty project ready for client deployment and custom data entry.
"""
import os
import shutil
import sqlite3
from pathlib import Path

STORAGE_DIR = Path("storage")
DB_PATH = STORAGE_DIR / "catalog.db"
FAISS_PATH = STORAGE_DIR / "shoe_index.faiss"
CATALOG_IMAGES_DIR = STORAGE_DIR / "catalog_images"
UPLOADS_DIR = STORAGE_DIR / "uploads"


def reset_catalog():
    print("=" * 60)
    print(" 🚀 SHOEMATCH AI CATALOG RESET UTILITY")
    print("=" * 60)

    # 1. Clear physical image folders
    if CATALOG_IMAGES_DIR.exists():
        print("📁 Clearing catalog images directory...")
        for item in CATALOG_IMAGES_DIR.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)
        print("  ✓ Catalog images cleared.")

    if UPLOADS_DIR.exists():
        print("📁 Clearing upload temp directory...")
        for item in UPLOADS_DIR.iterdir():
            if item.is_file():
                item.unlink(missing_ok=True)
        print("  ✓ Temp uploads cleared.")

    # 2. Reset FAISS Vector Index
    if FAISS_PATH.exists():
        print("🧠 Removing sample FAISS vector index...")
        FAISS_PATH.unlink(missing_ok=True)
        print("  ✓ FAISS vector index reset.")

    # 3. Wipe SQLite catalog tables
    if DB_PATH.exists():
        print("🗄️ Resetting catalog database tables...")
        try:
            conn = sqlite3.connect(str(DB_PATH))
            c = conn.cursor()
            c.execute("DELETE FROM reference_images;")
            c.execute("DELETE FROM designs;")
            c.execute("DELETE FROM query_logs;")
            try:
                c.execute("DELETE FROM sqlite_sequence WHERE name IN ('reference_images', 'designs', 'query_logs');")
            except Exception:
                pass
            conn.commit()
            conn.close()
            print("  ✓ SQLite database tables cleared.")
        except Exception as e:
            print(f"  ⚠️ Warning wiping database tables: {e}")

    print("\n✨ SUCCESS! Catalog successfully reset to 0 items.")
    print("👉 Your client can now log in and add their own shoe designs from scratch!")
    print("=" * 60)


if __name__ == "__main__":
    reset_catalog()
