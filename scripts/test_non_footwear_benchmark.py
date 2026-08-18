import io
import requests
from PIL import Image, ImageDraw
import numpy as np

# Generate diverse non-footwear images
test_samples = []

# 1. Car / Vehicle
img_car = Image.new("RGB", (224, 224), (230, 230, 230))
d = ImageDraw.Draw(img_car)
d.rectangle([20, 80, 200, 150], fill=(200, 30, 30))
d.ellipse([40, 135, 85, 180], fill=(20, 20, 20))
d.ellipse([135, 135, 180, 180], fill=(20, 20, 20))
test_samples.append(("Car / Vehicle", img_car))

# 2. Human Face / Portrait
img_face = Image.new("RGB", (224, 224), (245, 235, 220))
d = ImageDraw.Draw(img_face)
d.ellipse([50, 40, 170, 180], fill=(255, 215, 180))
d.ellipse([75, 85, 95, 105], fill=(30, 80, 180))
d.ellipse([125, 85, 145, 105], fill=(30, 80, 180))
d.line([95, 145, 125, 145], fill=(180, 40, 40), width=4)
test_samples.append(("Human Face", img_face))

# 3. Smartphone Screen
img_phone = Image.new("RGB", (224, 224), (240, 240, 240))
d = ImageDraw.Draw(img_phone)
d.rounded_rectangle([70, 20, 150, 200], radius=15, fill=(40, 40, 40))
d.rectangle([76, 35, 144, 185], fill=(70, 130, 240))
test_samples.append(("Smartphone", img_phone))

# 4. Pizza / Food
img_pizza = Image.new("RGB", (224, 224), (250, 245, 235))
d = ImageDraw.Draw(img_pizza)
d.ellipse([30, 30, 190, 190], fill=(220, 160, 60))
d.ellipse([45, 45, 175, 175], fill=(240, 80, 40))
for x, y in [(70, 70), (130, 80), (100, 130), (150, 140), (80, 150)]:
    d.ellipse([x, y, x+20, y+20], fill=(160, 20, 20))
test_samples.append(("Pizza / Food", img_pizza))

# 5. Tree / Nature
img_tree = Image.new("RGB", (224, 224), (135, 206, 235))
d = ImageDraw.Draw(img_tree)
d.rectangle([0, 160, 224, 224], fill=(34, 139, 34))
d.rectangle([100, 100, 124, 170], fill=(139, 69, 19))
d.ellipse([60, 30, 164, 120], fill=(46, 139, 87))
test_samples.append(("Tree / Nature", img_tree))

# 6. Coffee Mug
img_mug = Image.new("RGB", (224, 224), (250, 250, 250))
d = ImageDraw.Draw(img_mug)
d.rectangle([70, 60, 150, 170], fill=(220, 50, 50))
d.arc([130, 80, 180, 150], start=270, end=90, fill=(220, 50, 50), width=10)
test_samples.append(("Coffee Mug", img_mug))

# 7. T-Shirt
img_shirt = Image.new("RGB", (224, 224), (245, 245, 245))
d = ImageDraw.Draw(img_shirt)
d.polygon([(70, 40), (150, 40), (190, 80), (160, 110), (140, 90), (140, 200), (80, 200), (80, 90), (60, 110), (30, 80)], fill=(30, 90, 200))
test_samples.append(("T-Shirt", img_shirt))

# 8. Wristwatch
img_watch = Image.new("RGB", (224, 224), (245, 245, 245))
d = ImageDraw.Draw(img_watch)
d.rectangle([95, 10, 125, 214], fill=(80, 50, 30))
d.ellipse([70, 70, 150, 150], fill=(210, 210, 210), outline=(100, 100, 100), width=4)
test_samples.append(("Wristwatch", img_watch))

# 9. Random Noise
img_noise = Image.fromarray(np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))
test_samples.append(("Random Noise", img_noise))

# 10. Solid White & Black
test_samples.append(("Solid White", Image.new("RGB", (224, 224), (255, 255, 255))))
test_samples.append(("Solid Black", Image.new("RGB", (224, 224), (0, 0, 0))))

print("=" * 70)
print("TESTING NON-FOOTWEAR IMAGES AGAINST LIVE API (http://127.0.0.1:8000)")
print("=" * 70)

for name, img in test_samples:
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    
    r = requests.post("http://127.0.0.1:8000/api/match", files={"file": ("test.jpg", buf, "image/jpeg")})
    data = r.json()
    
    cat = data.get("detected_category")
    fw = data.get("is_footwear_detected")
    matches = len(data.get("matches", []))
    msg = data.get("message")
    
    status = "REJECTED (Correct)" if (cat == "none" and fw is False and matches == 0) else f"FALSE POSITIVE ({cat})"
    print(f"{name:20s} -> Cat: {str(cat):8s} | FW: {str(fw):5s} | Matches: {matches} | {status}")
    if matches == 0:
        print(f"     Message: '{msg}'")

print("=" * 70)
