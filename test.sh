#!/bin/bash

# --- CONFIGURATION ---
JSON_FILE="moonstone_data.json"
NEW_SIZE="200x200"

# --- SAFETY CHECKS ---
# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "🚨 Error: jq is not installed. Please install it to proceed."
    exit 1
fi
# Check if mogrify (part of ImageMagick) is installed
if ! command -v mogrify &> /dev/null; then
    echo "🚨 Error: ImageMagick is not installed. Please install it to proceed."
    exit 1
fi
# Check if the JSON file exists
if [ ! -f "$JSON_FILE" ]; then
    echo "🚨 Error: JSON file '$JSON_FILE' not found!"
    exit 1
fi

echo "✅ Starting image resizing process. This will overwrite files."

# --- MAIN LOGIC ---
# 1. Read the JSON file, and for each entry...
# 2. Get the value of "headFileName", skipping any that are null or empty.
# 3. Pipe each filename into a while loop.
jq -r '.[] | .headFileName | select(. != null and . != "")' "$JSON_FILE" | while IFS= read -r filename; do
    
    # Find the full path of the file. We expect only one result.
    filepath=$(find ./ -type f -name "$filename")

    if [ -n "$filepath" ]; then
        echo "Resizing: $filepath"
        # Use mogrify to resize and overwrite the image.
        # The '!' flag forces the exact dimensions, ignoring the original aspect ratio.
        mogrify -resize "${NEW_SIZE}!" "$filepath"
    else
        echo "⚠️ Warning: Could not find file for '$filename'"
    fi
done

echo "✅ Process complete."
