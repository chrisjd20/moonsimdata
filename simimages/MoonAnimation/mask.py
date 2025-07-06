from PIL import Image
import numpy as np
import os

# Load the mask's alpha channel
mask = Image.open('mask.png').convert('RGBA')
mask_alpha = np.array(mask.split()[-1], dtype=np.float32) / 255.0  # 0 (transparent) to 1 (opaque)

for filename in os.listdir('.'):
    if filename.startswith("masked_frame_") and filename.endswith(".png"):
        img = Image.open(filename).convert('RGBA')
        img_np = np.array(img)
        img_alpha = img_np[:, :, 3].astype(np.float32)

        # Fade/cut: Lower output alpha where mask alpha is HIGH
        # Output alpha = img_alpha * (1 - mask_alpha)
        out_alpha = (img_alpha * (1 - mask_alpha)).astype(np.uint8)
        img_np[:, :, 3] = out_alpha

        Image.fromarray(img_np).save('masked2_' + filename)
