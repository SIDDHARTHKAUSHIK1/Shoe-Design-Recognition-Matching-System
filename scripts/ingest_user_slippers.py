"""
Ingest the 20 user slipper photos from storage/Slippers into the active SQLite & FAISS catalog.
"""
import os
import sys
import glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.ingestion import ingest_single_design
from backend import database as db
from backend.classifier import ZeroShotCategoryClassifier

def ingest_user_slippers():
    print("Ingesting user slippers into catalog...")
    db.init_db()
    
    slipper_photos = sorted(glob.glob("storage/Slippers/*.jpeg") + glob.glob("storage/Slippers/*.jpg"))
    print(f"Found {len(slipper_photos)} user slipper photos.")
    
    categories = [
        "Slide Sandal", "Flip-Flop", "House Slipper", "Mule Slipper",
        "Open-Toe Slide", "Comfort Slipper", "Indoor Fleece Slipper", "Beach Sandal"
    ]
    
    slipper_names = [
        "CloudStep Foam Slide", "AeroBreeze Flip-Flop", "CozyComfort Indoor Slipper",
        "UrbanStyle Casual Mule", "VelvetLuxe House Slipper", "HydroFlex Beach Slide",
        "Orthopedic Arch Flip-Flop", "PlushWarm Bedroom Slipper", "Zenith Cork Mule",
        "WaveGrip Sport Slide", "UltraSoft Fleece Slipper", "SoleCushion Thong Sandal",
        "EcoStride Hemp Slipper", "Signature Leather Mule", "ActiveRecovery Slide",
        "Classic Home Slipper", "Nordic Winter Slipper", "BreezeWalk Flip-Flop",
        "ContourFit Slide Sandal", "MasterCraft Slipper Archive"
    ]
    
    for idx, img_path in enumerate(slipper_photos, start=1):
        design_id = f"SLIP-{idx+4:03d}"
        name = slipper_names[(idx - 1) % len(slipper_names)]
        category = categories[(idx - 1) % len(categories)]
        shelf = f"Warehouse B - Section 1 - Rack S-{(idx%5)+1:02d} - Shelf {(idx%3)+1}"
        materials = "Molded EVA Foam / Anti-Slip Rubber Sole" if "Slide" in category else "Soft Plush Velvet / Memory Foam"
        
        with open(img_path, "rb") as f:
            content = f.read()
            
        ingest_single_design(
            design_id=design_id,
            name=name,
            category=category,
            description=f"Authentic factory reference model: {name} with high-resolution visual embeddings.",
            created_by="Master Catalog",
            shelf_location=shelf,
            materials=materials,
            season="Summer/Winter 2026",
            production_status="Active Sample Room",
            image_files=[{
                "filename": os.path.basename(img_path),
                "content": content,
                "angle": "side"
            }]
        )
        print(f"  Indexed [{idx}/{len(slipper_photos)}] {design_id}: {name} ({category})")

    print("\nAll 20 user slippers successfully ingested into catalog!")

if __name__ == "__main__":
    ingest_user_slippers()
