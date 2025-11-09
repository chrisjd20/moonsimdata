#!/usr/bin/env python3
"""
Scan the Moonstone character data against the October 2025 character card PDF
to determine which characters appear to have a newer version printed.

For each character in `moonstone_data.json`, the script locates the page index
for that character in `names_by_page_in_pdf.txt`, extracts the PDF text for that
page, and looks for a version marker one increment higher than the JSON
`version` value (e.g. JSON version 1 looks for "v.2" on the page). Characters
with such a marker are reported as "modified".
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List


def _load_pdf_reader():
    """Return a PdfReader instance, preferring `pypdf` but falling back to PyPDF2."""

    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except ImportError as exc:
            raise SystemExit(
                "Unable to import `pypdf` or `PyPDF2`. Please install one of them:"
                " pip install pypdf"
            ) from exc
    return PdfReader


@dataclass(frozen=True)
class CharacterEntry:
    name: str
    version: int


def load_characters(json_path: Path) -> Iterable[CharacterEntry]:
    """Yield CharacterEntry records from the JSON data."""

    with json_path.open("r", encoding="utf-8") as fh:
        raw_data = json.load(fh)

    for item in raw_data:
        name = item.get("name")
        version = item.get("version")
        if not isinstance(name, str) or not isinstance(version, int):
            continue
        yield CharacterEntry(name=name.strip(), version=version)


def load_name_index_map(names_path: Path) -> Dict[str, List[int]]:
    """
    Build a mapping of character names to page indexes based on the ordering
    within `names_by_page_in_pdf.txt`. Duplicate names will keep all matching
    page indices (first occurrence at index 0).
    """

    names_map: Dict[str, List[int]] = {}
    with names_path.open("r", encoding="utf-8") as fh:
        for idx, line in enumerate(fh):
            name = line.strip()
            if not name:
                continue
            names_map.setdefault(name, []).append(idx)
    return names_map


def get_page_text(reader, page_index: int, cache: Dict[int, str]) -> str:
    """Fetch (and cache) lowercase text for the requested page index."""

    if page_index not in cache:
        page = reader.pages[page_index]
        text = page.extract_text() or ""
        cache[page_index] = text.lower()
    return cache[page_index]


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    json_path = base_dir / "moonstone_data.json"
    names_path = base_dir / "names_by_page_in_pdf.txt"
    pdf_path = base_dir / "character-cards-all-oct-2025.pdf"

    if not json_path.exists():
        raise SystemExit(f"Missing JSON data file: {json_path}")
    if not names_path.exists():
        raise SystemExit(f"Missing names index file: {names_path}")
    if not pdf_path.exists():
        raise SystemExit(f"Missing PDF file: {pdf_path}")

    PdfReader = _load_pdf_reader()
    reader = PdfReader(str(pdf_path))

    name_map = load_name_index_map(names_path)
    page_text_cache: Dict[int, str] = {}

    modified: List[str] = []
    missing_names: List[str] = []
    missing_pages: List[str] = []

    for entry in load_characters(json_path):
        page_indexes = name_map.get(entry.name)
        if not page_indexes:
            missing_names.append(entry.name)
            continue

        page_index = page_indexes[0]
        if page_index >= len(reader.pages):
            missing_pages.append(f"{entry.name} (page index {page_index})")
            continue

        page_text = get_page_text(reader, page_index, page_text_cache)
        next_version = entry.version + 1
        # Match patterns like "v.2", "V2", or "v 2".
        version_pattern = re.compile(rf"\bv\.?\s*{next_version}\b", re.IGNORECASE)

        if version_pattern.search(page_text):
            modified.append(f"{entry.name} (page index {page_index}, JSON version {entry.version})")

    if modified:
        print("Characters that appear to have updated versions in the PDF:")
        for item in modified:
            print(f"- {item}")
    else:
        print("No modified characters detected.")

    if missing_names:
        print("\nCharacters missing from names index:")
        for name in sorted(set(missing_names)):
            print(f"- {name}")

    if missing_pages:
        print("\nCharacters whose page index exceeded the PDF page count:")
        for detail in missing_pages:
            print(f"- {detail}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

