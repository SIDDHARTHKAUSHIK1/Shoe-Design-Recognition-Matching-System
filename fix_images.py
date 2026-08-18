"""
Script to link and copy shoe reference images for all imported Colab designs.
"""
import os
import json
import shutil
import glob
from pathlib import Path
from PIL import Image
import sqlite3

def fix_catalog_images():
    print("Fixing catalog image mapping...")
    
    # 1. Collect all available JPEG images from storage/catalog_images
    existing_images = sorted(glob.glob("storage/catalog_images/SHOE-*/*.jpeg"))
    print(f"Found {len(existing_images)} existing shoe photos in storage.")
    
    # 2. Read metadata.json
    with open("storage/metadata.json", "r", encoding="utf-8") as f:
        metadata = json.load(f)
        
    print(f"Metadata entries to map: {len(metadata)}")
    
    conn = sqlite3.connect("storage/catalog.db")
    cursor = conn.cursor()
    
    # Ensure all DESIGN_001 ... DESIGN_048 folders have their photos
    for idx, item in enumerate(metadata):
        design_name = item.get("design_name", f"design_{idx+1:03d}")
        design_id = item.get("design_id") or design_name.replace(" ", "_").upper()
        
        # Target folder
        target_dir = Path("storage/catalog_images") / design_id
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Pick the matching source image
        dest_filename = f"photo_{idx+1}.jpg"
        dest_path = target_dir / dest_filename
        
        # If we have an existing image for this index
        if idx < len(existing_images):
            src = existing_images[idx]
            shutil.copy2(src, dest_path)
            rel_path = f"/catalog_images/{design_id}/{dest_filename}"
        else:
            rel_path = f"/catalog_images/{design_id}/{dest_filename}"
            
        print(f"Mapped {design_id} (FAISS ID {idx}) -> {rel_path}")
        
        # Update SQLite database
        cursor.execute("""
            UPDATE reference_images 
            SET image_path = ? 
            WHERE faiss_id = ?;
        """, (rel_path, idx))
        
        cursor.execute("""
            UPDATE designs 
            SET thumbnail_path = ? 
            WHERE design_id = ?;
        """, (rel_path, design_id))
        
    conn.commit()
    conn.close()
    print("Catalog images successfully mapped and SQLite database updated!")

if __name__ == "__main__":
    fix_catalog_images()
