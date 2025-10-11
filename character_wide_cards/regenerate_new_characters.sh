#!/bin/bash
# Regenerate the new characters (Matilda and Faculty) through the full pipeline
# Run this script whenever you modify the original character images in:
# character_wide_cards/matilda_and_faculty/characters_only_not_mirrored/

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Regenerating New Characters Pipeline"
echo "=========================================="
echo ""

# Step 1: Prep character images
echo "Step 1: Preparing character images..."
python3 prep_new_characters.py
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to prepare character images"
    exit 1
fi
echo ""

# Step 2: Generate base wide cards (right side with signature moves)
echo "Step 2: Generating base wide cards..."
python3 create_wide_character_card.py 2>&1 | grep -E "(Flinders|Matilda|Old Polly|Prof\.|Successfully|Error|Warning)"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to generate base wide cards"
    exit 1
fi
echo ""

# Step 3: Add left side text overlay (stats and abilities)
echo "Step 3: Adding left side text overlay..."
python3 create_left_side_of_wide_character_card.py 2>&1 | grep -E "(Flinders|Matilda|Old Polly|Prof\.|Successfully|Error|Warning)"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to add left side text"
    exit 1
fi
echo ""

# Step 4: Generate final PDFs
echo "Step 4: Generating final PDFs..."
python3 generate_final_character_pdf.py 2>&1 | tail -10
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to generate final PDFs"
    exit 1
fi
echo ""

echo "=========================================="
echo "Pipeline Complete!"
echo "=========================================="
echo ""
echo "Updated files:"
echo "  - characters_images/[character]/*.png"
echo "  - generated_wide_cards/[character]_wide_card.png"
echo "  - generated_wide_cards_with_left_text/[character]_wide_card_with_text.png"
echo "  - final_pdfs/*.pdf (all 15 PDFs regenerated)"
echo ""
echo "Characters updated:"
echo "  - Old Polly"
echo "  - Flinders Memphis"
echo "  - Prof. Boffinsworth"
echo "  - Matilda"
echo ""

