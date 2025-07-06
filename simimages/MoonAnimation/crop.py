from PIL import Image
import os

CROP_LEFT = 275
CROP_RIGHT = 100

for filename in os.listdir('.'):
    if filename.startswith("final_") and filename.endswith(".png"):
        img = Image.open(filename)
        width, height = img.size
        # Crop box: (left, upper, right, lower)
        crop_box = (CROP_LEFT, 0, width - CROP_RIGHT, height)
        cropped = img.crop(crop_box)
        cropped.save(filename)  # Overwrite, or use a new prefix if you want

print("All images cropped!")
