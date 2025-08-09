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

from PIL import Image, ImageDraw, ImageFont

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

# Global cache for YAML ability definitions (normalized-name keyed)
ABILITIES_YAML: Dict[str, Dict[str, Any]] = {}


def get_font(size, bold=False):
    """Get font with fallback options."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/verdana.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Verdana.ttf",
        "C:/Windows/Fonts/verdana.ttf",
    ]

def get_font(size, bold=False):
    """Get font with fallback options."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/verdana.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Verdana.ttf",
        "C:/Windows/Fonts/verdana.ttf",
    ]

    for font_path in font_paths:
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
    """Wrap text into lines that fit within max_width without breaking words."""
    if not text:
        return []
    words = text.split()
    lines = []
    line = ""
    for w in words:
        test = (line + " " + w).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width or not line:
            line = test
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


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
    first_val: str | None = None
    for tok in tokens:
        if not tok:
            continue
        c = tok[0].lower()
        v = tok[1:].strip() or "X"
        if first_val is None:
            first_val = v
        if c == "g":
            mask |= 1
        elif c == "b":
            mask |= 2
        elif c == "r":
            mask |= 4
    if first_val is not None:
        value_text = first_val
    return value_text, mask, desc


def draw_stats_box(draw, x, y, width, character_data):
    """Draw a boxed stats area (Melee, Range, Arcane, Evade). Returns bottom y."""
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

    header_font = get_font(18, bold=True)
    value_font = get_font(26, bold=False)
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
        draw.text((tx, ty), h, fill=(0, 0, 0, 255), font=header_font)

    base_y = sep_y + 6
    for i, v in enumerate(values):
        v_str = str(v)
        cx = x + i * col_width
        text_bbox = draw.textbbox((0, 0), v_str, font=value_font)
        tw = text_bbox[2] - text_bbox[0]
        tx = cx + (col_width - tw) // 2
        draw.text((tx, base_y), v_str, fill=(0, 0, 0, 255), font=value_font)

    return y + box_height


def draw_bottom_row(draw, text_left, bottom_boundary, text_right, character_data):
    """Draw heart + up-to-15 health pips and base size label. Returns top Y of this row."""
    margin = 10
    row_height = 50  # Increased for bigger elements
    y = bottom_boundary - margin - row_height

    heart_font = get_font(32, bold=True)  # Bigger heart
    heart_y = y + 2
    heart_bbox = draw.textbbox((0, 0), "\u2665", font=heart_font)
    heart_w = heart_bbox[2] - heart_bbox[0]
    draw.text((text_left, heart_y), "\u2665", fill=(0, 0, 0, 255), font=heart_font)

    # Two-line base size text
    base_map = {0: "30mm", 1: "40mm"}
    bs_val = base_map.get(character_data.get('baseSize', 0), "30mm")
    base_font = get_font(16, bold=False)
    line1 = "Base:"
    line2 = bs_val.upper()
    
    bb1 = draw.textbbox((0, 0), line1, font=base_font)
    bb2 = draw.textbbox((0, 0), line2, font=base_font)
    base_w = max(bb1[2] - bb1[0], bb2[2] - bb2[0])
    line_h = bb1[3] - bb1[1]
    
    base_x = text_right - base_w
    base_y1 = y + 2
    base_y2 = base_y1 + line_h + 2
    
    draw.text((base_x, base_y1), line1, fill=(0, 0, 0, 255), font=base_font)
    draw.text((base_x, base_y2), line2, fill=(0, 0, 0, 255), font=base_font)

    try:
        maxhp = int(character_data.get('maxhp') or 0)
    except Exception:
        maxhp = 0
    maxhp = max(0, min(15, maxhp))

    # Parse energy blips
    energy_blips = set()
    try:
        energy_str = character_data.get('energyblips', '')
        if energy_str and str(energy_str).strip():
            # Parse comma-separated values like "1,4" or "1,2,3,5,6"
            for part in str(energy_str).split(','):
                part = part.strip()
                if part.isdigit():
                    blip_num = int(part)
                    if 1 <= blip_num <= 15:
                        energy_blips.add(blip_num)
    except Exception:
        pass

    start_x = text_left + heart_w + 20  # More space after heart
    end_x = base_x - 15
    if end_x <= start_x:
        return y
    total_slots = 15
    usable_width = end_x - start_x
    pitch = usable_width / (total_slots - 1)
    dot_d = max(12, min(24, int(pitch - 2)))  # Bigger dots
    stroke = 2
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

    # Draw health slots (outline only)
    for i in range(maxhp):
        cx = int(centers[i]) - dot_d // 2
        bbox = [cx, cy, cx + dot_d, cy + dot_d]
        draw.ellipse(bbox, outline=(0, 0, 0, 255), width=stroke)

    # Fill energy blips with blue
    blue_color = (0, 158, 228, 255)  # #009ee4
    for blip_pos in energy_blips:
        if 1 <= blip_pos <= maxhp:  # Only fill if within health range
            i = blip_pos - 1  # Convert to 0-based index
            cx = int(centers[i]) - dot_d // 2
            bbox = [cx, cy, cx + dot_d, cy + dot_d]
            draw.ellipse(bbox, fill=blue_color, outline=(0, 0, 0, 255), width=stroke)

    return y


