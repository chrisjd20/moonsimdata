import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import json

# Card definitions with text, positions, and styling
# Each card has moves with highlights positioned correctly:
# - High Guard: highlight on Deal column for Falling Swing
# - Falling Swing: highlight on Suffer column for High Guard  
# - etc.
CARD_DEFINITIONS = {
    "High Guard": {
        "title": "High Guard",
        "damage_type": None,
        "damage_choice": None,
        "opponent_plays": "Opponent Plays",
        "oval_suffix": "Deal / Suffer",
        "moves": [
            {"name": "High Guard", "cost": "∅", "suffer": "∅"},
            {"name": "Falling Swing", "cost": "∅", "suffer": "∅", "annotation": "(I or S)", "highlight": "deal"},
            {"name": "Thrust", "cost": "∅", "suffer": "0", "annotation": "(P)"},
            {"name": "Sweeping Cut", "cost": "∅", "suffer": "∅", "annotation": "(S)"},
            {"name": "Rising Attack", "cost": "∅", "suffer": "2", "annotation": "(I, S or P)"},
            {"name": "Low Guard", "cost": "∅", "suffer": "∅"}
        ]
    },
    "Falling Swing": {
        "title": "Falling Swing",
        "damage_type": "Damage Type:",
        "damage_choice": "Choose Impact or Slicing.",
        "opponent_plays": "Opponent Plays",
        "oval_suffix": "Deal / Suffer",
        "moves": [
            {"name": "High Guard", "cost": "∅", "suffer": "∅", "highlight": "suffer"},
            {"name": "Falling Swing", "cost": "0", "suffer": "0", "annotation": "(I or S)"},
            {"name": "Thrust", "cost": "0", "suffer": "2", "annotation": "(P)"},
            {"name": "Sweeping Cut", "cost": "3", "suffer": "2", "annotation": "(S)"},
            {"name": "Rising Attack", "cost": "3", "suffer": "1", "annotation": "(I, S or P)"},
            {"name": "Low Guard", "cost": "2", "suffer": "∅"}
        ]
    },
    "Thrust": {
        "title": "Thrust",
        "damage_type": "Damage Type:",
        "damage_choice": "Piercing",
        "opponent_plays": "Opponent Plays",
        "oval_suffix": "Deal / Suffer",
        "moves": [
            {"name": "High Guard", "cost": "0", "suffer": "∅"},
            {"name": "Falling Swing", "cost": "2", "suffer": "0", "annotation": "(I or S)"},
            {"name": "Thrust", "cost": "3", "suffer": "3", "annotation": "(P)"},
            {"name": "Sweeping Cut", "cost": "∅", "suffer": "0", "annotation": "(S)", "highlight": "suffer"},
            {"name": "Rising Attack", "cost": "2", "suffer": "1", "annotation": "(I, S or P)"},
            {"name": "Low Guard", "cost": "1", "suffer": "∅"}
        ]
    },
    "Sweeping Cut": {
        "title": "Sweeping Cut",
        "damage_type": "Damage Type:",
        "damage_choice": "Slicing",
        "opponent_plays": "Opponent Plays",
        "oval_suffix": "Deal / Suffer",
        "moves": [
            {"name": "High Guard", "cost": "∅", "suffer": "∅"},
            {"name": "Falling Swing", "cost": "2", "suffer": "3", "annotation": "(I or S)"},
            {"name": "Thrust", "cost": "0", "suffer": "∅", "annotation": "(P)", "highlight": "deal"},
            {"name": "Sweeping Cut", "cost": "0", "suffer": "0", "annotation": "(S)"},
            {"name": "Rising Attack", "cost": "2", "suffer": "2", "annotation": "(I, S or P)"},
            {"name": "Low Guard", "cost": "∅", "suffer": "∅"}
        ]
    },
    "Rising Attack": {
        "title": "Rising Attack",
        "damage_type": "Damage Type:",
        "damage_choice": "Choose Impact, Slicing or Piercing",
        "opponent_plays": "Opponent Plays",
        "oval_suffix": "Deal / Suffer",
        "moves": [
            {"name": "High Guard", "cost": "2", "suffer": "∅"},
            {"name": "Falling Swing", "cost": "1", "suffer": "3", "annotation": "(I or S)"},
            {"name": "Thrust", "cost": "1", "suffer": "2", "annotation": "(P)"},
            {"name": "Sweeping Cut", "cost": "2", "suffer": "2", "annotation": "(S)"},
            {"name": "Rising Attack", "cost": "1", "suffer": "1", "annotation": "(I, S or P)"},
            {"name": "Low Guard", "cost": "∅", "suffer": "∅", "highlight": "suffer"}
        ]
    },
    "Low Guard": {
        "title": "Low Guard",
        "damage_type": None,
        "damage_choice": None,
        "opponent_plays": "Opponent Plays",
        "oval_suffix": "Deal / Suffer",
        "moves": [
            {"name": "High Guard", "cost": "∅", "suffer": "∅"},
            {"name": "Falling Swing", "cost": "∅", "suffer": "2", "annotation": "(I or S)"},
            {"name": "Thrust", "cost": "∅", "suffer": "1", "annotation": "(P)"},
            {"name": "Sweeping Cut", "cost": "∅", "suffer": "∅", "annotation": "(S)"},
            {"name": "Rising Attack", "cost": "∅", "suffer": "∅", "annotation": "(I, S or P)", "highlight": "deal"},
            {"name": "Low Guard", "cost": "∅", "suffer": "∅"}
        ]
    }
}

