# Character Wide Cards Pipeline

This directory contains the complete pipeline for generating custom character cards for the Moonstone tabletop game. The cards combine character artwork with stats, abilities, and signature move information.

## Overview

The pipeline produces wide-format character cards (1200x700px) that display:
- **Left side**: Character name, keywords, stats (Melee/Range/Arcane/Evade), health pips, base size, and detailed abilities
- **Right side**: Character portrait and signature move information with a damage table

## Main Pipeline (Active Scripts)

These scripts form the core pipeline for generating the final PDFs:

### 1. `create_wide_character_card.py` → `generated_wide_cards/`

**Purpose**: Creates the base wide card with character image and signature move on the right side.

**What it does**:
- Reads character data from `moonstone_data.json`
- For each character, loads `character_tile.png` and `background.png` from `characters_images/<CharacterName>/`
- Creates a 1200x700px canvas:
  - Left: Character portrait (with mirrored effect)
  - Right: Background with signature move overlay
- Adds faction symbol in top-right corner from `symbols_factions/`
- Draws signature move table with damage values for each combat move
- Highlights damage values with yellow circles if specified in `yellowCircleMoves` field
- Outputs: `generated_wide_cards/<CharacterName>_wide_card.png`

**Key Features**:
- Dynamic font sizing to fit text
- Yellow circle highlights for energy-generating moves
- Damage type and upgrade information
- Support for special characters like ∅ (null/empty)

### 2. `create_left_side_of_wide_character_card.py` → `generated_wide_cards_with_left_text/`

**Purpose**: Adds detailed stats and abilities to the left side of the card.

**What it does**:
- Takes the base cards from `generated_wide_cards/`
- Overlays character information on the left side:
  - Character name (with subtitle if comma-separated)
  - Keywords
  - Version number (v.X)
  - Stats box (Melee, Range, Arcane, Evade)
  - Abilities section (passive, activated, arcane)
  - Health pips with energy indicators
  - Base size
- Uses `abilities_strings.yaml` for enhanced ability descriptions
- Applies text glow effect for better readability
- Supports custom overlay images (e.g., `liv_overlay.png`)
- Outputs: `generated_wide_cards_with_left_text/<CharacterName>_wide_card_with_text.png`

**Key Features**:
- Merges JSON ability data with YAML formatting overrides
- Dynamic font scaling to fit all content
- Special handling for ability tags like `[Protection: ...]` (bold)
- Color-coded arcane outcome tokens (green/blue/red)
- Once Per Turn/Game indicators in italics

### 3. `generate_final_character_pdf.py` → `final_pdfs/`

**Purpose**: Compiles the completed cards into printable PDF files.

**What it does**:
- Reads card order from `names_by_page_in_pdf.txt`
- Loads cards from `generated_wide_cards_with_left_text/`
- Sorts characters alphabetically and splits into 5 groups (a-e, f-j, etc.)
- Generates 3 PDF formats per group:
  - **Landscape 2x2** (120x70mm cards): `characters_tarot_120x70mm_2x2_landscape_<range>.pdf`
  - **Portrait 1x2 scaled** (90mm height): `characters_scaled_height_90mm_1x2_portrait_<range>.pdf`
  - **Native pixel size** (1:1): `characters_native_pixel_size_1up_<range>.pdf`
- Outputs: 15 total PDFs in `final_pdfs/`

## Data Files

### `moonstone_data.json`

The master data file containing all character information:

**Structure** (per character):
```json
{
  "id": "uuid",
  "name": "Character Name",
  "faction": "Commonwealth|Dominion|Leshavult|Shade",
  "maxhp": 10,
  "energyblips": "1,4",
  "keywords": "Soldier, Human",
  "melee": 4,
  "range": 6,
  "arcane": 3,
  "evade": 1,
  "baseSize": 0,  // 0=30mm, 1=40mm
  "version": 2,
  "yellowCircleMoves": ["High Guard", "Thrust"],
  "overlayImage": "liv_overlay.png",
  "Ability": [
    {
      "name": "Ability Name",
      "energyCost": null,  // null = passive
      "description": "Ability text",
      "oncePerTurn": false,
      "oncePerGame": false
    }
  ],
  "SignatureMove": {
    "name": "Move Name",
    "upgradeFor": 0,  // 0-5: High Guard to Low Guard
    "damageType": 1,  // 1=Slicing, 2=Thrust, 4=Impact, 8=Magical
    "highGuardDamage": 3,
    "fallingSwingDamage": 4,
    // ... other move damages
    "extraText": "Additional rules",
    "endStepEffect": "End of turn effect"
  }
}
```

**Updated by**:
- `get_versions_from_pdf.py` - Adds `version` field
- `extract_yellow_circles.py` - Adds `yellowCircleMoves` field

### `abilities_strings.yaml`

Enhanced ability descriptions with better formatting control:

