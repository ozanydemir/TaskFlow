import os
import sys
from PIL import Image, ImageDraw

def generate_icons():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    source_path = os.path.join(base_dir, "design_mockups", "Logo_3_Layered_Stack.jpg")
    resources_dir = os.path.join(base_dir, "resources")
    os.makedirs(resources_dir, exist_ok=True)

    if not os.path.exists(source_path):
        print(f"Source image not found: {source_path}")
        return False

    print(f"Generating high-fidelity icons from Concept 3: {source_path}")
    img = Image.open(source_path).convert("RGBA")

    # Center of squircle is at (512, 512.5), width/height approx 656px
    cx, cy = 512, 512.5
    half = 328
    x0, y0, x1, y1 = int(cx - half), int(cy - half), int(cx + half), int(cy + half)

    cropped = img.crop((x0, y0, x1, y1))
    w, h = cropped.size

    # High-resolution anti-aliased mask (8x supersampling for flawless edge smoothness)
    scale = 8
    mask_hi = Image.new("L", (w * scale, h * scale), 0)
    draw = ImageDraw.Draw(mask_hi)
    r_hi = 125 * scale
    inset = 2 * scale
    draw.rounded_rectangle((inset, inset, w * scale - inset, h * scale - inset), radius=r_hi, fill=255)

    mask = mask_hi.resize((w, h), Image.Resampling.LANCZOS)
    cropped.putalpha(mask)

    # 1. Master 512x512
    master_512 = cropped.resize((512, 512), Image.Resampling.LANCZOS)
    master_512.save(os.path.join(resources_dir, "app_icon_512.png"), "PNG")

    # 2. Window / QIcon 256x256
    icon_256 = cropped.resize((256, 256), Image.Resampling.LANCZOS)
    icon_256.save(os.path.join(resources_dir, "icon.png"), "PNG")

    # 3. Header Logo 128x128
    logo_128 = cropped.resize((128, 128), Image.Resampling.LANCZOS)
    logo_128.save(os.path.join(resources_dir, "app_logo.png"), "PNG")

    # 4. Multi-resolution Windows ICO (16, 24, 32, 48, 64, 128, 256)
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    master_512.save(os.path.join(resources_dir, "icon.ico"), format="ICO", sizes=ico_sizes)

    print("All icons successfully generated in resources/ folder!")
    return True

if __name__ == "__main__":
    generate_icons()
