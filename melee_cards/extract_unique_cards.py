import os
import hashlib
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image

def extract_text_from_page(doc, page_num):
    """Extract text from a specific page."""
    page = doc[page_num]
    return page.get_text()

def get_page_hash(text):
    """Create a hash of the page text to identify duplicates."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def convert_page_to_image(doc, page_num, output_path):
    """Convert a PDF page to an image with all text removed."""
    page = doc[page_num]
    
    # Create a new temporary document
    temp_doc = fitz.open()
    temp_page = temp_doc.new_page(width=page.rect.width, height=page.rect.height)
    
    # Copy images
    image_list = page.get_images()
    for img_index, img in enumerate(image_list):
        xref = img[0]
        try:
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            
            # Get image placement rectangles
            for rect in page.get_image_rects(img):
                temp_page.insert_image(rect, stream=image_bytes)
        except:
            continue  # Skip problematic images
    
    # Copy vector drawings (lines, shapes, etc.)
    drawings = page.get_drawings()
    for drawing in drawings:
        items = drawing.get("items", [])
        stroke = drawing.get("stroke")
        fill = drawing.get("fill")
        width = drawing.get("width", 1)
        
        for item in items:
            try:
                if item[0] == "l":  # line
                    p1 = item[1] if hasattr(item[1], 'x') else fitz.Point(item[1], item[2])
                    p2 = item[2] if hasattr(item[2], 'x') else fitz.Point(item[3], item[4])
                    temp_page.draw_line(p1, p2, color=stroke, width=width)
                elif item[0] == "re":  # rectangle
                    if len(item) >= 5:
                        rect = fitz.Rect(item[1], item[2], item[3], item[4])
                        temp_page.draw_rect(rect, color=stroke, fill=fill, width=width)
                elif item[0] == "c":  # curve - basic handling
                    continue  # Skip curves for now
            except:
                continue  # Skip problematic drawing items
    
    # Add black border around the entire page
    page_rect = temp_page.rect
    border_width = 5  # Make it even thicker
    
    # Draw filled black rectangles for each edge to ensure complete coverage
    # Top border
    temp_page.draw_rect(fitz.Rect(0, 0, page_rect.width, border_width), 
                       color=(0, 0, 0), fill=(0, 0, 0))
    # Bottom border
    temp_page.draw_rect(fitz.Rect(0, page_rect.height - border_width, page_rect.width, page_rect.height), 
                       color=(0, 0, 0), fill=(0, 0, 0))
    # Left border
    temp_page.draw_rect(fitz.Rect(0, 0, border_width, page_rect.height), 
                       color=(0, 0, 0), fill=(0, 0, 0))
    # Right border
    temp_page.draw_rect(fitz.Rect(page_rect.width - border_width, 0, page_rect.width, page_rect.height), 
                       color=(0, 0, 0), fill=(0, 0, 0))
    
    # Convert the clean page to image with higher resolution
    # Use 4x zoom for maximum detail before resizing
    mat = fitz.Matrix(4, 4)  # 4x zoom for better quality
    pix = temp_page.get_pixmap(matrix=mat)
    
    # Convert to PIL Image
    img_data = pix.tobytes("ppm")
    img = Image.open(io.BytesIO(img_data))
    
    # Resize to exactly 500x700 using high-quality resampling
    target_size = (500, 700)
    img_resized = img.resize(target_size, Image.Resampling.LANCZOS)
    
    # Save as PNG
    img_resized.save(output_path, "PNG")
    pix = None
    temp_doc.close()

def process_pdf_cards(pdf_path, start_page=22, end_page=39):
    """Extract unique cards from PDF pages and convert to images."""
    # Ensure output directory exists
    output_dir = Path(__file__).parent / "unique_cards"
    output_dir.mkdir(exist_ok=True)
    
    # Open PDF
    doc = fitz.open(pdf_path)
    
    # Track unique pages
    seen_hashes = set()
    unique_pages = []
    
    print(f"Processing pages {start_page} to {end_page}...")
    
    # Extract text and identify unique pages
    for page_num in range(start_page - 1, end_page):  # Convert to 0-based indexing
        text = extract_text_from_page(doc, page_num)
        page_hash = get_page_hash(text)
        
        if page_hash not in seen_hashes:
            seen_hashes.add(page_hash)
            unique_pages.append((page_num + 1, text))  # Store 1-based page number
            print(f"Found unique page: {page_num + 1}")
        else:
            print(f"Duplicate page found: {page_num + 1}")
    
    print(f"\nFound {len(unique_pages)} unique pages out of {end_page - start_page + 1} total pages")
    
    # Convert unique pages to images
    for page_num, text in unique_pages:
        output_path = output_dir / f"card_page_{page_num:02d}.png"
        convert_page_to_image(doc, page_num - 1, output_path)  # Convert back to 0-based
        print(f"Saved image: {output_path}")
        
        # Also save the text
        text_path = output_dir / f"card_page_{page_num:02d}.txt"
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text)
    
    doc.close()
    print(f"\nProcessing complete! Check the '{output_dir}' directory for results.")

if __name__ == "__main__":
    import io
    
    # Path to your PDF file
    pdf_path = "/home/admin/github/moonsimdata/melee_cards/moonstone-custom-card-decks-2.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"PDF file not found: {pdf_path}")
        print("Please update the pdf_path variable with the correct path to your PDF file.")
    else:
        process_pdf_cards(pdf_path)
