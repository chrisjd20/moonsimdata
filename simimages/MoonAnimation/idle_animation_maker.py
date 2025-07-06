from PIL import Image
import math
import os

# --- Parameters ---
FRAME_PREFIX = 'final_'
START_FRAME = 1
END_FRAME = 50
HEIGHT = 200  # Choose your desired height (match previous, or change)
OUT_NAME = 'spritesheet_1to50_251x200.png'  # Update size if you change HEIGHT

# --- Collect the correct frames ---
all_frames = [f for f in os.listdir('.') if f.startswith(FRAME_PREFIX) and f.endswith('.png')]
def frame_num(filename):
    return int(filename.split('_')[-1].split('.')[0])
all_frames = sorted(all_frames, key=frame_num)
frames = [f for f in all_frames if START_FRAME <= frame_num(f) <= END_FRAME]

# --- Load frames and calculate original dimensions ---
images = [Image.open(f) for f in frames]
orig_width, orig_height = images[0].size
num_frames = len(images)

# --- Resize if needed ---
out_height = HEIGHT
out_width = round(orig_width * (out_height / orig_height))

# --- Calculate best (rows, cols) for near-square ---
cols = math.ceil(math.sqrt(num_frames))
rows = math.ceil(num_frames / cols)

sprite_sheet = Image.new('RGBA', (cols * out_width, rows * out_height), (0, 0, 0, 0))

for idx, img in enumerate(images):
    img2 = img.resize((out_width, out_height), Image.LANCZOS)
    r = idx // cols
    c = idx % cols
    sprite_sheet.paste(img2, (c * out_width, r * out_height))

out_filename = f"spritesheet_1to50_{out_width}x{out_height}.png"
sprite_sheet.save(out_filename)
print(f"Saved {out_filename} ({cols} cols x {rows} rows, {num_frames} frames)")
