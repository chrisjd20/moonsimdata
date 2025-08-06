#!/usr/bin/env python3
"""
Create wide character cards by combining character_tile.png and background.png
from character directories onto a 700x1200 black canvas.
"""

import json
import os
from PIL import Image, ImageDraw
import sys

def get_faction_symbol_filename(faction_string):
    """
    Map faction string from JSON to corresponding faction symbol filename
    """
    if not faction_string:
        return None
    
    # Normalize the faction string and create mapping
    faction_map = {
        "Commonwealth": "Commonwealth.png",
        "Dominion": "Dominion.png",
        "Leshavult": "Leshavault.png",
        "Shade": "Shades.png",
        "Commonwealth,Dominion": "Commonwealth_Dominion.png",
        "Dominion,Commonwealth": "Dominion_Commonwealth.png",
        "Commonwealth,Leshavult": "Commonwealth_Leshavault.png",
        "Leshavult,Commonwealth": "Commonwealth_Leshavault.png",
        "Dominion,Leshavult": "Dominion_Leshavault.png",
        "Leshavult,Dominion": "Dominion_Leshavault.png",
        "Dominion,Shade": "Shades_Dominion.png",
        "Shade,Dominion": "Shades_Dominion.png",
        "Leshavult,Shade": "Shades_Leshavault.png",
        "Shade,Leshavult": "Shades_Leshavault.png",
        "Shade,Commonwealth": "Commonwealth_Shades.png",
        "Commonwealth,Shade": "Commonwealth_Shades.png"
    }
    
    return faction_map.get(faction_string, None)

def resize_image_keep_aspect(image, max_width, max_height):
    """
    Resize an image while keeping aspect ratio to fit within max_width x max_height
    """
    original_width, original_height = image.size
    
    # Calculate scaling factor to fit within the constraints
    scale_width = max_width / original_width
    scale_height = max_height / original_height
    scale = min(scale_width, scale_height)
    
    # Calculate new dimensions
    new_width = int(original_width * scale)
    new_height = int(original_height * scale)
    
    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

