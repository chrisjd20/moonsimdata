#!/usr/bin/env python3
"""
Unified character card generator for Moonstone.

This script generates character wide cards from unified_moonstone_data.yaml,
combining the functionality of:
- create_wide_character_card.py (base card with portrait + signature move)
- create_left_side_of_wide_character_card.py (text overlay with stats + abilities)
- generate_final_character_pdf.py (PDF generation)

Usage:
    python generate_character_cards.py -a          # Generate all characters + PDFs
    python generate_character_cards.py -c "Liv"   # Generate single character
    python generate_character_cards.py -p          # PDF only (from existing images)
    python generate_character_cards.py -a --no-pdf # Generate cards only, no PDFs
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

try:
    from reportlab.lib.pagesizes import landscape, letter, portrait
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as pdf_canvas
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class PathConfig:
    """Configuration for file paths."""
    base_dir: Path
    unified_yaml: Path
    characters_images_dir: Path
    faction_symbols_dir: Path
    overlays_dir: Path
    output_cards_dir: Path
    output_pdfs_dir: Path

    @classmethod
    def from_script_dir(cls, script_dir: Path) -> "PathConfig":
        return cls(
            base_dir=script_dir,
            unified_yaml=script_dir.parent / "unified_moonstone_data.yaml",
            characters_images_dir=script_dir / "characters_images",
            faction_symbols_dir=script_dir / "symbols_factions",
            overlays_dir=script_dir,
            output_cards_dir=script_dir / "generated_wide_cards_with_left_text",
            output_pdfs_dir=script_dir / "final_pdfs",
        )


# =============================================================================
# DataLoader - Load and dereference unified YAML data
# =============================================================================

class DataLoader:
    """Loads unified_moonstone_data.yaml and provides dereferencing for IDs."""

    def __init__(self, yaml_path: Path):
        self.yaml_path = yaml_path
        self.data: Dict[str, Any] = {}
        self.signature_moves: Dict[str, Dict[str, Any]] = {}
        self.abilities: Dict[str, Dict[str, Dict[str, Any]]] = {
            "passive": {},
            "activated": {},
            "arcane": {},
        }
        self.characters: Dict[str, Dict[str, Any]] = {}

    def load(self) -> bool:
        """Load and index the unified YAML file."""
        if yaml is None:
            print("Error: PyYAML is not installed. Run: pip install pyyaml")
            return False

        if not self.yaml_path.exists():
            print(f"Error: Unified YAML not found at {self.yaml_path}")
            return False

        try:
            with open(self.yaml_path, "r", encoding="utf-8") as f:
                self.data = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Error loading YAML: {e}")
            return False

        # Index signature moves
        for uuid, move in self.data.get("SignatureMoves", {}).items():
            self.signature_moves[uuid] = move

        # Index abilities by type
        abilities_section = self.data.get("Abilities", {})
        for uuid, ability in abilities_section.get("Passive", {}).items():
            self.abilities["passive"][uuid] = ability
        for uuid, ability in abilities_section.get("Activated", {}).items():
            self.abilities["activated"][uuid] = ability
        for uuid, ability in abilities_section.get("Arcane", {}).items():
            self.abilities["arcane"][uuid] = ability

        # Index characters
        for name, char in self.data.get("Characters", {}).items():
            self.characters[name] = char

        return True

    def get_signature_move(self, move_id: str) -> Dict[str, Any]:
        """Dereference a signature move ID to its full data."""
        return self.signature_moves.get(move_id, {})

    def get_ability(self, ability_id: str) -> Optional[Dict[str, Any]]:
        """Dereference an ability ID to its full data."""
        for ability_type in self.abilities.values():
            if ability_id in ability_type:
                return ability_type[ability_id]
        return None

    def get_character_names(self) -> List[str]:
        """Get list of all character names."""
        return list(self.characters.keys())

    def build_character_for_rendering(self, char_name: str) -> Optional[Dict[str, Any]]:
        """
        Build a character data structure compatible with rendering functions
        by dereferencing all IDs.
        """
        char = self.characters.get(char_name)
        if not char:
            return None

        # Convert faction list to comma-separated string
        faction_list = char.get("faction", [])
        faction_str = ",".join(faction_list) if faction_list else ""

        # Convert keywords list to comma-separated string
        keywords_list = char.get("keywords", [])
        keywords_str = ", ".join(keywords_list) if keywords_list else ""

        # Convert energy blips list to comma-separated string
        energy_list = char.get("stats", {}).get("energyblips", [])
        energy_str = ",".join(str(x) for x in energy_list) if energy_list else ""

        # Get stats from nested object
        stats = char.get("stats", {})

        # Build compatible structure
        result: Dict[str, Any] = {
            "name": char.get("name", char_name),
            "faction": faction_str,
            "keywords": keywords_str,
            "melee": stats.get("melee", 0),
            "range": stats.get("range", 0),
            "arcane": stats.get("arcane", 0),
            "evade": stats.get("evade", 0),
            "maxhp": stats.get("maxhp", 0),
            "energyblips": energy_str,
            "baseSize": stats.get("baseSize", 0),
            "version": char.get("version"),
            "yellowCircleMoves": char.get("yellowCircleMoves", []),
            "overlayImage": char.get("overlayImage"),
            "SignatureMove": self.get_signature_move(char.get("signatureMoveId", "")),
            "Ability": [],
        }

        # Dereference all abilities in order: passive, activated, arcane
        abilities_section = char.get("abilities", {})
        for ability_id in abilities_section.get("passive", []):
            ability = self.get_ability(ability_id)
            if ability:
                result["Ability"].append(self._convert_ability_format(ability))
        for ability_id in abilities_section.get("activated", []):
            ability = self.get_ability(ability_id)
            if ability:
                result["Ability"].append(self._convert_ability_format(ability))
        for ability_id in abilities_section.get("arcane", []):
            ability = self.get_ability(ability_id)
            if ability:
                result["Ability"].append(self._convert_ability_format(ability))

        return result

    def _convert_ability_format(self, ability: Dict[str, Any]) -> Dict[str, Any]:
        """Convert unified YAML ability format to render-compatible format."""
        result: Dict[str, Any] = {
            "name": ability.get("name", ""),
            "pulse": bool(ability.get("pulse", False)),
            "range": ability.get("range"),
            "energyCost": ability.get("cost"),
            "description": ability.get("description", ""),
            "oncePerTurn": bool(ability.get("oncePerTurn", False)),
            "oncePerGame": bool(ability.get("oncePerGame", False)),
            "tail": ability.get("textToRightInItalics", ""),
            "catastrophe": ability.get("catastrophe", ""),
            "subtext": ability.get("subtext", ""),
            "ArcaneOutcome": [],
        }

        # Convert arcane outcomes
        for outcome in ability.get("arcaneOutcomes", []):
            converted: Dict[str, Any] = {
                "outcomeText": outcome.get("outcomeText", ""),
                "catastropheOutcome": bool(outcome.get("catastropheOutcome", False)),
            }

            # Convert requirements to cardColourRequirement and cardValueRequirement
            requirements = outcome.get("requirements", [])
            if requirements:
                # Build color bitmask: green=1, blue=2, pink/red=4
                color_mask = 0
                values: List[str] = []
                for req in requirements:
                    color = (req.get("color") or "").lower()
                    value = req.get("value", "X")
                    values.append(str(value))
                    if color in ("green", "g"):
                        color_mask |= 1
                    elif color in ("blue", "b"):
                        color_mask |= 2
                    elif color in ("pink", "red", "r"):
                        color_mask |= 4

                converted["cardColourRequirement"] = color_mask
                # Join unique values with " or "
                unique_values = list(dict.fromkeys(values))
                converted["cardValueRequirement"] = " or ".join(unique_values) if unique_values else "X"

            result["ArcaneOutcome"].append(converted)

        return result


# =============================================================================
# Font utilities
# =============================================================================

def get_font(size: int, bold: bool = False, italic: bool = False) -> ImageFont.FreeTypeFont:
    """Get font with fallback options."""
    if italic and bold:
        preferred = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf",
        ]
    elif italic:
        preferred = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    elif bold:
        preferred = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    else:
        preferred = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/verdana.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]

    for font_path in preferred:
        try:
            if os.path.exists(font_path):
                try:
                    return ImageFont.truetype(font_path, size, layout_engine=ImageFont.Layout.BASIC)
                except Exception:
                    return ImageFont.truetype(font_path, size)
        except Exception:
            continue

    return ImageFont.load_default()


# =============================================================================
# Text utilities
# =============================================================================

def normalize_quotes(s: str) -> str:
    """Normalize curly quotes and special characters to ASCII equivalents."""
    if not isinstance(s, str):
        return s
    return (
        s.replace("\u201c", '"').replace("\u201d", '"')
        .replace("\u2018", "'").replace("\u2019", "'")
        .replace("\u2013", "-").replace("\u2014", "-")
        .replace("\u00a0", " ")
    )


def ensure_period(text: str) -> str:
    """Ensure text ends with a period."""
    s = (text or "").rstrip()
    if not s:
        return s
    if s.endswith((".", "!", "?", '"', "'")):
        return s
    return s + "."


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    """Wrap text into lines that fit within max_width."""
    if not text:
        return []

    def measure_width(t: str) -> int:
        total = 0
        for ch in t:
            use_font = font
            if ch == "\u2205":  # ∅
                use_font = get_font(max(8, int(getattr(font, "size", 16) * 1.25)))
            bb = draw.textbbox((0, 0), ch, font=use_font)
            total += bb[2] - bb[0]
        return total

    words = text.split(" ")
    lines: List[str] = []
    line = ""
    for w in words:
        test = f"{line} {w}".strip() if line else w
        if measure_width(test) <= max_width or not line:
            line = test
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def draw_text_with_special_symbols(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    base_font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int, int],
    special_scale: float = 1.25,
    italic: bool = False,
) -> int:
    """Draw text with ∅ glyph slightly larger. Returns new x after drawing."""
    if not text:
        return x
    special_font = get_font(max(8, int(getattr(base_font, "size", 16) * special_scale)), italic=italic)
    cursor_x = x
    for ch in text:
        if ch == "\u2205":  # ∅
            tb = draw.textbbox((0, 0), ch, font=special_font)
            ascent_base = abs(draw.textbbox((0, 0), "Ag", font=base_font)[1])
            ascent_spec = abs(draw.textbbox((0, 0), "Ag", font=special_font)[1])
            baseline_offset = max(0, (ascent_base - ascent_spec) - 1)
            draw.text((cursor_x, y + baseline_offset), ch, fill=fill, font=special_font)
            cursor_x += tb[2] - tb[0]
        else:
            draw.text((cursor_x, y), ch, fill=fill, font=base_font)
            tb = draw.textbbox((0, 0), ch, font=base_font)
            cursor_x += tb[2] - tb[0]
    return cursor_x


def draw_styled_text(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    base_font: ImageFont.FreeTypeFont,
    bold_font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int, int],
) -> int:
    """Draw text with bold tag names in [Tag: ...] patterns."""
    cursor_x = x
    pos = 0
    while pos < len(text):
        lb = text.find("[", pos)
        colon = text.find(":", lb + 1) if lb != -1 else -1
        if lb != -1 and colon != -1 and lb >= pos:
            cursor_x = draw_text_with_special_symbols(draw, cursor_x, y, text[pos:lb], base_font, fill)
            cursor_x = draw_text_with_special_symbols(draw, cursor_x, y, "[", base_font, fill)
            tag = text[lb + 1 : colon]
            if tag:
                cursor_x = draw_text_with_special_symbols(draw, cursor_x, y, tag, bold_font, fill)
            cursor_x = draw_text_with_special_symbols(draw, cursor_x, y, ":", base_font, fill)
            pos = colon + 1
        else:
            cursor_x = draw_text_with_special_symbols(draw, cursor_x, y, text[pos:], base_font, fill)
            break
    return cursor_x


# =============================================================================
# Signature move rendering (from create_wide_character_card.py)
# =============================================================================

def get_faction_symbol_filename(faction_string: str) -> Optional[str]:
    """Convert faction string to corresponding faction symbol filename."""
    if not faction_string:
        return None
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
        "Commonwealth,Shade": "Commonwealth_Shades.png",
    }
    return faction_map.get(faction_string)


def get_damage_type_text(damage_type: Optional[int]) -> Optional[str]:
    """Map damage type number to display text."""
    damage_type_map = {
        0: None,
        1: "Slicing",
        2: "Thrust",
        3: "Slicing or Piercing",
        4: "Impact",
        5: "Impact or Slicing",
        6: "Impact or Piercing",
        7: "Impact, Slicing or Piercing",
        8: "Magical",
        9: "Slicing or Magical",
    }
    return damage_type_map.get(damage_type)


def get_upgrade_for_text(upgrade_for: Optional[int]) -> Optional[str]:
    """Map upgrade_for number to move name."""
    upgrade_map = {
        0: "High Guard",
        1: "Falling Swing",
        2: "Thrust",
        3: "Sweeping Cut",
        4: "Rising Attack",
        5: "Low Guard",
    }
    return upgrade_map.get(upgrade_for)


def draw_yellow_highlight(draw: ImageDraw.ImageDraw, x: int, y: int, width: int, height: int) -> None:
    """Draw a yellow circle highlight with dark yellow border."""
    highlight_color = (255, 255, 0, 180)
    border_color = (204, 204, 0, 255)
    center_x = x + width // 2 + 8
    center_y = y + height // 2 + 3
    radius = int(11 * 1.5)
    border_radius = radius + 2
    draw.ellipse(
        [center_x - border_radius, center_y - border_radius, center_x + border_radius, center_y + border_radius],
        fill=border_color,
    )
    draw.ellipse(
        [center_x - radius, center_y - radius, center_x + radius, center_y + radius],
        fill=highlight_color,
    )


def draw_medium_weight_text(
    draw: ImageDraw.ImageDraw, position: Tuple[int, int], text: str, font: ImageFont.FreeTypeFont, fill: Tuple[int, ...]
) -> None:
    """Draw text with slightly heavier weight."""
    x, y = position
    offsets = [(0, 0), (0.5, 0), (0, 0.5), (0.5, 0.5)]
    for dx, dy in offsets:
        draw.text((x + dx, y + dy), text, fill=fill, font=font)


def draw_text_with_large_nulls(
    draw: ImageDraw.ImageDraw, position: Tuple[int, int], text: str, font: ImageFont.FreeTypeFont, fill: Tuple[int, ...]
) -> None:
    """Draw text with ∅ characters replaced by larger symbols."""
    x, y = position
    if "\u2205" not in text:
        draw_medium_weight_text(draw, position, text, font, fill)
        return

    font_size = getattr(font, "size", 18)
    large_null_font = get_font(int(font_size * 1.3), bold=True)
    parts = text.split("\u2205")
    current_x = x

    for i, part in enumerate(parts):
        if part:
            draw_medium_weight_text(draw, (current_x, y), part, font, fill)
            bbox = draw.textbbox((0, 0), part, font=font)
            current_x += bbox[2] - bbox[0]

        if i < len(parts) - 1:
            null_bbox = draw.textbbox((0, 0), "\u2205", font=large_null_font)
            text_bbox = draw.textbbox((0, 0), "A", font=font)
            y_offset = (text_bbox[3] - text_bbox[1] - (null_bbox[3] - null_bbox[1])) // 2
            draw_medium_weight_text(draw, (current_x, y + y_offset - 2), "\u2205", large_null_font, fill)
            current_x += null_bbox[2] - null_bbox[0]


def wrap_text_with_nulls_to_lines(
    text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw
) -> List[str]:
    """Wrap text to fit within max_width, handling ∅ characters."""
    if not text or not text.strip():
        return []

    lines: List[str] = []
    words = text.split()
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip() if current_line else word
        test_line_for_measurement = test_line.replace("\u2205", " ")
        bbox = draw.textbbox((0, 0), test_line_for_measurement, font=font)
        text_width = bbox[2] - bbox[0]

        if text_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
                current_line = word
            else:
                lines.append(word)
                current_line = ""

    if current_line:
        lines.append(current_line)

    return lines


def draw_table_lines(
    draw: ImageDraw.ImageDraw,
    table_x: int,
    table_y: int,
    table_width: int,
    table_height: int,
    num_rows: int,
    deal_x: int,
) -> None:
    """Draw grey table lines around the moves section."""
    line_color = (128, 128, 128, 255)
    line_width = 1

    draw.rectangle([table_x, table_y, table_x + table_width, table_y + table_height], outline=line_color, width=line_width)

    row_height = table_height / num_rows
    for i in range(1, num_rows):
        y = table_y + int(i * row_height)
        draw.line([table_x, y, table_x + table_width, y], fill=line_color, width=line_width)

    deal_column_left = deal_x - 40
    draw.line([deal_column_left, table_y, deal_column_left, table_y + table_height], fill=line_color, width=line_width)


def draw_signature_move_card(
    draw: ImageDraw.ImageDraw,
    signature_move: Dict[str, Any],
    bg_x: int,
    bg_y: int,
    bg_width: int,
    bg_height: int,
    character_data: Dict[str, Any],
) -> None:
    """Draw signature move card text overlay on the background area."""
    if not signature_move or not signature_move.get("name"):
        font = get_font(24, bold=True)
        draw.text((bg_x + bg_width // 2, bg_y + bg_height // 2), "No Signature Move", fill=(0, 0, 0, 255), font=font, anchor="mm")
        return

    title = signature_move.get("name", "Unknown Move")
    if title.lower() in ["no signature", "none"]:
        font = get_font(24, bold=True)
        draw.text((bg_x + bg_width // 2, bg_y + bg_height // 2), "No Signature Move", fill=(0, 0, 0, 255), font=font, anchor="mm")
        return

    # Fonts
    subtitle_font = get_font(22, bold=False)
    value_font = get_font(22, bold=True)
    body_font = get_font(18)
    end_step_header_font = get_font(20, bold=True)

    black = (0, 0, 0, 255)
    dark_gray = (64, 64, 64, 255)
    margin = 15
    current_y = bg_y + margin
    line_width = bg_width - (margin * 2)

    # Title with fallback sizing
    title_font_sizes = [40, 36, 32, 28, 24]
    title_font = get_font(24, bold=True)
    for size in title_font_sizes:
        font = get_font(size, bold=True)
        bbox = draw.textbbox((0, 0), title, font=font)
        if bbox[2] - bbox[0] <= line_width:
            title_font = font
            break

    draw.text((bg_x + margin, current_y), title, fill=black, font=title_font)
    current_y += 55

    # Upgrade For information
    upgrade_for = signature_move.get("upgradeFor")
    upgrade_for_text = get_upgrade_for_text(upgrade_for)
    if upgrade_for_text:
        upgrade_prefix = "Upgrade for "
        draw.text((bg_x + margin, current_y), upgrade_prefix, fill=black, font=subtitle_font)
        prefix_bbox = draw.textbbox((0, 0), upgrade_prefix, font=subtitle_font)
        prefix_width = prefix_bbox[2] - prefix_bbox[0]
        draw.text((bg_x + margin + prefix_width, current_y), upgrade_for_text, fill=black, font=value_font)
        current_y += 26

    # Damage Type
    damage_type = signature_move.get("damageType")
    damage_type_text = get_damage_type_text(damage_type)
    if damage_type_text:
        current_y += 5
        draw.text((bg_x + margin, current_y), "Damage Type:", fill=black, font=subtitle_font)
        current_y += 26

        if " or " in damage_type_text:
            parts = damage_type_text.split(" or ")
            current_x = bg_x + margin
            regular_font = get_font(22, bold=False)
            for i, part in enumerate(parts):
                draw.text((current_x, current_y), part, fill=black, font=value_font)
                bbox = draw.textbbox((0, 0), part, font=value_font)
                current_x += bbox[2] - bbox[0]
                if i < len(parts) - 1:
                    draw.text((current_x, current_y), " or ", fill=black, font=regular_font)
                    or_bbox = draw.textbbox((0, 0), " or ", font=regular_font)
                    current_x += or_bbox[2] - or_bbox[0]
        else:
            draw.text((bg_x + margin, current_y), damage_type_text, fill=black, font=value_font)

        current_y += 32

    # Moves table
    moves = [
        ("High Guard", signature_move.get("highGuardDamage")),
        ("Falling Swing", signature_move.get("fallingSwingDamage")),
        ("Thrust", signature_move.get("thrustDamage")),
        ("Sweeping Cut", signature_move.get("sweepingCutDamage")),
        ("Rising Attack", signature_move.get("risingAttackDamage")),
        ("Low Guard", signature_move.get("lowGuardDamage")),
    ]

    num_moves = len(moves)
    row_height = 44
    header_height = 44
    table_start_y = bg_y + int(bg_height * 0.25)
    table_width = bg_width - (margin * 2)
    table_x = bg_x + margin

    move_column_width = int(table_width * 0.7)
    deal_column_width = int(table_width * 0.3)
    move_column_x = table_x + 10
    deal_column_x = table_x + move_column_width + (deal_column_width // 2)

    header_y = table_start_y - 4
    opponent_plays_font = get_font(24, bold=False)
    deal_header_font = get_font(24, bold=False)

    manual_deal_col_x_offset = 8
    deal_col_y_manual_adjust = -2

    deal_bbox = draw.textbbox((0, 0), "Deal", font=deal_header_font)
    deal_width = deal_bbox[2] - deal_bbox[0]
    deal_text_height = deal_bbox[3] - deal_bbox[1]
    deal_y_centered = header_y + (header_height - deal_text_height) // 2
    draw.text((move_column_x, deal_y_centered), "Opponent Plays", fill=black, font=opponent_plays_font)
    deal_x_centered = deal_column_x - (deal_width // 2)
    draw.text((deal_x_centered + manual_deal_col_x_offset, deal_y_centered), "Deal", fill=black, font=deal_header_font)
    current_y = header_y + header_height

    move_name_font = get_font(26, bold=True)
    damage_value_font = get_font(32, bold=True)
    yellow_circle_moves = character_data.get("yellowCircleMoves", [])

    for move_name, damage in moves:
        damage_text = str(damage) if damage is not None else "\u2205"
        should_highlight = move_name in yellow_circle_moves

        move_bbox = draw.textbbox((0, 0), move_name, font=move_name_font)
        move_text_height = move_bbox[3] - move_bbox[1]
        move_y_centered = current_y + (row_height - move_text_height) // 2
        draw.text((move_column_x, move_y_centered), move_name, fill=black, font=move_name_font)

        damage_bbox = draw.textbbox((0, 0), damage_text, font=damage_value_font)
        damage_width = damage_bbox[2] - damage_bbox[0]
        damage_text_height = damage_bbox[3] - damage_bbox[1]
        damage_y_centered = current_y + (row_height - damage_text_height) // 2
        damage_x_centered = deal_column_x - (damage_width // 2)

        if should_highlight:
            yoff = 1
            xoff = -5.5
            if damage_text == "\u2205":
                xoff = -3
                yoff = 1
            highlight_x = damage_x_centered + manual_deal_col_x_offset - (damage_width // 2) + xoff
            highlight_y = damage_y_centered + deal_col_y_manual_adjust + yoff
            highlight_width = damage_width + 16
            highlight_height = damage_text_height + 4
            draw_yellow_highlight(draw, int(highlight_x), int(highlight_y), int(highlight_width), int(highlight_height))

        draw.text(
            (damage_x_centered + manual_deal_col_x_offset, damage_y_centered + deal_col_y_manual_adjust),
            damage_text,
            fill=black,
            font=damage_value_font,
        )
        current_y += row_height

    table_height = header_height + (num_moves * row_height)
    draw_table_lines(draw, table_x, table_start_y, table_width, table_height, num_moves + 1, deal_column_x)

    current_y = table_start_y + table_height + 8
    available_height = bg_y + bg_height - current_y - 10

    extra_text = signature_move.get("extraText", "")
    end_effect = signature_move.get("endStepEffect", "")

    if extra_text and extra_text.strip():
        extra_text = extra_text.strip()
        if not extra_text.endswith("."):
            extra_text += "."

    if end_effect and end_effect.strip():
        end_effect = end_effect.strip()
        if not end_effect.endswith("."):
            end_effect += "."

    # Get body font with fallback sizing
    body_font_sizes = [18, 17, 16, 15]
    line_spacing = 20
    temp_font = get_font(18, bold=False)
    rough_lines: List[str] = []

    if extra_text and extra_text.strip():
        rough_lines.extend(wrap_text_with_nulls_to_lines(extra_text, temp_font, line_width, draw))
    if end_effect and end_effect.strip():
        rough_lines.append("End Step Effect:")
        rough_lines.extend(wrap_text_with_nulls_to_lines(end_effect, temp_font, line_width, draw))

    if rough_lines:
        body_font_final = temp_font
        for size in body_font_sizes:
            font = get_font(size, bold=False)
            total_height = len(rough_lines) * line_spacing
            if total_height <= available_height:
                body_font_final = font
                break
        else:
            body_font_final = get_font(15, bold=False)
            line_spacing = 18

        if extra_text and extra_text.strip():
            final_extra_lines = wrap_text_with_nulls_to_lines(extra_text, body_font_final, line_width, draw)
            for line in final_extra_lines:
                draw_text_with_large_nulls(draw, (bg_x + margin, current_y), line, body_font_final, dark_gray)
                current_y += line_spacing
            current_y += 6

        if end_effect and end_effect.strip():
            draw.text((bg_x + margin, current_y), "End Step Effect:", fill=black, font=end_step_header_font)
            current_y += 24
            final_end_lines = wrap_text_with_nulls_to_lines(end_effect, body_font_final, line_width, draw)
            for line in final_end_lines:
                draw_text_with_large_nulls(draw, (bg_x + margin, current_y), line, body_font_final, dark_gray)
                current_y += line_spacing


# =============================================================================
# Left side text rendering (from create_left_side_of_wide_character_card.py)
# =============================================================================

def draw_stats_box(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    character_data: Dict[str, Any],
    text_draw: Optional[ImageDraw.ImageDraw] = None,
) -> int:
    """Draw a boxed stats area (Melee, Range, Arcane, Evade). Returns bottom y."""
    text_draw = text_draw or draw
    headers = ["Melee", "Range", "Arcane", "Evade"]
    values: List[Any] = [
        character_data.get("melee", ""),
        character_data.get("range", ""),
        character_data.get("arcane", ""),
        character_data.get("evade", ""),
    ]

    # Format Range with inches
    try:
        if isinstance(values[1], (int, float)):
            values[1] = f'{int(values[1])}"'
    except Exception:
        pass

    # Format Evade with + prefix if positive
    try:
        ev_val_raw = character_data.get("evade", "")
        if isinstance(ev_val_raw, str):
            values[3] = ev_val_raw
        else:
            ev_int = int(ev_val_raw)
            if ev_int >= 1:
                values[3] = f"+{ev_int}"
    except Exception:
        pass

    header_font = get_font(18, bold=False)
    value_font = get_font(28, bold=True)
    padding = 8
    col_width = width // 4
    header_height = draw.textbbox((0, 0), "Ag", font=header_font)[3]
    value_height = draw.textbbox((0, 0), "Ag", font=value_font)[3]
    box_height = padding + header_height + 6 + value_height + padding

    draw.rectangle([x, y, x + width, y + box_height], outline=(0, 0, 0, 255), width=2)
    for i in range(1, 4):
        cx = x + i * col_width
        draw.line([cx, y, cx, y + box_height], fill=(0, 0, 0, 255), width=1)
    sep_y = y + padding + header_height + 4
    draw.line([x, sep_y, x + width, sep_y], fill=(0, 0, 0, 255), width=1)

    for i, h in enumerate(headers):
        cx = x + i * col_width
        text_bbox = draw.textbbox((0, 0), h, font=header_font)
        tw = text_bbox[2] - text_bbox[0]
        tx = cx + (col_width - tw) // 2
        ty = y + padding
        text_draw.text((tx, ty), h, fill=(0, 0, 0, 255), font=header_font)

    base_y = sep_y + 6
    for i, v in enumerate(values):
        v_str = str(v)
        cx = x + i * col_width
        text_bbox = draw.textbbox((0, 0), v_str, font=value_font)
        tw = text_bbox[2] - text_bbox[0]
        tx = cx + (col_width - tw) // 2 - 4
        text_draw.text((tx, base_y - 2), v_str, fill=(0, 0, 0, 255), font=value_font)

    return y + box_height


def draw_bottom_row(
    draw: ImageDraw.ImageDraw,
    text_left: int,
    bottom_boundary: int,
    text_right: int,
    character_data: Dict[str, Any],
    text_draw: Optional[ImageDraw.ImageDraw] = None,
) -> int:
    """Draw heart + health pips and base size label. Returns top Y of this row."""
    text_draw = text_draw or draw
    margin = 6
    row_height = 44
    y = bottom_boundary - margin - row_height

    heart_font = get_font(32, bold=True)
    heart_y = y + 0
    heart_bbox = draw.textbbox((0, 0), "\u2665", font=heart_font)
    heart_w = heart_bbox[2] - heart_bbox[0]
    text_draw.text((text_left, heart_y), "\u2665", fill=(0, 0, 0, 255), font=heart_font)

    # Base size label
    base_map = {0: "30MM", 1: "40MM"}
    bs_val = base_map.get(character_data.get("baseSize", 0), "30MM")
    base_lbl_font = get_font(16, bold=True)
    base_val_font = get_font(18, bold=False)
    bb1 = draw.textbbox((0, 0), "Base:", font=base_lbl_font)
    bb2 = draw.textbbox((0, 0), bs_val, font=base_val_font)
    base_w = max(bb1[2] - bb1[0], bb2[2] - bb2[0])
    base_h = (bb1[3] - bb1[1]) + 2 + (bb2[3] - bb2[1])
    base_x = text_right - base_w + 10
    base_y_top = y + row_height - base_h - 14
    text_draw.text((base_x + (base_w - (bb1[2] - bb1[0])), base_y_top), "Base:", fill=(0, 0, 0, 255), font=base_lbl_font)
    val_y = base_y_top + (bb1[3] - bb1[1]) + 2
    text_draw.text((base_x + (base_w - (bb2[2] - bb2[0])), val_y), bs_val, fill=(0, 0, 0, 255), font=base_val_font)

    try:
        maxhp = int(character_data.get("maxhp") or 0)
    except Exception:
        maxhp = 0
    maxhp = max(0, min(15, maxhp))

    start_x = text_left + heart_w + 20
    end_x = base_x - 10
    if end_x <= start_x:
        return y
    total_slots = 15
    usable_width = end_x - start_x
    pitch = usable_width / (total_slots - 1)
    dot_d = max(12, min(24, int(pitch - 1)))
    stroke = 3
    cy = y + 8

    extra_gap_factor = 0.8
    total_gaps = 14 + 2 * extra_gap_factor
    pitch = usable_width / total_gaps
    big_gap = extra_gap_factor * pitch

    centers: List[float] = []
    x_cursor = float(start_x)
    for idx in range(15):
        centers.append(x_cursor)
        if idx < 14:
            x_cursor += pitch
            if idx in (4, 9):
                x_cursor += big_gap

    # Fill selected energy blips in blue (1-indexed positions)
    energy_blips_raw = str(character_data.get("energyblips") or "").strip()
    energy_positions: set[int] = set()
    for part in energy_blips_raw.split(","):
        part = part.strip()
        if part:
            try:
                energy_positions.add(int(part))
            except Exception:
                pass

    blue = (0, 158, 228, 255)
    for i in range(maxhp):
        cx = int(centers[i]) - dot_d // 2
        bbox = [cx, cy, cx + dot_d, cy + dot_d]
        if (i + 1) in energy_positions:
            inset = 2
            fill_box = [cx + inset, cy + inset, cx + dot_d - inset, cy + dot_d - inset]
            draw.ellipse(fill_box, fill=blue)
        draw.ellipse(bbox, outline=(0, 0, 0, 255), width=stroke)

    return y


def layout_and_draw_abilities(
    draw: ImageDraw.ImageDraw,
    abilities: List[Dict[str, Any]],
    area_x: int,
    area_y: int,
    area_w: int,
    area_bottom: int,
    text_draw: Optional[ImageDraw.ImageDraw] = None,
    tokens_draw: Optional[ImageDraw.ImageDraw] = None,
) -> int:
    """Draw passive, then activated, then arcane abilities."""
    if not abilities:
        return area_y

    text_draw = text_draw or draw
    tokens_draw = tokens_draw or text_draw  # Fall back to text_draw if not provided

    passive: List[Dict[str, Any]] = []
    activated: List[Dict[str, Any]] = []
    arcane: List[Dict[str, Any]] = []

    def inch_text_from_value(val: Any) -> str:
        if val is None or val == "":
            return ""
        try:
            if isinstance(val, (int, float)):
                return f' {int(val)}"'
            s = normalize_quotes(str(val))
            if re.fullmatch(r"\d+", s):
                s = f'{s}"'
            return f" {s}"
        except Exception:
            return ""

    # Sort abilities into categories
    for a in abilities:
        name = normalize_quotes(a.get("name", "Unnamed"))
        energy = a.get("energyCost")

        if energy is None:
            # Passive
            once_text = ""
            if a.get("oncePerTurn"):
                once_text = " Once Per Turn."
            elif a.get("oncePerGame"):
                once_text = " Once Per Game."
            passive_entry: Dict[str, Any] = {
                "name": name,
                "description": ensure_period(normalize_quotes(a.get("description") or "")),
                "once_text": once_text,
            }
            # Include ArcaneOutcome for passive abilities that have them (e.g., Reading the Runes)
            ao = a.get("ArcaneOutcome") or []
            if ao:
                passive_entry["ArcaneOutcome"] = ao
            passive.append(passive_entry)
        else:
            ao = a.get("ArcaneOutcome") or []
            if ao:
                # Arcane
                arcane.append({
                    "name": name,
                    "cost": energy,
                    "range_txt": inch_text_from_value(a.get("range")),
                    "pulse": bool(a.get("pulse")),
                    "tail": normalize_quotes(a.get("tail") or ""),
                    "description": ensure_period(normalize_quotes(a.get("description") or "")),
                    "subtext": normalize_quotes(a.get("subtext") or ""),
                    "ArcaneOutcome": ao,
                })
            else:
                # Activated
                activated.append({
                    "name": name,
                    "cost": energy,
                    "range_txt": inch_text_from_value(a.get("range")),
                    "pulse": bool(a.get("pulse")),
                    "tail": normalize_quotes(a.get("tail") or ""),
                    "description": ensure_period(normalize_quotes(a.get("description") or "")),
                    "catastrophe": normalize_quotes(a.get("catastrophe") or ""),
                })

    title_size = 24
    body_size = 23
    min_size = 12

    def compose_title_parts(a: Dict[str, Any]) -> Tuple[str, str]:
        base = a.get("name", "Unnamed")
        cost = a.get("cost")
        if isinstance(cost, (int, float)):
            base = f"{base} ({int(cost)})"
        rng_txt = a.get("range_txt") or ""
        if rng_txt:
            base += rng_txt
        if a.get("pulse"):
            base += " Pulse"
        tail_raw = a.get("tail") or ""
        if tail_raw:
            dash = " \u2013 " if (rng_txt or a.get("pulse")) else " - "
            tail = f"{dash}{tail_raw}"
        else:
            tail = ""
        return base, tail

    def non_cat_outcomes(ao_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [o for o in ao_list if not o.get("catastropheOutcome")]

    def first_cata(ao_list: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        for o in ao_list:
            if o.get("catastropheOutcome"):
                return o
        return None

    def suit_color(code: int) -> Tuple[int, int, int, int]:
        mapping = {1: (67, 168, 59, 255), 2: (0, 158, 228, 255), 4: (230, 0, 125, 255)}
        return mapping.get(code, (0, 0, 0, 255))

    def colors_for_code(code_int: Any) -> List[int]:
        try:
            c = int(code_int or 0)
        except Exception:
            c = 0
        cols: List[int] = []
        if c & 1:
            cols.append(1)
        if c & 2:
            cols.append(2)
        if c & 4:
            cols.append(4)
        return cols

    # Measurement pass to determine font sizes
    def measure(total_title_size: int, total_body_size: int) -> int:
        y = area_y
        title_font = get_font(total_title_size, bold=True)
        body_font = get_font(total_body_size, bold=False)
        line_gap = 8
        line_h = draw.textbbox((0, 0), "Ag", font=body_font)[3]

        def token_width_sequence(val_text: str, color_code: Any) -> int:
            pad_x = 3
            token_font_size = max(12, int(getattr(body_font, "size", 18) - 2))
            token_font = get_font(token_font_size, bold=False)
            or_w = draw.textbbox((0, 0), " or ", font=body_font)[2]
            colon_w = draw.textbbox((0, 0), ": ", font=body_font)[2]
            cols = colors_for_code(color_code)
            if not cols:
                return draw.textbbox((0, 0), f"{val_text}: ", font=body_font)[2]

            values = [v.strip() for v in val_text.split(" or ")]
            if len(cols) == 1 and len(values) > 1:
                width = 0
                for i, val in enumerate(values):
                    tb = draw.textbbox((0, 0), val, font=token_font)
                    text_w = tb[2] - tb[0]
                    token_h_est = max(min(line_h - 3, (tb[3] - tb[1]) + 8), (tb[3] - tb[1]) + 6)
                    token_w = max(text_w + pad_x * 2 - 2, token_h_est - 6)
                    width += token_w
                    if i < len(values) - 1:
                        width += or_w
                width += colon_w
                return width
            else:
                tb = draw.textbbox((0, 0), val_text, font=token_font)
                text_w = tb[2] - tb[0]
                token_h_est = max(min(line_h - 3, (tb[3] - tb[1]) + 8), (tb[3] - tb[1]) + 6)
                token_w = max(text_w + pad_x * 2 - 2, token_h_est - 6)
                width = 0
                for i in range(len(cols)):
                    width += token_w
                    if i < len(cols) - 2:
                        width += draw.textbbox((0, 0), ", ", font=body_font)[2]
                    elif i == len(cols) - 2:
                        width += or_w
                width += colon_w
                return width

        # Passive
        for a in passive:
            label = f"{a.get('name', 'Unnamed')}: "
            desc = a.get("description", "") or ""
            full = f"{label}{desc}".strip()
            lines = wrap_text(draw, full, body_font, area_w)
            for line in lines:
                lb = draw.textbbox((0, 0), line, font=body_font)
                y += (lb[3] - lb[1]) + 2
            tail = (a.get("once_text") or "").rstrip()
            if tail:
                italic_body = get_font(total_body_size, italic=True)
                for ln in wrap_text(draw, tail, italic_body, area_w):
                    lb = draw.textbbox((0, 0), ln, font=italic_body)
                    y += (lb[3] - lb[1]) + 2
            # Measure arcaneOutcomes for passive abilities (e.g., Reading the Runes)
            ao_list = a.get("ArcaneOutcome") or []
            if ao_list:
                non_cats = non_cat_outcomes(ao_list)
                cata = first_cata(ao_list)
                for nc in non_cats:
                    val = nc.get("cardValueRequirement")
                    token_val = str(val) if (isinstance(val, (int, float)) and val != 0) else (val if isinstance(val, str) else "X")
                    token_w = token_width_sequence(token_val, nc.get("cardColourRequirement", 0))
                    desc_text = (nc.get("outcomeText") or "").strip()
                    words = desc_text.split()
                    first_line = ""
                    max_first = max(10, area_w - token_w)
                    for w in words:
                        test = (first_line + " " + w).strip()
                        if draw.textbbox((0, 0), test, font=body_font)[2] <= max_first or not first_line:
                            first_line = test
                        else:
                            break
                    if first_line:
                        lb = draw.textbbox((0, 0), first_line, font=body_font)
                        y += (lb[3] - lb[1]) + 2
                    remaining = desc_text[len(first_line) :].lstrip()
                    for cont in wrap_text(draw, remaining, body_font, area_w):
                        lb = draw.textbbox((0, 0), cont, font=body_font)
                        y += (lb[3] - lb[1]) + 2
                if cata:
                    c_text_full = f"Catastrophe: {(cata.get('outcomeText') or '').strip()}"
                    for line in wrap_text(draw, c_text_full, body_font, area_w):
                        lb = draw.textbbox((0, 0), line, font=body_font)
                        y += (lb[3] - lb[1]) + 2
            y += line_gap
        if passive and (activated or arcane):
            y += 6

        # Activated
        for a in activated:
            base_text, _ = compose_title_parts(a)
            nb = draw.textbbox((0, 0), base_text, font=title_font)
            y += (nb[3] - nb[1]) + 4
            desc = a.get("description", "") or ""
            for line in wrap_text(draw, desc, body_font, area_w):
                lb = draw.textbbox((0, 0), line, font=body_font)
                y += (lb[3] - lb[1]) + 2
            c_text = (a.get("catastrophe") or "").strip()
            if c_text:
                c_full = f"Catastrophe: {ensure_period(c_text)}"
                for line in wrap_text(draw, c_full, body_font, area_w):
                    lb = draw.textbbox((0, 0), line, font=body_font)
                    y += (lb[3] - lb[1]) + 2
            y += line_gap
        if activated and arcane:
            y += 6

        # Arcane
        for a in arcane:
            base_text, _ = compose_title_parts(a)
            nb = draw.textbbox((0, 0), base_text, font=title_font)
            y += (nb[3] - nb[1]) + 4
            # Description (for activated abilities with arcaneOutcomes like Goblin Mischief)
            desc = (a.get("description") or "").strip()
            if desc:
                for line in wrap_text(draw, desc, body_font, area_w):
                    lb = draw.textbbox((0, 0), line, font=body_font)
                    y += (lb[3] - lb[1]) + 2
            subtext = (a.get("subtext") or "").strip()
            if subtext:
                italic_body = get_font(total_body_size, italic=True)
                for line in wrap_text(draw, subtext, italic_body, area_w):
                    lb = draw.textbbox((0, 0), line, font=italic_body)
                    y += (lb[3] - lb[1]) + 2
            ao_list = a.get("ArcaneOutcome") or []
            non_cats = non_cat_outcomes(ao_list)
            cata = first_cata(ao_list)
            for nc in non_cats:
                val = nc.get("cardValueRequirement")
                token_val = str(val) if (isinstance(val, (int, float)) and val != 0) else (val if isinstance(val, str) else "X")
                token_w = token_width_sequence(token_val, nc.get("cardColourRequirement", 0))
                desc_text = (nc.get("outcomeText") or "").strip()
                words = desc_text.split()
                first_line = ""
                max_first = max(10, area_w - token_w)
                for w in words:
                    test = (first_line + " " + w).strip()
                    if draw.textbbox((0, 0), test, font=body_font)[2] <= max_first or not first_line:
                        first_line = test
                    else:
                        break
                if first_line:
                    lb = draw.textbbox((0, 0), first_line, font=body_font)
                    y += (lb[3] - lb[1]) + 2
                remaining = desc_text[len(first_line) :].lstrip()
                for cont in wrap_text(draw, remaining, body_font, area_w):
                    lb = draw.textbbox((0, 0), cont, font=body_font)
                    y += (lb[3] - lb[1]) + 2
            if cata:
                c_text_full = f"Catastrophe: {(cata.get('outcomeText') or '').strip()}"
                for line in wrap_text(draw, c_text_full, body_font, area_w):
                    lb = draw.textbbox((0, 0), line, font=body_font)
                    y += (lb[3] - lb[1]) + 2
            y += line_gap
        return y

    # Find appropriate font sizes
    while True:
        needed = measure(title_size, body_size)
        if needed <= area_bottom - 2 or (title_size <= min_size and body_size <= min_size):
            break
        title_size = max(min_size, title_size - 1)
        body_size = max(min_size, body_size - 1)

    # Actual drawing
    y = area_y
    title_font = get_font(title_size, bold=True)
    body_font = get_font(body_size, bold=False)
    title_italic_font = get_font(max(min_size, title_size - 4), italic=True)
    body_italic_font = get_font(body_size, italic=True)
    line_gap = 8
    label_bold = get_font(body_size, bold=True)
    line_h = draw.textbbox((0, 0), "Ag", font=body_font)[3]

    def draw_token_sequence(x: int, y: int, value_text: str, color_code: Any, font: ImageFont.FreeTypeFont) -> int:
        # Colored tokens drawn to tokens_draw layer (no white glow applied)
        # Separators (", ", " or ", ": ") drawn to text_draw layer (gets white glow)
        pad_x, pad_y, radius = 3, 4, 5
        white = (255, 255, 255, 255)
        token_font_size = max(12, int(getattr(font, "size", 18) - 2))
        token_font = get_font(token_font_size, bold=False)
        token_bold_font = get_font(token_font_size, bold=True)

        cols = colors_for_code(color_code)
        if not cols:
            simple = f"{value_text}: "
            text_draw.text((x, y), simple, fill=(0, 0, 0, 255), font=token_bold_font)
            sb = text_draw.textbbox((0, 0), simple, font=token_bold_font)
            return x + (sb[2] - sb[0])

        values = [v.strip() for v in value_text.split(" or ")]
        if len(cols) == 1 and len(values) > 1:
            c = cols[0]
            for i, val in enumerate(values):
                tb = draw.textbbox((0, 0), val, font=token_font)
                tb_bold = draw.textbbox((0, 0), val, font=token_bold_font)
                text_w = tb[2] - tb[0]
                text_h = tb[3] - tb[1]
                token_h = max(min(line_h - 3, text_h + pad_y * 2), text_h + pad_y * 2 - 1)
                token_w = max(text_w + pad_x * 2 - 2, token_h - 6)
                ty = y + (line_h - token_h) // 2
                rect = [x, ty, x + token_w, ty + token_h]
                try:
                    tokens_draw.rounded_rectangle(rect, radius=radius, fill=suit_color(c))
                except Exception:
                    tokens_draw.rectangle(rect, fill=suit_color(c))
                tx = x + (token_w - (tb_bold[2] - tb_bold[0])) // 2 - tb_bold[0]
                ty_text = ty + (token_h - (tb_bold[3] - tb_bold[1])) // 2 - tb_bold[1]
                tokens_draw.text((tx, ty_text), val, fill=white, font=token_bold_font)
                x += token_w
                if i < len(values) - 1:
                    text_draw.text((x, y), " or ", fill=(0, 0, 0, 255), font=font)
                    x += text_draw.textbbox((0, 0), " or ", font=font)[2]
        else:
            tb = draw.textbbox((0, 0), value_text, font=token_font)
            tb_bold = draw.textbbox((0, 0), value_text, font=token_bold_font)
            text_w = tb[2] - tb[0]
            text_h = tb[3] - tb[1]
            token_h = max(min(line_h - 3, text_h + pad_y * 2), text_h + pad_y * 2 - 1)
            token_w = max(text_w + pad_x * 2 - 2, token_h - 6)
            ty = y + (line_h - token_h) // 2
            for i, c in enumerate(cols):
                rect = [x, ty, x + token_w, ty + token_h]
                try:
                    tokens_draw.rounded_rectangle(rect, radius=radius, fill=suit_color(c))
                except Exception:
                    tokens_draw.rectangle(rect, fill=suit_color(c))
                tx = x + (token_w - (tb_bold[2] - tb_bold[0])) // 2 - tb_bold[0]
                ty_text = ty + (token_h - (tb_bold[3] - tb_bold[1])) // 2 - tb_bold[1]
                tokens_draw.text((tx, ty_text), value_text, fill=white, font=token_bold_font)
                x += token_w
                if i < len(cols) - 2:
                    text_draw.text((x, y), ", ", fill=(0, 0, 0, 255), font=font)
                    x += text_draw.textbbox((0, 0), ", ", font=font)[2]
                elif i == len(cols) - 2:
                    text_draw.text((x, y), " or ", fill=(0, 0, 0, 255), font=font)
                    x += text_draw.textbbox((0, 0), " or ", font=font)[2]

        text_draw.text((x, y), ": ", fill=(0, 0, 0, 255), font=font)
        x += text_draw.textbbox((0, 0), ": ", font=font)[2]
        return x

    # Draw passives
    for a in passive:
        label = f"{a.get('name', 'Unnamed')}: "
        desc = a.get("description", "") or ""
        full = f"{label}{desc}".strip()
        lines = wrap_text(draw, full, body_font, area_w)
        last_w = 0
        last_y_start = y
        if lines:
            first = lines[0]
            label_w = draw.textbbox((0, 0), label, font=label_bold)[2]
            first_w = draw.textbbox((0, 0), first, font=body_font)[2]
            if label_w <= first_w:
                draw_text_with_special_symbols(text_draw, area_x, y, label, label_bold, (0, 0, 0, 255))
                draw_styled_text(text_draw, area_x + label_w, y, first[len(label) :], body_font, label_bold, (0, 0, 0, 255))
            else:
                draw_styled_text(text_draw, area_x, y, first, body_font, label_bold, (0, 0, 0, 255))
            lb = draw.textbbox((0, 0), first, font=body_font)
            y += (lb[3] - lb[1]) + 2
            last_w = lb[2] - lb[0]
            last_y_start = y - (lb[3] - lb[1]) - 2
        for line in lines[1:]:
            draw_styled_text(text_draw, area_x, y, line, body_font, label_bold, (0, 0, 0, 255))
            lb = draw.textbbox((0, 0), line, font=body_font)
            y += (lb[3] - lb[1]) + 2
            last_w = lb[2] - lb[0]
            last_y_start = y - (lb[3] - lb[1]) - 2
        tail = (a.get("once_text") or "").rstrip()
        if tail:
            tail_w = draw.textbbox((0, 0), tail, font=body_italic_font)[2]
            remaining = max(0, area_w - last_w)
            if tail_w <= remaining and last_w > 0:
                draw_text_with_special_symbols(text_draw, area_x + last_w, last_y_start, tail, body_italic_font, (0, 0, 0, 255), italic=True)
            else:
                draw_text_with_special_symbols(text_draw, area_x, y, tail, body_italic_font, (0, 0, 0, 255), italic=True)
                lb = draw.textbbox((0, 0), tail, font=body_italic_font)
                y += (lb[3] - lb[1]) + 2
        # Draw arcaneOutcomes for passive abilities (e.g., Reading the Runes)
        ao_list = a.get("ArcaneOutcome") or []
        if ao_list:
            non_cats = non_cat_outcomes(ao_list)
            cata = first_cata(ao_list)
            for nc in non_cats:
                val = nc.get("cardValueRequirement")
                token_val = str(val) if (isinstance(val, (int, float)) and val != 0) else (val if isinstance(val, str) else "X")
                start_x = draw_token_sequence(area_x, y, token_val, nc.get("cardColourRequirement", 0), body_font)
                available_first = area_w - (start_x - area_x)
                desc_text = (nc.get("outcomeText") or "").strip()
                words = desc_text.split()
                first_line = ""
                for w in words:
                    test = (first_line + " " + w).strip()
                    if draw.textbbox((0, 0), test, font=body_font)[2] <= available_first or not first_line:
                        first_line = test
                    else:
                        break
                if first_line:
                    draw_styled_text(text_draw, start_x, y, first_line, body_font, label_bold, (0, 0, 0, 255))
                    lb = draw.textbbox((0, 0), first_line, font=body_font)
                    y += (lb[3] - lb[1]) + 2
                remaining_text = desc_text[len(first_line) :].lstrip()
                for cont in wrap_text(draw, remaining_text, body_font, area_w):
                    draw_styled_text(text_draw, area_x, y, cont, body_font, label_bold, (0, 0, 0, 255))
                    lb = draw.textbbox((0, 0), cont, font=body_font)
                    y += (lb[3] - lb[1]) + 2
            if cata:
                c_text_full = f"Catastrophe: {ensure_period((cata.get('outcomeText') or '').strip())}"
                for line in wrap_text(draw, c_text_full, body_font, area_w):
                    draw_styled_text(text_draw, area_x, y, line, body_font, label_bold, (0, 0, 0, 255))
                    lb = draw.textbbox((0, 0), line, font=body_font)
                    y += (lb[3] - lb[1]) + 2
        y += line_gap
    if passive and (activated or arcane):
        draw.line([area_x + 12, y, area_x + area_w - 12, y], fill=(0, 0, 0, 255), width=1)
        y += 6

    # Draw activated
    for a in activated:
        base_text, tail_text = compose_title_parts(a)
        draw_text_with_special_symbols(text_draw, area_x, y, base_text, title_font, (0, 0, 0, 255))
        nb = draw.textbbox((0, 0), base_text, font=title_font)
        if tail_text:
            tx = area_x + (nb[2] - nb[0])
            draw_text_with_special_symbols(text_draw, tx, y, tail_text, title_italic_font, (0, 0, 0, 255), italic=True)
        y += (nb[3] - nb[1]) + 4
        desc = a.get("description", "") or ""
        for line in wrap_text(draw, desc, body_font, area_w):
            draw_styled_text(text_draw, area_x, y, line, body_font, label_bold, (0, 0, 0, 255))
            lb = draw.textbbox((0, 0), line, font=body_font)
            y += (lb[3] - lb[1]) + 2
        c_text = (a.get("catastrophe") or "").strip()
        if c_text:
            c_full = f"Catastrophe: {ensure_period(c_text)}"
            for line in wrap_text(draw, c_full, body_font, area_w):
                draw_styled_text(text_draw, area_x, y, line, body_font, label_bold, (0, 0, 0, 255))
                lb = draw.textbbox((0, 0), line, font=body_font)
                y += (lb[3] - lb[1]) + 2
        y += line_gap
    if activated and arcane:
        draw.line([area_x + 12, y, area_x + area_w - 12, y], fill=(0, 0, 0, 255), width=1)
        y += 6

    # Draw arcane
    for a in arcane:
        base_text, tail_text = compose_title_parts(a)
        draw_text_with_special_symbols(text_draw, area_x, y, base_text, title_font, (0, 0, 0, 255))
        nb = draw.textbbox((0, 0), base_text, font=title_font)
        if tail_text:
            tx = area_x + (nb[2] - nb[0])
            draw_text_with_special_symbols(text_draw, tx, y, tail_text, title_italic_font, (0, 0, 0, 255), italic=True)
        y += (nb[3] - nb[1]) + 4
        # Description (for activated abilities with arcaneOutcomes like Goblin Mischief)
        desc = (a.get("description") or "").strip()
        if desc:
            for line in wrap_text(draw, desc, body_font, area_w):
                draw_styled_text(text_draw, area_x, y, line, body_font, label_bold, (0, 0, 0, 255))
                lb = draw.textbbox((0, 0), line, font=body_font)
                y += (lb[3] - lb[1]) + 2
        subtext = (a.get("subtext") or "").strip()
        if subtext:
            for line in wrap_text(draw, subtext, body_italic_font, area_w):
                draw_text_with_special_symbols(text_draw, area_x, y, line, body_italic_font, (0, 0, 0, 255), italic=True)
                lb = draw.textbbox((0, 0), line, font=body_italic_font)
                y += (lb[3] - lb[1]) + 2
        ao_list = a.get("ArcaneOutcome") or []
        non_cats = non_cat_outcomes(ao_list)
        cata = first_cata(ao_list)
        for nc in non_cats:
            val = nc.get("cardValueRequirement")
            token_val = str(val) if (isinstance(val, (int, float)) and val != 0) else (val if isinstance(val, str) else "X")
            start_x = draw_token_sequence(area_x, y, token_val, nc.get("cardColourRequirement", 0), body_font)
            available_first = area_w - (start_x - area_x)
            desc_text = (nc.get("outcomeText") or "").strip()
            words = desc_text.split()
            first_line = ""
            for w in words:
                test = (first_line + " " + w).strip()
                if draw.textbbox((0, 0), test, font=body_font)[2] <= available_first or not first_line:
                    first_line = test
                else:
                    break
            if first_line:
                draw_styled_text(text_draw, start_x, y, first_line, body_font, label_bold, (0, 0, 0, 255))
                lb = draw.textbbox((0, 0), first_line, font=body_font)
                y += (lb[3] - lb[1]) + 2
            remaining = desc_text[len(first_line) :].lstrip()
            for cont in wrap_text(draw, remaining, body_font, area_w):
                draw_styled_text(text_draw, area_x, y, cont, body_font, label_bold, (0, 0, 0, 255))
                lb = draw.textbbox((0, 0), cont, font=body_font)
                y += (lb[3] - lb[1]) + 2
        if cata:
            c_text_full = f"Catastrophe: {ensure_period((cata.get('outcomeText') or '').strip())}"
            for line in wrap_text(draw, c_text_full, body_font, area_w):
                draw_styled_text(text_draw, area_x, y, line, body_font, label_bold, (0, 0, 0, 255))
                lb = draw.textbbox((0, 0), line, font=body_font)
                y += (lb[3] - lb[1]) + 2
        y += line_gap

    return y


# =============================================================================
# Card Renderer - Main card generation
# =============================================================================

class CardRenderer:
    """Renders complete character cards."""

    def __init__(self, paths: PathConfig):
        self.paths = paths

    def resize_image_keep_aspect(self, image: Image.Image, max_width: int, max_height: int) -> Image.Image:
        """Resize an image while keeping aspect ratio."""
        original_width, original_height = image.size
        scale_width = max_width / original_width
        scale_height = max_height / original_height
        scale = min(scale_width, scale_height)
        new_width = int(original_width * scale)
        new_height = int(original_height * scale)
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    def create_base_card(self, char_name: str, char_data: Dict[str, Any]) -> Optional[Image.Image]:
        """Create the base card with portrait and signature move."""
        canvas_width = 1200
        canvas_height = 700
        padding = 10

        canvas = Image.new("RGB", (canvas_width, canvas_height), "black")
        char_dir = self.paths.characters_images_dir / char_name

        if not char_dir.exists():
            print(f"Warning: Character directory not found: {char_dir}")
            return None

        char_tile_path = char_dir / "character_tile.png"
        background_path = char_dir / "background.png"

        if not char_tile_path.exists():
            print(f"Warning: character_tile.png not found for {char_name}")
            return None
        if not background_path.exists():
            print(f"Warning: background.png not found for {char_name}")
            return None

        try:
            char_tile = Image.open(char_tile_path).convert("RGB")
            background = Image.open(background_path).convert("RGB")

            char_tile_max_height = canvas_height - (padding * 2)
            char_tile_max_width = canvas_width
            char_tile_resized = self.resize_image_keep_aspect(char_tile, char_tile_max_width, char_tile_max_height)

            char_tile_x = padding
            char_tile_y = padding
            canvas.paste(char_tile_resized, (char_tile_x, char_tile_y))

            char_tile_flipped = char_tile_resized.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            flipped_crop_width = char_tile_flipped.width // 2
            char_tile_flipped_cropped = char_tile_flipped.crop((0, 0, flipped_crop_width, char_tile_flipped.height))
            flipped_x = char_tile_x + char_tile_resized.width
            canvas.paste(char_tile_flipped_cropped, (flipped_x, char_tile_y))

            background_start_x = flipped_x + char_tile_flipped_cropped.width
            available_background_width = canvas_width - background_start_x - padding
            background_max_height = canvas_height - (padding * 2)

            if available_background_width > 0:
                scale_height = background_max_height / background.height
                new_width = int(background.width * scale_height)
                new_height = int(background.height * scale_height)
                background_resized = background.resize((new_width, new_height), Image.Resampling.LANCZOS)

                if background_resized.width > available_background_width:
                    background_resized = background_resized.crop((0, 0, available_background_width, background_resized.height))

                background_x = background_start_x
                background_y = padding
                canvas.paste(background_resized, (background_x, background_y))

                # Black divider
                divider_width = 8
                divider_x = background_start_x
                divider_y = padding
                divider_height = background_max_height
                draw = ImageDraw.Draw(canvas)
                draw.rectangle([divider_x, divider_y, divider_x + divider_width, divider_y + divider_height], fill="black")

                # Signature move overlay
                signature_move = char_data.get("SignatureMove", {})
                overlay = Image.new("RGBA", (background_resized.width, background_resized.height), (255, 255, 255, 60))
                overlay_draw = ImageDraw.Draw(overlay)
                draw_signature_move_card(overlay_draw, signature_move, 0, 0, background_resized.width, background_resized.height, char_data)
                background_with_text = Image.alpha_composite(background_resized.convert("RGBA"), overlay)
                canvas.paste(background_with_text, (background_x, background_y), background_with_text)

                # Redraw divider
                draw.rectangle([divider_x, divider_y, divider_x + divider_width, divider_y + divider_height], fill="black")

            # Faction symbol
            faction_string = char_data.get("faction", "")
            if faction_string:
                faction_filename = get_faction_symbol_filename(faction_string)
                if faction_filename:
                    faction_path = self.paths.faction_symbols_dir / faction_filename
                    if faction_path.exists():
                        try:
                            faction_symbol = Image.open(faction_path).convert("RGBA")
                            faction_target_height = 140
                            faction_aspect_ratio = faction_symbol.width / faction_symbol.height
                            faction_new_width = int(faction_target_height * faction_aspect_ratio)
                            faction_resized = faction_symbol.resize((faction_new_width, faction_target_height), Image.Resampling.LANCZOS)
                            faction_x = background_start_x - faction_new_width
                            faction_y = padding
                            if faction_x >= padding:
                                canvas.paste(faction_resized, (faction_x, faction_y), faction_resized)
                        except Exception as e:
                            print(f"Warning: Could not load faction symbol for {char_name}: {e}")

            return canvas

        except Exception as e:
            print(f"Error creating base card for {char_name}: {e}")
            return None

    def add_left_side_text(self, base_image: Image.Image, char_data: Dict[str, Any]) -> Image.Image:
        """Add left side text overlay (stats, abilities, etc.) to the card."""
        img = base_image.convert("RGBA")
        textless_overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(textless_overlay)
        all_text_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
        text_draw = ImageDraw.Draw(all_text_layer)
        # Separate layer for colored tokens (no white glow)
        tokens_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
        tokens_draw = ImageDraw.Draw(tokens_layer)

        left_boundary, top_boundary, right_boundary, bottom_boundary = 10, 10, 745, 690
        text_margin = 6
        text_left = left_boundary + text_margin
        text_right = right_boundary - 30
        text_width = text_right - text_left

        black = (0, 0, 0, 255)
        character_name = char_data.get("name", "Unknown Character")

        def pick_name_fonts(main: str, sub: str, max_w: int) -> Tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
            for size in range(48, 12, -1):
                main_font = get_font(size, bold=True)
                sub_font = get_font(max(8, int(size * 0.80)), bold=True)
                w_main = draw.textbbox((0, 0), main, font=main_font)[2]
                w_comma = draw.textbbox((0, 0), ", ", font=main_font)[2]
                w_sub = draw.textbbox((0, 0), sub, font=sub_font)[2]
                if (w_main + w_comma + w_sub) <= max_w:
                    return main_font, sub_font
            return get_font(12, bold=True), get_font(10, bold=True)

        # Name (with optional subtitle after comma)
        if "," in character_name:
            main_name, subtitle = [p.strip() for p in character_name.split(",", 1)]
            name_font, subtitle_font = pick_name_fonts(main_name, subtitle, max(0, text_width - 50))
            name_x = text_left
            name_y = top_boundary + text_margin
            main_metrics = draw.textbbox((0, 0), "Ag", font=name_font)
            subtitle_metrics = draw.textbbox((0, 0), "Ag", font=subtitle_font)
            main_ascent = abs(main_metrics[1])
            subtitle_ascent = abs(subtitle_metrics[1])
            baseline_offset = max(0, main_ascent - subtitle_ascent) + 5
            text_draw.text((name_x, name_y), main_name, fill=black, font=name_font)
            main_bbox = draw.textbbox((0, 0), main_name, font=name_font)
            main_width = main_bbox[2] - main_bbox[0]
            comma_x = name_x + main_width
            text_draw.text((comma_x, name_y), ", ", fill=black, font=name_font)
            comma_w = draw.textbbox((0, 0), ", ", font=name_font)[2]
            subtitle_x = comma_x + comma_w
            subtitle_y = name_y + baseline_offset
            text_draw.text((subtitle_x, subtitle_y), subtitle, fill=black, font=subtitle_font)
            current_y = top_boundary + 60
        else:
            for size in range(48, 12, -1):
                font = get_font(size, bold=True)
                bbox = draw.textbbox((0, 0), character_name, font=font)
                if bbox[2] - bbox[0] <= max(0, text_width - 50):
                    name_font = font
                    break
            else:
                name_font = get_font(12, bold=True)
            name_x = text_left
            name_y = top_boundary + text_margin
            text_draw.text((name_x, name_y), character_name, fill=black, font=name_font)
            current_y = top_boundary + 60

        # Keywords
        keywords = char_data.get("keywords", "")
        if keywords and str(keywords).strip():
            formatted = str(keywords).replace(",", ", ").replace(", ,", ",").replace("  ", " ").strip()
            while ", ," in formatted:
                formatted = formatted.replace(", ,", ",")
            formatted = formatted.rstrip(", ")
            keywords_font = get_font(20, bold=False)
            keywords_y = current_y
            text_draw.text((name_x, keywords_y), formatted, fill=black, font=keywords_font)
            kw_bbox = draw.textbbox((0, 0), formatted, font=keywords_font)

            # Version
            try:
                version_val = char_data.get("version")
                version_int = int(version_val) if version_val is not None else None
            except Exception:
                version_int = None
            if version_int is not None and version_int >= 1:
                version_font = get_font(15, bold=False)
                v_text = f"v.{version_int}"
                v_y = keywords_y + (kw_bbox[3] - kw_bbox[1]) + 6
                text_draw.text((name_x, v_y), v_text, fill=black, font=version_font)
            current_y += (kw_bbox[3] - kw_bbox[1]) + 15

        # Stats box
        stats_area_width = int(text_width * 0.60)
        stats_x = text_left + (text_width - stats_area_width) // 2
        stats_y = current_y
        after_stats_y = draw_stats_box(draw, stats_x, stats_y, stats_area_width, char_data, text_draw=text_draw)

        # Bottom row
        bottom_row_top_y = draw_bottom_row(draw, text_left, bottom_boundary, text_right, char_data, text_draw=text_draw)

        # Abilities
        abilities_x = text_left
        abilities_y = after_stats_y + 10
        abilities_w = text_right - text_left
        abilities_bottom = bottom_row_top_y + 2
        layout_and_draw_abilities(draw, char_data.get("Ability", []), abilities_x, abilities_y, abilities_w, abilities_bottom, text_draw=text_draw, tokens_draw=tokens_draw)

        # Composite
        final_rgba = Image.alpha_composite(img, textless_overlay)

        # Determine glow parameters based on faction
        # Shades faction characters get stronger glow for better readability
        faction = char_data.get("faction", "")
        is_shades = "Shade" in faction

        if is_shades:
            # Stronger glow for Shades faction (darker backgrounds)
            max_filter_size = 7
            blur_radius = 5.0
            fade_multiplier = 0.85
        else:
            # Standard glow (increased from original values)
            max_filter_size = 5
            blur_radius = 3.5
            fade_multiplier = 0.65

        # Build glow behind text (but NOT behind colored tokens)
        try:
            text_alpha = all_text_layer.split()[3]
            expanded = text_alpha.filter(ImageFilter.MaxFilter(max_filter_size))
            blurred = expanded.filter(ImageFilter.GaussianBlur(radius=blur_radius))
            faded = blurred.point(lambda a: int(min(255, a) * fade_multiplier))
            white_glow = Image.new("RGBA", img.size, (255, 255, 255, 0))
            white_glow.putalpha(faded)
            final_rgba = Image.alpha_composite(final_rgba, white_glow)
            final_rgba = Image.alpha_composite(final_rgba, all_text_layer)
        except Exception:
            final_rgba = Image.alpha_composite(final_rgba, all_text_layer)

        # Add colored tokens layer on top (no white glow)
        final_rgba = Image.alpha_composite(final_rgba, tokens_layer)

        final_rgba = Image.alpha_composite(img, final_rgba)
        return final_rgba

    def apply_overlay(self, image: Image.Image, overlay_name: str) -> Image.Image:
        """Apply a custom overlay image on top of the card."""
        overlay_path = self.paths.overlays_dir / overlay_name
        if not overlay_path.exists():
            # Try common extensions
            for ext in [".png", ".PNG"]:
                alt_path = self.paths.overlays_dir / f"{overlay_name.rsplit('.', 1)[0]}{ext}"
                if alt_path.exists():
                    overlay_path = alt_path
                    break

        if not overlay_path.exists():
            print(f"Warning: Overlay not found: {overlay_name}")
            return image

        try:
            print(f"Applying overlay: {overlay_name}")
            top_overlay = Image.open(overlay_path).convert("RGBA")
            if top_overlay.size != image.size:
                top_overlay = top_overlay.resize(image.size, Image.Resampling.LANCZOS)
            return Image.alpha_composite(image.convert("RGBA"), top_overlay)
        except Exception as e:
            print(f"Warning: Failed to apply overlay: {e}")
            return image

    def generate_card(self, char_name: str, char_data: Dict[str, Any]) -> bool:
        """Generate a complete character card."""
        print(f"Processing {char_name}...")

        # Create base card
        base_card = self.create_base_card(char_name, char_data)
        if base_card is None:
            return False

        # Add left side text
        card_with_text = self.add_left_side_text(base_card, char_data)

        # Apply overlay if specified
        overlay_name = char_data.get("overlayImage")
        if overlay_name:
            card_with_text = self.apply_overlay(card_with_text, overlay_name)

        # Save final card
        self.paths.output_cards_dir.mkdir(parents=True, exist_ok=True)
        safe_filename = char_name.replace("/", "_").replace("\\", "_")
        output_path = self.paths.output_cards_dir / f"{safe_filename}_wide_card_with_text.png"
        card_with_text.convert("RGB").save(output_path, "PNG")
        print(f"Created card: {output_path}")
        return True


# =============================================================================
# PDF Generator (from generate_final_character_pdf.py)
# =============================================================================

class PDFGenerator:
    """Generates PDFs from character card images."""

    def __init__(self, paths: PathConfig):
        self.paths = paths

    def generate_all_pdfs(self, character_names: List[str]) -> None:
        """Generate all PDF layouts for the given characters."""
        if not REPORTLAB_AVAILABLE:
            print("Warning: reportlab is not installed. Skipping PDF generation.")
            print("Install with: pip install reportlab")
            return

        # Sort names alphabetically
        sorted_names = sorted(character_names, key=str.casefold)

        # Build name to path mapping
        name_to_path: Dict[str, Path] = {}
        for name in sorted_names:
            safe_name = name.replace("/", "_").replace("\\", "_")
            path = self.paths.output_cards_dir / f"{safe_name}_wide_card_with_text.png"
            if path.exists():
                name_to_path[name] = path

        if not name_to_path:
            print("No card images found for PDF generation.")
            return

        # Split into 5 chunks
        available_names = [n for n in sorted_names if n in name_to_path]

        def split_into_chunks(seq: List[str], num_chunks: int) -> List[List[str]]:
            n = len(seq)
            base = n // num_chunks
            rem = n % num_chunks
            chunks: List[List[str]] = []
            idx = 0
            for i in range(num_chunks):
                size = base + (1 if i < rem else 0)
                chunks.append(seq[idx : idx + size])
                idx += size
            return chunks

        chunks = split_into_chunks(available_names, 5)

        def first_alpha_lower(s: str) -> str:
            for ch in s:
                if ch.isalpha():
                    return ch.lower()
            return "misc"

        self.paths.output_pdfs_dir.mkdir(parents=True, exist_ok=True)

        # Settings for different layouts
        landscape_settings = {
            "page_size": landscape(letter),
            "columns": 2,
            "rows": 2,
            "image_width_pt": 120 * mm,
            "image_height_pt": 70 * mm,
            "gutter_x_pt": 5 * mm,
            "gutter_y_pt": 5 * mm,
            "title": "Character Wide Cards (Tarot 120x70mm, 2x2 Landscape)",
            "preserve_aspect": False,
        }

        scale = 90.0 / 70.0
        portrait_settings = {
            "page_size": portrait(letter),
            "columns": 1,
            "rows": 2,
            "image_width_pt": (120.0 * scale) * mm,
            "image_height_pt": 90.0 * mm,
            "gutter_x_pt": 5 * mm,
            "gutter_y_pt": 5 * mm,
            "title": "Character Wide Cards (Scaled to 90mm Height, 1x2 Portrait)",
            "preserve_aspect": False,
        }

        for chunk in chunks:
            if not chunk:
                continue

            start_label = first_alpha_lower(chunk[0])
            end_label = first_alpha_lower(chunk[-1])
            range_label = f"{start_label}-{end_label}"
            images_chunk = [name_to_path[n] for n in chunk]

            # Landscape 2x2
            out_landscape = self.paths.output_pdfs_dir / f"characters_tarot_120x70mm_2x2_landscape_{range_label}.pdf"
            self._generate_pdf_with_grid(images_chunk, out_landscape, **landscape_settings)
            print(f"Wrote PDF: {out_landscape}")

            # Portrait 1x2
            out_scaled = self.paths.output_pdfs_dir / f"characters_scaled_height_90mm_1x2_portrait_{range_label}.pdf"
            self._generate_pdf_with_grid(images_chunk, out_scaled, **portrait_settings)
            print(f"Wrote PDF: {out_scaled}")

            # Tight 1:1 pages
            out_tight = self.paths.output_pdfs_dir / f"characters_native_pixel_size_1up_{range_label}.pdf"
            self._generate_pdf_tight(images_chunk, out_tight)
            print(f"Wrote PDF: {out_tight}")

    def _generate_pdf_with_grid(
        self,
        images: List[Path],
        output_pdf: Path,
        page_size: Tuple[float, float],
        columns: int,
        rows: int,
        image_width_pt: float,
        image_height_pt: float,
        gutter_x_pt: float,
        gutter_y_pt: float,
        title: str,
        preserve_aspect: bool,
    ) -> None:
        """Generate PDF with grid layout."""
        if not images:
            return

        page_width_pt, page_height_pt = page_size
        total_images_width_pt = (columns * image_width_pt) + ((columns - 1) * gutter_x_pt)
        total_images_height_pt = (rows * image_height_pt) + ((rows - 1) * gutter_y_pt)
        left_margin_pt = (page_width_pt - total_images_width_pt) / 2.0
        bottom_margin_pt = (page_height_pt - total_images_height_pt) / 2.0

        xs = [left_margin_pt + c * (image_width_pt + gutter_x_pt) for c in range(columns)]
        ys = [bottom_margin_pt + r * (image_height_pt + gutter_y_pt) for r in range(rows)]
        ys_draw = list(reversed(ys))

        c = pdf_canvas.Canvas(str(output_pdf), pagesize=page_size, pageCompression=1)
        c.setTitle(title)
        c.setAuthor("moonsimdata")

        per_page = rows * columns
        for i in range(0, len(images), per_page):
            page_images = images[i : i + per_page]
            for idx, img_path in enumerate(page_images):
                col = idx % columns
                row = idx // columns
                x = xs[col]
                y = ys_draw[row]
                c.drawImage(str(img_path), x=x, y=y, width=image_width_pt, height=image_height_pt, preserveAspectRatio=preserve_aspect, anchor="sw")
            c.showPage()
        c.save()

    def _generate_pdf_tight(self, images: List[Path], output_pdf: Path) -> None:
        """Generate PDF with one image per page, sized to image."""
        if not images:
            return

        c = pdf_canvas.Canvas(str(output_pdf), pageCompression=1)
        c.setTitle("Character Wide Cards (tight pages, 1 per image)")
        c.setAuthor("moonsimdata")

        for img_path in images:
            ir = ImageReader(str(img_path))
            width_px, height_px = ir.getSize()
            c.setPageSize((width_px, height_px))
            c.drawImage(str(img_path), x=0, y=0, width=width_px, height=height_px, preserveAspectRatio=False, anchor="sw")
            c.showPage()
        c.save()


# =============================================================================
# Main CLI
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate character cards from unified_moonstone_data.yaml",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_character_cards.py -a          # Generate all characters + PDFs
  python generate_character_cards.py -c "Liv"    # Generate single character
  python generate_character_cards.py -p          # PDF only (from existing images)
  python generate_character_cards.py -a --no-pdf # Generate cards only, no PDFs
  python generate_character_cards.py --list      # List all available characters
""",
    )

    parser.add_argument("-c", "--character", help="Generate card for a single character (by name)")
    parser.add_argument("-a", "--all", action="store_true", help="Generate cards for all characters")
    parser.add_argument("-p", "--pdf-only", action="store_true", help="Skip image generation, only generate PDFs")
    parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation")
    parser.add_argument("-y", "--yaml", help="Path to unified_moonstone_data.yaml (default: ../unified_moonstone_data.yaml)")
    parser.add_argument("--list", action="store_true", help="List all available characters")

    args = parser.parse_args()

    # Setup paths
    script_dir = Path(__file__).resolve().parent
    paths = PathConfig.from_script_dir(script_dir)

    if args.yaml:
        paths.unified_yaml = Path(args.yaml)

    # Load data
    loader = DataLoader(paths.unified_yaml)
    if not loader.load():
        sys.exit(1)

    # List characters
    if args.list:
        print("Available characters:")
        for name in sorted(loader.get_character_names(), key=str.casefold):
            print(f"  - {name}")
        return

    # Validate arguments
    if not args.all and not args.character and not args.pdf_only:
        parser.print_help()
        print("\nError: Must specify -a/--all, -c/--character, or -p/--pdf-only")
        sys.exit(1)

    renderer = CardRenderer(paths)
    pdf_generator = PDFGenerator(paths)

    # Generate cards
    if args.pdf_only:
        # PDF only mode
        character_names = loader.get_character_names()
    elif args.all:
        # Generate all cards
        character_names = loader.get_character_names()
        successful = 0
        total = len(character_names)

        for char_name in character_names:
            char_data = loader.build_character_for_rendering(char_name)
            if char_data and renderer.generate_card(char_name, char_data):
                successful += 1

        print(f"\nGenerated {successful}/{total} character cards.")
    elif args.character:
        # Generate single character
        char_data = loader.build_character_for_rendering(args.character)
        if not char_data:
            print(f"Error: Character not found: {args.character}")
            sys.exit(1)
        if not renderer.generate_card(args.character, char_data):
            sys.exit(1)
        character_names = [args.character]

    # Generate PDFs
    if not args.no_pdf:
        if args.pdf_only:
            character_names = loader.get_character_names()
        pdf_generator.generate_all_pdfs(character_names)
        print("\nPDF generation complete.")


if __name__ == "__main__":
    main()
