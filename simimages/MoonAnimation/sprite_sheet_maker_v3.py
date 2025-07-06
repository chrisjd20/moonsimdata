from PIL import Image
import math
import os

# --- Parameters ---
FRAME_PREFIX = 'final_'
HEIGHTS = [720, 400, 200, 100]  # Add 100 height for the 4th sheet

# --- Collect frame filenames, skipping the first 52 ---
all_frames = [f for f in os.listdir('.') if f.startswith(FRAME_PREFIX) and f.endswith('.png')]
def frame_num(filename):
    return int(filename.split('_')[-1].split('.')[0])
all_frames = sorted(all_frames, key=frame_num)
frames = all_frames[105:]  # skip first 52

# --- Load frames and calculate original dimensions ---
images = [Image.open(f) for f in frames]
orig_width, orig_height = images[0].size
num_frames = len(images)

# --- Calculate best (rows, cols) for near-square ---
cols = math.ceil(math.sqrt(num_frames))
rows = math.ceil(num_frames / cols)

for out_height in HEIGHTS:
    out_width = round(orig_width * (out_height / orig_height))
    sprite_sheet = Image.new('RGBA', (cols * out_width, rows * out_height), (0, 0, 0, 0))

    for idx, img in enumerate(images):
        # Resize if needed
        if (img.height, img.width) != (out_height, out_width):
            img2 = img.resize((out_width, out_height), Image.LANCZOS)
        else:
            img2 = img
        r = idx // cols
        c = idx % cols
        sprite_sheet.paste(img2, (c * out_width, r * out_height))

    # Save with dimensions in the name
    out_filename = f"spritesheet_{out_width}x{out_height}.png"
    sprite_sheet.save(out_filename)
    print(f"Saved {out_filename} ({cols} cols x {rows} rows, {num_frames} frames)")

print("All sprite sheets generated!")
