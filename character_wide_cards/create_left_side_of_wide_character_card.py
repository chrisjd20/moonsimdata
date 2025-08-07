#!/usr/bin/env python3
"""
Create left side text overlay for wide character cards by adding character stats,
abilities, and other text elements to the left side of existing wide cards.
"""

import json
import os
from PIL import Image, ImageDraw, ImageFont
import sys

def get_font(size, bold=False):
    """Get font with fallback options."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/verdana.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Verdana.ttf",
        "C:/Windows/Fonts/verdana.ttf"
    ]
    
    for font_path in font_paths:
        try:
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, size, layout_engine=ImageFont.Layout.BASIC)
                return font
        except:
            continue
    
    # Fallback to default font
    try:
        return ImageFont.load_default()
    except:
        return ImageFont.load_default()

def get_character_name_font(character_name, max_width, draw):
    """Get character name font that fits within max_width, starting large and scaling down."""
    # Start with a large font size and decrease by 1px until it fits
    for size in range(48, 12, -1):  # Start at 48px, go down to 12px minimum
        font = get_font(size, bold=True)
        bbox = draw.textbbox((0, 0), character_name, font=font)
        text_width = bbox[2] - bbox[0]
        
        if text_width <= max_width:
            return font
    
    # If even 12px doesn't fit, return it anyway
    return get_font(12, bold=True)

def create_left_side_character_card(input_image_path, character_data, output_path):
    """
    Add left side text overlay to an existing wide character card image.
    """
    try:
        # Open the existing wide card image
        img = Image.open(input_image_path).convert("RGBA")
        
        # Create a transparent overlay for text
        text_overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(text_overlay)
        
        # Define the working area boundaries
        left_boundary = 10  # Actual target area starts at 10
        top_boundary = 10
        right_boundary = 745
        bottom_boundary = 690
        
        # Calculate working dimensions
        work_width = right_boundary - left_boundary  # 735px
        work_height = bottom_boundary - top_boundary  # 680px
        
        # Text margins within the working area (6px padding from target area boundaries)
        text_margin = 6  # 6px padding from the target area boundaries
        text_left = left_boundary + text_margin  # 16px from absolute left
        text_right = right_boundary - 15  # Keep right margin for safety
        text_width = text_right - text_left  # Available text width
        
        # Colors
        black = (0, 0, 0, 255)
        dark_gray = (64, 64, 64, 255)
        
        # Character name at the top
        character_name = character_data.get('name', 'Unknown Character')
        
        # Check if name has a comma (main name + subtitle)
        if ',' in character_name:
            name_parts = character_name.split(',', 1)
            main_name = name_parts[0].strip()
            subtitle = name_parts[1].strip()
            
            # Get font that fits for the main name within available width
            # We need to account for the subtitle width too, so use a bit less space for main name
            name_font = get_character_name_font(main_name + ", ", 400, draw)  # Use less space to account for subtitle
            
            # Create subtitle font (80% of main font size, but still bold)
            main_font_size = getattr(name_font, 'size', 24)
            subtitle_font_size = max(8, int(main_font_size * 0.80))  # 80% of main font, minimum 8px
            subtitle_font = get_font(subtitle_font_size, bold=True)
            
            # Position main name at top left of working area with 6px padding
            name_x = text_left  # 16px from absolute left
            name_y = top_boundary + text_margin  # 16px from absolute top
            
            # Get proper font metrics for baseline alignment
            # Use a test string to get accurate baseline measurements
            test_text = "Ag"  # Use characters with ascenders and descenders for accurate metrics
            main_metrics = draw.textbbox((0, 0), test_text, font=name_font)
            subtitle_metrics = draw.textbbox((0, 0), test_text, font=subtitle_font)
            
            # Calculate baseline positions - the difference in ascent between fonts
            main_ascent = abs(main_metrics[1])  # Distance from top to baseline
            subtitle_ascent = abs(subtitle_metrics[1])  # Distance from top to baseline
            baseline_offset = main_ascent - subtitle_ascent  # How much to offset subtitle
            
            # Draw main name
            draw.text((name_x, name_y), main_name, fill=black, font=name_font)
            
            # Calculate position for comma and subtitle
            main_bbox = draw.textbbox((0, 0), main_name, font=name_font)
            main_width = main_bbox[2] - main_bbox[0]
            
            # Draw comma with main font
            comma_x = name_x + main_width
            draw.text((comma_x, name_y), ", ", fill=black, font=name_font)
            
            # Calculate comma width
            comma_bbox = draw.textbbox((0, 0), ", ", font=name_font)
            comma_width = comma_bbox[2] - comma_bbox[0]
            
            # Draw subtitle with smaller font, properly aligned to baseline
            subtitle_x = comma_x + comma_width
            subtitle_y = name_y + baseline_offset
            
            draw.text((subtitle_x, subtitle_y), subtitle, fill=black, font=subtitle_font)

            # Use fixed positioning for keywords - name area ends at max 60px from top
            current_y = top_boundary + 60 # 60px max name height

        else:
            # Single name, use existing logic
            # Get font that fits within 600px width constraint
            name_font = get_character_name_font(character_name, 600, draw)
            
            # Position character name at top left of working area with 6px padding
            name_x = text_left  # 16px from absolute left
            name_y = top_boundary + text_margin  # 16px from absolute top
            
            draw.text((name_x, name_y), character_name, fill=black, font=name_font)

            # Use fixed positioning for keywords - name area ends at max 60px from top
            current_y = top_boundary + 60 # 60px max name height

        # Keywords/subtitle below the character name
        keywords = character_data.get('keywords', '')
        if keywords and keywords.strip():
            # Fix comma spacing - add space after commas if not present
            formatted_keywords = keywords.replace(',', ', ').replace(', ,', ',').replace('  ', ' ').strip()
            # Remove any double spaces and trailing commas that might have been created
            while ', ,' in formatted_keywords:
                formatted_keywords = formatted_keywords.replace(', ,', ',')
            formatted_keywords = formatted_keywords.rstrip(', ')
            
            # Use a consistent font size for keywords based on default name font size (48px)
            # 45% of 48px = ~22px, but let's use a fixed readable size
            keywords_font_size = 20  # Fixed size for consistency across all cards
            keywords_font = get_font(keywords_font_size, bold=False)
            
            # Use exact same X position as character name for perfect alignment
            keywords_x = name_x  # Use same X as character name
            keywords_y = current_y
            
            draw.text((keywords_x, keywords_y), formatted_keywords, fill=black, font=keywords_font)
            
            # Update current_y for next elements
            keywords_bbox = draw.textbbox((0, 0), formatted_keywords, font=keywords_font)
            keywords_height = keywords_bbox[3] - keywords_bbox[1]
            current_y = keywords_y + keywords_height + 15  # Increased spacing after keywords
        
        # TODO: Add other elements here:
        # - Stats table
        # - Abilities
        # - Energy dots
        # - Base size
        
        # Composite the text overlay onto the original image
        final_img = Image.alpha_composite(img, text_overlay)
        
        # Convert back to RGB for saving as PNG
        final_img = final_img.convert("RGB")
        
        # Save the result
        final_img.save(output_path, "PNG")
        
        print(f"Created left side card: {output_path}")
        return True
        
    except Exception as e:
        print(f"Error creating left side card: {str(e)}")
        return False

def main():
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Paths
    json_path = os.path.join(script_dir, 'moonstone_data.json')
    input_cards_dir = os.path.join(script_dir, 'generated_wide_cards')
    output_dir = os.path.join(script_dir, 'generated_wide_cards_with_left_text')
    
    # Check if moonstone_data.json exists
    if not os.path.exists(json_path):
        print(f"Error: moonstone_data.json not found at {json_path}")
        sys.exit(1)
    
    # Check if input cards directory exists
    if not os.path.exists(input_cards_dir):
        print(f"Error: generated_wide_cards directory not found at {input_cards_dir}")
        print("Please run create_wide_character_card.py first to generate the base cards.")
        sys.exit(1)
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
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
        total_characters += 1
        
        print(f"Processing {character_name}...")
        
        # Look for existing wide card image
        safe_filename = character_name.replace('/', '_').replace('\\', '_')
        input_image_path = os.path.join(input_cards_dir, f"{safe_filename}_wide_card.png")
        
        if not os.path.exists(input_image_path):
            print(f"Warning: Base wide card not found for {character_name}: {input_image_path}")
            continue
        
        # Create output path
        output_path = os.path.join(output_dir, f"{safe_filename}_wide_card_with_text.png")
        
        if create_left_side_character_card(input_image_path, entry, output_path):
            successful_cards += 1
    
    print(f"\nCompleted! Successfully created {successful_cards} out of {total_characters} character cards with left side text.")
    print(f"Output directory: {output_dir}")

if __name__ == "__main__":
    main()
