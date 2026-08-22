import io
import os
import requests
from PIL import Image, ImageOps
from backend.main import validate_and_sanitize_image
from backend.engine import EmbeddingEngine
from backend.matcher import ShoeMatcher
from backend import database as db
from pathlib import Path

def benchmark_accuracy():
    print("==================================================")
    print("     SHOEMATCH AI MATCH ACCURACY BENCHMARK       ")
    print("==================================================")

    matcher = ShoeMatcher()
    
    # 1. Fetch reference images from DB
    all_refs = db.get_all_shoe_reference_images()
    print(f"Total reference images in DB: {len(all_refs)}")

    tested = 0
    for r in all_refs:
        if tested >= 5:
            break
            
        design_id = r["design_id"]
        rel_path = r["image_path"]
        img_path = Path("storage") / rel_path.lstrip("/storage/").lstrip("/")
        if not img_path.exists():
            img_path = Path(rel_path)
        if not img_path.exists():
            continue

        tested += 1
        with open(img_path, "rb") as f:
            raw_bytes = f.read()

        # Run direct match on raw_bytes
        match_raw = matcher.match_image(query_image_input=raw_bytes)
        top1_raw = match_raw["matches"][0] if match_raw.get("matches") else {}
        
        # Test with EXIF orientation simulation (Portrait 90-degree tag)
        raw_pil = Image.open(io.BytesIO(raw_bytes))
        exif = raw_pil.getexif()
        exif[0x0112] = 6  # Orientation = 6 (90 deg CW)
        
        buf_exif = io.BytesIO()
        raw_pil.save(buf_exif, format="JPEG", exif=exif)
        exif_bytes = buf_exif.getvalue()

        # Test match with EXIF bytes through matcher (which applies exif_transpose)
        match_exif = matcher.match_image(query_image_input=exif_bytes)
        top1_exif = match_exif["matches"][0] if match_exif.get("matches") else {}

        # Test if re-encoded WITHOUT exif_transpose (stripped EXIF without pixel rotation)
        buf_bad = io.BytesIO()
        pil_bad = Image.open(io.BytesIO(exif_bytes)) # opened without exif_transpose
        pil_bad.save(buf_bad, format="JPEG", quality=95) # EXIF stripped, pixels un-rotated!
        bad_reencoded_bytes = buf_bad.getvalue()

        match_bad = matcher.match_image(query_image_input=bad_reencoded_bytes)
        top1_bad = match_bad["matches"][0] if match_bad.get("matches") else {}

        # Test if re-encoded WITH exif_transpose
        buf_good = io.BytesIO()
        pil_good = Image.open(io.BytesIO(exif_bytes))
        pil_good = ImageOps.exif_transpose(pil_good) # Pixel rotation baked in!
        pil_good.convert("RGB").save(buf_good, format="JPEG", quality=95)
        good_reencoded_bytes = buf_good.getvalue()

        match_good = matcher.match_image(query_image_input=good_reencoded_bytes)
        top1_good = match_good["matches"][0] if match_good.get("matches") else {}

        print(f"\nDesign ID: {design_id} | Path: {img_path.name}")
        print(f"  Raw Photo Top-1 Match: {top1_raw.get('design_id')} ({top1_raw.get('design_name')}) -> Conf: {top1_raw.get('confidence_pct')}%")
        print(f"  EXIF Photo (Preserved EXIF) Top-1 Match: {top1_exif.get('design_id')} -> Conf: {top1_exif.get('confidence_pct')}%")
        print(f"  EXIF Photo (Stripped Without Transpose): {top1_bad.get('design_id')} -> Conf: {top1_bad.get('confidence_pct')}% <-- DEGRADED MATCH!")
        print(f"  EXIF Photo (Stripped WITH Transpose): {top1_good.get('design_id')} -> Conf: {top1_good.get('confidence_pct')}% <-- RESTORED MATCH!")

if __name__ == "__main__":
    benchmark_accuracy()
