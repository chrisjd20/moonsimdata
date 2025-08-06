#!/usr/bin/env python3
"""
Simplified Character Card Extractor for Moonstone Game Data

This script extracts character cards from a PDF file using a manual page mapping.
For each character, it:
1. Maps the character name from JSON to the correct page number
2. Creates a directory for the character (using exact JSON name)
3. Extracts all images from that page preserving transparency and resolution
4. Exports page text split into left and right halves

Requirements: PyMuPDF (fitz), json, os, sys
"""

import json
import os
import sys
import hashlib
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF (fitz) is required but not installed.")
    print("Please install it with: pip install PyMuPDF")
    sys.exit(1)


class SimplifiedCharacterCardExtractor:
    def __init__(self, json_file, pdf_file, page_mapping_file, output_dir="characters"):
        self.json_file = json_file
        self.pdf_file = pdf_file
        self.page_mapping_file = page_mapping_file
        self.output_dir = output_dir
        self.characters = []
        self.page_mapping = {}
        self.pdf_doc = None
        
        # Known background image MD5 hashes
        self.background_md5s = {
            "38261cdb92175a495d22479663e6df05",
            "b359768fc466b6ca19859ce9aaebef85", 
            "7a8152c9e95da53b212bacd791a68b06",
            "ac059a17e80a00e62a723a01aefb13cd",
            "705a6575eef50209a6b320a630a80fce"
        }
        
    def load_character_data(self):
        """Load character data from JSON file"""
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Extract character names, filtering out empty entries
            self.characters = []
            for item in data:
                if isinstance(item, dict) and 'name' in item and item['name']:
                    name = item['name'].strip()
                    if name:  # Only add non-empty names
                        self.characters.append(name)
                        
            print(f"Loaded {len(self.characters)} characters from JSON")
            return True
            
        except Exception as e:
            print(f"Error loading character data: {e}")
            return False
    
    def load_page_mapping(self):
        """Load the manual page mapping from text file"""
        try:
            with open(self.page_mapping_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Create mapping from PDF name to page number (1-indexed)
            pdf_to_page = {}
            for page_num, line in enumerate(lines, 1):
                pdf_name = line.strip()
                if pdf_name:
                    pdf_to_page[pdf_name] = page_num
            
            # Now create mapping from JSON names to page numbers
            self.page_mapping = {}
            
            for json_name in self.characters:
                # Try direct match first
                if json_name in pdf_to_page:
                    self.page_mapping[json_name] = pdf_to_page[json_name]
                    continue
                
                # Handle common variations
                found = False
                
                # Check for minor differences in formatting
                for pdf_name, page_num in pdf_to_page.items():
                    # Handle specific known mappings
                    if self._names_match(json_name, pdf_name):
                        self.page_mapping[json_name] = page_num
                        found = True
                        break
                
                if not found:
                    print(f"Warning: No page mapping found for '{json_name}'")
            
            print(f"Created page mapping for {len(self.page_mapping)} characters")
            return True
            
        except Exception as e:
            print(f"Error loading page mapping: {e}")
            return False
    
    def _names_match(self, json_name, pdf_name):
        """Check if JSON name matches PDF name, handling common variations"""
        # Direct match
        if json_name == pdf_name:
            return True
        
        # Known specific mappings
        mappings = {
            "Agatha": "Agatha, Tavernfrau",
            "Boom Boom Mc Boom": "Boo Boom Mc Boom",
            "El Capitano": "EL Capitano",
            "Gump": "Gum",
            "Seasick Stu": "Seasick St",
            "Sir Guillemot Poppycock": "Sir GuillemotPoppycock",
            "Tabby, the Librarian": "Tabby, the Libraria",
            "The Mortician": "The Morticia",
            "Danica, Dusk Witch  ": "Danica, Dusk Witch"  # Note trailing spaces in JSON
        }
        
        # Check if json_name maps to pdf_name
        if json_name in mappings and mappings[json_name] == pdf_name:
            return True
        
        # Check reverse mapping
        if pdf_name in mappings and mappings[pdf_name] == json_name:
            return True
        
        # Handle trailing spaces in JSON names
        if json_name.strip() == pdf_name:
            return True
        
        return False
    
    def open_pdf(self):
        """Open the PDF document"""
        try:
            self.pdf_doc = fitz.open(self.pdf_file)
            print(f"Opened PDF with {len(self.pdf_doc)} pages")
            return True
        except Exception as e:
            print(f"Error opening PDF: {e}")
            return False
    
    def extract_images_from_page(self, page_num, character_name):
        """Extract all images from a specific page"""
        try:
            page = self.pdf_doc[page_num - 1]  # Convert to 0-indexed
            image_list = page.get_images(full=True)
            
            # First pass: collect all valid images and check for backgrounds
            valid_images = []
            
            for img_index, img in enumerate(image_list):
                try:
                    # Get image data
                    xref = img[0]
                    pix = fitz.Pixmap(self.pdf_doc, xref)
                    
                    # Check image dimensions - skip if smaller than 400x400
                    if pix.width < 400 or pix.height < 400:
                        print(f"  Skipping image {img_index + 1}: too small ({pix.width}x{pix.height})")
                        pix = None
                        continue
                    
                    # Always convert to RGB for consistent PNG output
                    if pix.colorspace and pix.colorspace.name not in ("DeviceRGB", "DeviceGray"):
                        # Convert non-RGB colorspaces (including CMYK) to RGB
                        pix_rgb = fitz.Pixmap(fitz.csRGB, pix)
                        pix = None  # Clean up original
                        pix = pix_rgb
                    elif pix.n > 4:  # More than RGBA channels
                        # Convert to RGB
                        pix_rgb = fitz.Pixmap(fitz.csRGB, pix)
                        pix = None  # Clean up original
                        pix = pix_rgb
                    
                    # Check if image is all white/near-white - skip if it is
                    if self._is_all_white_image(pix):
                        print(f"  Skipping image {img_index + 1}: mostly white/near-white")
                        pix = None
                        continue
                    
                    # Calculate MD5 hash to check if it's a known background
                    md5_hash = self._calculate_image_md5(pix)
                    is_background = md5_hash in self.background_md5s if md5_hash else False
                    
                    # Store valid image with its background status
                    valid_images.append({
                        'index': img_index + 1,
                        'pix': pix,
                        'md5': md5_hash,
                        'is_background': is_background,
                        'width': pix.width,
                        'height': pix.height
                    })
                    
                    print(f"  Valid image {img_index + 1}: {pix.width}x{pix.height}, MD5: {md5_hash}, Background: {is_background}")
                    
                except Exception as e:
                    print(f"  Error processing image {img_index + 1}: {e}")
                    try:
                        if 'pix' in locals():
                            pix = None
                    except:
                        pass
                    continue
            
            if len(valid_images) == 0:
                print("  No valid images found")
                return 0
            
            # Sort images: backgrounds first, then others
            valid_images.sort(key=lambda x: (not x['is_background'], x['index']))
            
            # Second pass: save images with intelligent naming
            extracted_count = 0
            background_saved = False
            character_tile_saved = False
            
            for i, img_data in enumerate(valid_images):
                try:
                    # Determine filename based on background detection
                    if img_data['is_background'] and not background_saved:
                        # Known background image
                        img_filename = "background.png"
                        background_saved = True
                        print(f"  → Identified as background (MD5 match)")
                    elif not character_tile_saved:
                        # First non-background image = character tile
                        img_filename = "character_tile.png"
                        character_tile_saved = True
                    elif not background_saved:
                        # Still need background = use this one
                        img_filename = "background.png"
                        background_saved = True
                    else:
                        # Additional images
                        img_filename = f"image_{extracted_count + 1:02d}.png"
                    
                    img_path = os.path.join(self.get_character_dir(character_name), img_filename)
                    
                    # Save image as PNG
                    img_data['pix'].save(img_path)
                    extracted_count += 1
                    print(f"  Extracted {img_filename}: {img_data['width']}x{img_data['height']}")
                    
                    # Clean up
                    img_data['pix'] = None
                    
                except Exception as e:
                    print(f"  Error saving image: {e}")
                    continue
            
            return extracted_count
            
        except Exception as e:
            print(f"Error extracting images from page {page_num}: {e}")
            return 0
    
    def extract_text_from_page(self, page_num, character_name):
        """Extract text from a page and split into left/right halves"""
        try:
            page = self.pdf_doc[page_num - 1]  # Convert to 0-indexed
            
            # Get page dimensions
            rect = page.rect
            page_width = rect.width
            mid_x = page_width / 2
            
            # Extract text from left half
            left_rect = fitz.Rect(0, 0, mid_x, rect.height)
            left_text = page.get_text("text", clip=left_rect)
            
            # Extract text from right half
            right_rect = fitz.Rect(mid_x, 0, page_width, rect.height)
            right_text = page.get_text("text", clip=right_rect)
            
            # Save text files
            char_dir = self.get_character_dir(character_name)
            
            with open(os.path.join(char_dir, "left_text.txt"), 'w', encoding='utf-8') as f:
                f.write(left_text)
            
            with open(os.path.join(char_dir, "right_text.txt"), 'w', encoding='utf-8') as f:
                f.write(right_text)
            
            # Also save full page text
            full_text = page.get_text()
            with open(os.path.join(char_dir, "full_text.txt"), 'w', encoding='utf-8') as f:
                f.write(full_text)
            
            return True
            
        except Exception as e:
            print(f"Error extracting text from page {page_num}: {e}")
            return False
    
    def _is_all_white_image(self, pix):
        """Check if a pixmap image is all white or near-white (90% threshold)"""
        try:
            # Sample pixels to check if image is all white/near-white
            # We'll check a grid of sample points across the image
            sample_size = min(50, pix.width // 4, pix.height // 4)  # Don't sample more than needed
            sample_step_x = max(1, pix.width // sample_size)
            sample_step_y = max(1, pix.height // sample_size)
            
            white_threshold = 250  # Consider pixels with RGB values above this as "white"
            near_white_threshold = 230  # Consider pixels above this as "near-white"
            non_white_pixels = 0
            non_near_white_pixels = 0
            total_samples = 0
            
            for y in range(0, pix.height, sample_step_y):
                for x in range(0, pix.width, sample_step_x):
                    # Get pixel color at this position
                    pixel = pix.pixel(x, y)
                    total_samples += 1
                    
                    # Check if pixel is not white or near-white
                    if isinstance(pixel, (tuple, list)) and len(pixel) >= 3:
                        # RGB/RGBA image - pixel is a tuple/list with at least 3 values
                        r, g, b = pixel[:3]
                        if r < white_threshold or g < white_threshold or b < white_threshold:
                            non_white_pixels += 1
                        if r < near_white_threshold or g < near_white_threshold or b < near_white_threshold:
                            non_near_white_pixels += 1
                    elif isinstance(pixel, (tuple, list)) and len(pixel) == 1:
                        # Single channel in a tuple/list
                        if pixel[0] < white_threshold:
                            non_white_pixels += 1
                        if pixel[0] < near_white_threshold:
                            non_near_white_pixels += 1
                    elif isinstance(pixel, (int, float)):
                        # Grayscale image - pixel is a single number
                        if pixel < white_threshold:
                            non_white_pixels += 1
                        if pixel < near_white_threshold:
                            non_near_white_pixels += 1
                    else:
                        # Unknown format, assume it's not white to be safe
                        non_white_pixels += 1
                        non_near_white_pixels += 1
                    
                    # Early exit if we find enough non-near-white pixels
                    if non_near_white_pixels > total_samples * 0.10:  # More than 10% non-near-white
                        return False
            
            # Check both white and near-white thresholds
            white_percentage = (total_samples - non_white_pixels) / total_samples
            near_white_percentage = (total_samples - non_near_white_pixels) / total_samples
            
            # If 90% or more pixels are white OR near-white, consider it a white image
            return white_percentage >= 0.90 or near_white_percentage >= 0.90
            
        except Exception as e:
            print(f"  Error checking if image is white: {e}")
            # If we can't check, assume it's not all white to be safe
            return False
    
    def _calculate_image_md5(self, pix):
        """Calculate MD5 hash of a pixmap image"""
        try:
            # Convert pixmap to PNG bytes
            png_data = pix.tobytes("png")
            # Calculate MD5 hash
            md5_hash = hashlib.md5(png_data).hexdigest()
            return md5_hash
        except Exception as e:
            print(f"  Error calculating MD5: {e}")
            return None
    
    def get_character_dir(self, character_name):
        """Get the directory path for a character (create if needed)"""
        # Use exact character name from JSON for directory
        char_dir = os.path.join(self.output_dir, character_name)
        os.makedirs(char_dir, exist_ok=True)
        return char_dir
    
    def process_character(self, character_name):
        """Process a single character: extract images and text"""
        if character_name not in self.page_mapping:
            print(f"No page mapping for character: {character_name}")
            return False
        
        page_num = self.page_mapping[character_name]
        print(f"Processing {character_name} (Page {page_num})...")
        
        # Create character directory
        char_dir = self.get_character_dir(character_name)
        
        # Extract images
        image_count = self.extract_images_from_page(page_num, character_name)
        print(f"  Extracted {image_count} images")
        
        # Extract text
        if self.extract_text_from_page(page_num, character_name):
            print(f"  Extracted text files")
        else:
            print(f"  Failed to extract text")
        
        return True
    
    def run(self):
        """Main execution method"""
        print("=== Simplified Character Card Extractor ===")
        
        # Load character data from JSON
        if not self.load_character_data():
            return False
        
        # Load page mapping
        if not self.load_page_mapping():
            return False
        
        # Open PDF
        if not self.open_pdf():
            return False
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Process each character
        successful = 0
        failed = 0
        failed_characters = []
        
        for character_name in self.characters:
            if self.process_character(character_name):
                successful += 1
            else:
                failed += 1
                failed_characters.append(character_name)
        
        print(f"\n=== Extraction Complete ===")
        print(f"Successfully processed: {successful}")
        print(f"Failed: {failed}")
        if failed_characters:
            print(f"Failed characters: {', '.join(failed_characters)}")
        print(f"Total characters: {len(self.characters)}")
        
        # Close PDF
        if self.pdf_doc:
            self.pdf_doc.close()
        
        return failed == 0


def main():
    # Configuration
    json_file = "moonstone_data.json"
    pdf_file = "character-cards-all-June-2025.pdf"
    page_mapping_file = "names_by_page_in_pdf.txt"
    output_dir = "characters_images"
    
    # Verify files exist
    for file_path in [json_file, pdf_file, page_mapping_file]:
        if not os.path.exists(file_path):
            print(f"Error: Required file not found: {file_path}")
            return False
    
    # Create and run extractor
    extractor = SimplifiedCharacterCardExtractor(json_file, pdf_file, page_mapping_file, output_dir)
    return extractor.run()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