def create_wide_character_card(character_name, characters_images_dir, output_dir, faction_symbols_dir, faction_string):
    """
    Create a wide character card for a given character
    """
    # Canvas dimensions
    canvas_width = 1200
    canvas_height = 700
    padding = 10
    
    # Create black canvas
    canvas = Image.new('RGB', (canvas_width, canvas_height), 'black')
    
    # Character directory path
    char_dir = os.path.join(characters_images_dir, character_name)
    
    if not os.path.exists(char_dir):
        print(f"Warning: Character directory not found: {char_dir}")
        return False
    
    # Paths to the images
    char_tile_path = os.path.join(char_dir, 'character_tile.png')
    background_path = os.path.join(char_dir, 'background.png')
    
    if not os.path.exists(char_tile_path):
        print(f"Warning: character_tile.png not found for {character_name}")
        return False
    
    if not os.path.exists(background_path):
        print(f"Warning: background.png not found for {character_name}")
        return False
    
    try:
        # Load images
        char_tile = Image.open(char_tile_path).convert('RGB')
        background = Image.open(background_path).convert('RGB')
        
        # Calculate available space for character tile
        char_tile_max_height = canvas_height - (padding * 2)  # Full height minus top/bottom padding
        # Allow character tile to use as much width as needed to fill the height (we'll adjust later based on actual size)
        char_tile_max_width = canvas_width  # Start with full width, we'll manage the layout after
        
        # Resize character tile to fill the available height while maintaining aspect ratio
        char_tile_resized = resize_image_keep_aspect(char_tile, char_tile_max_width, char_tile_max_height)
        
        # Position original character tile in top-left with padding
        char_tile_x = padding
        char_tile_y = padding
        
        # Paste original character tile onto canvas
        canvas.paste(char_tile_resized, (char_tile_x, char_tile_y))
        
        # Create flipped copy of character tile
        char_tile_flipped = char_tile_resized.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        
        # Crop flipped tile to keep only the left 50%
        flipped_crop_width = char_tile_flipped.width // 2
        char_tile_flipped_cropped = char_tile_flipped.crop((0, 0, flipped_crop_width, char_tile_flipped.height))
        
        # Position flipped tile directly to the right of original
        flipped_x = char_tile_x + char_tile_resized.width
        flipped_y = char_tile_y
        
        # Paste flipped tile onto canvas
        canvas.paste(char_tile_flipped_cropped, (flipped_x, flipped_y))
        
        # Calculate position for background image (to the right of flipped tile)
        background_start_x = flipped_x + char_tile_flipped_cropped.width
        available_background_width = canvas_width - background_start_x - padding
        background_max_height = canvas_height - (padding * 2)
        
        # Only proceed with background if there's available space
        if available_background_width > 0:
            # Calculate scale to fill the full available height while maintaining aspect ratio
            scale_height = background_max_height / background.height
            scale_width = available_background_width / background.width
            
            # Use the height scale to ensure we fill the full height
            scale = scale_height
            
            # Calculate new dimensions
            new_width = int(background.width * scale)
            new_height = int(background.height * scale)
            
            # Resize background to fill height
            background_resized = background.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # If background is wider than available space, crop it from the right
            if background_resized.width > available_background_width:
                background_resized = background_resized.crop((0, 0, available_background_width, background_resized.height))
            
            # Position background image
            background_x = background_start_x
            background_y = padding
            
            # Paste background onto canvas
            canvas.paste(background_resized, (background_x, background_y))
            
            # Add 8-pixel black divider where character images meet background
            divider_width = 8
            divider_x = background_start_x
            divider_y = padding
            divider_height = background_max_height
            
            # Create a black rectangle for the divider
            draw = ImageDraw.Draw(canvas)
            draw.rectangle([divider_x, divider_y, divider_x + divider_width, divider_y + divider_height], fill='black')
        
        # Add faction symbol in top-right of character area
        if faction_string:
            faction_filename = get_faction_symbol_filename(faction_string)
            if faction_filename:
                faction_path = os.path.join(faction_symbols_dir, faction_filename)
                if os.path.exists(faction_path):
                    try:
                        faction_symbol = Image.open(faction_path).convert('RGBA')
                        
                        # Scale faction symbol to 140px height while keeping aspect ratio
                        faction_target_height = 140
                        faction_aspect_ratio = faction_symbol.width / faction_symbol.height
                        faction_new_width = int(faction_target_height * faction_aspect_ratio)
                        faction_resized = faction_symbol.resize((faction_new_width, faction_target_height), Image.Resampling.LANCZOS)
                        
                        # Position in top-right of character area (touching the divider and top border)
                        faction_x = background_start_x - faction_new_width  # Touch the divider line
                        faction_y = padding  # Touch the top border
                        
                        # Make sure faction symbol fits within character area
                        if faction_x >= padding:
                            # Paste faction symbol (handling transparency if it's RGBA)
                            if faction_resized.mode == 'RGBA':
                                canvas.paste(faction_resized, (faction_x, faction_y), faction_resized)
                            else:
                                canvas.paste(faction_resized.convert('RGB'), (faction_x, faction_y))
                    except Exception as e:
                        print(f"Warning: Could not load faction symbol {faction_filename} for {character_name}: {str(e)}")
                else:
                    print(f"Warning: Faction symbol file not found: {faction_path}")
            else:
                print(f"Warning: No faction symbol mapping found for faction '{faction_string}' for {character_name}")
        
        # Save the final image
        os.makedirs(output_dir, exist_ok=True)
        safe_filename = character_name.replace('/', '_').replace('\\', '_')  # Handle special characters
        output_path = os.path.join(output_dir, f"{safe_filename}_wide_card.png")
        canvas.save(output_path, 'PNG')
        
        print(f"Created wide card for {character_name}: {output_path}")
        return True
        
    except Exception as e:
        print(f"Error creating card for {character_name}: {str(e)}")
        return False

def main():
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Paths
    json_path = os.path.join(script_dir, 'moonstone_data.json')
    characters_images_dir = os.path.join(script_dir, 'characters_images')
    faction_symbols_dir = os.path.join(script_dir, 'symbols_factions')
    output_dir = os.path.join(script_dir, 'generated_wide_cards')
    
    # Check if moonstone_data.json exists
    if not os.path.exists(json_path):
        print(f"Error: moonstone_data.json not found at {json_path}")
        sys.exit(1)
    
    # Check if characters_images directory exists
    if not os.path.exists(characters_images_dir):
        print(f"Error: characters_images directory not found at {characters_images_dir}")
        sys.exit(1)
    
    # Check if faction symbols directory exists
    if not os.path.exists(faction_symbols_dir):
        print(f"Warning: symbols_factions directory not found at {faction_symbols_dir}")
        print("Faction symbols will be skipped.")
    
    # Load the JSON data
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            moonstone_data = json.load(f)
    except Exception as e:
        print(f"Error reading moonstone_data.json: {str(e)}")
        sys.exit(1)
    
    # Process each character
    successful_cards = 0
    total_characters = 0
    
    for entry in moonstone_data:
        # Skip empty entries
        if not entry or 'name' not in entry:
            continue
            
        character_name = entry['name']
        faction_string = entry.get('faction', '')
        total_characters += 1
        
        print(f"Processing {character_name}...")
        
        if create_wide_character_card(character_name, characters_images_dir, output_dir, faction_symbols_dir, faction_string):
            successful_cards += 1
    
    print(f"\nCompleted! Successfully created {successful_cards} out of {total_characters} character cards.")
    print(f"Output directory: {output_dir}")

if __name__ == "__main__":
    main()