def layout_and_draw_abilities(draw, abilities, yaml_map, area_x, area_y, area_w, area_bottom):
    """Draw passive, then activated, then arcane abilities, using YAML overrides when present."""
    if not abilities:
        return area_y

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
                "description": normalize_quotes(ydef.get("activatedText") or ""),
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
                    "outcomeText": normalize_quotes(desc),
                    "catastropheOutcome": False,
                })
            cata = ydef.get("catastrophe")
            if cata:
                outcomes.append({
                    "catastropheOutcome": True,
                    "outcomeText": normalize_quotes(str(cata)),
                })
            arcane.append({
                "name": name,
                "cost": ydef.get("cost"),
                "range_txt": inch_text_from_yaml(ydef.get("range")),
                "pulse": bool(ydef.get("isPulse")),
                "tail": normalize_quotes(ydef.get("textToRightInItalics") or ""),
                "ArcaneOutcome": outcomes,
            })
        else:
            passive.append({
                "name": name,
                "description": normalize_quotes(base_obj.get("description") or base_obj.get("text") or ""),
            })

    for a in abilities:
        name = normalize_quotes(a.get("name", "Unnamed"))
        ydef = yaml_map.get(norm_key(name)) if yaml_map else None
        if ydef:
            build_from_yaml(ydef.get("__name", name), a, ydef)
        else:
            energy = a.get("energyCost")
            if energy is None:
                passive.append({
                    "name": name,
                    "description": normalize_quotes(a.get("description") or a.get("text") or ""),
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
                            "outcomeText": normalize_quotes(item.get("outcomeText") or ""),
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
                        "description": normalize_quotes(a.get("description") or a.get("text") or ""),
                    })

    title_size = 24
    body_size = 22
    min_size = 12

    def compose_title(a):
        name_line = a.get('name', 'Unnamed')
        cost = a.get('cost')
        if isinstance(cost, (int, float)):
            name_line = f"{name_line} ({int(cost)})"
        rng_txt = a.get('range_txt') or ""
        if rng_txt:
            name_line += rng_txt
        if a.get('pulse'):
            name_line += " Pulse"
        tail = a.get('tail') or ""
        if tail:
            dash = " – " if (rng_txt or a.get('pulse')) else " - "
            name_line += f"{dash}{tail}"
        return name_line

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
        line_gap = 8  # Increased spacing to prevent token overlap

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
            pad_x = 6
            tb = draw.textbbox((0, 0), val_text, font=body_font)
            text_w = tb[2] - tb[0]
            token_w = text_w + pad_x * 2
            punct_w = draw.textbbox((0, 0), ", ", font=body_font)[2]
            or_w = draw.textbbox((0, 0), " or ", font=body_font)[2]
            colon_w = draw.textbbox((0, 0), ": ", font=body_font)[2]
            cols = colors_for_code(color_code)
            if not cols:
                return draw.textbbox((0, 0), f"{val_text}: ", font=body_font)[2]
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
            for line in wrap_text(draw, full, body_font, area_w):
                lb = draw.textbbox((0, 0), line, font=body_font)
                y += (lb[3] - lb[1]) + 2
            y += line_gap
        if passive and (activated or arcane):
            y += 6

        # Activated
        for a in activated:
            name_line = compose_title(a)
            nb = draw.textbbox((0, 0), name_line, font=title_font)
            y += (nb[3] - nb[1]) + 2
            desc = a.get('description', '') or ''
            for line in wrap_text(draw, desc, body_font, area_w):
                lb = draw.textbbox((0, 0), line, font=body_font)
                y += (lb[3] - lb[1]) + 2
            y += line_gap
        if activated and arcane:
            y += 6

        # Arcane
        for a in arcane:
            name_line = compose_title(a)
            nb = draw.textbbox((0, 0), name_line, font=title_font)
            y += (nb[3] - nb[1]) + 2
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
        if needed <= area_bottom - 10 or (title_size <= min_size and body_size <= min_size):
            break
        title_size = max(min_size, title_size - 1)
        body_size = max(min_size, body_size - 1)

    y = area_y
    title_font = get_font(title_size, bold=True)
    body_font = get_font(body_size, bold=False)
    line_gap = 8  # Increased spacing to prevent token overlap

    label_bold = get_font(body_size, bold=True)
    for a in passive:
        label = f"{a.get('name', 'Unnamed')}: "
        desc = (a.get('description', '') or '')
        full = f"{label}{desc}".strip()
        lines = wrap_text(draw, full, body_font, area_w)
        if lines:
            first = lines[0]
            label_w = draw.textbbox((0, 0), label, font=label_bold)[2]
            first_w = draw.textbbox((0, 0), first, font=body_font)[2]
            if label_w <= first_w:
                draw.text((area_x, y), label, fill=(0, 0, 0, 255), font=label_bold)
                draw.text((area_x + label_w, y), first[len(label):], fill=(0, 0, 0, 255), font=body_font)
            else:
                draw.text((area_x, y), first, fill=(0, 0, 0, 255), font=body_font)
            lb = draw.textbbox((0, 0), first, font=body_font)
            y += (lb[3] - lb[1]) + 2
        for line in lines[1:]:
            draw.text((area_x, y), line, fill=(0, 0, 0, 255), font=body_font)
            lb = draw.textbbox((0, 0), line, font=body_font)
            y += (lb[3] - lb[1]) + 2
        y += line_gap
    if passive and (activated or arcane):
        draw.line([area_x, y, area_x + area_w - 12, y], fill=(0, 0, 0, 255), width=1)
        y += 6

    for a in activated:
        name_line = compose_title(a)
        draw.text((area_x, y), name_line, fill=(0, 0, 0, 255), font=title_font)
        nb = draw.textbbox((0, 0), name_line, font=title_font)
        y += (nb[3] - nb[1]) + 2
        desc = a.get('description', '') or ''
        for line in wrap_text(draw, desc, body_font, area_w):
            draw.text((area_x, y), line, fill=(0, 0, 0, 255), font=body_font)
            lb = draw.textbbox((0, 0), line, font=body_font)
            y += (lb[3] - lb[1]) + 2
        y += line_gap
    if activated and arcane:
        draw.line([area_x, y, area_x + area_w - 12, y], fill=(0, 0, 0, 255), width=1)
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

    def draw_token_sequence(x, y, value_text, color_code, font):
        pad_x, pad_y, radius = 8, 6, 4  # More rectangular padding
        white = (255, 255, 255, 255)
        line_h = draw.textbbox((0, 0), "Ag", font=font)[3]
        tb = draw.textbbox((0, 0), value_text, font=font)
        text_w = tb[2] - tb[0]
        text_h = tb[3] - tb[1]
        token_w = text_w + pad_x * 2
        token_h = max(text_h + pad_y * 2, int(line_h * 1.3))  # Taller tokens
        ty = y + (line_h - token_h) // 2

        cols = colors_for_code(color_code)
        if not cols:
            simple = f"{value_text}: "
            draw.text((x, y), simple, fill=(0, 0, 0, 255), font=font)
            sb = draw.textbbox((0, 0), simple, font=font)
            return x + (sb[2] - sb[0])
        for i, c in enumerate(cols):
            rect = [x, ty, x + token_w, ty + token_h]
            try:
                draw.rounded_rectangle(rect, radius=radius, fill=suit_color(c))
            except Exception:
                draw.rectangle(rect, fill=suit_color(c))
            tx = x + (token_w - text_w) // 2 - tb[0]
            ty_text = ty + (token_h - text_h) // 2 - tb[1]
            draw.text((tx, ty_text), value_text, fill=white, font=font)
            x += token_w
            if i < len(cols) - 2:
                draw.text((x, y), ", ", fill=(0, 0, 0, 255), font=font)
                x += draw.textbbox((0, 0), ", ", font=font)[2]
            elif i == len(cols) - 2:
                draw.text((x, y), " or ", fill=(0, 0, 0, 255), font=font)
                x += draw.textbbox((0, 0), " or ", font=font)[2]
        draw.text((x, y), ": ", fill=(0, 0, 0, 255), font=font)
        x += draw.textbbox((0, 0), ": ", font=font)[2]
        return x

    for a in arcane:
        name_line = compose_title(a)
        draw.text((area_x, y), name_line, fill=(0, 0, 0, 255), font=title_font)
        nb = draw.textbbox((0, 0), name_line, font=title_font)
        y += (nb[3] - nb[1]) + 2
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
                draw.text((start_after_tokens_x, y), first_line, fill=(0, 0, 0, 255), font=body_font)
                lb = draw.textbbox((0, 0), first_line, font=body_font)
                y += (lb[3] - lb[1]) + 2
            remaining = desc_text[len(first_line):].lstrip()
            for cont in wrap_text(draw, remaining, body_font, area_w):
                draw.text((area_x, y), cont, fill=(0, 0, 0, 255), font=body_font)
                lb = draw.textbbox((0, 0), cont, font=body_font)
                y += (lb[3] - lb[1]) + 2
        if cata:
            c_text_full = f"Catastrophe: {(cata.get('outcomeText') or '').strip()}"
            for line in wrap_text(draw, c_text_full, body_font, area_w):
                draw.text((area_x, y), line, fill=(0, 0, 0, 255), font=body_font)
                lb = draw.textbbox((0, 0), line, font=body_font)
                y += (lb[3] - lb[1]) + 2
        y += line_gap
    return y