# Card order mapping
CARD_ORDER = [
    "High Guard",      # card_page_22.png
    "Falling Swing",   # card_page_25.png
    "Thrust",          # card_page_28.png
    "Sweeping Cut",    # card_page_31.png
    "Rising Attack",   # card_page_34.png
    "Low Guard"        # card_page_37.png
]

def get_font(size, bold=False):
    """Get Verdana font with fallback options."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/verdana.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Verdana.ttf",  # macOS
        "C:/Windows/Fonts/verdana.ttf"        # Windows
    ]
    
    for font_path in font_paths:
        try:
            if os.path.exists(font_path):
                return ImageFont.truetype(font_path, size)
        except:
            continue
    
    # Fallback to default font
    try:
        return ImageFont.truetype("arial.ttf", size)
    except:
        return ImageFont.load_default()

def draw_yellow_highlight(draw, x, y, width, height):
    """Draw a yellow circle highlight with dark yellow border."""
    # Create a circular highlight
    highlight_color = (255, 255, 0, 180)  # Yellow with transparency
    border_color = (204, 204, 0, 255)     # Dark yellow border
    
    # Calculate circle center and radius - make it even bigger
    center_x = x + width // 2 + 2
    center_y = y + height // 2 + 8        # Shift up by 3 pixels (8-3=5)
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

def draw_table_lines(draw, table_x, table_y, table_width, table_height, num_rows, deal_x, suffer_x):
    """Draw grey table lines around the moves section."""
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
    
    # Draw vertical lines based on actual column positions
    # Calculate the distance between Deal and Suffer centers
    column_spacing = suffer_x - deal_x
    # Use this spacing as the width for both columns
    column_width = column_spacing
    
    # Create 2 vertical lines: left of Deal and between Deal/Suffer
    # The table's right border serves as the right edge of Suffer column
    
    # Line 1: Left edge of Deal column
    x1 = deal_x - column_width // 2
    draw.line([x1, table_y, x1, table_y + table_height], fill=line_color, width=line_width)
    
    # Line 2: Between Deal and Suffer (centered between them)
    x2 = (deal_x + suffer_x) // 2
    draw.line([x2, table_y, x2, table_y + table_height], fill=line_color, width=line_width)

def add_text_to_card(image_path, card_name, output_path):
    """Add text overlay to a card image."""
    if card_name not in CARD_DEFINITIONS:
        print(f"Card definition not found for: {card_name}")
        return False
    
    card_data = CARD_DEFINITIONS[card_name]
    
    # Open the image
    img = Image.open(image_path).convert("RGBA")
    
    # Create a transparent overlay for text
    text_overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(text_overlay)
    
    # Define fonts with larger sizes for better readability and more space usage
    title_font = get_font(48, bold=True)          # Bigger title
    subtitle_font = get_font(20, bold=False)      # Smaller for "Damage Type:" label
    body_font = get_font(20)                      # Bigger body text
    body_bold_font = get_font(24, bold=True)      # Bigger and bold for damage types
    move_font = get_font(28, bold=True)           # Even bigger move names
    cost_font = get_font(26, bold=True)           # Even bigger cost/suffer
    num_font = get_font(32, bold=True)           # Bigger numbers
    annotation_font = get_font(14, bold=True)                # Smaller annotations
    
    # Colors
    black = (0, 0, 0, 255)
    dark_gray = (64, 64, 64, 255)
    light_gray = (60, 60, 60, 255)               # Darker for annotations
    suffer_gray = (90, 90, 90, 255)           # Darker for suffer column
    
    # Card dimensions
    card_width, card_height = img.size
    
    # Use more of the card space - move further left
    margin_left = 30                              # Adjusted for better alignment
    margin_right = 60
    content_width = card_width - margin_left - margin_right
    
    # Title position (top of card)
    title_x = margin_left
    title_y = 40
    draw.text((title_x, title_y), card_data["title"], fill=black, font=title_font)
    
    # Damage type section (if applicable)
    if card_data["damage_type"]:
        damage_y = title_y + 90
        # "Damage Type:" is not bold
        draw.text((title_x, damage_y), card_data["damage_type"], fill=black, font=subtitle_font)
        
        choice_y = damage_y + 32
        # Parse and make damage types bold with proper baseline alignment
        choice_text = card_data["damage_choice"]
        if "Choose" in choice_text:
            # Split the text to make damage types bold
            parts = choice_text.split()
            
            # Collect all text elements for this line to calculate baseline
            choice_texts = []
            for part in parts:
                clean_part = part.rstrip('.,')
                if clean_part in ["Impact", "Slicing", "Piercing"]:
                    choice_texts.append((part, body_bold_font))
                else:
                    choice_texts.append((part, body_font))
            
            # Calculate maximum ascent for baseline alignment
            max_ascent = 0
            for text, font in choice_texts:
                ascent = font.getmetrics()[0]
                max_ascent = max(max_ascent, ascent)
            
            # Calculate common baseline
            choice_baseline_y = choice_y + max_ascent
            
            # Draw all text on the same baseline
            x_pos = title_x
            for i, part in enumerate(parts):
                # Remove punctuation for checking
                clean_part = part.rstrip('.,')
                if clean_part in ["Impact", "Slicing", "Piercing"]:
                    # This is a damage type - make it bold
                    font_to_use = body_bold_font
                else:
                    font_to_use = body_font
                
                # Calculate Y position based on baseline
                font_ascent = font_to_use.getmetrics()[0]
                text_y = choice_baseline_y - font_ascent
                
                draw.text((x_pos, text_y), part, fill=black, font=font_to_use)
                # Calculate width of this word for next position
                bbox = draw.textbbox((0, 0), part + " ", font=font_to_use)
                x_pos += bbox[2] - bbox[0]
        else:
            # Just draw the damage type bold
            draw.text((title_x, choice_y), choice_text, fill=black, font=body_bold_font)
        
        start_y = choice_y + 90  # Increased spacing after damage type
    else:
        start_y = title_y + 110  # Increased spacing when no damage type
    margin_left = 24
    # Calculate column positions first to align headers properly
    # First calculate annotation space to properly align headers
    max_annotation_width = 0
    for move in card_data["moves"]:
        if "annotation" in move:
            move_bbox = draw.textbbox((0, 0), move["name"] + " ", font=move_font)
            annotation_bbox = draw.textbbox((0, 0), move["annotation"], font=annotation_font)
            total_width = (move_bbox[2] - move_bbox[0]) + (annotation_bbox[2] - annotation_bbox[0])
            max_annotation_width = max(max_annotation_width, total_width)
    
    # Position columns based on the longest move name + annotation - move further right
    deal_col_x = margin_left + max_annotation_width + 50  # Restored original spacing
    suffer_col_x = deal_col_x + 70  # Restored original spacing
    
    # Calculate table positioning from bottom of card for consistency
    # Define table dimensions first
    num_moves = len(card_data["moves"])
    line_height = 58  # Height per row
    table_padding_from_bottom = 60  # Distance from bottom of card
    header_height = 50  # Height for header row
    
    # Calculate table position from bottom
    table_height = header_height + (num_moves * line_height)
    table_end_y = card_height - table_padding_from_bottom
    table_start_y = table_end_y - table_height
    
    # Header row positioning
    opponent_y = table_start_y + 10  # Small padding from table top
    
    # Moves start position
    moves_start_y = opponent_y + header_height
    
    # Calculate baseline for header row - find max ascent among all header texts
    header_texts = [
        (card_data["opponent_plays"], body_font),
        ("Deal", body_font),
        ("Suffer", body_font)
    ]
    
    max_ascent = 0
    for text, font in header_texts:
        bbox = draw.textbbox((0, 0), text, font=font)
        ascent = font.getmetrics()[0]  # Get ascent from font metrics
        max_ascent = max(max_ascent, ascent)
    
    # Calculate common baseline for header row
    header_baseline_y = opponent_y + max_ascent + 6
    
    # Draw all header texts on the same baseline
    # "Opponent Plays"
    opponent_ascent = body_font.getmetrics()[0]
    opponent_text_y = header_baseline_y - opponent_ascent
    draw.text((title_x, opponent_text_y), card_data["opponent_plays"], fill=black, font=body_font)
    
    # "Deal" and "Suffer" headers - center them over their columns
    deal_bbox = draw.textbbox((0, 0), "Deal", font=body_font)
    suffer_bbox = draw.textbbox((0, 0), "Suffer", font=body_font)
    deal_width = deal_bbox[2] - deal_bbox[0]
    suffer_width = suffer_bbox[2] - suffer_bbox[0]
    
    deal_ascent = body_font.getmetrics()[0]
    suffer_ascent = body_font.getmetrics()[0]
    deal_text_y = header_baseline_y - deal_ascent
    suffer_text_y = header_baseline_y - suffer_ascent
    
    draw.text((deal_col_x - deal_width//2, deal_text_y), "Deal", fill=black, font=body_font)
    draw.text((suffer_col_x - suffer_width//2 + 4, suffer_text_y), "Suffer", fill=dark_gray, font=body_font)
    
    # Calculate column positions
    move_name_x = title_x
    
    for i, move in enumerate(card_data["moves"]):
        # Calculate the top Y position for this row
        row_top_y = moves_start_y + (i * line_height)
        
        # Collect all text elements that will be drawn in this row
        row_texts = []
        
        # Move name
        move_text = move["name"]
        row_texts.append((move_text, move_font))
        
        # Annotation if present
        if "annotation" in move:
            row_texts.append((move["annotation"], annotation_font))
        
        # Cost and suffer values
        cost_text = str(move['cost'])
        suffer_text = str(move['suffer'])
        row_texts.append((cost_text, cost_font))
        row_texts.append((suffer_text, cost_font))
        
        # Calculate maximum ascent for this row
        max_ascent = 0
        for text, font in row_texts:
            ascent = font.getmetrics()[0]  # Get ascent from font metrics
            max_ascent = max(max_ascent, ascent)
        
        # Calculate common baseline for this row
        row_baseline_y = row_top_y + max_ascent + 5  # Add small padding from top of cell
        
        # Draw move name on baseline
        move_ascent = move_font.getmetrics()[0]
        move_y = row_baseline_y - move_ascent
        draw.text((move_name_x, move_y), move_text, fill=black, font=move_font)
        
        # Draw annotation if present, on same baseline
        if "annotation" in move:
            move_text_bbox = draw.textbbox((0, 0), move_text + " ", font=move_font)
            annotation_x = move_name_x + (move_text_bbox[2] - move_text_bbox[0])
            annotation_ascent = annotation_font.getmetrics()[0]
            annotation_y = row_baseline_y - annotation_ascent
            
            draw.text((annotation_x, annotation_y - 4), move["annotation"], fill=light_gray, font=annotation_font)
        
        # Check if this move should be highlighted and in which column
        highlight_type = move.get("highlight", None)
        
        # Calculate text dimensions for highlighting and positioning
        cost_bbox = draw.textbbox((0, 0), cost_text, font=cost_font)
        suffer_bbox = draw.textbbox((0, 0), suffer_text, font=cost_font)
        cost_width = cost_bbox[2] - cost_bbox[0]
        suffer_width = suffer_bbox[2] - suffer_bbox[0]
        cost_height = cost_bbox[3] - cost_bbox[1]
        suffer_height = suffer_bbox[3] - suffer_bbox[1]
        
        # Calculate Y positions for cost and suffer text on baseline
        cost_ascent = num_font.getmetrics()[0]
        suffer_ascent = num_font.getmetrics()[0]
        cost_y = row_baseline_y - cost_ascent
        suffer_y = row_baseline_y - suffer_ascent
        
        # Draw highlights if needed (position them relative to the baseline-aligned text)
        if highlight_type == "deal":
            highlight_y = cost_y  # Use the baseline-aligned position
            draw_yellow_highlight(draw, deal_col_x - cost_width//2 - 10, highlight_y, cost_width + 20, cost_height)
        elif highlight_type == "suffer":
            highlight_y = suffer_y  # Use the baseline-aligned position
            draw_yellow_highlight(draw, suffer_col_x - suffer_width//2 - 10, highlight_y, suffer_width + 20, suffer_height)
        
        # Draw the cost and suffer values (centered in their columns, on baseline)
        draw.text((deal_col_x - cost_width//2, cost_y), cost_text, fill=black, font=num_font)
        # Suffer column is more greyed out
        draw.text((suffer_col_x - suffer_width//2, suffer_y), suffer_text, fill=suffer_gray, font=num_font)
    
    # Draw table lines around the moves section
    table_start_x = margin_left - 5  # Start slightly left of text
    table_end_x = suffer_col_x + 40  # End slightly right of suffer column
    table_width = table_end_x - table_start_x
    
    draw_table_lines(draw, table_start_x, table_start_y, table_width, table_height, 
                     num_moves + 1, deal_col_x, suffer_col_x)  # Pass actual column positions
    
    # Composite the text overlay onto the original image
    final_img = Image.alpha_composite(img, text_overlay)
    
    # Convert back to RGB for saving as PNG
    final_img = final_img.convert("RGB")
    
    # Save the result
    final_img.save(output_path, "PNG")
    print(f"Created card with text: {output_path}")
    return True

def process_all_cards():
    """Process all card images and add text overlays."""
    # Define input and output directories
    input_dir = Path(__file__).parent / "unique_cards"
    output_dir = Path(__file__).parent / "cards_with_text"
    output_dir.mkdir(exist_ok=True)
    
    # Find all PNG files
    png_files = sorted(list(input_dir.glob("*.png")))
    
    if not png_files:
        print("No PNG files found in unique_cards directory")
        return
    
    print(f"Found {len(png_files)} PNG files")
    
    # Process each file
    file_mapping = [
        ("card_page_22.png", "High Guard"),
        ("card_page_25.png", "Falling Swing"),
        ("card_page_28.png", "Thrust"),
        ("card_page_31.png", "Sweeping Cut"),
        ("card_page_34.png", "Rising Attack"),
        ("card_page_37.png", "Low Guard")
    ]
    
    for filename, card_name in file_mapping:
        input_path = input_dir / filename
        if input_path.exists():
            # Create output filename
            safe_card_name = card_name.replace(" ", "_").lower()
            output_filename = f"{safe_card_name}.png"
            
            output_path = output_dir / output_filename
            
            success = add_text_to_card(input_path, card_name, output_path)
            if not success:
                print(f"Failed to process: {filename}")
        else:
            print(f"File not found: {filename}")

if __name__ == "__main__":
    print("Adding text overlays to card images...")
    process_all_cards()
    print("Text overlay processing complete!")
