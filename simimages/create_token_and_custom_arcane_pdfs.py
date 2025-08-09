#!/usr/bin/env python3
"""
Create two PDFs:

1) Tokens deck (various tokens at specified physical sizes and counts)
   - Output: simimages/final_pdfs/tokens_deck.pdf

2) Custom Arcane deck split from a spritesheet (ArcaneDeck.png)
   - Spritesheet frame size: 500x700 px, 3 columns x 7 rows (21 cards)
   - Printed card size: 63.5mm x 88.9mm (2.5in x 3.5in)
   - Layout: landscape US Letter, 3 cols x 2 rows (6 per page)
   - Output: simimages/final_pdfs/arcane_deck.pdf
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import List

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

try:
    from PIL import Image
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "Pillow (PIL) is required. Please install with: python3 -m pip install --user pillow"
    ) from exc


@dataclass(frozen=True)
class TokenSpec:
    filename_stem: str
    size_mm: float
    count: int


def ensure_output_dir(base_dir: Path) -> Path:
    out_dir = base_dir / "final_pdfs"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def draw_grid(images: List[ImageReader], image_w_pt: float, image_h_pt: float, page_size, columns: int, rows: int, output_pdf: Path, title: str) -> None:
    page_w_pt, page_h_pt = page_size
    gutter_x_pt = 5 * mm
    gutter_y_pt = 5 * mm

    total_w_pt = (columns * image_w_pt) + ((columns - 1) * gutter_x_pt)
    total_h_pt = (rows * image_h_pt) + ((rows - 1) * gutter_y_pt)

    if total_w_pt > page_w_pt or total_h_pt > page_h_pt:
        raise SystemExit("Grid does not fit on page. Adjust sizes/gutters/cols/rows.")

    left_margin = (page_w_pt - total_w_pt) / 2.0
    bottom_margin = (page_h_pt - total_h_pt) / 2.0

    xs = [left_margin + c * (image_w_pt + gutter_x_pt) for c in range(columns)]
    ys = [bottom_margin + r * (image_h_pt + gutter_y_pt) for r in range(rows)]
    ys_draw = list(reversed(ys))

    c = canvas.Canvas(str(output_pdf), pagesize=page_size, pageCompression=1)
    c.setTitle(title)
    c.setAuthor("moonsimdata")

    per_page = columns * rows
    for i in range(0, len(images), per_page):
        page_images = images[i : i + per_page]
        for idx, img in enumerate(page_images):
            col = idx % columns
            row = idx // columns
            x = xs[col]
            y = ys_draw[row]
            c.drawImage(
                img,
                x=x,
                y=y,
                width=image_w_pt,
                height=image_h_pt,
                preserveAspectRatio=False,
                anchor="sw",
                mask=None,
            )
        c.showPage()
    c.save()


def build_token_pages(base_dir: Path, output_dir: Path) -> Path:
    specs: List[TokenSpec] = [
        TokenSpec("WaterFeatureToken1alt", 51.0, 1),
        TokenSpec("WaterFeatureToken2alt", 51.0, 1),
        TokenSpec("WaterFeatureToken3alt", 51.0, 1),
        TokenSpec("WoodedPatchToken1alt", 51.0, 1),
        TokenSpec("WoodedPatchToken2alt", 51.0, 1),
        TokenSpec("WoodedPatchToken3alt", 51.0, 1),
        TokenSpec("moneybag", 31.0, 5),
        TokenSpec("bags", 31.0, 5),
    ]

    # Split by size so we can pack efficiently with clean grids
    by_size: dict[float, List[ImageReader]] = {}
    for spec in specs:
        img_path = (base_dir / f"{spec.filename_stem}.png")
        if not img_path.exists():
            raise SystemExit(f"Missing token image: {img_path}")
        reader = ImageReader(str(img_path))
        by_size.setdefault(spec.size_mm, [])
        by_size[spec.size_mm].extend([reader] * spec.count)

    # Single-page layout combining both 50mm and 30mm tokens
    out_pdf = output_dir / "tokens_deck.pdf"

    page_w_pt, page_h_pt = landscape(letter)
    gutter_x_pt = 5 * mm
    gutter_y_pt = 5 * mm
    outer_margin_x_pt = 10 * mm  # left/right page margin to avoid hugging edges
    outer_margin_y_pt = 10 * mm  # top/bottom page margin

    images_51 = by_size.get(51.0, [])
    images_31 = by_size.get(31.0, [])

    size51_pt = 51.0 * mm
    size31_pt = 31.0 * mm

    def max_cols_that_fit(item_w: float, available_w: float, gutter: float) -> int:
        cols = 1
        while True:
            next_cols = cols + 1
            total = next_cols * item_w + (next_cols - 1) * gutter
            if total <= available_w:
                cols = next_cols
            else:
                break
        return cols

    available_w_pt = max(0.0, page_w_pt - 2 * outer_margin_x_pt)
    cols_51 = max_cols_that_fit(size51_pt, available_w_pt, gutter_x_pt) if images_51 else 0
    cols_31 = max_cols_that_fit(size31_pt, available_w_pt, gutter_x_pt) if images_31 else 0

    rows_51 = math.ceil(len(images_51) / cols_51) if cols_51 else 0
    rows_31 = math.ceil(len(images_31) / cols_31) if cols_31 else 0

    section50_h = rows_51 * size51_pt + max(0, rows_51 - 1) * gutter_y_pt
    section30_h = rows_31 * size31_pt + max(0, rows_31 - 1) * gutter_y_pt
    inter_section_gutter = gutter_y_pt if (rows_51 and rows_31) else 0
    total_h = section50_h + inter_section_gutter + section30_h

    available_h_pt = max(0.0, page_h_pt - 2 * outer_margin_y_pt)
    if total_h > available_h_pt:
        raise SystemExit("Tokens exceed single page height with current layout; reduce gutters or sizes.")

    c = canvas.Canvas(str(out_pdf), pagesize=landscape(letter), pageCompression=1)
    c.setTitle("Tokens Deck")
    c.setAuthor("moonsimdata")

    bottom_margin = outer_margin_y_pt + (available_h_pt - total_h) / 2.0

    # Draw 50mm section at top portion
    if rows_51:
        section_total_w_50 = cols_51 * size51_pt + (cols_51 - 1) * gutter_x_pt
        left_margin_50 = outer_margin_x_pt + (available_w_pt - section_total_w_50) / 2.0
        # y position of the top of the 50mm section
        top_50 = bottom_margin + total_h
        for idx, img in enumerate(images_51):
            col = idx % cols_51
            row = idx // cols_51
            x = left_margin_50 + col * (size51_pt + gutter_x_pt)
            # place rows from top down within the 50mm section
            y = top_50 - (row + 1) * size51_pt - row * gutter_y_pt
            c.drawImage(
                img,
                x=x,
                y=y,
                width=size51_pt,
                height=size51_pt,
                preserveAspectRatio=False,
                anchor="sw",
                mask="auto",
            )

    # Draw 30mm section below 50mm section
    if rows_31:
        section_total_w_30 = cols_31 * size31_pt + (cols_31 - 1) * gutter_x_pt
        left_margin_30 = outer_margin_x_pt + (available_w_pt - section_total_w_30) / 2.0
        # base y at the bottom margin
        y_base_30 = bottom_margin
        for idx, img in enumerate(images_31):
            col = idx % cols_31
            row = idx // cols_31
            x = left_margin_30 + col * (size31_pt + gutter_x_pt)
            # place rows from bottom up within the 30mm section
            y = y_base_30 + row * (size31_pt + gutter_y_pt)
            c.drawImage(
                img,
                x=x,
                y=y,
                width=size31_pt,
                height=size31_pt,
                preserveAspectRatio=False,
                anchor="sw",
                mask="auto",
            )

    c.showPage()
    c.save()
    return out_pdf


def slice_arcane_spritesheet(sheet_path: Path, frame_w: int, frame_h: int, cols: int, rows: int) -> List[Image.Image]:
    # Load full sheet as RGBA to preserve alpha if present
    sheet_rgba = Image.open(sheet_path).convert("RGBA")
    sheet_w, sheet_h = sheet_rgba.size
    expected_w = cols * frame_w
    expected_h = rows * frame_h
    if sheet_w < expected_w or sheet_h < expected_h:
        raise SystemExit(
            f"Spritesheet smaller than expected grid. Sheet: {sheet_w}x{sheet_h}, "
            f"Expected at least: {expected_w}x{expected_h} for {cols}x{rows} of {frame_w}x{frame_h}"
        )
    sprites: List[Image.Image] = []
    for r in range(rows):
        for c in range(cols):
            left = c * frame_w
            upper = r * frame_h
            right = left + frame_w
            lower = upper + frame_h
            crop_rgba = sheet_rgba.crop((left, upper, right, lower))
            # Composite onto white to eliminate alpha (prevents black tiles in some PDF viewers)
            white_bg = Image.new("RGBA", crop_rgba.size, (255, 255, 255, 255))
            composited = Image.alpha_composite(white_bg, crop_rgba).convert("RGB")
            # Copy to ensure no reference to parent sheet remains
            sprites.append(composited.copy())
    return sprites


def build_arcane_deck(base_dir: Path, output_dir: Path) -> Path:
    sheet = base_dir / "ArcaneDeck.png"
    if not sheet.exists():
        raise SystemExit(f"Arcane deck spritesheet not found: {sheet}")

    # Actual grid is 7 columns x 3 rows of 500x700px frames
    frames = slice_arcane_spritesheet(sheet, frame_w=500, frame_h=700, cols=7, rows=3)
    # Convert to ImageReader for direct drawing without writing temp files
    readers: List[ImageReader] = [ImageReader(frame) for frame in frames]

    # Card size
    card_w_pt = 63.5 * mm
    card_h_pt = 88.9 * mm

    # Layout: landscape letter, 3 cols x 2 rows
    page_size = landscape(letter)
    columns = 3
    rows = 2

    # Build grid pages
    page_w_pt, page_h_pt = page_size
    gutter_x_pt = 5 * mm
    gutter_y_pt = 5 * mm

    total_w_pt = (columns * card_w_pt) + ((columns - 1) * gutter_x_pt)
    total_h_pt = (rows * card_h_pt) + ((rows - 1) * gutter_y_pt)
    if total_w_pt > page_w_pt or total_h_pt > page_h_pt:
        raise SystemExit("Arcane deck grid does not fit on page; adjust sizes or gutters.")

    left_margin = (page_w_pt - total_w_pt) / 2.0
    bottom_margin = (page_h_pt - total_h_pt) / 2.0

    xs = [left_margin + c * (card_w_pt + gutter_x_pt) for c in range(columns)]
    ys = [bottom_margin + r * (card_h_pt + gutter_y_pt) for r in range(rows)]
    ys_draw = list(reversed(ys))

    out_pdf = output_dir / "arcane_deck.pdf"
    c = canvas.Canvas(str(out_pdf), pagesize=page_size, pageCompression=1)
    c.setTitle("Custom Arcane Deck")
    c.setAuthor("moonsimdata")

    per_page = columns * rows
    for i in range(0, len(readers), per_page):
        page_images = readers[i : i + per_page]
        for idx, img in enumerate(page_images):
            col = idx % columns
            row = idx // columns
            x = xs[col]
            y = ys_draw[row]
            c.drawImage(
                img,
                x=x,
                y=y,
                width=card_w_pt,
                height=card_h_pt,
                preserveAspectRatio=False,
                anchor="sw",
                mask=None,
            )
        c.showPage()
    c.save()
    return out_pdf


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    output_dir = ensure_output_dir(base_dir)

    tokens_pdf = build_token_pages(base_dir, output_dir)
    print(f"Wrote tokens PDF: {tokens_pdf}")

    arcane_pdf = build_arcane_deck(base_dir, output_dir)
    print(f"Wrote arcane deck PDF: {arcane_pdf}")


if __name__ == "__main__":
    main()


