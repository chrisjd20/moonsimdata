from PIL import Image
import numpy as np
import os
from scipy.ndimage import label

# Parameters
DARK_THRESHOLD = 45  # Below this, a pixel is considered "dark"
ROI_N = (730, 340, 900, 390)   # Nose area: (x1, y1, x2, y2)
ROI_C = (765, 480, 900, 540)   # Chin area: (x1, y1, x2, y2)
CHIN_X_LIMIT = 752

def remove_dark_blobs(img_np, roi, chin_x_limit=None):
    x1, y1, x2, y2 = roi
    region = img_np[y1:y2, x1:x2, :]

    # Compute darkness mask
    darkness = region[:, :, :3].mean(axis=2) < DARK_THRESHOLD
    if chin_x_limit:
        x_indices = np.arange(x1, x2)
        mask_x = x_indices > chin_x_limit
        darkness = darkness & mask_x[np.newaxis, :]
    # Label contiguous dark regions
    structure = np.ones((3,3), dtype=np.int_)
    labeled, ncomponents = label(darkness, structure=structure)
    # Remove blobs: make alpha 0 wherever dark and not already transparent
    region[:, :, 3][darkness] = 0
    img_np[y1:y2, x1:x2, :] = region
    return img_np

for filename in os.listdir('.'):
    if filename.startswith("masked2_masked_frame_") and filename.endswith(".png"):
        # Extract frame number
        try:
            frame_num = int(filename.split('_')[-1].split('.')[0])
        except:
            frame_num = 0
        img = Image.open(filename).convert('RGBA')
        img_np = np.array(img)

        # Only apply to frames > 125
        if frame_num > 125:
            img_np = remove_dark_blobs(img_np, ROI_N)
            img_np = remove_dark_blobs(img_np, ROI_C, chin_x_limit=CHIN_X_LIMIT)

        Image.fromarray(img_np).save('final_' + filename)

print("Done!")
