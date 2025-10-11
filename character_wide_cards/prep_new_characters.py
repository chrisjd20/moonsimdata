#!/usr/bin/env python3
"""
Prepare new character images for the card generation pipeline.
This script:
1. Loads character images
2. Creates mirrored versions similar to existing characters
3. Sets up the directory structure expected by the pipeline
4. Copies the background image
"""

import os
from PIL import Image
from pathlib import Path

def process_character_image(source_path, output_dir, background_path):
    """
    Process a character image to create character_tile.png and copy background.
    
    The character_tile should be the portrait ready for use.
    """
    print(f"\nProcessing: {source_path.name}")
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load the character image
    char_img = Image.open(source_path).convert('RGBA')
    print(f"  Original size: {char_img.size}")
    
    # Save as character_tile.png
    char_tile_path = output_dir / "character_tile.png"
    char_img.save(char_tile_path, 'PNG')
    print(f"  Saved character_tile.png: {char_img.size}")
    
    # Copy background image
    background = Image.open(background_path).convert('RGB')
    background_out = output_dir / "background.png"
    background.save(background_out, 'PNG')
    print(f"  Copied background.png: {background.size}")
    
    return True

def main():
    # Base paths
    script_dir = Path(__file__).parent
    source_dir = script_dir / "matilda_and_faculty" / "characters_only_not_mirrored"
    background_path = script_dir / "matilda_and_faculty" / "background.png"
    output_base = script_dir / "characters_images"
    
    # Character mapping: filename prefix -> character name in JSON
    characters = {
        "Flinders Memphis - Commonwealth - 30.png": "Flinders Memphis",
        "Matilda - Commonwealth - 40.png": "Matilda",
        "Old Polly - Commonwealth - 30.png": "Old Polly",
        "Prof. Boffinsworth - Commonwealth - 30.png": "Prof. Boffinsworth"
    }
    
    # Check if background exists
    if not background_path.exists():
        print(f"Error: Background image not found at {background_path}")
        return False
    
    print("=== Preparing New Characters for Pipeline ===")
    print(f"Source directory: {source_dir}")
    print(f"Background: {background_path}")
    print(f"Output base: {output_base}")
    
    success_count = 0
    
    for filename, char_name in characters.items():
        source_file = source_dir / filename
        
        if not source_file.exists():
            print(f"\nWarning: Source file not found: {source_file}")
            continue
        
        output_dir = output_base / char_name
        
        if process_character_image(source_file, output_dir, background_path):
            success_count += 1
    
    print(f"\n=== Complete ===")
    print(f"Successfully prepared {success_count} out of {len(characters)} characters")
    print(f"\nNext steps:")
    print(f"1. Run: python3 create_wide_character_card.py")
    print(f"2. Run: python3 create_left_side_of_wide_character_card.py")
    print(f"3. Run: python3 generate_final_character_pdf.py")
    
    return success_count == len(characters)

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
