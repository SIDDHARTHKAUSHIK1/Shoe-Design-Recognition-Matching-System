"""
Seed realistic warehouse shelf locations and manufacturing specs for all catalog shoes.
"""
import sqlite3

SHELF_DATA = {
    "SHOE-001": ("Building A - Section 2 - Rack A-01 - Shelf 1", "Full Grain Italian Calfskin / Blake Stitch", "Active Sample Room", "FW26"),
    "SHOE-002": ("Building A - Section 2 - Rack A-01 - Shelf 2", "Nubuck Leather / Gum Rubber Outsole", "Production Line 1", "SS26"),
    "SHOE-003": ("Building A - Section 3 - Rack B-04 - Shelf 3", "Engineered Jacquard Mesh / EVA Midsole", "QC Testing Lab", "FW26"),
    "SHOE-004": ("Building B - Section 1 - Rack C-02 - Shelf 1", "Waterproof Suede / Vibram Arctic Grip", "Material Archive", "Winter 26"),
    "SHOE-005": ("Building A - Section 1 - Rack A-03 - Shelf 4", "Nappa Leather / Memory Foam Insole", "Sample Room #2", "SS26"),
    "SHOE-006": ("Building B - Section 2 - Rack D-01 - Shelf 2", "Vintage Suede / Cupsole Construction", "Factory Archive", "Heritage Line"),
    "SHOE-007": ("Building A - Section 4 - Rack A-08 - Shelf 1", "Ultra-Lightweight TPU / Carbon Plate", "Pro Lab Rack", "Sprint 26"),
    "SHOE-008": ("Building A - Section 2 - Rack B-02 - Shelf 3", "Breathable Knit / Air Cushion Unit", "Active Production", "SS26"),
    "SHOE-009": ("Building B - Section 3 - Rack E-05 - Shelf 2", "Full Grain Hydrophobic Leather / Steel Shank", "Heavy Duty Vault", "FW26"),
    "SHOE-010": ("Building A - Section 1 - Rack A-05 - Shelf 2", "Recycled Canvas / Natural Latex Sole", "Eco Sample Rack", "Summer 26"),
    "SHOE-011": ("Building A - Section 3 - Rack C-01 - Shelf 1", "Hand-Burnished Crust Leather / Leather Sole", "Executive Archive", "Classic Line"),
    "SHOE-012": ("Building A - Section 4 - Rack B-06 - Shelf 2", "Seamless Engineered Knit / React Foam", "R&D Prototype Rack", "SS26"),
    "SHOE-013": ("Building A - Section 2 - Rack A-04 - Shelf 3", "Ripstop Nylon & Suede Overlay / Dual Foam", "Active Floor", "FW26"),
    "SHOE-014": ("Building B - Section 1 - Rack D-03 - Shelf 1", "Matte Action Leather / Vulcanized Rubber", "Design Studio", "Core Line"),
    "SHOE-015": ("Building A - Section 3 - Rack B-03 - Shelf 2", "Reflective Mesh / High-Rebound PU Sole", "Lab Testing", "FW26"),
    "SHOE-016": ("Building B - Section 4 - Rack F-02 - Shelf 1", "Oiled Nubuck / Goodyear Welted Vibram Sole", "Factory Vault", "Trek Series"),
    "SHOE-017": ("Building A - Section 1 - Rack A-02 - Shelf 3", "Organic Heavy Cotton Duck / Crepe Rubber", "Showroom Floor", "Casual 26"),
    "SHOE-018": ("Building A - Section 4 - Rack C-04 - Shelf 2", "Microfiber Synthetic Leather / Phylon Sole", "Sample Room #1", "Sport 26"),
    "SHOE-019": ("Building B - Section 2 - Rack E-01 - Shelf 4", "Gore-Tex Membrane / Cordura Upper / Trail Sole", "Weather Test Lab", "Outdoor 26"),
    "SHOE-020": ("Building A - Section 2 - Rack D-02 - Shelf 1", "Patent Leather & Suede Mix / Chunky Platform", "Fashion Archive", "Limited Ed."),
    "SHOE-021": ("Building A - Section 3 - Rack A-07 - Shelf 2", "Vegetable-Tanned Cowhide / Hand-Finished Edge", "Master Craftsman Room", "Heritage 26"),
    "SHOE-022": ("Building A - Section 1 - Rack B-01 - Shelf 1", "Croc-Embossed Calfskin / Brass Buckle / Leather Sole", "VIP Sample Vault - Shelf 1", "Luxury Collection"),
    "SHOE-023": ("Building A - Section 1 - Rack B-01 - Shelf 2", "Smooth Box Calf / Hand-Sewn Apron / Dainite Sole", "VIP Sample Vault - Shelf 2", "Luxury Collection"),
    "SHOE-024": ("Building A - Section 1 - Rack B-01 - Shelf 3", "Full Brogue Scotch Grain Leather / Goodyear Welt", "VIP Sample Vault - Shelf 3", "Luxury Collection")
}

from backend import database as db

def seed_locations():
    db.init_db()
    conn = db.get_db_connection()
    cursor = conn.cursor()
    
    for design_id, (shelf, mat, status, season) in SHELF_DATA.items():
        cursor.execute("""
            UPDATE designs
            SET shelf_location = ?, materials = ?, production_status = ?, season = ?
            WHERE design_id = ?;
        """, (shelf, mat, status, season, design_id))
        
    conn.commit()
    conn.close()
    print("Warehouse shelf locations and specs successfully seeded for all shoes!")

if __name__ == "__main__":
    seed_locations()