def create_left_side_character_card(input_image_path, character_data, output_path):
    """Add left side text overlay to an existing wide character card image."""
    try:
        img = Image.open(input_image_path).convert("RGBA")
        text_overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(text_overlay)

        # Working area boundaries
        left_boundary, top_boundary, right_boundary, bottom_boundary = 10, 10, 745, 720  # Extended bottom for more space
        text_margin = 6
        text_left = left_boundary + text_margin
        text_right = right_boundary - 24
        text_width = text_right - text_left

        black = (0, 0, 0, 255)
        character_name = character_data.get('name', 'Unknown Character')

        # Name (with optional subtitle after comma)
        if ',' in character_name:
            main_name, subtitle = [p.strip() for p in character_name.split(',', 1)]
            name_font = get_character_name_font(main_name + ", ", 400, draw)
            main_font_size = getattr(name_font, 'size', 24)
            subtitle_font = get_font(max(8, int(main_font_size * 0.80)), bold=True)
            name_x = text_left
            name_y = top_boundary + text_margin
            test_text = "Ag"
            main_metrics = draw.textbbox((0, 0), test_text, font=name_font)
            subtitle_metrics = draw.textbbox((0, 0), test_text, font=subtitle_font)
            main_ascent = abs(main_metrics[1])
            subtitle_ascent = abs(subtitle_metrics[1])
            baseline_offset = main_ascent - subtitle_ascent
            draw.text((name_x, name_y), main_name, fill=black, font=name_font)
            main_bbox = draw.textbbox((0, 0), main_name, font=name_font)
            main_width = main_bbox[2] - main_bbox[0]
            comma_x = name_x + main_width
            draw.text((comma_x, name_y), ", ", fill=black, font=name_font)
            comma_w = draw.textbbox((0, 0), ", ", font=name_font)[2]
            subtitle_x = comma_x + comma_w
            subtitle_y = name_y + baseline_offset
            draw.text((subtitle_x, subtitle_y), subtitle, fill=black, font=subtitle_font)
            current_y = top_boundary + 60
        else:
            name_font = get_character_name_font(character_name, 600, draw)
            name_x = text_left
            name_y = top_boundary + text_margin
            draw.text((name_x, name_y), character_name, fill=black, font=name_font)
            current_y = top_boundary + 60

        # Keywords
        keywords = character_data.get('keywords', '')
        if keywords and str(keywords).strip():
            formatted = str(keywords).replace(',', ', ').replace(', ,', ',').replace('  ', ' ').strip()
            while ', ,' in formatted:
                formatted = formatted.replace(', ,', ',')
            formatted = formatted.rstrip(', ')
            keywords_font = get_font(20, bold=False)
            draw.text((name_x, current_y), formatted, fill=black, font=keywords_font)
            kw_bbox = draw.textbbox((0, 0), formatted, font=keywords_font)
            current_y += (kw_bbox[3] - kw_bbox[1]) + 15

        # Stats box
        stats_area_width = int(text_width * 0.60)
        stats_x = text_left + (text_width - stats_area_width) // 2
        stats_y = current_y
        after_stats_y = draw_stats_box(draw, stats_x, stats_y, stats_area_width, character_data)

        # Bottom row
        bottom_row_top_y = draw_bottom_row(draw, text_left, bottom_boundary, text_right, character_data)

        # Abilities
        abilities_x = text_left
        abilities_y = after_stats_y + 10
        abilities_w = text_right - text_left
        abilities_bottom = bottom_row_top_y - 10
        layout_and_draw_abilities(draw, character_data.get('Ability', []), ABILITIES_YAML, abilities_x, abilities_y, abilities_w, abilities_bottom)

        final_img = Image.alpha_composite(img, text_overlay).convert("RGB")
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
