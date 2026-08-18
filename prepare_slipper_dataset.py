import os
import sys
import glob
import shutil
import zipfile
import argparse
from pathlib import Path

# Fix Windows terminal UTF-8 encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def prepare_slipper_dataset(input_folder_path: str = None):
    print("=" * 65)
    print(">> SLIPPER DATASET PACKAGING TOOL FOR GOOGLE COLAB")
    print("=" * 65)

    base_dir = Path(__file__).resolve().parent
    
    # 1. Determine input directory
    if input_folder_path:
        input_dir = Path(input_folder_path)
    else:
        # Check standard default folders or prompt
        candidates = [
            base_dir / "my_slippers",
            base_dir / "slipper_photos",
            base_dir / "slippers",
            base_dir / "raw_slippers",
            Path.home() / "Downloads" / "slippers"
        ]
        found_dir = None
        for c in candidates:
            if c.exists() and c.is_dir():
                found_dir = c
                break
        
        if found_dir:
            input_dir = found_dir
            print(f"Found input slipper folder at: {input_dir}")
        else:
            # Create a folder for user if not exists
            default_dir = base_dir / "my_slippers"
            default_dir.mkdir(parents=True, exist_ok=True)
            input_dir = default_dir
            print(f"\n📂 Created folder: {input_dir}")
            print("👉 Please place your 20 slipper images inside this 'my_slippers' folder and re-run this script!")

    # 2. Scan for images
    image_extensions = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".jfif")
    image_files = []
    
    for root, _, files in os.walk(input_dir):
        for f in files:
            if os.path.splitext(f)[1].lower() in image_extensions:
                image_files.append(Path(root) / f)

    image_files = sorted(image_files)
    total_imgs = len(image_files)

    print(f"\nDiscovered {total_imgs} slipper image(s) in {input_dir}")

    if total_imgs == 0:
        print("\n⚠️ No image files found in the folder.")
        print(f"Please put your slipper images (.jpg / .png) into: '{input_dir}'")
        print("Then run: python prepare_slipper_dataset.py")
        return None

    # 3. Build organized dataset folder structure
    output_dataset_dir = base_dir / "dataset" / "slippers"
    output_dataset_dir.mkdir(parents=True, exist_ok=True)

    print("\n📦 Organizing into catalog structure: dataset/slippers/<design_name>/...")

    # Group images by design prefix or assign sequential designs
    for idx, img_path in enumerate(image_files, start=1):
        stem = img_path.stem.replace(" ", "_").lower()
        # If user named files like 'flipflop_01_side', use prefix, else sequential
        design_folder_name = f"slipper_design_{idx:03d}_{stem}"
        
        target_dir = output_dataset_dir / design_folder_name
        target_dir.mkdir(parents=True, exist_ok=True)
        
        dest_img_path = target_dir / f"photo_{img_path.name}"
        shutil.copy2(img_path, dest_img_path)
        print(f"  ✓ [{idx}/{total_imgs}] {img_path.name} -> {design_folder_name}/")

    # 4. Create ZIP package for Google Colab
    zip_output_path = base_dir / "slipper_dataset.zip"
    print(f"\n🗜️ Packaging into '{zip_output_path.name}' for Google Colab...")

    with zipfile.ZipFile(zip_output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(base_dir / "dataset"):
            for file in files:
                file_path = Path(root) / file
                rel_path = file_path.relative_to(base_dir)
                zipf.write(file_path, rel_path)

    print("\n" + "=" * 65)
    print("🎉 SUCCESS! DATASET READY FOR GOOGLE COLAB")
    print("=" * 65)
    print(f"📦 Generated Zip File: {zip_output_path}")
    print(f"📊 Total Photos Packaged: {total_imgs}")
    print("\n🚀 NEXT STEPS TO TRAIN ON GOOGLE COLAB:")
    print("1. Open Google Colab (https://colab.research.google.com/)")
    print("2. Open the notebook: 'colab_shoe_slipper_indexer.ipynb'")
    print("3. When prompted in Step 2, upload 'slipper_dataset.zip'")
    print("4. Run all cells -> It will process on GPU and download 'shoe_matching_colab_export.zip'")
    print("5. Place 'shoe_matching_colab_export.zip' here and run:")
    print("      python import_colab_index.py")
    print("=" * 65)

    return str(zip_output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare and package slipper dataset for Google Colab")
    parser.add_argument("--folder", "-f", type=str, default=None, help="Path to folder containing slipper images")
    args = parser.parse_args()
    
    prepare_slipper_dataset(args.folder)
