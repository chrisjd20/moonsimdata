import cv2
import numpy as np
import os

def remove_bg_by_floodfill(image_path, out_path):
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img.shape[2] == 3:  # If no alpha, add alpha channel
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    bgr = img[:, :, :3].copy()  # Just the color part

    h, w = bgr.shape[:2]
    mask = np.zeros((h + 2, w + 2), np.uint8)

    # Fill from all four corners on the BGR image
    for seed in [(0,0), (0,h-1), (w-1,0), (w-1,h-1)]:
        cv2.floodFill(bgr, mask, seedPoint=seed, newVal=(0,0,0), loDiff=(10,10,10), upDiff=(10,10,10), flags=cv2.FLOODFILL_FIXED_RANGE)

    # Now, wherever mask == 1, set alpha to 0 (transparent) in the original image
    floodfilled_mask = mask[1:-1, 1:-1]  # Remove the padding
    img[floodfilled_mask == 1, 3] = 0

    cv2.imwrite(out_path, img)

# Batch process
for filename in os.listdir('.'):
    if filename.startswith("frame_") and filename.endswith(".png"):
        remove_bg_by_floodfill(filename, "masked_" + filename)
