#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import importlib
from pathlib import Path
from typing import Dict, List, Optional


VERSION_REGEX = re.compile(r"\bv\.\s*(\d+)\b", flags=re.IGNORECASE)


def extract_page_texts(pdf_path: Path) -> List[str]:
    """Extract text for each page of the PDF.

    Attempts to use pdfplumber (pdfminer-based) first for higher-fidelity text extraction,
    and falls back to PyPDF2 if pdfplumber is not available.
    Returns a list where index i corresponds to page i (0-based) text.
    """
    texts: List[str] = []

    # Try pdfplumber first
    try:
        pdfplumber = importlib.import_module("pdfplumber")
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                texts.append(text)
        return texts
    except Exception:
        # Fall through to next extractor
        pass

    # Fallback to PyPDF2
    try:
        PdfReader = importlib.import_module("PyPDF2").PdfReader

        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            texts.append(text)
        return texts
    except Exception as e:
        raise RuntimeError(f"Failed to read PDF: {pdf_path} ({e})") from e


def detect_version_from_text(text: str) -> int:
    """Return detected version from page text using VERSION_REGEX; default to 1.

    If multiple markers exist, prefers the highest numeric version found.
    """
    versions = [int(m.group(1)) for m in VERSION_REGEX.finditer(text or "")]
    if not versions:
        return 1
    return max(versions)


def load_names(names_path: Path) -> List[str]:
    with names_path.open("r", encoding="utf-8") as f:
        names = [line.strip() for line in f.readlines()]
    # Remove empties while preserving order/page alignment for non-empty lines
    names = [n for n in names if n]
    return names


def load_json(json_path: Path) -> List[dict]:
    with json_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(json_path: Path, data: List[dict]) -> None:
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def build_name_index(data: List[dict]) -> Dict[str, List[int]]:
    name_to_indices: Dict[str, List[int]] = {}
    for idx, item in enumerate(data):
        name = item.get("name")
        if not isinstance(name, str):
            continue
        name_to_indices.setdefault(name, []).append(idx)
    return name_to_indices


def assign_versions(
    names_in_order: List[str],
    page_texts: List[str],
    json_data: List[dict],
) -> Dict[str, int]:
    """Assign versions to json_data based on names_in_order and corresponding page_texts.

    For duplicate names, assigns to the next JSON entry with that name that does not
    yet have a version set. If all duplicates already have version, the last one is updated.

    Returns a mapping of name to last assigned version (for summary only).
    """
    name_to_indices = build_name_index(json_data)
    name_to_cursor: Dict[str, int] = {name: 0 for name in name_to_indices.keys()}

    applied_summary: Dict[str, int] = {}

    total_pages = len(page_texts)
    total_names = len(names_in_order)
    limit = min(total_pages, total_names)

    for i in range(limit):
        name = names_in_order[i]
        text = page_texts[i]
        version = detect_version_from_text(text)

        indices = name_to_indices.get(name)
        if not indices:
            # Name not found in JSON; skip but log to stderr
            print(f"[warn] Name not found in JSON: {name}", file=sys.stderr)
            continue

        cursor = name_to_cursor.get(name, 0)
        # Find next index without version set if possible
        target_idx: Optional[int] = None
        for j in range(cursor, len(indices)):
            idx = indices[j]
            if "version" not in json_data[idx]:
                target_idx = idx
                name_to_cursor[name] = j + 1
                break
        if target_idx is None:
            # All duplicates already have version; update the last one
            target_idx = indices[-1]

        json_data[target_idx]["version"] = version
        applied_summary[name] = version

    if total_names > total_pages:
        print(
            f"[info] More names ({total_names}) than PDF pages ({total_pages}); processed first {limit} entries.",
            file=sys.stderr,
        )
    elif total_pages > total_names:
        print(
            f"[info] More PDF pages ({total_pages}) than names ({total_names}); processed first {limit} entries.",
            file=sys.stderr,
        )

    return applied_summary


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    pdf_path = base_dir / "character-cards-all-June-2025.pdf"
    names_path = base_dir / "names_by_page_in_pdf.txt"
    json_path = base_dir / "moonstone_data.json"
    backup_path = base_dir / "moonstone_data.json.bak"

    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)
    if not names_path.exists():
        print(f"Names file not found: {names_path}", file=sys.stderr)
        sys.exit(1)
    if not json_path.exists():
        print(f"JSON file not found: {json_path}", file=sys.stderr)
        sys.exit(1)

    print("Extracting text from PDF pages...")
    page_texts = extract_page_texts(pdf_path)

    print("Loading names and JSON data...")
    names_in_order = load_names(names_path)
    # Read raw file to create a backup before modifying
    try:
        raw_json = json_path.read_text(encoding="utf-8")
        backup_path.write_text(raw_json, encoding="utf-8")
        print(f"Backup written to {backup_path.name}")
    except Exception as e:
        print(f"[warn] Failed to create backup: {e}", file=sys.stderr)
    json_data = load_json(json_path)

    print("Assigning versions to JSON entries...")
    summary = assign_versions(names_in_order, page_texts, json_data)

    print("Writing updated JSON...")
    write_json(json_path, json_data)

    print(f"Done. Updated versions for {len(summary)} entries.")


if __name__ == "__main__":
    main()


