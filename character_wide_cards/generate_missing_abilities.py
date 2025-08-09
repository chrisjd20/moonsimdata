#!/usr/bin/env python3
"""
Auto-generate missing activated / arcane abilities from character stat card images
using the GPT-5 Chat Completions API.

Process overview:
1. Load character data from character_wide_cards/moonstone_data.json
2. For each character meeting inclusion rules:
   - Ability array not empty
   - At least one non-passive ability (entry with non-null energyCost)
   - Has a statCardFileName and corresponding image under characters/<Name>/<statCardFileName>
3. Send the stat card image + the current abilities_strings.yaml file to the model
   (model: gpt-5-2025-08-07) with an instruction prompt asking ONLY for new
   activated or arcane abilities not already present. The model must output just
   YAML fragments for new abilities (or a sentinel if none).
4. Parse model response, filter out any abilities that already exist, append new
   ones to abilities_strings.yaml.
5. Keep an audit log per character under character_wide_cards/model_ability_generation/

Safety / Idempotence:
- Existing abilities in YAML are never modified (we only append).
- If model returns abilities already present, they are ignored.
- Dry run mode (--dry-run) performs all steps except the API call & file writes.

Dependencies: openai>=1.0.0 (hypothetical GPT-5 compatible), pyyaml
Environment: Requires OPENAI_API_KEY to be set.

NOTE: This script assumes a structure for the "Ability" entries inside the JSON.
If the schema differs, adjust the function `character_has_active_or_arcane_ability` accordingly.
"""
from __future__ import annotations
import os
import sys
import json
import time
import argparse
import base64
import re
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple

try:
    import yaml
except ImportError:
    print("pyyaml not installed. Please install with: pip install pyyaml")
    sys.exit(1)

# OpenAI SDK (GPT-5). Fallback friendly import.
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
CHAR_JSON = ROOT / "moonstone_data.json"
ABILITIES_YAML = ROOT / "abilities_strings.yaml"
CHAR_DIR = PROJECT_ROOT / "characters"
OUTPUT_LOG_DIR = ROOT / "model_ability_generation"
MODEL_NAME = "gpt-5-2025-08-07"
SENTINEL_NO_NEW = "# NO NEW ABILITIES"

PROMPT_INSTRUCTIONS = """You are an assistant that extracts ONLY activated or arcane abilities from a Moonstone character stat card image and outputs new YAML entries.
Rules:
- Input includes: 1) The stat card image. 2) The entire current abilities YAML file.
- Only add activated or arcane abilities NOT already included by name.
- Passive abilities (just a heading and descriptive text at top) MUST be ignored. They never appear in the output.
- Preserve exact naming from the card (no version suffixes like v.2) – just the ability name as shown.
- YAML format must match existing examples exactly:
  AbilityName:
    cost: <int>
    range: <int|null>
    type: activated|arcane
    isPulse: <true|false>
    textToRightInItalics: <string|null>
    activatedText: <string|null>
    arcaneOutcomes: <null or list of strings>
    catastrophe: <string|null>
- For arcane abilities: arcaneOutcomes list items are strings of the form one or more card-color:value pairs followed by a colon and a space then the effect text.
  * Valid card color letters: g (green), b (blue), r (red-ish-purple-pink) ONLY.
  * Values allowed per color token: X, 1, 2, 3 only.
  * Multiple color:value pairs are comma separated with no spaces after commas (e.g. "g2,b2,r2: Effect text..."). or gX,bX: etc... if they appear horozontally on the same line in the image with a command or and or
- Activated abilities NEVER have color prefixes in their effect text; they may optionally have a catastrophe.
- If an ability has no italic side text, set textToRightInItalics: null.
- If an ability is activated (non-arcane) set arcaneOutcomes: null.
- If an ability has no catastrophe, set catastrophe: null.
- Do NOT re-output abilities that already exist (their names are provided). Only output *new* top-level YAML entries.
- Output must be ONLY the YAML fragments for new abilities in the exact format (2-space indent) OR the line '# NO NEW ABILITIES' if there are none.
- Do not wrap output in code fences.
- Do not include commentary.
"""

