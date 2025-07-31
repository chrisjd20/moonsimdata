#!/usr/bin/env python3
"""
Create a PDF for printing cards on 8.5" x 11" paper.
Cards will be 2.5" x 3.5" in landscape mode, 3 columns x 2 rows per page.
Each card appears 3 times across multiple pages.
"""

import os
from pathlib import Path
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch

def create_printable_pdf():
    """Create a PDF with cards sized for printing at 2.5" x 3.5"."""
    
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
    
    # PDF configuration
    output_path = output_dir / "printable_cards.pdf"
    
    # Page setup - landscape 8.5" x 11"
    page_width, page_height = landscape(letter)  # 11" x 8.5"
    print(f"Page size: {page_width/inch:.1f}\" x {page_height/inch:.1f}\"")
    
    # Card dimensions in points (72 points per inch)
    card_width = 2.5 * inch   # 2.5 inches
    card_height = 3.5 * inch  # 3.5 inches
    
    # Padding between cards (small amount for cutting guides)
    card_padding = 2  # 2 points ≈ 0.028 inches (about 2 pixels at 72 DPI)
    
    # Grid configuration
    cards_per_row = 3
    rows_per_page = 2
    cards_per_page = cards_per_row * rows_per_page  # 6 cards per page
    
    # Calculate total dimensions including padding
    total_card_width = (cards_per_row * card_width) + ((cards_per_row - 1) * card_padding)
    total_card_height = (rows_per_page * card_height) + ((rows_per_page - 1) * card_padding)
    
    # Calculate margins to center the grid
    x_margin = (page_width - total_card_width) / 2
    y_margin = (page_height - total_card_height) / 2
    
    print(f"Card size: {card_width/inch:.1f}\" x {card_height/inch:.1f}\"")
    print(f"Card padding: {card_padding/inch:.3f}\" ({card_padding} points)")
    print(f"Grid: {cards_per_row} x {rows_per_page} cards per page")
    print(f"Margins: {x_margin/inch:.1f}\" x {y_margin/inch:.1f}\"")
    
    # Create the PDF
    c = canvas.Canvas(str(output_path), pagesize=landscape(letter))
    
    # Create the sequence: each card 3 times in order
    card_sequence = []
    for card_file in card_files:
        for _ in range(3):  # Each card appears 3 times
            card_sequence.append(card_file)
    
    print(f"Total cards to place: {len(card_sequence)}")
    
    # Calculate number of pages needed
    total_pages = (len(card_sequence) + cards_per_page - 1) // cards_per_page
    print(f"Pages needed: {total_pages}")
    
    # Place cards across multiple pages
    for page_num in range(total_pages):
        print(f"\nCreating page {page_num + 1}/{total_pages}")
        
        # Calculate card range for this page
        start_card = page_num * cards_per_page
        end_card = min(start_card + cards_per_page, len(card_sequence))
        page_cards = card_sequence[start_card:end_card]
        
        # Place cards on this page
        for i, card_file in enumerate(page_cards):
            # Calculate grid position on this page
            row = i // cards_per_row
            col = i % cards_per_row
            
            # Calculate position from bottom-left (PDF coordinate system)
            x = x_margin + (col * (card_width + card_padding))
            y = y_margin + ((rows_per_page - 1 - row) * (card_height + card_padding))  # Flip Y for PDF coords
            
            # Load the card image
            card_path = input_dir / card_file
            
            # Draw the card on the PDF
            c.drawImage(str(card_path), x, y, width=card_width, height=card_height)
            
            print(f"  Placed {card_file} at position ({col}, {row}) -> ({x/inch:.1f}\", {y/inch:.1f}\")")
        
        # Add page break (except for last page)
        if page_num < total_pages - 1:
            c.showPage()
    
    # Save the PDF
    c.save()
    
    print(f"\nPrintable PDF created: {output_path}")
    print(f"Instructions:")
    print(f"- Print on 8.5\" x 11\" paper in landscape mode")
    print(f"- Each card will be exactly 2.5\" x 3.5\"")
    print(f"- {cards_per_page} cards per page, centered")
    print(f"- Total pages: {total_pages}")
    
    return True

if __name__ == "__main__":
    print("Creating printable PDF...")
    success = create_printable_pdf()
    if success:
        print("PDF creation complete!")
    else:
        print("PDF creation failed!")
