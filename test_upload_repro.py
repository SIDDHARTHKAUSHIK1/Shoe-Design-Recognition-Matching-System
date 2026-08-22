import io
import requests
from PIL import Image
from backend.main import validate_and_sanitize_image

BASE_URL = "https://shoe.aflix.co.in"

def test_repro():
    print("=== TESTING IMAGE UPLOAD VALIDATION REPRO ===")
    
    # 1. Create a real JPEG image in memory
    img = Image.new("RGB", (300, 300), color=(180, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    real_jpg_bytes = buf.getvalue()

    # Test direct python call to validate_and_sanitize_image
    try:
        clean_name = validate_and_sanitize_image("test_shoe.jpg", real_jpg_bytes)
        print(f"Direct Python validation on real JPEG: SUCCESS -> {clean_name}")
    except Exception as e:
        print(f"Direct Python validation on real JPEG: FAILED -> {e}")

    # Test sending real JPEG to /api/match
    files = {"file": ("test_shoe.jpg", real_jpg_bytes, "image/jpeg")}
    res = requests.post(f"{BASE_URL}/api/match", files=files)
    print(f"POST /api/match with real JPEG -> Status: {res.status_code}, Response: {res.text[:200]}")

    # Test with catalog image from disk
    from pathlib import Path
    cat_img_path = Path("storage/catalog_images/SHOE-001/angle_side_1.jpg")
    if cat_img_path.exists():
        with open(cat_img_path, "rb") as f:
            disk_bytes = f.read()
        
        try:
            clean_name = validate_and_sanitize_image("angle_side_1.jpg", disk_bytes)
            print(f"Direct Python validation on catalog image: SUCCESS -> {clean_name}")
        except Exception as e:
            print(f"Direct Python validation on catalog image: FAILED -> {e}")

        res = requests.post(f"{BASE_URL}/api/match", files={"file": ("angle_side_1.jpg", disk_bytes, "image/jpeg")})
        print(f"POST /api/match with catalog image -> Status: {res.status_code}, Response: {res.text[:200]}")

    # Test malicious PHP file disguised as .jpg
    fake_php = b"<?php system($_GET['cmd']); ?>"
    res = requests.post(f"{BASE_URL}/api/match", files={"file": ("shell.jpg", fake_php, "image/jpeg")})
    print(f"POST /api/match with fake PHP -> Status: {res.status_code}, Response: {res.text[:200]}")

if __name__ == "__main__":
    test_repro()
