#!/usr/bin/env python3
"""
Script to extract yellow circle information from character cards PDF.

This script processes the character-cards-all-June-2025.pdf file to identify
which signature moves have yellow circles underneath their damage values,
then updates the moonstone_data.json file with this information.
"""

import json
import fitz  # PyMuPDF
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import numpy as np
from PIL import Image
import io
import sys

# The signature move options that appear on cards
SIGNATURE_MOVES = [
    "High Guard",
    "Falling Swing", 
    "Thrust",
    "Sweeping Cut",
    "Rising Attack",
    "Low Guard"
]

def load_character_names(names_file: str) -> List[str]:
    """Load character names from the names_by_page_in_pdf.txt file."""
    with open(names_file, 'r', encoding='utf-8') as f:
        names = [line.strip() for line in f if line.strip()]
    return names

def load_json_data(json_file: str) -> List[Dict]:
    """Load character data from moonstone_data.json."""
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def save_json_data(json_file: str, data: List[Dict]):
    """Save updated character data to moonstone_data.json."""
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def is_yellow_color(rgb: Tuple[int, int, int], target_rgb: Tuple[int, int, int] = (255, 238, 0), tolerance: int = 30) -> bool:
    """
    Check if an RGB color is close to the target yellow color (#ffee00).
    
    Args:
        rgb: RGB tuple to check
        target_rgb: Target yellow RGB (255, 238, 0)
        tolerance: Allowed difference per channel (increased for better detection)
    
    Returns:
        True if the color is close enough to yellow
    """
    r, g, b = rgb
    tr, tg, tb = target_rgb
    
    # Check if it's close to our target yellow
    is_target_yellow = (abs(r - tr) <= tolerance and 
                       abs(g - tg) <= tolerance and 
                       abs(b - tb) <= tolerance)
    
    # Also check for general yellowish colors (high red and green, low blue)
    is_generally_yellow = (r > 200 and g > 200 and b < 100)
    
    return is_target_yellow or is_generally_yellow

def find_text_regions_on_right_side(page) -> Dict[str, Tuple[float, float, float, float]]:
    """
    Find the bounding boxes of signature move text on the right 50% of the page.
    
    Returns:
        Dictionary mapping move names to their bounding boxes (x0, y0, x1, y1)
    """
    text_regions = {}
    text_dict = page.get_text("dict")
    page_rect = page.rect
    page_width = page_rect.width
    right_half_start = page_width * 0.5  # Right 50% of the page
    
    # Remove the verbose page width output since we're debugging all characters
    # print(f"  Page width: {page_width}, searching right side from x >= {right_half_start}")
    
    for block in text_dict.get("blocks", []):
        if "lines" in block:
            for line in block["lines"]:
                line_text = ""
                line_bbox = None
                
                # Combine all spans in the line to get full text
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    line_text += text + " "
                    
                    # Get the bounding box of this span
                    if "bbox" in span:
                        span_bbox = span["bbox"]
                        if line_bbox is None:
                            line_bbox = span_bbox
                        else:
                            # Expand line bbox to include this span
                            line_bbox = (
                                min(line_bbox[0], span_bbox[0]),
                                min(line_bbox[1], span_bbox[1]),
                                max(line_bbox[2], span_bbox[2]),
                                max(line_bbox[3], span_bbox[3])
                            )
                
                line_text = line_text.strip()
                
                # Check if this line contains any of our signature moves and is on the right side
                for move in SIGNATURE_MOVES:
                    if move in line_text and line_bbox and line_bbox[0] >= right_half_start:
                        text_regions[move] = line_bbox
                        # Keep minimal debug output for now
                        break
    
    return text_regions