def load_characters() -> List[Dict[str, Any]]:
    with open(CHAR_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # Keep only dict entries with a name
    chars = [c for c in data if isinstance(c, dict) and c.get('name')]
    return chars


def load_existing_ability_names() -> Tuple[Set[str], Set[str], Set[str]]:
    """Return both raw keys from YAML and their normalized variants.

    Using a YAML parser avoids issues with inline comments (e.g., `Key: # comment`).
    """
    raw: Set[str] = set()
    norm: Set[str] = set()
    canon: Set[str] = set()
    if not ABILITIES_YAML.exists():
        return raw, norm, canon
    try:
        with open(ABILITIES_YAML, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        if isinstance(data, dict):
            for k in data.keys():
                if isinstance(k, str) and k.strip():
                    raw.add(k)
                    n = normalize_name(k)
                    norm.add(n)
                    canon.add(canonicalize_name(n))
        else:
            # Fallback to line scan if unexpected shape
            with open(ABILITIES_YAML, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped = line.strip()
                    if stripped and not line.startswith(' ') and stripped.endswith(':'):
                        key = stripped[:-1]
                        raw.add(key)
                        n = normalize_name(key)
                        norm.add(n)
                        canon.add(canonicalize_name(n))
    except Exception:
        # As a last resort, do a defensive line-based parse
        with open(ABILITIES_YAML, 'r', encoding='utf-8') as f:
            for line in f:
                stripped = line.strip()
                if stripped and not line.startswith(' ') and stripped.endswith(':'):
                    key = stripped[:-1]
                    raw.add(key)
                    n = normalize_name(key)
                    norm.add(n)
                    canon.add(canonicalize_name(n))
    return raw, norm, canon


def normalize_name(name: str) -> str:
    return name.strip().strip('"').strip("'").lower()


def canonicalize_name(name: str) -> str:
    """Stronger normalization for comparison:
    - lowercases, trims quotes/spaces
    - normalizes unicode quotes/dashes
    - collapses whitespace
    - removes trailing details like " (2) 10\"", " – ...", " - ...", or " : ..."
    """
    s = name
    # Normalize quotes/dashes
    s = s.replace('“', '"').replace('”', '"').replace('’', "'").replace('\u2013', '-').replace('\u2014', '-')
    s = s.strip().strip('"').strip("'").lower()
    s = re.sub(r"\s+", " ", s)
    # Strip content starting with space + dash/en dash/em dash + space
    s = re.sub(r"\s+[\-\u2013\u2014]\s+.*$", "", s)
    # Strip content starting with space + colon
    s = re.sub(r"\s*:\s*.*$", "", s)
    # Strip trailing parenthetical details
    s = re.sub(r"\s*\(.*\)\s*$", "", s)
    return s
def name_in_yaml_text(yaml_text: str, name: str) -> bool:
    """Simple substring presence check against the full YAML text, per user request."""
    if not name:
        return False
    return '\n' + name.strip().lower() in yaml_text.lower() or '"'+name.strip().lower() in yaml_text.lower()



def character_has_active_or_arcane_ability(char: Dict[str, Any]) -> bool:
    abilities = char.get('Ability')
    if not isinstance(abilities, list) or len(abilities) == 0:
        return False
    # Passive ability heuristic: energyCost is null. We need at least one with non-null energyCost
    for a in abilities:
        if isinstance(a, dict) and a.get('energyCost') is not None:
            return True
    return False


def get_non_passive_ability_names(char: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    abilities = char.get('Ability')
    if not isinstance(abilities, list):
        return names
    for a in abilities:
        if not isinstance(a, dict):
            continue
        # Heuristic: energyCost not None => activated/arcane (non-passive)
        if a.get('energyCost') is not None:
            # name key could be 'name' or 'abilityName'; try common fallbacks
            aname = a.get('name') or a.get('abilityName') or a.get('title')
            if isinstance(aname, str) and aname.strip():
                names.append(aname.strip())
    return names


def find_stat_card_image(char: Dict[str, Any]) -> Path | None:
    name = char.get('name')
    img_file = char.get('statCardFileName')
    if not name or not img_file:
        return None
    # Directory named exactly as character name
    char_path = CHAR_DIR / name
    if not char_path.exists():
        return None
    # The JSON value might be e.g. 'Billy.webp'; try exact filename first
    direct = char_path / img_file
    if direct.exists():
        return direct
    # Fallback: search for matching stem ignoring case
    stem = Path(img_file).stem.lower()
    for p in char_path.glob('*.webp'):
        if p.stem.lower() == stem:
            return p
    return None


def image_to_data_uri(path: Path) -> str:
    b = path.read_bytes()
    b64 = base64.b64encode(b).decode('ascii')
    return f"data:image/webp;base64,{b64}"


def build_messages(existing_names: Set[str], yaml_text: str, img_data_uri: str) -> List[Dict[str, Any]]:
    # Provide existing ability names as a quick reference list to reduce duplication.
    existing_list = sorted(existing_names)
    existing_block = "\n".join(existing_list)
    user_instruction = (
        "Existing ability names (do NOT repeat):\n" + existing_block +
        "\n\nFull current abilities YAML (reference only, do not copy existing entries):\n---\n" + yaml_text + "\n---\n" +
        "Return ONLY new ability YAML entries or '# NO NEW ABILITIES'."
    )
    # Multi-modal message with image + text (GPT-5 vision style)
    return [
        {"role": "system", "content": PROMPT_INSTRUCTIONS},
        {"role": "user", "content": [
            {"type": "text", "text": user_instruction},
            {"type": "image_url", "image_url": {"url": img_data_uri}}
        ]}
    ]


def call_model(messages: List[Dict[str, Any]], reasoning: str, verbosity: str, dry_run: bool) -> str:
    if dry_run:
        return SENTINEL_NO_NEW + "  # dry run"
    if OpenAI is None:
        raise RuntimeError("openai package not installed. Run: pip install openai")
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable not set")
    client = OpenAI()
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        reasoning_effort=reasoning,
        verbosity=verbosity,
        temperature=1,
        max_completion_tokens=1200  # Updated per API error: use max_completion_tokens
    )
    return response.choices[0].message.content.strip()


def extract_new_ability_blocks(raw_text: str, existing_names: Set[str]) -> Dict[str, str]:
    """Return mapping of ability name -> YAML block text for new abilities."""
    if raw_text.strip().startswith(SENTINEL_NO_NEW):
        return {}
    # Split by top-level ability name lines (start of line, no leading space, word chars / punctuation, colon)
    lines = raw_text.splitlines()
    blocks: Dict[str, List[str]] = {}
    current_name = None
    for line in lines:
        if line and not line.startswith(' ') and line.endswith(':'):
            name = line[:-1]
            current_name = name
            blocks[current_name] = [line]
        else:
            if current_name:
                blocks[current_name].append(line)
    # Join and filter out existing names
    result: Dict[str, str] = {}
    for name, blines in blocks.items():
        if name in existing_names:
            continue
        result[name] = "\n".join(blines).rstrip() + "\n"
    return result


def append_abilities_to_yaml(blocks: Dict[str, str]):
    if not blocks:
        return False
    with open(ABILITIES_YAML, 'a', encoding='utf-8') as f:
        f.write('\n')
        for _, block in blocks.items():
            f.write(block)
            if not block.endswith('\n'):
                f.write('\n')
    return True


def process_character(char: Dict[str, Any], existing_raw_names: Set[str], existing_norm_names: Set[str], existing_canon_names: Set[str], yaml_text: str, args) -> None:
    name = char.get('name')
    # Pre-check: if all non-passive ability names already exist, skip expensive API call
    non_passive_names = get_non_passive_ability_names(char)
    # Substring-based presence check in the YAML text
    missing = [n for n in non_passive_names if not name_in_yaml_text(yaml_text, n)]
    if non_passive_names and not missing:
        print(f"[SKIP-NO-MISSING] {name}: all {len(non_passive_names)} abilities already present")
        return
    image_path = find_stat_card_image(char)
    if not image_path:
        print(f"[SKIP] {name}: image not found")
        return
    print(f"[PROCESS] {name} (missing: {', '.join(missing) if missing else 'unknown – proceeding'})")
    img_uri = image_to_data_uri(image_path)
    messages = build_messages(existing_raw_names, yaml_text, img_uri)
    try:
        raw_response = call_model(messages, args.reasoning, args.verbosity, args.dry_run)
    except Exception as e:
        print(f"  API error: {e}")
        return
    new_blocks = extract_new_ability_blocks(raw_response, existing_raw_names)
    if new_blocks:
        print(f"  New abilities detected: {', '.join(new_blocks.keys())}")
        if not args.dry_run:
            append_abilities_to_yaml(new_blocks)
            # Update in-memory set so subsequent characters don't duplicate
            for k in new_blocks.keys():
                existing_raw_names.add(k)
                nk = normalize_name(k)
                existing_norm_names.add(nk)
                existing_canon_names.add(canonicalize_name(nk))
    else:
        print("  No new abilities")
    # Write log
    OUTPUT_LOG_DIR.mkdir(exist_ok=True)
    log_file = OUTPUT_LOG_DIR / f"{name.replace(' ', '_')}.log"
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(f"Character: {name}\nImage: {image_path}\n\nRAW RESPONSE:\n{raw_response}\n")


def main():
    parser = argparse.ArgumentParser(description="Generate missing abilities using GPT-5")
    parser.add_argument('--reasoning', default='low', help='GPT-5 reasoning_effort (low|medium|high)')
    parser.add_argument('--verbosity', default='medium', help='GPT-5 verbosity (low|medium|high)')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between API calls (seconds)')
    parser.add_argument('--limit', type=int, default=None, help='Process only first N eligible characters')
    parser.add_argument('--dry-run', action='store_true', help='Do not call API or modify YAML')
    args = parser.parse_args()

    if not CHAR_JSON.exists():
        print(f"Missing JSON file: {CHAR_JSON}")
        return 1
    if not ABILITIES_YAML.exists():
        print(f"Missing abilities YAML: {ABILITIES_YAML}")
        return 1

    characters = load_characters()
    existing_raw, existing_norm, existing_canon = load_existing_ability_names()
    yaml_text = ABILITIES_YAML.read_text(encoding='utf-8')

    eligible: List[Dict[str, Any]] = []
    skipped_all_present = 0
    for c in characters:
        if character_has_active_or_arcane_ability(c):
            np_names = get_non_passive_ability_names(c)
            # If there are no names we can evaluate, include (model may extract)
            if np_names:
                # Substring-based presence check on current YAML snapshot
                missing = [n for n in np_names if not name_in_yaml_text(yaml_text, n)]
                if not missing:
                    skipped_all_present += 1
                    continue
            eligible.append(c)
    print(f"Eligible characters with at least one missing ability: {len(eligible)} (skipped fully present: {skipped_all_present})")

    if args.limit is not None:
        eligible = eligible[:args.limit]

    for idx, char in enumerate(eligible, 1):
        process_character(char, existing_raw, existing_norm, existing_canon, yaml_text, args)
        # Reload YAML text after potential append so model always gets freshest file
        if ABILITIES_YAML.exists():
            yaml_text = ABILITIES_YAML.read_text(encoding='utf-8')
        if idx < len(eligible):
            time.sleep(args.delay)

    print("Done.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
