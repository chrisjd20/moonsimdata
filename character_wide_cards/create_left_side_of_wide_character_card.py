#!/usr/bin/env python3
"""
Create left side text overlay for wide character cards by adding character stats,
abilities, and other text elements to the left side of existing wide cards.
"""

import json
import os
import re
import sys
from typing import Dict, List, Tuple, Any

from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

# Global cache for YAML ability definitions (normalized-name keyed)
ABILITIES_YAML: Dict[str, Dict[str, Any]] = {}


def get_font(size, bold=False, italic=False):
    """Get font with fallback options.

    Attempts to pick an italic face when italic=True. Falls back gracefully to
    a regular face if an italic face is unavailable on the system.
    """
    # Preferred families (regular/bold/italic variants when available)
    if italic and bold:
        preferred = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
            "/System/Library/Fonts/Verdana Italic.ttf",
            "C:/Windows/Fonts/verdana.ttf",
        ]
    elif italic:
        preferred = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
            "/System/Library/Fonts/Verdana Italic.ttf",
            "C:/Windows/Fonts/verdana.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    elif bold:
        preferred = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/Verdana Bold.ttf",
            "C:/Windows/Fonts/verdana.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    else:
        preferred = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/verdana.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/System/Library/Fonts/Verdana.ttf",
            "C:/Windows/Fonts/verdana.ttf",
        ]

    for font_path in preferred:
        try:
            if os.path.exists(font_path):
                try:
                    return ImageFont.truetype(font_path, size, layout_engine=ImageFont.Layout.BASIC)  # type: ignore[attr-defined]
                except Exception:
                    return ImageFont.truetype(font_path, size)
        except Exception:
            continue

    # Fallback to default font
    try:
        return ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()


def get_character_name_font(character_name, max_width, draw):
    """Get character name font that fits within max_width, starting large and scaling down."""
    for size in range(48, 12, -1):
        font = get_font(size, bold=True)
        bbox = draw.textbbox((0, 0), character_name, font=font)
        text_width = bbox[2] - bbox[0]
        if text_width <= max_width:
            return font
    return get_font(12, bold=True)


# ---------- Helpers for left-side layout ----------

def wrap_text(draw, text, font, max_width):
    """Wrap text into lines that fit within max_width without breaking words.

    Uses special-width handling for the '∅' glyph so the measurement reflects its
    slightly larger rendered size.
    """
    if not text:
        return []
    def measure_width(t: str) -> int:
        total = 0
        for ch in t:
            use_font = font
            if ch == '∅':
                use_font = get_font(max(8, int(getattr(font, 'size', 16) * 1.25)))
            bb = draw.textbbox((0, 0), ch, font=use_font)
            total += (bb[2] - bb[0])
        return total
    words = text.split(' ')
    lines: List[str] = []
    line = ""
    for w in words:
        if line:
            test = line + " " + w
        else:
            test = w
        if measure_width(test) <= max_width or not line:
            line = test
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def draw_text_with_special_symbols(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, base_font: ImageFont.FreeTypeFont, fill: Tuple[int, int, int, int], special_scale: float = 1.25, italic: bool = False) -> int:
    """Draw text but render '∅' glyph slightly larger. Returns new x after drawing.

    We keep layout simple by drawing sequential segments. This is primarily a visual
    enhancement; wrapping continues to be based on normal text metrics.
    """
    if not text:
        return x
    special_font = get_font(max(8, int(getattr(base_font, 'size', 16) * special_scale)), italic=italic)
    cursor_x = x
    for ch in text:
        if ch == '∅':
            tb = draw.textbbox((0, 0), ch, font=special_font)
            # Baseline align: nudge down slightly
            ascent_base = abs(draw.textbbox((0, 0), "Ag", font=base_font)[1])
            ascent_spec = abs(draw.textbbox((0, 0), "Ag", font=special_font)[1])
            # Move the symbol up a bit compared to previous version
            baseline_offset = max(0, (ascent_base - ascent_spec) - 1)
            draw.text((cursor_x, y + baseline_offset), ch, fill=fill, font=special_font)
            cursor_x += (tb[2] - tb[0])
        else:
            draw.text((cursor_x, y), ch, fill=fill, font=base_font)
            tb = draw.textbbox((0, 0), ch, font=base_font)
            cursor_x += (tb[2] - tb[0])
    return cursor_x


def draw_styled_text(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, base_font: ImageFont.FreeTypeFont, bold_font: ImageFont.FreeTypeFont, fill: Tuple[int, int, int, int]) -> int:
    """Draw text with two inline styles:
    - scale '∅' slightly larger (delegates to draw_text_with_special_symbols)
    - bold any tag name between '[' and ':' (e.g., [Protection: ...])
    Returns new x after drawing.
    """
    cursor_x = x
    pos = 0
    while pos < len(text):
        lb = text.find('[', pos)
        colon = text.find(':', lb + 1) if lb != -1 else -1
        if lb != -1 and colon != -1 and lb >= pos:
            # before '['
            cursor_x = draw_text_with_special_symbols(draw, cursor_x, y, text[pos:lb], base_font, fill)
            # draw '[', then bold tag, then ':'
            cursor_x = draw_text_with_special_symbols(draw, cursor_x, y, "[", base_font, fill)
            tag = text[lb + 1:colon]
            if tag:
                cursor_x = draw_text_with_special_symbols(draw, cursor_x, y, tag, bold_font, fill)
            cursor_x = draw_text_with_special_symbols(draw, cursor_x, y, ":", base_font, fill)
            pos = colon + 1
        else:
            cursor_x = draw_text_with_special_symbols(draw, cursor_x, y, text[pos:], base_font, fill)
            break
    return cursor_x


