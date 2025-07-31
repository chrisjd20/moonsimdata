#!/usr/bin/env python3
"""
Create a sheet with all card images arranged in a 6x3 grid.
Each card appears 3 times in the specified order.
"""

import os
from pathlib import Path
from PIL import Image

def create_card_sheet():
    """Create a 6x3 grid sheet with each card appearing 3 times."""
    
    # Define input and output directories
    input_dir = Path(__file__).parent / "cards_with_text"
    output_dir = Path(__file__).parent
    
    # Card order (each will appear 3 times)
    card_files = [
        "high_guard.png",
        "falling_swing.png", 
        "thrust.png",
        "sweeping_cut.png",
        "rising_attack.png",
        "low_guard.png"
    ]
    
    # Verify all files exist
    missing_files = []
    for filename in card_files:
        file_path = input_dir / filename
        if not file_path.exists():
            missing_files.append(filename)
    
    if missing_files:
        print(f"Missing files: {missing_files}")
        return False
    
    # Load the first image to get dimensions
    first_image = Image.open(input_dir / card_files[0])
    card_width, card_height = first_image.size
    first_image.close()
    
    print(f"Card dimensions: {card_width} x {card_height}")
    
    # Grid configuration
    cards_per_row = 6
    rows = 3
    total_cards = cards_per_row * rows  # Should be 18
    
    # Calculate final image dimensions
    final_width = card_width * cards_per_row
    final_height = card_height * rows
    
    print(f"Final sheet dimensions: {final_width} x {final_height}")
    
    # Create the final image
    final_image = Image.new('RGB', (final_width, final_height), color='white')
    
    # Create the sequence: each card 3 times in order
    card_sequence = []
    for card_file in card_files:
        for _ in range(3):  # Each card appears 3 times
            card_sequence.append(card_file)
    
    print(f"Card sequence: {card_sequence}")
    
    # Place cards in the grid
    for i, card_file in enumerate(card_sequence):
        # Calculate grid position
        row = i // cards_per_row
        col = i % cards_per_row
        
        # Calculate pixel position
        x = col * card_width
        y = row * card_height
        
        # Load and paste the card
        card_image = Image.open(input_dir / card_file)
        final_image.paste(card_image, (x, y))
        card_image.close()
        
        print(f"Placed {card_file} at position ({col}, {row}) -> ({x}, {y})")
    
    # Save the final sheet
    output_path = output_dir / "card_sheet.png"
    final_image.save(output_path, "PNG")
    
    print(f"Card sheet created: {output_path}")
    print(f"Final dimensions: {final_image.size}")
    
    return True

if __name__ == "__main__":
    print("Creating card sheet...")
    success = create_card_sheet()
    if success:
        print("Card sheet creation complete!")
    else:
        print("Card sheet creation failed!")