**Structure**:
```yaml
Ability Name:
  cost: 2
  range: 8
  type: activated|arcane|passive
  isPulse: true|false
  textToRightInItalics: "Optional italic text"
  activatedText: "Description for activated abilities"
  arcaneOutcomes:
    - "gX: Effect with green card requirement"
    - "bX,rX: Effect with blue and red cards"
  catastrophe: "Catastrophe effect for arcane abilities"
```

**Purpose**: 
- Provides precise formatting for complex abilities
- Overrides JSON descriptions when present
- Supports arcane outcome notation (gX, bX, rX for card colors)
- Used by `create_left_side_of_wide_character_card.py`

**Updated by**:
- `generate_missing_abilities.py` - Uses GPT-5 to add missing entries

### `names_by_page_in_pdf.txt`

Simple text file with one character name per line, defining:
- Order of characters in the source PDF
- Which character appears on which page
- Card output order for final PDFs

Used by `generate_final_character_pdf.py` and `get_versions_from_pdf.py`.

## Utility Scripts (Active)

### `extract_character_cards_simple.py`

**Purpose**: Extracts character images from the source PDF.

**What it does**:
- Reads `character-cards-all-June-2025.pdf`
- Uses `names_by_page_in_pdf.txt` for page mapping
- Extracts images from each page:
  - `character_tile.png` - The character portrait
  - `background.png` - The signature move background
- Saves to `characters_images/<CharacterName>/`
- Also extracts text in left/right halves

**Run**: One-time setup or when PDF is updated.

### `extract_yellow_circles.py`

**Purpose**: Identifies which signature moves have yellow circle highlights in the PDF.