# ---------- YAML helpers ----------

def normalize_quotes(s: str) -> str:
    if not isinstance(s, str):
        return s
    return (
        s.replace("\u201c", '"').replace("\u201d", '"')
        .replace("\u2018", "'").replace("\u2019", "'")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u00a0", " ")
        .replace("”", '"').replace("“", '"').replace("’", "'").replace("‘", "'")
    )


def norm_key(s: str) -> str:
    s = normalize_quotes(s or "").strip().lower()
    s = re.sub(r"[\"'“”‘’]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


def load_yaml_abilities(yaml_path: str) -> Dict[str, Dict[str, Any]]:
    global ABILITIES_YAML
    ABILITIES_YAML = {}
    if not os.path.exists(yaml_path):
        return {}
    if yaml is None:
        print("Warning: PyYAML not installed; cannot read abilities_strings.yaml. Falling back to JSON data only.")
        return {}
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for key, val in (data.items() if isinstance(data, dict) else []):
            if not isinstance(val, dict):
                continue
            nkey = norm_key(str(key))
            val = dict(val)
            val.setdefault("type", None)
            val.setdefault("isPulse", False)
            val.setdefault("textToRightInItalics", None)
            val.setdefault("arcaneSubText", None)
            val.setdefault("activatedText", None)
            val.setdefault("arcaneOutcomes", None)
            val.setdefault("catastrophe", None)
            val.setdefault("range", None)
            val.setdefault("cost", None)
            val["__name"] = normalize_quotes(str(key))
            ABILITIES_YAML[nkey] = val
        return ABILITIES_YAML
    except Exception as e:
        print(f"Warning: Failed to load YAML abilities from {yaml_path}: {e}")
        return {}


def parse_yaml_outcome(outcome_str: str) -> Tuple[str, int, str]:
    """Parse a YAML arcane outcome string like 'gX,bX: Target suffers X Dmg.'
    Returns (value_text, color_mask, description).
    color bitmask: green=1, blue=2, red=4.
    
    For multiple values of the same color (e.g. 'b2,b3'), returns "2 or 3".
    """
    s = normalize_quotes(outcome_str or "").strip()
    if ":" in s:
        left, right = s.split(":", 1)
        desc = right.strip()
    else:
        left, desc = s, ""
    tokens = [t.strip() for t in left.split(",") if t.strip()]
    mask = 0
    value_text = "X"
    values = []  # Collect all values
    for tok in tokens:
        if not tok:
            continue
        c = tok[0].lower()
        v = tok[1:].strip() or "X"
        values.append(v)
        if c == "g":
            mask |= 1
        elif c == "b":
            mask |= 2
        elif c == "r":
            mask |= 4
    # Build value_text: join unique values with " or "
    if values:
        unique_values = []
        seen = set()
        for v in values:
            if v not in seen:
                unique_values.append(v)
                seen.add(v)
        value_text = " or ".join(unique_values)
    return value_text, mask, desc


# ---------- Text helpers ----------

def ensure_period(text: str) -> str:
    """Ensure text ends with a period. Leave empty strings unchanged."""
    s = (text or "").rstrip()
    if not s:
        return s
    if s.endswith(('.', '!', '?', '"', "'")):
        return s
    return s + "."


def draw_stats_box(draw, x, y, width, character_data, text_draw_override=None):
    """Draw a boxed stats area (Melee, Range, Arcane, Evade). Returns bottom y."""
    text_draw = text_draw_override or draw
    headers = ["Melee", "Range", "Arcane", "Evade"]
    values = [
        character_data.get('melee', ''),
        character_data.get('range', ''),
        character_data.get('arcane', ''),
        character_data.get('evade', ''),
    ]
    try:
        if isinstance(values[1], (int, float)):
            values[1] = f"{int(values[1])}\""
    except Exception:
        pass

    # Append '+' to Evade if 1 or greater (prefix form '+N')
    try:
        ev_val_raw = character_data.get('evade', '')
        if type(ev_val_raw) == str:
            values[3] = ev_val_raw
        else:
            ev_int = int(ev_val_raw)
            if ev_int >= 1:
                values[3] = f"+{ev_int}"
    except Exception:
        pass

    # Headers not bold, values bold
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
        # Slight left and upward nudge for better visual balance
        tx = cx + (col_width - tw) // 2 - 4
        text_draw.text((tx, base_y - 2), v_str, fill=(0, 0, 0, 255), font=value_font)

    return y + box_height


def draw_bottom_row(draw, text_left, bottom_boundary, text_right, character_data, text_draw_override=None):
    """Draw heart + up-to-15 health pips and base size label. Returns top Y of this row."""
    text_draw = text_draw_override or draw
    margin = 6
    row_height = 44
    y = bottom_boundary - margin - row_height

    heart_font = get_font(32, bold=True)
    heart_y = y + 0
    heart_bbox = draw.textbbox((0, 0), "\u2665", font=heart_font)
    heart_w = heart_bbox[2] - heart_bbox[0]
    text_draw.text((text_left, heart_y), "\u2665", fill=(0, 0, 0, 255), font=heart_font)

    # Right-aligned two-line base block
    base_map = {0: "30MM", 1: "40MM"}
    bs_val = base_map.get(character_data.get('baseSize', 0), "30MM")
    base_lbl_font = get_font(16, bold=True)
    base_val_font = get_font(18, bold=False)
    bb1 = draw.textbbox((0, 0), "Base:", font=base_lbl_font)
    bb2 = draw.textbbox((0, 0), bs_val, font=base_val_font)
    base_w = max(bb1[2] - bb1[0], bb2[2] - bb2[0])
    base_h = (bb1[3] - bb1[1]) + 2 + (bb2[3] - bb2[1])
    # Align tight to the bottom-right inside the text area
    base_x = text_right - base_w + 10
    base_y_top = y + row_height - base_h - 14
    text_draw.text((base_x + (base_w - (bb1[2] - bb1[0])), base_y_top), "Base:", fill=(0, 0, 0, 255), font=base_lbl_font)
    val_y = base_y_top + (bb1[3] - bb1[1]) + 2
    text_draw.text((base_x + (base_w - (bb2[2] - bb2[0])), val_y), bs_val, fill=(0, 0, 0, 255), font=base_val_font)

    try:
        maxhp = int(character_data.get('maxhp') or 0)
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

    centers = []
    x_cursor = start_x
    for idx in range(15):
        centers.append(x_cursor)
        if idx < 14:
            x_cursor += pitch
            if idx in (4, 9):
                x_cursor += big_gap

    # Fill selected energy blips in blue (1-indexed positions)
    energy_blips_raw = str(character_data.get('energyblips') or "").strip()
    energy_positions = set()
    for part in energy_blips_raw.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            energy_positions.add(int(part))
        except Exception:
            continue

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


def layout_and_draw_abilities(draw, abilities, yaml_map, area_x, area_y, area_w, area_bottom, text_draw_override=None):
    """Draw passive, then activated, then arcane abilities, using YAML overrides when present."""
    if not abilities:
        return area_y

    # Use a separate draw object for rendering text if provided (to support post effects)
    text_draw = text_draw_override or draw

    passive: List[Dict[str, Any]] = []
    activated: List[Dict[str, Any]] = []
    arcane: List[Dict[str, Any]] = []

    def inch_text_from_yaml(val):
        if val is None or val == "":
            return ""
        try:
            if isinstance(val, (int, float)):
                return f" {int(val)}\""
            s = normalize_quotes(str(val))
            if re.fullmatch(r"\d+", s):
                s = f"{s}\""
            return f" {s}"
        except Exception:
            return ""

    def build_from_yaml(name: str, base_obj: Dict[str, Any], ydef: Dict[str, Any]):
        t = (ydef.get("type") or "").strip().lower()
        if t == "activated":
            activated.append({
                "name": name,
                "cost": ydef.get("cost"),
                "range_txt": inch_text_from_yaml(ydef.get("range")),
                "pulse": bool(ydef.get("isPulse")),
                "tail": normalize_quotes(ydef.get("textToRightInItalics") or ""),
                "description": ensure_period(normalize_quotes(ydef.get("activatedText") or "")),
                # Some activated abilities can have a catastrophe in YAML
                "catastrophe": normalize_quotes(ydef.get("catastrophe") or ""),
            })
        elif t == "arcane":
            outcomes_src = ydef.get("arcaneOutcomes") or []
            outcomes: List[Dict[str, Any]] = []
            for item in outcomes_src:
                if not isinstance(item, str):
                    continue
                vtxt, mask, desc = parse_yaml_outcome(item)
                outcomes.append({
                    "cardValueRequirement": vtxt,
                    "cardColourRequirement": mask,
                    "outcomeText": ensure_period(normalize_quotes(desc)),
                    "catastropheOutcome": False,
                })
            cata = ydef.get("catastrophe")
            if cata:
                outcomes.append({
                    "catastropheOutcome": True,
                    "outcomeText": ensure_period(normalize_quotes(str(cata))),
                })
            arcane.append({
                "name": name,
                "cost": ydef.get("cost"),
                "range_txt": inch_text_from_yaml(ydef.get("range")),
                "pulse": bool(ydef.get("isPulse")),
                "tail": normalize_quotes(ydef.get("textToRightInItalics") or ""),
                "subtext": normalize_quotes(ydef.get("arcaneSubText") or ""),
                "ArcaneOutcome": outcomes,
            })
        else:
            # Passive: include once-per flags if present on base_obj
            once_text = ""
            try:
                if base_obj.get("oncePerTurn"):
                    once_text = " Once Per Turn."
                elif base_obj.get("oncePerGame"):
                    once_text = " Once Per Game."
            except Exception:
                once_text = ""
            passive.append({
                "name": name,
                "description": ensure_period(normalize_quotes(base_obj.get("description") or base_obj.get("text") or "")),
                "once_text": once_text,
            })

    for a in abilities:
        name = normalize_quotes(a.get("name", "Unnamed"))
        ydef = yaml_map.get(norm_key(name)) if yaml_map else None
        if ydef:
            build_from_yaml(ydef.get("__name", name), a, ydef)
        else:
            energy = a.get("energyCost")
            if energy is None:
                # Passive w/ optional once-per flags from JSON
                once_text = ""
                try:
                    if a.get("oncePerTurn"):
                        once_text = " Once Per Turn."
                    elif a.get("oncePerGame"):
                        once_text = " Once Per Game."
                except Exception:
                    once_text = ""
                passive.append({
                    "name": name,
                    "description": ensure_period(normalize_quotes(a.get("description") or a.get("text") or "")),
                    "once_text": once_text,
                })
            else:
                ao = a.get("ArcaneOutcome") or []
                if ao:
                    outs: List[Dict[str, Any]] = []
                    for item in ao:
                        if not isinstance(item, dict):
                            continue
                        outs.append({
                            "cardValueRequirement": item.get("cardValueRequirement"),
                            "cardColourRequirement": item.get("cardColourRequirement", 0),
                            "outcomeText": ensure_period(normalize_quotes(item.get("outcomeText") or "")),
                            "catastropheOutcome": bool(item.get("catastropheOutcome")),
                        })
                    arcane.append({
                        "name": name,
                        "cost": energy,
                        "range_txt": inch_text_from_yaml(a.get("range")),
                        "pulse": bool(a.get("pulse")),
                        "tail": normalize_quotes(a.get("tail") or ""),
                        "ArcaneOutcome": outs,
                    })
                else:
                    activated.append({
                        "name": name,
                        "cost": energy,
                        "range_txt": inch_text_from_yaml(a.get("range")),
                        "pulse": bool(a.get("pulse")),
                        "tail": normalize_quotes(a.get("tail") or ""),
                        "description": ensure_period(normalize_quotes(a.get("description") or a.get("text") or "")),
                    })

    title_size = 24
    body_size = 23
    min_size = 12

    def compose_title_parts(a):
        """Return (base_text, tail_text) where tail is italic-friendly and smaller.

        The base_text contains name, (cost), range text and Pulse. The tail_text
        contains the prefixed dash and the YAML `textToRightInItalics` content,
        intended to be rendered with a smaller italic font.
        """
        base = a.get('name', 'Unnamed')
        cost = a.get('cost')
        if isinstance(cost, (int, float)):
            base = f"{base} ({int(cost)})"
        rng_txt = a.get('range_txt') or ""
        if rng_txt:
            base += rng_txt
        if a.get('pulse'):
            base += " Pulse"
        tail_raw = a.get('tail') or ""
        if tail_raw:
            dash = " – " if (rng_txt or a.get('pulse')) else " - "
            tail = f"{dash}{tail_raw}"
        else:
            tail = ""
        return base, tail

    def non_cat_outcomes(ao_list):
        return [o for o in (ao_list or []) if not o.get('catastropheOutcome')]

    def first_cata(ao_list):
        for o in ao_list or []:
            if o.get('catastropheOutcome'):
                return o
        return None

    def measure(total_title_size, total_body_size):
        y = area_y
        title_font = get_font(total_title_size, bold=True)
        body_font = get_font(total_body_size, bold=False)
        line_gap = 8
        line_h = draw.textbbox((0, 0), "Ag", font=body_font)[3]

        def colors_for_code(code_int):
            try:
                c = int(code_int or 0)
            except Exception:
                c = 0
            cols = []
            if c & 1:
                cols.append(1)
            if c & 2:
                cols.append(2)
            if c & 4:
                cols.append(4)
            return cols

        def token_width_sequence(val_text, color_code):
            # Mirror draw_token_sequence geometry with a slightly smaller token font
            pad_x = 3
            token_font_size = max(12, int(getattr(body_font, 'size', 18) - 2))
            token_font = get_font(token_font_size, bold=False)
            
            punct_w = draw.textbbox((0, 0), ", ", font=body_font)[2]
            or_w = draw.textbbox((0, 0), " or ", font=body_font)[2]
            colon_w = draw.textbbox((0, 0), ": ", font=body_font)[2]
            cols = colors_for_code(color_code)
            
            if not cols:
                return draw.textbbox((0, 0), f"{val_text}: ", font=body_font)[2]
            
            # Split value_text by " or " to handle multiple values like "2 or 3"
            values = [v.strip() for v in val_text.split(" or ")]
            
            # If we have a single color and multiple values, calculate width for multiple tokens
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
                # Original logic: one token per color
                tb = draw.textbbox((0, 0), val_text, font=token_font)
                text_w = tb[2] - tb[0]
                token_h_est = max(min(line_h - 3, (tb[3] - tb[1]) + 8), (tb[3] - tb[1]) + 6)
                token_w = max(text_w + pad_x * 2 - 2, token_h_est - 6)
                
                width = 0
                for i in range(len(cols)):
                    width += token_w
                    if i < len(cols) - 2:
                        width += punct_w
                    elif i == len(cols) - 2:
                        width += or_w
                width += colon_w
                return width

        # Passive
        for a in passive:
            label = f"{a.get('name', 'Unnamed')}: "
            desc = (a.get('description', '') or '')
            full = f"{label}{desc}".strip()
            lines = wrap_text(draw, full, body_font, area_w)
            last_w = 0
            last_h = 0
            for idx, line in enumerate(lines):
                lb = draw.textbbox((0, 0), line, font=body_font)
                y += (lb[3] - lb[1]) + 2
                if idx == len(lines) - 1:
                    last_w = lb[2] - lb[0]
                    last_h = lb[3] - lb[1]
            # Measure optional italic once-per tail
            tail = a.get('once_text') or ''
            # Preserve leading space so it doesn't butt up against the final word
            tail = tail.rstrip()
            if tail:
                italic_body = get_font(total_body_size, italic=True)
                remaining = max(0, area_w - last_w)
                if draw.textbbox((0, 0), tail, font=italic_body)[2] <= remaining:
                    # Fits on same line: no extra height
                    pass
                else:
                    # Will wrap to at least one new line
                    for ln in wrap_text(draw, tail, italic_body, area_w):
                        lb = draw.textbbox((0, 0), ln, font=italic_body)
                        y += (lb[3] - lb[1]) + 2
            y += line_gap
        if passive and (activated or arcane):
            y += 6

        # Activated
        for a in activated:
            base_text, _tail = compose_title_parts(a)
            nb = draw.textbbox((0, 0), base_text, font=title_font)
            y += (nb[3] - nb[1]) + 4
            desc = a.get('description', '') or ''
            for line in wrap_text(draw, desc, body_font, area_w):
                lb = draw.textbbox((0, 0), line, font=body_font)
                y += (lb[3] - lb[1]) + 2
            # Optional catastrophe for activated from YAML
            c_text = (a.get('catastrophe') or '').strip()
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
            base_text, _tail = compose_title_parts(a)
            nb = draw.textbbox((0, 0), base_text, font=title_font)
            y += (nb[3] - nb[1]) + 4
            # Optional subtext (italic), before outcomes
            subtext = (a.get('subtext') or '').strip()
            if subtext:
                italic_body = get_font(total_body_size, italic=True)
                for line in wrap_text(draw, subtext, italic_body, area_w):
                    lb = draw.textbbox((0, 0), line, font=italic_body)
                    y += (lb[3] - lb[1]) + 2
            ao_list = a.get('ArcaneOutcome') or []
            non_cats = non_cat_outcomes(ao_list)
            cata = first_cata(ao_list)
            for nc in non_cats:
                val = nc.get('cardValueRequirement')
                token_val = str(val) if (isinstance(val, (int, float)) and val != 0) else (val if isinstance(val, str) else 'X')
                token_w = token_width_sequence(token_val, nc.get('cardColourRequirement', 0))
                desc_text = (nc.get('outcomeText') or '').strip()
                # First line with reduced width
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
                remaining = desc_text[len(first_line):].lstrip()
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

    while True:
        needed = measure(title_size, body_size)
        if needed <= area_bottom - 2 or (title_size <= min_size and body_size <= min_size):
            break
        title_size = max(min_size, title_size - 1)
        body_size = max(min_size, body_size - 1)

    y = area_y
    title_font = get_font(title_size, bold=True)
    body_font = get_font(body_size, bold=False)
    title_italic_font = get_font(max(min_size, title_size - 4), italic=True)
    body_italic_font = get_font(body_size, italic=True)
    line_gap = 8

    label_bold = get_font(body_size, bold=True)
    for a in passive:
        label = f"{a.get('name', 'Unnamed')}: "
        desc = (a.get('description', '') or '')
        full = f"{label}{desc}".strip()
        lines = wrap_text(draw, full, body_font, area_w)
        last_w = 0
        last_h = 0
        last_y_start = y
        if lines:
            first = lines[0]
            label_w = draw.textbbox((0, 0), label, font=label_bold)[2]
            first_w = draw.textbbox((0, 0), first, font=body_font)[2]
            if label_w <= first_w:
                # Draw label and the remainder of the first line with styling
                draw_text_with_special_symbols(text_draw, area_x, y, label, label_bold, (0, 0, 0, 255))
                draw_styled_text(text_draw, area_x + label_w, y, first[len(label):], body_font, label_bold, (0, 0, 0, 255))
            else:
                draw_styled_text(text_draw, area_x, y, first, body_font, label_bold, (0, 0, 0, 255))
            lb = draw.textbbox((0, 0), first, font=body_font)
            y += (lb[3] - lb[1]) + 2
            last_w = lb[2] - lb[0]
            last_h = lb[3] - lb[1]
            last_y_start = y - last_h - 2
        for line in lines[1:]:
            draw_styled_text(text_draw, area_x, y, line, body_font, label_bold, (0, 0, 0, 255))
            lb = draw.textbbox((0, 0), line, font=body_font)
            y += (lb[3] - lb[1]) + 2
            last_w = lb[2] - lb[0]
            last_h = lb[3] - lb[1]
            last_y_start = y - last_h - 2
        # Draw optional italic once-per tail appended
        tail = (a.get('once_text') or '').rstrip()
        if tail:
            tail_w = draw.textbbox((0, 0), tail, font=body_italic_font)[2]
            remaining = max(0, area_w - last_w)
            if tail_w <= remaining and last_h > 0:
                # Draw on the same last line, immediately after text
                draw_text_with_special_symbols(text_draw, area_x + last_w, last_y_start, tail, body_italic_font, (0, 0, 0, 255), italic=True)
            else:
                # New line, left-aligned
                draw_text_with_special_symbols(text_draw, area_x, y, tail, body_italic_font, (0, 0, 0, 255), italic=True)
                lb = draw.textbbox((0, 0), tail, font=body_italic_font)
                y += (lb[3] - lb[1]) + 2
        y += line_gap
    if passive and (activated or arcane):
        draw.line([area_x + 12, y, area_x + area_w - 12, y], fill=(0, 0, 0, 255), width=1)
        y += 6

    for a in activated:
        base_text, tail_text = compose_title_parts(a)
        draw_text_with_special_symbols(text_draw, area_x, y, base_text, title_font, (0, 0, 0, 255))
        nb = draw.textbbox((0, 0), base_text, font=title_font)
        # Draw tail in smaller italics on the same baseline
        if tail_text:
            tx = area_x + (nb[2] - nb[0])
            draw_text_with_special_symbols(text_draw, tx, y, tail_text, title_italic_font, (0, 0, 0, 255), italic=True)
            nb = draw.textbbox((0, 0), base_text, font=title_font)
        y += (nb[3] - nb[1]) + 4
        desc = a.get('description', '') or ''
        for line in wrap_text(draw, desc, body_font, area_w):
            draw_styled_text(text_draw, area_x, y, line, body_font, label_bold, (0, 0, 0, 255))
            lb = draw.textbbox((0, 0), line, font=body_font)
            y += (lb[3] - lb[1]) + 2
        # Draw catastrophe line for activated if present
        c_text = (a.get('catastrophe') or '').strip()
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

    def suit_color(code):
        mapping = {1: (67, 168, 59, 255), 2: (0, 158, 228, 255), 4: (230, 0, 125, 255)}
        try:
            return mapping[int(code)]
        except Exception:
            return (0, 0, 0, 255)

    def colors_for_code(code_int):
        try:
            c = int(code_int or 0)
        except Exception:
            c = 0
        cols = []
        if c & 1:
            cols.append(1)
        if c & 2:
            cols.append(2)
        if c & 4:
            cols.append(4)
        return cols

    shapes_draw = draw
    def draw_token_sequence(x, y, value_text, color_code, font):
        # Slightly smaller/thinner tokens (shrink background without shrinking text)
        pad_x, pad_y, radius = 3, 4, 5
        white = (255, 255, 255, 255)
        line_h = shapes_draw.textbbox((0, 0), "Ag", font=font)[3]
        token_font_size = max(12, int(getattr(font, 'size', 18) - 2))
        token_font = get_font(token_font_size, bold=False)
        token_bold_font = get_font(token_font_size, bold=True)

        cols = colors_for_code(color_code)
        if not cols:
            simple = f"{value_text}: "
            # Punctuation/text belongs on the text layer for glow
            text_draw.text((x, y), simple, fill=(0, 0, 0, 255), font=token_bold_font)
            sb = text_draw.textbbox((0, 0), simple, font=token_bold_font)
            return x + (sb[2] - sb[0])
        
        # Split value_text by " or " to handle multiple values like "2 or 3"
        values = [v.strip() for v in value_text.split(" or ")]
        
        # If we have a single color and multiple values, draw multiple tokens of that color
        if len(cols) == 1 and len(values) > 1:
            c = cols[0]
            for i, val in enumerate(values):
                # Calculate token size for this value
                tb = shapes_draw.textbbox((0, 0), val, font=token_font)
                tb_bold = shapes_draw.textbbox((0, 0), val, font=token_bold_font)
                text_w = tb[2] - tb[0]
                text_h = tb[3] - tb[1]
                token_h = max(min(line_h - 3, text_h + pad_y * 2), text_h + pad_y * 2 - 1)
                token_w = max(text_w + pad_x * 2 - 2, token_h - 6)
                ty = y + (line_h - token_h) // 2
                
                # Draw token
                rect = [x, ty, x + token_w, ty + token_h]
                try:
                    shapes_draw.rounded_rectangle(rect, radius=radius, fill=suit_color(c))
                except Exception:
                    shapes_draw.rectangle(rect, fill=suit_color(c))
                
                # Center text inside token
                tx = x + (token_w - (tb_bold[2] - tb_bold[0])) // 2 - tb_bold[0]
                ty_text = ty + (token_h - (tb_bold[3] - tb_bold[1])) // 2 - tb_bold[1]
                text_draw.text((tx, ty_text), val, fill=white, font=token_bold_font)
                x += token_w
                
                # Add " or " between tokens
                if i < len(values) - 1:
                    text_draw.text((x, y), " or ", fill=(0, 0, 0, 255), font=font)
                    x += text_draw.textbbox((0, 0), " or ", font=font)[2]
        else:
            # Original logic: one token per color
            tb = shapes_draw.textbbox((0, 0), value_text, font=token_font)
            tb_bold = shapes_draw.textbbox((0, 0), value_text, font=token_bold_font)
            text_w = tb[2] - tb[0]
            text_h = tb[3] - tb[1]
            token_h = max(min(line_h - 3, text_h + pad_y * 2), text_h + pad_y * 2 - 1)
            token_w = max(text_w + pad_x * 2 - 2, token_h - 6)
            ty = y + (line_h - token_h) // 2
            
            for i, c in enumerate(cols):
                rect = [x, ty, x + token_w, ty + token_h]
                try:
                    shapes_draw.rounded_rectangle(rect, radius=radius, fill=suit_color(c))
                except Exception:
                    shapes_draw.rectangle(rect, fill=suit_color(c))
                # Center text precisely inside the token using the token_font
                tx = x + (token_w - (tb_bold[2] - tb_bold[0])) // 2 - tb_bold[0]
                ty_text = ty + (token_h - (tb_bold[3] - tb_bold[1])) // 2 - tb_bold[1]
                text_draw.text((tx, ty_text), value_text, fill=white, font=token_bold_font)
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

    for a in arcane:
        base_text, tail_text = compose_title_parts(a)
        draw_text_with_special_symbols(text_draw, area_x, y, base_text, title_font, (0, 0, 0, 255))
        nb = draw.textbbox((0, 0), base_text, font=title_font)
        if tail_text:
            tx = area_x + (nb[2] - nb[0])
            draw_text_with_special_symbols(text_draw, tx, y, tail_text, title_italic_font, (0, 0, 0, 255), italic=True)
        y += (nb[3] - nb[1]) + 4
        # Arcane subtext before outcomes
        subtext = (a.get('subtext') or '').strip()
        if subtext:
            for line in wrap_text(draw, subtext, body_italic_font, area_w):
                draw_text_with_special_symbols(text_draw, area_x, y, line, body_italic_font, (0, 0, 0, 255), italic=True)
                lb = draw.textbbox((0, 0), line, font=body_italic_font)
                y += (lb[3] - lb[1]) + 2
        ao_list = a.get('ArcaneOutcome') or []
        non_cats = non_cat_outcomes(ao_list)
        cata = first_cata(ao_list)
        for nc in non_cats:
            val = nc.get('cardValueRequirement')
            token_val = str(val) if (isinstance(val, (int, float)) and val != 0) else (val if isinstance(val, str) else 'X')
            start_after_tokens_x = draw_token_sequence(area_x, y, token_val, nc.get('cardColourRequirement', 0), body_font)
            available_first = area_w - (start_after_tokens_x - area_x)
            desc_text = (nc.get('outcomeText') or '').strip()
            words = desc_text.split()
            first_line = ""
            for w in words:
                test = (first_line + " " + w).strip()
                if draw.textbbox((0, 0), test, font=body_font)[2] <= available_first or not first_line:
                    first_line = test
                else:
                    break
            if first_line:
                draw_styled_text(text_draw, start_after_tokens_x, y, first_line, body_font, label_bold, (0, 0, 0, 255))
                lb = draw.textbbox((0, 0), first_line, font=body_font)
                y += (lb[3] - lb[1]) + 2
            remaining = desc_text[len(first_line):].lstrip()
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


def create_left_side_character_card(input_image_path, character_data, output_path):
    """Add left side text overlay to an existing wide character card image."""
    try:
        img = Image.open(input_image_path).convert("RGBA")
        # Shapes/lines layer (textless): boxes, dividers, tokens, pips, etc.
        textless_overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(textless_overlay)
        # Dedicated text layer for all text with optional glow
        all_text_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
        text_draw = ImageDraw.Draw(all_text_layer)

        # Working area boundaries
        left_boundary, top_boundary, right_boundary, bottom_boundary = 10, 10, 745, 690
        text_margin = 6
        text_left = left_boundary + text_margin
        # Increase right-side safety margin slightly to avoid touching the thick border
        text_right = right_boundary - 30
        text_width = text_right - text_left

        black = (0, 0, 0, 255)
        character_name = character_data.get('name', 'Unknown Character')

        # Helper to compute fonts for main + subtitle fitting combined width
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
        if ',' in character_name:
            main_name, subtitle = [p.strip() for p in character_name.split(',', 1)]
            # Reserve extra right-side buffer to avoid overlapping faction emblem
            name_font, subtitle_font = pick_name_fonts(main_name, subtitle, max(0, text_width - 50))
            name_x = text_left
            name_y = top_boundary + text_margin
            test_text = "Ag"
            main_metrics = draw.textbbox((0, 0), test_text, font=name_font)
            subtitle_metrics = draw.textbbox((0, 0), test_text, font=subtitle_font)
            main_ascent = abs(main_metrics[1])
            subtitle_ascent = abs(subtitle_metrics[1])
            # Lower the subtitle further to sit flush with the main name
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
            # Apply the same right-side buffer for long single-line names
            name_font = get_character_name_font(character_name, max(0, text_width - 50), draw)
            name_x = text_left
            name_y = top_boundary + text_margin
            text_draw.text((name_x, name_y), character_name, fill=black, font=name_font)
            current_y = top_boundary + 60

        # Keywords
        keywords = character_data.get('keywords', '')
        if keywords and str(keywords).strip():
            formatted = str(keywords).replace(',', ', ').replace(', ,', ',').replace('  ', ' ').strip()
            while ', ,' in formatted:
                formatted = formatted.replace(', ,', ',')
            formatted = formatted.rstrip(', ')
            keywords_font = get_font(20, bold=False)
            keywords_y = current_y
            text_draw.text((name_x, keywords_y), formatted, fill=black, font=keywords_font)
            kw_bbox = draw.textbbox((0, 0), formatted, font=keywords_font)
            # Draw version line in the gap between keywords and stats without moving stats down
            try:
                version_val = character_data.get('version')
                version_int = int(version_val) if version_val is not None else None
            except Exception:
                version_int = None
            if version_int is not None and version_int >= 1:
                #v_size = max(8, int(getattr(keywords_font, 'size', 20) * 0.8))
                version_font = get_font(15, bold=False)
                v_text = f"v.{version_int}"
                v_y = keywords_y + (kw_bbox[3] - kw_bbox[1]) + 6
                text_draw.text((name_x, v_y), v_text, fill=black, font=version_font)
            current_y += (kw_bbox[3] - kw_bbox[1]) + 15

        # Stats box
        stats_area_width = int(text_width * 0.60)
        stats_x = text_left + (text_width - stats_area_width) // 2
        stats_y = current_y
        after_stats_y = draw_stats_box(draw, stats_x, stats_y, stats_area_width, character_data, text_draw_override=text_draw)

        # Bottom row
        bottom_row_top_y = draw_bottom_row(draw, text_left, bottom_boundary, text_right, character_data, text_draw_override=text_draw)

        # Abilities
        abilities_x = text_left
        abilities_y = after_stats_y + 10
        abilities_w = text_right - text_left
        # Draw all ability text onto its own transparent layer to allow soft outline
        abilities_text_layer = all_text_layer
        abilities_text_draw = text_draw
        # Allow abilities content to extend slightly further toward the bottom row
        abilities_bottom = bottom_row_top_y + 2
        layout_and_draw_abilities(draw, character_data.get('Ability', []), ABILITIES_YAML, abilities_x, abilities_y, abilities_w, abilities_bottom, text_draw_override=abilities_text_draw)

        # Composite text on base
        final_rgba = Image.alpha_composite(img, textless_overlay)

        # Build a subtle white feathered outline behind the ability text
        try:
            # Build glow using all text drawn so far
            text_alpha = all_text_layer.split()[3]
            expanded = text_alpha.filter(ImageFilter.MaxFilter(3))
            blurred = expanded.filter(ImageFilter.GaussianBlur(radius=2.4))
            # Keep subtle but a bit stronger: cap opacity at ~50%
            faded = blurred.point(lambda a: int(min(255, a) * 0.5))
            white_glow = Image.new("RGBA", img.size, (255, 255, 255, 0))
            white_glow.putalpha(faded)
            # Composite glow first, then the actual ability text
            final_rgba = Image.alpha_composite(final_rgba, white_glow)
            final_rgba = Image.alpha_composite(final_rgba, all_text_layer)
        except Exception:
            # Fallback: just add text without glow
            final_rgba = Image.alpha_composite(final_rgba, all_text_layer)

        # Now composite all text (including abilities/glow) onto the base image
        final_rgba = Image.alpha_composite(img, final_rgba)

        # Optional: apply a top overlay image if specified for this character
        try:
            overlay_name = character_data.get('overlayImage')
            if isinstance(overlay_name, str) and overlay_name.strip():
                script_dir = os.path.dirname(os.path.abspath(__file__))
                raw_name = overlay_name.strip()

                def candidate_paths(name: str):
                    base = os.path.join(script_dir, name)
                    yield base
                    # Fix common typo: trailing 'p' in .pngp
                    if name.lower().endswith('.pngp'):
                        yield os.path.join(script_dir, name[:-1])
                    # If no extension, try .png
                    if '.' not in os.path.basename(name):
                        yield os.path.join(script_dir, name + '.png')
                    # Try common case variants
                    for ext in ['.png', '.PNG', '.webp', '.jpg', '.jpeg']:
                        if not name.lower().endswith(ext):
                            yield os.path.join(script_dir, os.path.splitext(name)[0] + ext)

                resolved_path = None
                for p in candidate_paths(raw_name):
                    if os.path.exists(p):
                        resolved_path = p
                        break

                if resolved_path:
                    print(f"Applying overlay: {os.path.basename(resolved_path)}")
                    top_overlay = Image.open(resolved_path).convert("RGBA")
                    if top_overlay.size != final_rgba.size:
                        # Use a broadly compatible resample method
                        resample = getattr(Image, 'LANCZOS', getattr(Image, 'BICUBIC', 3))
                        try:
                            # Pillow>=9 prefers Image.Resampling
                            from PIL import Image as _IMG
                            if hasattr(_IMG, 'Resampling'):
                                resample = _IMG.Resampling.LANCZOS
                        except Exception:
                            pass
                        top_overlay = top_overlay.resize(final_rgba.size, resample)
                    final_rgba = Image.alpha_composite(final_rgba, top_overlay)
                else:
                    print(f"Warning: overlayImage specified but not found: {raw_name}")
        except Exception as overlay_err:
            print(f"Warning: failed to apply overlayImage: {overlay_err}")

        final_img = final_rgba.convert("RGB")
        final_img.save(output_path, "PNG")
        print(f"Created left side card: {output_path}")
        return True
    except Exception as e:
        print(f"Error creating left side card: {str(e)}")
        return False


def main():
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Paths
    json_path = os.path.join(script_dir, 'moonstone_data.json')
    yaml_path = os.path.join(script_dir, 'abilities_strings.yaml')
    input_cards_dir = os.path.join(script_dir, 'generated_wide_cards')
    output_dir = os.path.join(script_dir, 'generated_wide_cards_with_left_text')

    # Check if moonstone_data.json exists
    if not os.path.exists(json_path):
        print(f"Error: moonstone_data.json not found at {json_path}")
        sys.exit(1)

    # Check if input cards directory exists
    if not os.path.exists(input_cards_dir):
        print(f"Error: generated_wide_cards directory not found at {input_cards_dir}")
        print("Please run create_wide_character_card.py first to generate the base cards.")
        sys.exit(1)

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Load the YAML abilities map if available
    load_yaml_abilities(yaml_path)

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
        if not entry or 'name' not in entry:
            continue
        character_name = entry['name']
        total_characters += 1

        print(f"Processing {character_name}...")

        safe_filename = character_name.replace('/', '_').replace('\\', '_')
        input_image_path = os.path.join(input_cards_dir, f"{safe_filename}_wide_card.png")

        if not os.path.exists(input_image_path):
            print(f"Warning: Base wide card not found for {character_name}: {input_image_path}")
            continue

        output_path = os.path.join(output_dir, f"{safe_filename}_wide_card_with_text.png")

        if create_left_side_character_card(input_image_path, entry, output_path):
            successful_cards += 1

    print(f"\nCompleted! Successfully created {successful_cards} out of {total_characters} character cards with left side text.")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
