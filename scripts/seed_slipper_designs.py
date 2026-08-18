import os
import sys
import glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.ingestion import ingest_single_design
from backend import database as db

def seed_slippers():
    print("Seeding slipper designs into catalog...")
    db.init_db()
    
    # Get available reference images
    sample_images = glob.glob("storage/catalog_images/*/*.jpg") + glob.glob("storage/catalog_images/*/*.jpeg")
    if not sample_images:
        print("No sample images found.")
        return

    slipper_designs = [
        {
            "id": "SLIP-001",
            "name": "Comfort Cloud Slide Sandal",
            "category": "Slide Sandal",
            "description": "Ergonomic open-toe EVA foam slide with contoured footbed for indoor and outdoor wear.",
            "shelf": "Warehouse B - Rack 01 - Shelf S-01",
            "materials": "Hydrophobic EVA Foam / Anti-Slip Tread",
            "season": "Summer 2026",
            "status": "Active Production Sample"
        },
        {
            "id": "SLIP-002",
            "name": "Breeze Ergonomic Flip-Flop",
            "category": "Flip-Flop",
            "description": "Lightweight dual-density rubber flip-flop with textured grip strap and arch support.",
            "shelf": "Warehouse B - Rack 01 - Shelf S-02",
            "materials": "Natural Gum Rubber / Soft Woven Strap",
            "season": "Summer 2026",
            "status": "Sample Archive"
        },
        {
            "id": "SLIP-003",
            "name": "Cozy Velvet Bedroom Slipper",
            "category": "House Slipper",
            "description": "Plush memory foam indoor slipper with warm fleece lining and non-marking TPR sole.",
            "shelf": "Warehouse B - Rack 02 - Shelf S-03",
            "materials": "Plush Velvet / Memory Foam / TPR Sole",
            "season": "Winter 2026",
            "status": "Active Production Sample"
        },
        {
            "id": "SLIP-004",
            "name": "Urban Mule Casual Slide",
            "category": "Mule Slipper",
            "description": "Open-back slip-on mule slide crafted with perforated suede and cork footbed.",
            "shelf": "Warehouse B - Rack 02 - Shelf S-04",
            "materials": "Perforated Suede / Natural Cork / Rubber Outsole",
            "season": "Collection 2026",
            "status": "Prototype"
        }
    ]

    for idx, s in enumerate(slipper_designs):
        existing = db.get_design(s["id"])
        if existing:
            print(f"Slipper design {s['id']} already exists.")
            continue
            
        img_src = sample_images[(idx + 3) % len(sample_images)]
        with open(img_src, "rb") as f:
            content = f.read()
            
        ingest_single_design(
            design_id=s["id"],
            name=s["name"],
            category=s["category"],
            description=s["description"],
            created_by="Master Catalog",
            shelf_location=s["shelf"],
            materials=s["materials"],
            season=s["season"],
            production_status=s["status"],
            image_files=[{
                "filename": os.path.basename(img_src),
                "content": content,
                "angle": "side"
            }]
        )
        print(f"Indexed {s['id']}: {s['name']} (Category: {s['category']})")

if __name__ == "__main__":
    seed_slippers()