**What it does**:
- Analyzes each page of the source PDF
- Detects yellow color (#ffee00) near signature move damage values
- Updates `moonstone_data.json` with `yellowCircleMoves` array
- Creates backup before modifying JSON

**Usage**:
- Normal mode: `python extract_yellow_circles.py`
- Debug mode: `python extract_yellow_circles.py debug` (saves debug images)

**Run**: When updating from a new PDF with changed yellow circles.

### `get_versions_from_pdf.py`

**Purpose**: Extracts version numbers from the PDF and adds them to the JSON.

**What it does**:
- Reads `character-cards-all-June-2025.pdf`
- Searches each page for "v.X" markers
- Updates `moonstone_data.json` with `version` field
- Handles duplicate character names correctly
- Creates backup before modifying

**Run**: When PDF version numbers change.

### `generate_missing_abilities.py`

**Purpose**: Uses GPT-5 AI to generate missing ability descriptions.

**What it does**:
- Scans `moonstone_data.json` for characters with activated/arcane abilities
- Checks if abilities exist in `abilities_strings.yaml`
- For missing abilities:
  - Loads character stat card image
  - Sends to GPT-5 with context
  - Extracts ability YAML from response
  - Appends to `abilities_strings.yaml`
- Saves logs to `model_ability_generation/<CharacterName>.log`

**Usage**:
```bash
python generate_missing_abilities.py \
  --reasoning low \
  --verbosity medium \
  --limit 10 \
  --dry-run  # Test without API calls
```

**Requirements**: 
- OpenAI API key in environment
- `OPENAI_API_KEY` environment variable

**Run**: When new characters are added or abilities need updating.

## Debugging/Analysis Scripts

### `find_color_on_page.py`

**Purpose**: PDF color analysis utility for debugging.

**What it does**:
- Finds objects matching specific colors in PDF pages
- Searches text, vector graphics, and raster images
- Reports bounding boxes and distances from target colors
- Useful for debugging yellow circle detection

**Usage**:
```bash
python find_color_on_page.py \
  --pdf character-cards-all-June-2025.pdf \
  --page 0 \
  --colors '#43a83b,#009ee4,#e6007d' \
  --only-x-badges
```

**Run**: As needed for debugging color detection issues.

## Old/Unused Scripts

These scripts are backup versions or no longer part of the active pipeline:

### `create_wide_character_card.v4.py`
- **Status**: Backup/old version
- **Note**: Identical to `create_wide_character_card.py`
- **Use**: Kept for version history

### `create_left_side_of_wide_character_card_no_shadowing.py`
- **Status**: Old version
- **Difference**: Lacks the text glow effect for better readability
- **Use**: Superseded by the version with glow

### `extract_arcane_colour_requirements.py`
- **Status**: Empty file
- **Use**: Not currently implemented

## Complete Pipeline Workflow

### Initial Setup (One-time)
```bash
# 1. Extract character images from PDF
python extract_character_cards_simple.py

# 2. Extract yellow circle data
python extract_yellow_circles.py

# 3. Extract version numbers
python get_versions_from_pdf.py

# 4. Generate missing ability descriptions (optional)
python generate_missing_abilities.py --limit 10
```

### Regular Generation (Every update)
```bash
# 1. Generate base cards (right side)
python3 create_wide_character_card.py

# 2. Add left side text overlay
python3 create_left_side_of_wide_character_card.py

# 3. Generate final PDFs
python3 generate_final_character_pdf.py
```

### Quick Regeneration for New Characters (Matilda & Faculty)

If you've edited the images in `matilda_and_faculty/characters_only_not_mirrored/`, run:

```bash
./regenerate_new_characters.sh
```

This automated script runs all 4 steps:
1. Prep images (copy to `characters_images/`)
2. Generate base cards
3. Add text overlays
4. Generate PDFs

**Characters updated**: Old Polly, Flinders Memphis, Prof. Boffinsworth, Matilda

### Output Directories
- `generated_wide_cards/` - Base cards (Step 1 output)
- `generated_wide_cards_with_left_text/` - Complete cards (Step 2 output)
- `final_pdfs/` - Ready-to-print PDFs (Step 3 output)

## Browser-Based PDF Generator

For users who want to generate custom PDFs without running Python scripts, use the browser-based generator:

**File**: `card_generator.html`

### Features
- Generate PDFs directly in your browser
- Filter characters by name or faction
- Select only the characters you want
- Choose from 3 PDF formats (same as Python output)
- Preview before generating
- No installation required

### Setup for GitHub Pages

1. **Update Configuration**: Edit `card_generator.html` and change line ~138:
   ```javascript
   const GITHUB_USER = 'your-username';  // Change to your GitHub username
   ```

2. **Enable GitHub Pages**:
   - Go to your repository Settings
   - Navigate to Pages section
   - Set Source to `main` branch, `/ (root)` directory
   - Save

3. **Access the Generator**:
   ```
   https://[your-username].github.io/moonsimdata/character_wide_cards/card_generator.html
   ```

### Usage
1. Characters load automatically from `moonstone_data.json`
2. Use search/filter to find characters
3. Click cards to select/deselect (checkboxes)
4. Choose PDF format(s) in right panel
5. Click "Preview" to see first page layout
6. Click "Generate PDFs" to download

### Technical Details
- **Bootstrap 5** for UI styling
- **jsPDF** for client-side PDF generation
- Fetches images from GitHub raw URLs
- Works offline after first load (images cached)
- No server required - runs entirely in browser

### Supported Formats
All three match the Python script output exactly:
- **Landscape 2x2 Tarot**: 120x70mm cards, 4 per page
- **Portrait 1x2 Scaled**: 90mm height, 2 per page  
- **Native Pixel Size**: 1:1 scale, 1 per page

## Dependencies

**Python Packages**:
- `Pillow` (PIL) - Image processing
- `reportlab` - PDF generation
- `PyMuPDF` (fitz) - PDF reading/extraction
- `pyyaml` - YAML file handling
- `openai` - GPT-5 API (optional, for generate_missing_abilities.py)
- `numpy` - Numerical operations (for yellow circle detection)

**Install**:
```bash
pip install Pillow reportlab PyMuPDF pyyaml numpy
# Optional for AI generation:
pip install openai
```

## Directory Structure

```
character_wide_cards/
├── README.md (this file)
├── moonstone_data.json          # Master character data
├── abilities_strings.yaml        # Enhanced ability descriptions
├── names_by_page_in_pdf.txt     # Character ordering
├── character-cards-all-June-2025.pdf  # Source PDF
├── create_wide_character_card.py          # Step 1: Base cards
├── create_left_side_of_wide_character_card.py  # Step 2: Add text
├── generate_final_character_pdf.py        # Step 3: PDFs
├── extract_character_cards_simple.py      # Setup: Extract images
├── extract_yellow_circles.py              # Setup: Yellow circles
├── get_versions_from_pdf.py               # Setup: Versions
├── generate_missing_abilities.py          # Utility: AI generation
├── find_color_on_page.py                  # Utility: Debug colors
├── characters_images/                # Extracted character images
│   └── <CharacterName>/
│       ├── character_tile.png
│       └── background.png
├── symbols_factions/                 # Faction symbols
│   ├── Commonwealth.png
│   ├── Dominion.png
│   └── ...
├── generated_wide_cards/             # Step 1 output
│   └── <CharacterName>_wide_card.png
├── generated_wide_cards_with_left_text/  # Step 2 output
│   └── <CharacterName>_wide_card_with_text.png
└── final_pdfs/                       # Step 3 output
    ├── characters_tarot_120x70mm_2x2_landscape_a-c.pdf
    ├── characters_scaled_height_90mm_1x2_portrait_a-c.pdf
    └── ...
```

## Notes

- All scripts run from the `character_wide_cards/` directory
- Character names must exactly match between JSON, directory names, and PDF
- The pipeline preserves character name formatting (commas, spaces, etc.)
- Custom overlays (like `liv_overlay.png`) are optional per-character
- Yellow circles only appear on signature moves that grant energy
- The ∅ symbol is used to represent "no damage" or empty values
