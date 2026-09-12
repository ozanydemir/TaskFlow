import os
import sys
import struct
import io
from PIL import Image, ImageDraw

def create_windows_ico(master_img, output_ico_path):
    # Sizes standard for Windows Shell, Explorer and System Tray
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images_data = []

    for s in sizes:
        resized = master_img.resize((s, s), Image.Resampling.LANCZOS).convert('RGBA')
        if s == 256:
            # Vista+ PNG format for 256x256
            buf = io.BytesIO()
            resized.save(buf, format='PNG')
            png_bytes = buf.getvalue()
            images_data.append({'size': s, 'bpp': 32, 'data': png_bytes})
        else:
            # Standard uncompressed DIB (BITMAPINFOHEADER + BGRA + AND mask)
            # Essential for Windows System Tray ("gizli simgeler") and legacy GDI shell compatibility!
            w, h = s, s
            bih = struct.pack('<IIIHHIIIIII',
                40,          # biSize
                w,           # biWidth
                h * 2,       # biHeight (doubled for XOR + AND mask)
                1,           # biPlanes
                32,          # biBitCount
                0,           # biCompression (BI_RGB)
                w * h * 4,   # biSizeImage (XOR mask)
                0, 0, 0, 0   # XPelsPerMeter, YPelsPerMeter, ClrUsed, ClrImportant
            )
            # BGRA pixels, bottom-to-top
            xor_bytes = bytearray()
            for y in range(h - 1, -1, -1):
                for x in range(w):
                    r, g, b, a = resized.getpixel((x, y))
                    xor_bytes.extend([b, g, r, a])

            # AND mask (1-bit per pixel, padded to 32-bit boundary)
            row_bytes = (w + 31) // 32 * 4
            and_bytes = bytearray(row_bytes * h)

            dib_data = bih + bytes(xor_bytes) + bytes(and_bytes)
            images_data.append({'size': s, 'bpp': 32, 'data': dib_data})

    # Pack ICO
    ico_bytes = bytearray()
    ico_bytes.extend(struct.pack('<HHH', 0, 1, len(images_data)))

    offset = 6 + len(images_data) * 16
    for item in images_data:
        s = item['size']
        w_byte = 0 if s == 256 else s
        h_byte = 0 if s == 256 else s
        data_len = len(item['data'])
        ico_bytes.extend(struct.pack('<BBBBHHII', w_byte, h_byte, 0, 0, 1, 32, data_len, offset))
        offset += data_len

    for item in images_data:
        ico_bytes.extend(item['data'])

    with open(output_ico_path, 'wb') as f:
        f.write(ico_bytes)

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

    # 4. Multi-resolution Windows ICO (16, 24, 32, 48, 64, 128, 256) with native DIB for tray
    create_windows_ico(master_512, os.path.join(resources_dir, "icon.ico"))

    print("All icons successfully generated in resources/ folder!")
    return True

if __name__ == "__main__":
    generate_icons()
