import os
from PIL import Image

# Set your main character directory and the parchment background
CHARACTER_DIR = 'characters'
PARCHMENT = 'SquareParchmentCropped.png'

for root, dirs, files in os.walk(CHARACTER_DIR):
    for fname in files:
        if not fname.lower().endswith('.webp'):
            continue
        fpath = os.path.join(root, fname)
        try:
            im = Image.open(fpath).convert('RGBA')
        except Exception as e:
            print(f"Could not open {fpath}: {e}")
            continue

        w, h = im.size
        aspect = w / h

        # Nearly square headshots: width/height between 0.85 and 1.18
        if 0.85 < aspect < 1.18:
            # Open and resize parchment to match
            parchment = Image.open(PARCHMENT).convert('RGBA').resize((w, h), Image.LANCZOS)
            # Compose: parchment underneath, headshot on top
            combined = parchment.copy()
            combined.alpha_composite(im)
            # Save back over the original headshot
            combined.save(fpath)
            print(f"Updated headshot with parchment: {fpath}")

print("All headshots processed.")
