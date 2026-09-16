import os
from PIL import Image

SRC_IMAGE = r"C:/Users/Siddharth Kaushik/.gemini/antigravity/brain/2997a08b-254a-44dc-9de2-3321c98a6bea/.user_uploaded/media_1789464040084.jpg"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def generate_icons():
    print(f"Loading source image: {SRC_IMAGE}")
    img = Image.open(SRC_IMAGE).convert("RGBA")
    
    # 1. Playstore icon (512x512 PNG)
    playstore_path = os.path.join(BASE_DIR, "android", "app", "src", "main", "ic_launcher-playstore.png")
    playstore_img = img.resize((512, 512), Image.Resampling.LANCZOS)
    playstore_img.save(playstore_path, "PNG")
    print(f"Saved: {playstore_path}")

    # 2. Frontend mobile brand-icon (512x512 PNG)
    brand_icon_path = os.path.join(BASE_DIR, "frontend", "mobile", "brand-icon.png")
    playstore_img.save(brand_icon_path, "PNG")
    print(f"Saved: {brand_icon_path}")

    # 3. Android Mipmap densities
    densities = {
        "mipmap-mdpi": {"icon": 48, "fg": 108},
        "mipmap-hdpi": {"icon": 72, "fg": 162},
        "mipmap-xhdpi": {"icon": 96, "fg": 216},
        "mipmap-xxhdpi": {"icon": 144, "fg": 324},
        "mipmap-xxxhdpi": {"icon": 192, "fg": 432},
    }

    res_dir = os.path.join(BASE_DIR, "android", "app", "src", "main", "res")

    for density, sizes in densities.items():
        folder = os.path.join(res_dir, density)
        os.makedirs(folder, exist_ok=True)
        
        icon_size = sizes["icon"]
        fg_size = sizes["fg"]

        # ic_launcher.webp & ic_launcher_round.webp
        icon_img = img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
        icon_path = os.path.join(folder, "ic_launcher.webp")
        round_path = os.path.join(folder, "ic_launcher_round.webp")
        icon_img.save(icon_path, "WEBP")
        icon_img.save(round_path, "WEBP")
        print(f"Saved: {icon_path} ({icon_size}x{icon_size})")

        # ic_launcher_foreground.webp (Centered in fg canvas with 72% inner safe area scaling)
        fg_canvas = Image.new("RGBA", (fg_size, fg_size), (0, 0, 0, 255))
        inner_size = int(fg_size * 0.72)
        inner_scaled = img.resize((inner_size, inner_size), Image.Resampling.LANCZOS)
        offset = (fg_size - inner_size) // 2
        fg_canvas.paste(inner_scaled, (offset, offset), inner_scaled)
        
        fg_path = os.path.join(folder, "ic_launcher_foreground.webp")
        mono_path = os.path.join(folder, "ic_launcher_monochrome.webp")
        fg_canvas.save(fg_path, "WEBP")
        fg_canvas.save(mono_path, "WEBP")
        print(f"Saved: {fg_path} ({fg_size}x{fg_size})")

    print("\nAll icon assets successfully generated!")

if __name__ == "__main__":
    generate_icons()