def check_for_yellow_pixel_by_pixel(image: Image.Image, region: Tuple[float, float, float, float], 
                                   page_width: float, page_height: float, debug_image=None, move_name="", debug_log=None, verbose=False) -> bool:
    """
    Check if there's yellow color to the right of a text region by scanning pixel by pixel.
    
    Args:
        image: PIL Image of the page
        region: Text bounding box (x0, y0, x1, y1) in PDF coordinates
        page_width: PDF page width
        page_height: PDF page height
        debug_image: Optional PIL Image to draw debug info on
        move_name: Name of the move for debug purposes
        debug_log: List to append debug messages to
        verbose: Whether to print detailed output
    
    Returns:
        True if yellow color is found
    """
    if debug_log is None:
        debug_log = []
        
    # Convert PDF coordinates to image coordinates
    img_width, img_height = image.size
    scale_x = img_width / page_width
    scale_y = img_height / page_height
    
    x0, y0, x1, y1 = region
    
    # Convert to image coordinates
    img_x0 = int(x0 * scale_x)
    img_y0 = int(y0 * scale_y)
    img_x1 = int(x1 * scale_x)
    img_y1 = int(y1 * scale_y)
    
    # Calculate the Y center of the text
    y_center = (img_y0 + img_y1) // 2
    
    # Start searching from the end of the text and move right pixel by pixel
    start_x = img_x1  # Start right after the text ends
    max_search_distance = 200  # Increased search distance
    
    debug_info = f"    Searching from x={start_x}, y_center={y_center}, for up to {max_search_distance} pixels"
    debug_log.append(debug_info)
    debug_log.append(f"    PDF region: ({x0:.1f}, {y0:.1f}) to ({x1:.1f}, {y1:.1f})")
    debug_log.append(f"    Image region: ({img_x0}, {img_y0}) to ({img_x1}, {img_y1})")
    if verbose:
        print(debug_info)
    
    # Convert image to numpy array for faster access
    img_array = np.array(image)
    
    if len(img_array.shape) != 3 or img_array.shape[2] < 3:
        error_msg = f"    Invalid image array shape: {img_array.shape}"
        debug_log.append(error_msg)
        if verbose:
            print(error_msg)
        return False
    
    # Draw debug info if debug image is provided
    if debug_image is not None:
        from PIL import ImageDraw
        draw = ImageDraw.Draw(debug_image)
        # Draw the text bounding box in blue
        draw.rectangle([img_x0, img_y0, img_x1, img_y1], outline="blue", width=2)
        # Draw the search line in red
        draw.line([start_x, y_center, min(start_x + max_search_distance, img_width-1), y_center], 
                 fill="red", width=2)
        # Add text label
        draw.text((img_x0, img_y0 - 20), move_name, fill="black")
    
    # Search pixel by pixel to the right
    yellow_found_at = []
    sample_colors = []  # Sample some colors for debugging
    
    for x_offset in range(max_search_distance):
        x_coord = start_x + x_offset
        
        # Make sure we're within image bounds
        if x_coord >= img_width or y_center >= img_height:
            break
            
        # Get the pixel color at this location
        pixel_rgb = tuple(img_array[y_center, x_coord][:3])
        
        # Sample some colors for debugging (every 20 pixels)
        if x_offset % 20 == 0:
            sample_colors.append((x_coord, pixel_rgb))
        
        # Check if it's yellow
        if is_yellow_color(pixel_rgb):
            yellow_found_at.append((x_coord, pixel_rgb))
            if debug_image is not None:
                from PIL import ImageDraw
                draw = ImageDraw.Draw(debug_image)
                # Mark yellow pixels in green
                draw.rectangle([x_coord-2, y_center-2, x_coord+2, y_center+2], fill="green")
    
    # Log sample colors
    debug_log.append(f"    Sample colors every 20 pixels: {sample_colors[:10]}")  # First 10 samples
    
    if yellow_found_at:
        result_msg = f"    Found yellow at {len(yellow_found_at)} positions: {yellow_found_at[:3]}"  # First 3
        debug_log.append(result_msg)
        if verbose:
            print(f"    Found yellow at {len(yellow_found_at)} positions")
        return True
    else:
        result_msg = f"    No yellow found in {max_search_distance} pixel search"
        debug_log.append(result_msg)
        if verbose:
            print(result_msg)
        return False

