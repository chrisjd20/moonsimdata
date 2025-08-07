#!/usr/bin/env python3
"""
Create wide character cards by combining character_tile.png and background.png
from character directories onto a 700x1200 black canvas.
"""

import json
import os
from PIL import Image, ImageDraw, ImageFont
import sys

def get_faction_symbol_filename(faction_string):
    """Convert faction string from JSON to corresponding faction symbol filename"""
    if not faction_string:
        return None
    
    # Normalize the faction string and create mapping
    faction_map = {
        "Commonwealth": "Commonwealth.png",
        "Dominion": "Dominion.png",
        "Leshavult": "Leshavault.png",
        "Shade": "Shades.png",
        "Commonwealth,Dominion": "Dominion_Commonwealth.png",
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

def get_font(size, bold=False):
    """Get Verdana font with fallback options and improved rendering."""
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
                # Try to load with layout engine for better rendering
                font = ImageFont.truetype(font_path, size, layout_engine=ImageFont.Layout.BASIC)
                return font
        except:
            continue
    
    # Fallback to default font
    try:
        return ImageFont.load_default()
    except:
        return ImageFont.load_default()

def get_title_font_with_fallback(title_text, available_width, draw):
    """Get title font that fits within available width with fallback sizes."""
    title_font_sizes = [40, 36, 32, 28, 24]  # Added two more fallback sizes: 28 and 24
    
    for size in title_font_sizes:
        font = get_font(size, bold=True)
        bbox = draw.textbbox((0, 0), title_text, font=font)
        text_width = bbox[2] - bbox[0]
        
        if text_width <= available_width:
            return font
    
    # If even the smallest size doesn't fit, return the smallest anyway
    return get_font(24, bold=True)

def get_body_font_with_fallback(text_lines, available_height, line_spacing=20):
    """Get body font that fits within available height with fallback sizes."""
    body_font_sizes = [18, 17, 16, 15]  # Smaller jumps: only 1px steps
    
    for size in body_font_sizes:
        font = get_font(size, bold=False)
        # Calculate total height needed for all lines
        total_height = len(text_lines) * line_spacing
        
        if total_height <= available_height:
            return font, line_spacing
    
    # If even the smallest size doesn't fit, return smallest with reduced line spacing
    return get_font(15, bold=False), 18  # Reduce line spacing as well

def get_damage_type_text(damage_type):
    """Map damage type number to display text."""
    damage_type_map = {
        0: None,  # No damage type
        1: "Slicing",
        2: "Thrust", 
        3: "Slicing or Piercing",
        4: "Impact",
        5: "Impact or Slicing",
        6: "Impact or Piercing", 
        7: "Impact, Slicing or Piercing",
        8: "Magical",
        9: "Slicing or Magical"
    }
    return damage_type_map.get(damage_type, None)

def get_upgrade_for_text(upgrade_for):
    """Map upgrade_for number to move name."""
    upgrade_map = {
        0: "High Guard",
        1: "Falling Swing", 
        2: "Thrust",
        3: "Sweeping Cut",
        4: "Rising Attack",
        5: "Low Guard"
    }
    return upgrade_map.get(upgrade_for, None)

def wrap_text_to_lines(text, font, max_width, draw):
    """Wrap text to fit within max_width, breaking at word boundaries."""
    if not text or not text.strip():
        return []
    
    lines = []
    words = text.split()
    current_line = ""
    
    for word in words:
        # Test if adding this word would exceed the width
        test_line = current_line + (" " if current_line else "") + word
        bbox = draw.textbbox((0, 0), test_line, font=font)
        text_width = bbox[2] - bbox[0]
        
        if text_width <= max_width:
            current_line = test_line
        else:
            # Current line is full, save it and start new line with current word
            if current_line:
                lines.append(current_line)
                current_line = word
            else:
                # Single word is too long, add it anyway
                lines.append(word)
                current_line = ""
    
    # Add the last line if it has content
    if current_line:
        lines.append(current_line)
    
    return lines

def wrap_text_with_nulls_to_lines(text, font, max_width, draw):
    """Wrap text to fit within max_width, handling ∅ characters specially."""
    if not text or not text.strip():
        return []
    
    lines = []
    words = text.split()
    current_line = ""
    
    for word in words:
        # Test if adding this word would exceed the width
        test_line = current_line + (" " if current_line else "") + word
        # Replace ∅ with space for width calculation
        test_line_for_measurement = test_line.replace('∅', ' ')
        bbox = draw.textbbox((0, 0), test_line_for_measurement, font=font)
        text_width = bbox[2] - bbox[0]
        
        if text_width <= max_width:
            current_line = test_line
        else:
            # Current line is full, save it and start new line with current word
            if current_line:
                lines.append(current_line)
                current_line = word
            else:
                # Single word is too long, add it anyway
                lines.append(word)
                current_line = ""
    
    # Add the last line if it has content
    if current_line:
        lines.append(current_line)
    
    return lines

def draw_yellow_highlight(draw, x, y, width, height):
    """Draw a yellow circle highlight with dark yellow border."""
    # Create a circular highlight
    highlight_color = (255, 255, 0, 180)  # Yellow with transparency
    border_color = (204, 204, 0, 255)     # Dark yellow border
    
    # Calculate circle center and radius - adjusted positioning
    center_x = x + width // 2 + 8         # Shifted more to the right (was +2, now +8)
    center_y = y + height // 2 + 3        # Shifted up a bit more (was +8, now +3)
    radius = int(11 * 1.5)  # Make it 1.5x bigger again (was 9, now 13.5 -> 14)
    
    # Draw dark yellow border circle (slightly larger)
    border_radius = radius + 2
    draw.ellipse([center_x - border_radius, center_y - border_radius, 
                  center_x + border_radius, center_y + border_radius], 
                 fill=border_color)
    
    # Draw yellow circle
    draw.ellipse([center_x - radius, center_y - radius, 
                  center_x + radius, center_y + radius], 
                 fill=highlight_color)

def draw_medium_weight_text(draw, position, text, font, fill):
    """Draw text with slightly heavier weight by drawing multiple times with tiny offsets."""
    x, y = position
    # Draw the text multiple times with slight offsets to simulate medium weight
    offsets = [(0, 0), (0.5, 0), (0, 0.5), (0.5, 0.5)]
    for dx, dy in offsets:
        draw.text((x + dx, y + dy), text, fill=fill, font=font)

def draw_text_with_large_nulls(draw, position, text, font, fill):
    """Draw text with ∅ characters replaced by larger symbols at the correct positions."""
    x, y = position
    
    if '∅' not in text:
        # No null characters, draw normally
        draw_medium_weight_text(draw, position, text, font, fill)
        return
    
    # Create a larger font for the ∅ character (30% bigger)
    font_size = font.size if hasattr(font, 'size') else 18
    large_null_font = get_font(int(font_size * 1.3), bold=True)
    
    # Split text by ∅ characters and track positions
    parts = text.split('∅')
    current_x = x
    
    for i, part in enumerate(parts):
        if part:  # Draw the text part
            draw_medium_weight_text(draw, (current_x, y), part, font, fill)
            # Calculate width of this part to advance position
            bbox = draw.textbbox((0, 0), part, font=font)
            part_width = bbox[2] - bbox[0]
            current_x += part_width
        
        # Draw the ∅ character if this isn't the last part
        if i < len(parts) - 1:
            # Calculate vertical offset to center the larger ∅ with the text baseline
            null_bbox = draw.textbbox((0, 0), '∅', font=large_null_font)
            text_bbox = draw.textbbox((0, 0), 'A', font=font)  # Use 'A' as reference
            
            # Adjust Y position to align baselines
            y_offset = (text_bbox[3] - text_bbox[1] - (null_bbox[3] - null_bbox[1])) // 2
            
            draw_medium_weight_text(draw, (current_x, y + y_offset-2), '∅', large_null_font, fill)
            
            # Advance position by the width of the ∅ character
            null_width = null_bbox[2] - null_bbox[0]
            current_x += null_width

def draw_table_lines(draw, table_x, table_y, table_width, table_height, num_rows, deal_x):
    """Draw grey table lines around the moves section (adapted from add_card_text.py)."""
    line_color = (128, 128, 128, 255)  # Grey color for table lines
    line_width = 1
    
    # Draw outer border
    draw.rectangle([table_x, table_y, table_x + table_width, table_y + table_height], 
                   outline=line_color, width=line_width)
    
    # Draw horizontal lines (between rows)
    row_height = table_height / num_rows
    for i in range(1, num_rows):
        y = table_y + int(i * row_height)
        draw.line([table_x, y, table_x + table_width, y], fill=line_color, width=line_width)
    
    # Draw vertical line to separate move names from deal column
    # Position it to the left of the deal column
    deal_column_left = deal_x - 40  # Adjust this offset as needed
    draw.line([deal_column_left, table_y, deal_column_left, table_y + table_height], 
              fill=line_color, width=line_width)

def draw_signature_move_card(draw, signature_move, bg_x, bg_y, bg_width, bg_height, character_data):
    """Draw signature move card text overlay on the background area."""
    if not signature_move or not signature_move.get('name'):
        # No signature move - draw placeholder text
        font = get_font(24, bold=True)
        text = "No Signature Move"
        draw.text((bg_x + bg_width//2, bg_y + bg_height//2), text, 
                 fill=(0, 0, 0, 255), font=font, anchor="mm")
        return
    
    # Check for "No Signature" or "None" cases - these should show no table
    title = signature_move.get('name', 'Unknown Move')
    if title.lower() in ["no signature", "none"]:
        font = get_font(24, bold=True)
        text = "No Signature Move"
        draw.text((bg_x + bg_width//2, bg_y + bg_height//2), text, 
                 fill=(0, 0, 0, 255), font=font, anchor="mm")
        return
    
    # Define fonts - updated for consistency and clarity
    subtitle_font = get_font(22, bold=False)  # For 'Upgrade for' and 'Damage Type:' labels
    value_font = get_font(22, bold=True)      # For values after those labels
    body_font = get_font(18)  # Increased from 16 for extraText/endStepEffect
    move_font = get_font(18, bold=True)
    cost_font = get_font(18, bold=True)
    info_font = get_font(20, bold=False)  # Increased from 16
    info_bold_font = get_font(20, bold=True)  # Increased from 16
    damage_type_font = get_font(22, bold=True)  # Increased from 18
    end_step_header_font = get_font(20, bold=True)  # 2 points bigger than body text (18)
    body_font_medium = get_font(18, bold=False)  # For slightly heavier regular text
    
    # Colors
    black = (0, 0, 0, 255)
    dark_gray = (64, 64, 64, 255)
    
    # Card layout
    margin = 15
    current_y = bg_y + margin
    line_width = bg_width - (margin * 2)
    
    # Title - with fallback sizing to fit width
    title_font = get_title_font_with_fallback(title, line_width, draw)
    draw.text((bg_x + margin, current_y), title, fill=black, font=title_font)
    current_y += 55  # Increased spacing for larger title (was 40)
    
    # Upgrade For information (right after title) - unified font logic
    upgrade_for = signature_move.get('upgradeFor')
    upgrade_for_text = get_upgrade_for_text(upgrade_for)
    if upgrade_for_text:
        upgrade_prefix = "Upgrade for "
        draw.text((bg_x + margin, current_y), upgrade_prefix, fill=black, font=subtitle_font)
        prefix_bbox = draw.textbbox((0, 0), upgrade_prefix, font=subtitle_font)
        prefix_width = prefix_bbox[2] - prefix_bbox[0]
        draw.text((bg_x + margin + prefix_width, current_y), upgrade_for_text, fill=black, font=value_font)
        current_y += 26

    # Damage Type information (after upgrade for) - type on line below
    damage_type = signature_move.get('damageType')
    damage_type_text = get_damage_type_text(damage_type)
    if damage_type_text:
        current_y += 5
        draw.text((bg_x + margin, current_y), "Damage Type:", fill=black, font=subtitle_font)
        current_y += 26  # Move to next line for the type
        
        # Handle " or " specially - make only damage types bold, not the " or "
        if " or " in damage_type_text:
            # Split by " or " and draw each part with appropriate formatting
            parts = damage_type_text.split(" or ")
            current_x = bg_x + margin
            
            for i, part in enumerate(parts):
                # Draw the damage type in bold
                draw.text((current_x, current_y), part, fill=black, font=value_font)
                
                # Calculate width to advance position
                bbox = draw.textbbox((0, 0), part, font=value_font)
                part_width = bbox[2] - bbox[0]
                current_x += part_width
                
                # Draw " or " in regular font if not the last part
                if i < len(parts) - 1:
                    regular_font = get_font(22, bold=False)  # Same size as value_font but not bold
                    draw.text((current_x, current_y), " or ", fill=black, font=regular_font)
                    
                    # Calculate width of " or " to advance position
                    or_bbox = draw.textbbox((0, 0), " or ", font=regular_font)
                    or_width = or_bbox[2] - or_bbox[0]
                    current_x += or_width
        else:
            # No " or " in text, draw normally in bold
            draw.text((bg_x + margin, current_y), damage_type_text, fill=black, font=value_font)
        
        current_y += 32  # Increased spacing (was 28)
    
    # Set table to start at 35% from the top of the background area
    moves = [
        ("High Guard", signature_move.get('highGuardDamage')),
        ("Falling Swing", signature_move.get('fallingSwingDamage')),
        ("Thrust", signature_move.get('thrustDamage')),
        ("Sweeping Cut", signature_move.get('sweepingCutDamage')),
        ("Rising Attack", signature_move.get('risingAttackDamage')),
        ("Low Guard", signature_move.get('lowGuardDamage'))
    ]
    
    # Calculate space needed for table with larger text
    num_moves = len(moves)
    row_height = 44  # Doubled from 22 to accommodate larger text
    header_height = 44  # Adjusted to match font size and vertical centering
    table_content_height = header_height + (num_moves * row_height)
    
    # Set table to start at 25% from top of background area
    table_start_y = bg_y + int(bg_height * 0.25)
    
    # Table layout - center horizontally in the background area
    table_width = bg_width - (margin * 2)
    table_x = bg_x + margin
    
    # Column positions - center the deal column in the right portion
    move_column_width = int(table_width * 0.7)  # 70% for move names
    deal_column_width = int(table_width * 0.3)  # 30% for deal values
    
    move_column_x = table_x + 10
    deal_column_x = table_x + move_column_width + (deal_column_width // 2)
    
    # Draw table header with "Opponent Plays" and "Deal" - smaller, non-bold fonts
    header_y = table_start_y - 4 # manually adjust by 4
    
    # "Opponent Plays" replaces "Move" in the left column - smaller and not bold
    opponent_plays_font = get_font(24, bold=False)  # Smaller and not bold
    deal_header_font = get_font(24, bold=False)  # Smaller and not bold

    manual_deal_col_x_offset = 8
    deal_col_y_manual_adjust = -2
    
    # Center "Deal" in its column
    deal_bbox = draw.textbbox((0, 0), "Deal", font=deal_header_font)
    deal_width = deal_bbox[2] - deal_bbox[0]
    deal_text_height = deal_bbox[3] - deal_bbox[1]
    deal_y_centered = header_y + (header_height - deal_text_height) // 2
    draw.text((move_column_x, deal_y_centered), "Opponent Plays", fill=black, font=opponent_plays_font)
    deal_x_centered = deal_column_x - (deal_width // 2)
    draw.text((deal_x_centered + manual_deal_col_x_offset, deal_y_centered), "Deal", fill=black, font=deal_header_font)
    current_y = header_y + header_height

    # Draw moves in table with bold fonts, center Deal values horizontally and vertically
    move_name_font = get_font(26, bold=True)
    damage_value_font = get_font(32, bold=True)
    
    # Get yellow circle moves from character data
    yellow_circle_moves = character_data.get('yellowCircleMoves', [])
    
    for move_name, damage in moves:
        damage_text = str(damage) if damage is not None else "∅"
        
        # Check if this move should have a yellow circle highlight
        should_highlight = move_name in yellow_circle_moves
        
        # Vertically center text in row
        move_bbox = draw.textbbox((0, 0), move_name, font=move_name_font)
        move_text_height = move_bbox[3] - move_bbox[1]
        move_y_centered = current_y + (row_height - move_text_height) // 2
        draw.text((move_column_x, move_y_centered), move_name, fill=black, font=move_name_font)
        
        damage_bbox = draw.textbbox((0, 0), damage_text, font=damage_value_font)
        damage_width = damage_bbox[2] - damage_bbox[0]
        damage_text_height = damage_bbox[3] - damage_bbox[1]
        damage_y_centered = current_y + (row_height - damage_text_height) // 2
        damage_x_centered = deal_column_x - (damage_width // 2)
        
        # Draw yellow highlight behind the damage value if needed
        if should_highlight:
            yoff = 1
            xoff = -5.5
            if damage_text == "∅":
                xoff = -3
                yoff = 1
            highlight_x = damage_x_centered + manual_deal_col_x_offset - (damage_width // 2) + xoff
            highlight_y = damage_y_centered + deal_col_y_manual_adjust + yoff
            highlight_width = damage_width + 16
            highlight_height = damage_text_height + 4
            draw_yellow_highlight(draw, highlight_x, highlight_y, highlight_width, highlight_height)
        
        draw.text((damage_x_centered + manual_deal_col_x_offset, damage_y_centered+deal_col_y_manual_adjust), damage_text, fill=black, font=damage_value_font)
        current_y += row_height
    
    # Draw table lines
    table_height = header_height + (num_moves * row_height)
    draw_table_lines(draw, table_x, table_start_y, table_width, table_height, 
                     num_moves + 1, deal_column_x)  # +1 for header row
    
    # Position for text after table
    current_y = table_start_y + table_height + 8
    
    # Calculate available height for text (accounting for bottom padding)
    available_height = bg_y + bg_height - current_y - 10  # 10px bottom padding
    
    # Extra text (if any) - placed after damage table
    extra_text = signature_move.get('extraText', '')
    end_effect = signature_move.get('endStepEffect', '')
    
    # Add periods if missing and process ∅ characters
    if extra_text and extra_text.strip():
        extra_text = extra_text.strip()
        if not extra_text.endswith('.'):
            extra_text += '.'
    
    if end_effect and end_effect.strip():
        end_effect = end_effect.strip()
        if not end_effect.endswith('.'):
            end_effect += '.'
    
    # First, get rough line counts to estimate needed space
    temp_font = get_font(18, bold=False)  # Use default size for initial estimation
    rough_lines = []
    
    if extra_text and extra_text.strip():
        # Replace ∅ with spaces for line wrapping calculation
        extra_text_for_wrapping = extra_text.replace('∅', ' ')
        rough_extra_lines = wrap_text_with_nulls_to_lines(extra_text, temp_font, line_width, draw)
        rough_lines.extend(rough_extra_lines)

    if end_effect and end_effect.strip():
        rough_lines.append("End Step Effect:")  # Header
        # Replace ∅ with spaces for line wrapping calculation
        end_effect_for_wrapping = end_effect.replace('∅', ' ')
        rough_end_lines = wrap_text_with_nulls_to_lines(end_effect, temp_font, line_width, draw)
        rough_lines.extend(rough_end_lines)
    
    # Get appropriate font and line spacing based on available height
    if rough_lines:
        body_font_final, line_spacing = get_body_font_with_fallback(rough_lines, available_height)
        
        # Now re-wrap text with the final font for accurate line breaks
        if extra_text and extra_text.strip():
            final_extra_lines = wrap_text_with_nulls_to_lines(extra_text, body_font_final, line_width, draw)
            for line in final_extra_lines:
                draw_text_with_large_nulls(draw, (bg_x + margin, current_y), line, body_font_final, dark_gray)
                current_y += line_spacing
            current_y += 6  # Reduced extra spacing after extra text
        
        if end_effect and end_effect.strip():
            draw.text((bg_x + margin, current_y), "End Step Effect:", fill=black, font=end_step_header_font)
            current_y += 24  # Increased from 22 to 24 for more spacing
            
            final_end_lines = wrap_text_with_nulls_to_lines(end_effect, body_font_final, line_width, draw)
            for line in final_end_lines:
                draw_text_with_large_nulls(draw, (bg_x + margin, current_y), line, body_font_final, dark_gray)
                current_y += line_spacing

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

def create_wide_character_card(character_name, characters_images_dir, output_dir, faction_symbols_dir, faction_string, character_data):
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
            
            # Add signature move text overlay to background area AFTER basic background is placed
            signature_move = character_data.get('SignatureMove', {})
            
            # Create a semi-transparent overlay for better text readability (much less opacity)
            overlay = Image.new('RGBA', (background_resized.width, background_resized.height), (255, 255, 255, 60))
            overlay_draw = ImageDraw.Draw(overlay)
            
            # Draw signature move card on the overlay
            draw_signature_move_card(overlay_draw, signature_move, 0, 0, background_resized.width, background_resized.height, character_data)
            
            # Composite the overlay onto the background area of the canvas
            background_with_text = Image.alpha_composite(
                background_resized.convert('RGBA'),
                overlay
            )
            
            # Paste the background with text overlay onto the canvas (this replaces the plain background)
            canvas.paste(background_with_text, (background_x, background_y), background_with_text)
            
            # Redraw the black divider on top of everything
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
        
        # Add signature move text overlay to background area if no background was placed
        if available_background_width <= 0:
            signature_move = character_data.get('SignatureMove', {})
            # Handle case where there's no background area - could draw on a small area
            # For now, just skip if no background area available
        
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
        
        if create_wide_character_card(character_name, characters_images_dir, output_dir, faction_symbols_dir, faction_string, entry):
            successful_cards += 1
    
    print(f"\nCompleted! Successfully created {successful_cards} out of {total_characters} character cards.")
    print(f"Output directory: {output_dir}")

if __name__ == "__main__":
    main()