def find_yellow_circles_in_image(page, debug_character_name=None, debug_dir=None, verbose=False) -> Set[str]:
    """
    Convert PDF page to image and look for yellow circles next to signature moves.
    
    Args:
        page: PDF page object
        debug_character_name: If provided, save debug image for this character
        debug_dir: Debug directory to save files in
        verbose: Whether to print detailed output and save debug files
    
    Returns:
        Set of signature move names that have yellow circles
    """
    yellow_moves = set()
    debug_log = []
    
    try:
        # Convert PDF page to image at high resolution for better accuracy
        mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better resolution
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("ppm")
        
        # Convert to PIL Image
        image = Image.open(io.BytesIO(img_data))
        debug_log.append(f"Image size: {image.size}")
        
        # Create debug image copy if requested
        debug_image = None
        if verbose and debug_character_name and debug_dir:
            debug_image = image.copy()
        
        # Get page dimensions
        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height
        debug_log.append(f"Page dimensions: {page_width} x {page_height}")
        
        # Find text regions for signature moves on the right side of the page
        text_regions = find_text_regions_on_right_side(page)
        debug_log.append(f"Found text regions: {list(text_regions.keys())}")
        if verbose:
            print(f"  Found text regions: {list(text_regions.keys())}")
        
        # Check each signature move for yellow to its right
        for move, region in text_regions.items():
            debug_log.append(f"\nChecking for yellow near '{move}'...")
            if verbose:
                print(f"  Checking for yellow near '{move}'...")
            
            found_yellow = check_for_yellow_pixel_by_pixel(image, region, page_width, page_height, debug_image, move, debug_log, verbose)
            
            if found_yellow:
                yellow_moves.add(move)
                debug_log.append(f"  FOUND yellow circle for: {move}")
                if verbose:
                    print(f"  Found yellow circle for: {move}")
            else:
                debug_log.append(f"  NO yellow found for: {move}")
                if verbose:
                    print(f"  No yellow found for: {move}")
        
        # Save debug image and log if requested
        if verbose and debug_image and debug_character_name and debug_dir:
            safe_name = debug_character_name.replace(' ', '_').replace(',', '').replace('/', '_')
            debug_image_path = debug_dir / f"{safe_name}_debug.png"
            debug_log_path = debug_dir / f"{safe_name}_debug.txt"
            
            debug_image.save(debug_image_path)
            
            with open(debug_log_path, 'w', encoding='utf-8') as f:
                f.write(f"Debug log for {debug_character_name}\n")
                f.write("=" * 50 + "\n")
                for line in debug_log:
                    f.write(line + "\n")
            
            print(f"  Saved debug files: {debug_image_path.name}, {debug_log_path.name}")
        
    except Exception as e:
        error_msg = f"Error processing image: {e}"
        debug_log.append(error_msg)
        if verbose:
            print(f"  {error_msg}")
    
    return yellow_moves

def check_for_no_signature_move(page) -> bool:
    """Check if the page shows 'No Signature Move' or similar text."""
    text = page.get_text()
    no_signature_patterns = [
        "No Signature Move",
        "No Signature",
        "None"
    ]
    
    for pattern in no_signature_patterns:
        if pattern.lower() in text.lower():
            return True
    
    return False

def extract_yellow_circles_from_pdf(pdf_file: str, character_names: List[str], verbose=False) -> Dict[str, List[str]]:
    """
    Extract yellow circle information from the PDF for each character.
    
    Returns a dictionary mapping character names to lists of signature moves
    that have yellow circles.
    """
    results = {}
    
    # Create debug directory only if verbose mode is on
    debug_dir = None
    if verbose:
        debug_dir = Path(__file__).parent / "yellow_debug"
        debug_dir.mkdir(exist_ok=True)
        print(f"Created debug directory: {debug_dir}")
    
    try:
        doc = fitz.open(pdf_file)
        
        for page_num, character_name in enumerate(character_names):
            if page_num >= len(doc):
                print(f"Warning: Not enough pages in PDF for character {character_name}")
                continue
                
            page = doc[page_num]
            print(f"Processing page {page_num + 1}: {character_name}")
            
            # Check if this card has no signature move
            if check_for_no_signature_move(page):
                results[character_name] = []  # Convert null to empty array
                print(f"  Character '{character_name}' has no signature move")
                continue
            
            # Find yellow highlights/circles using image analysis
            yellow_moves = find_yellow_circles_in_image(page, character_name if verbose else None, debug_dir, verbose)
            
            if yellow_moves:
                results[character_name] = list(yellow_moves)
                print(f"  Character '{character_name}' has yellow circles for: {', '.join(yellow_moves)}")
            else:
                results[character_name] = []
                print(f"  Character '{character_name}' has no yellow circles detected")
        
        doc.close()
        
    except Exception as e:
        print(f"Error processing PDF: {e}")
        return {}
    
    return results

def update_json_with_yellow_circles(json_data: List[Dict], yellow_circles: Dict[str, List[str]]) -> List[Dict]:
    """
    Update the JSON data with yellow circle information.
    
    Adds a 'yellowCircleMoves' attribute to each character that specifies
    which signature moves have yellow circles. Always uses empty arrays instead of null.
    """
    
    # Create a lookup dictionary for faster searching
    name_to_character = {}
    for character in json_data:
        if 'name' in character:
            name_to_character[character['name']] = character
    
    # Update characters with yellow circle information
    for character_name, moves in yellow_circles.items():
        if character_name in name_to_character:
            character = name_to_character[character_name]
            
            # Always use empty array instead of null
            character['yellowCircleMoves'] = moves if moves is not None else []
                
            print(f"Updated '{character_name}' with yellow circles: {character['yellowCircleMoves']}")
        else:
            print(f"Warning: Character '{character_name}' not found in JSON data")
    
    # Also convert any existing null yellowCircleMoves to empty arrays
    for character in json_data:
        if 'yellowCircleMoves' in character and character['yellowCircleMoves'] is None:
            character['yellowCircleMoves'] = []
            print(f"Converted null yellowCircleMoves to empty array for '{character.get('name', 'unknown')}'")
    
    return json_data

def main():
    """Main function to process the PDF and update the JSON file."""
    
    # Check for debug mode via command line arguments
    verbose = len(sys.argv) > 1 and ('debug' in sys.argv[1].lower() or 'verbose' in sys.argv[1].lower())
    
    if verbose:
        print("Running in verbose/debug mode - detailed output and debug files will be generated")
    
    # File paths
    script_dir = Path(__file__).parent
    pdf_file = script_dir / "character-cards-all-June-2025.pdf"
    names_file = script_dir / "names_by_page_in_pdf.txt"
    json_file = script_dir / "moonstone_data.json"
    
    # Check if files exist
    for file_path in [pdf_file, names_file, json_file]:
        if not file_path.exists():
            print(f"Error: File not found: {file_path}")
            return
    
    print("Loading character names...")
    character_names = load_character_names(names_file)
    print(f"Loaded {len(character_names)} character names")
    
    print("Loading JSON data...")
    json_data = load_json_data(json_file)
    print(f"Loaded {len(json_data)} character records")
    
    print("Processing PDF to extract yellow circles...")
    # Process all characters with optional verbose mode
    yellow_circles = extract_yellow_circles_from_pdf(pdf_file, character_names, verbose)
    
    if not yellow_circles:
        print("No yellow circle data extracted. Check PDF processing.")
        return
    
    print("Updating JSON data...")
    updated_data = update_json_with_yellow_circles(json_data, yellow_circles)
    
    # Create backup
    backup_file = script_dir / "moonstone_data.json.backup"
    print(f"Creating backup at {backup_file}")
    save_json_data(backup_file, json_data)
    
    print("Saving updated JSON data...")
    save_json_data(json_file, updated_data)
    
    print("Process completed successfully!")
    
    # Print summary
    total_with_circles = sum(1 for moves in yellow_circles.values() 
                           if moves is not None and len(moves) > 0)
    total_no_signature = sum(1 for moves in yellow_circles.values() 
                           if moves is not None and len(moves) == 0 and 
                           any(char.get('yellowCircleMoves') == [] for char in updated_data))
    total_no_circles = sum(1 for moves in yellow_circles.values() 
                         if moves is not None and len(moves) == 0)
    
    print(f"\nSummary:")
    print(f"  Characters with yellow circles: {total_with_circles}")
    print(f"  Characters with no signature move or no yellow circles: {total_no_circles}")
    print(f"  Total processed: {len(yellow_circles)}")
    
    if verbose:
        print(f"\nTo run without debug output, use: python {Path(__file__).name}")
    else:
        print(f"\nTo run with debug output, use: python {Path(__file__).name} debug")

if __name__ == "__main__":
    main()
