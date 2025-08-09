#!/usr/bin/env python3
"""
Generate a landscape US Letter PDF composed of character wide card images.

- Images are sourced from `generated_wide_cards_with_left_text/`
- Ordering is taken from `names_by_page_in_pdf.txt`
- Output is a landscape 8.5x11-inch PDF with 4 images per page (2x2 grid)
- Each image is drawn at exactly 120mm x 70mm
- A small gutter of 5mm is placed between rows and columns

This script assumes the filenames follow the pattern:
  <Character Name>_wide_card_with_text.png

Example: "Eric, the Squire_wide_card_with_text.png"
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

from reportlab.lib.pagesizes import letter, landscape, portrait
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


def read_names_in_order(names_file: Path) -> List[str]:
    names: List[str] = []
    for line in names_file.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if name:
            names.append(name)
    return names


def build_ordered_image_paths(names: List[str], images_dir: Path) -> List[Path]:
    ordered_paths: List[Path] = []
    missing: List[str] = []

    for name in names:
        filename = f"{name}_wide_card_with_text.png"
        candidate = images_dir / filename
        if candidate.exists():
            ordered_paths.append(candidate)
        else:
            missing.append(name)

    if missing:
        sys.stderr.write(
            f"[WARN] {len(missing)} entries from names file had no matching image and were skipped.\n"
        )
        # Print up to first 10 missing to keep output readable
        for n in missing[:10]:
            sys.stderr.write(f"  - Missing image for: {n}\n")
        if len(missing) > 10:
            sys.stderr.write("  ... (more omitted)\n")

    return ordered_paths


def generate_pdf_with_grid(
    images: List[Path],
    output_pdf: Path,
    page_size,
    columns: int,
    rows: int,
    image_width_pt: float,
    image_height_pt: float,
    gutter_x_pt: float,
    gutter_y_pt: float,
    title: str,
    preserve_aspect: bool,
) -> None:
    if not images:
        raise SystemExit("No images to render. Aborting.")

    page_width_pt, page_height_pt = page_size

    total_images_width_pt = (columns * image_width_pt) + ((columns - 1) * gutter_x_pt)
    total_images_height_pt = (rows * image_height_pt) + ((rows - 1) * gutter_y_pt)

    if total_images_width_pt > page_width_pt or total_images_height_pt > page_height_pt:
        raise SystemExit(
            "Configured image sizes + gutters do not fit on the selected page."
        )

    left_margin_pt = (page_width_pt - total_images_width_pt) / 2.0
    bottom_margin_pt = (page_height_pt - total_images_height_pt) / 2.0

    # Precompute placement coordinates (bottom-left origin)
    xs = [left_margin_pt + c * (image_width_pt + gutter_x_pt) for c in range(columns)]
    ys = [bottom_margin_pt + r * (image_height_pt + gutter_y_pt) for r in range(rows)]

    # We want top-to-bottom for rows when placing, so reverse ys for drawing order
    ys_draw = list(reversed(ys))

    c = canvas.Canvas(str(output_pdf), pagesize=page_size, pageCompression=1)
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

            c.drawImage(
                str(img_path),
                x=x,
                y=y,
                width=image_width_pt,
                height=image_height_pt,
                preserveAspectRatio=preserve_aspect,
                anchor="sw",
                mask=None,
            )
        c.showPage()

    c.save()


def generate_pdf_one_per_image_tight_page(images: List[Path], output_pdf: Path) -> None:
    if not images:
        raise SystemExit("No images to render. Aborting.")

    c = canvas.Canvas(str(output_pdf), pageCompression=1)
    c.setTitle("Character Wide Cards (tight pages, 1 per image)")
    c.setAuthor("moonsimdata")

    for img_path in images:
        ir = ImageReader(str(img_path))
        width_px, height_px = ir.getSize()

        # Set the page size to exactly the image size in points (1 pt = 1/72 inch)
        # This produces a page with no whitespace and no scaling by default.
        c.setPageSize((width_px, height_px))
        c.drawImage(
            str(img_path),
            x=0,
            y=0,
            width=width_px,
            height=height_px,
            preserveAspectRatio=False,
            anchor="sw",
            mask=None,
        )
        c.showPage()

    c.save()


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    images_dir = repo_root / "generated_wide_cards_with_left_text"
    names_file = repo_root / "names_by_page_in_pdf.txt"
    output_dir = repo_root / "final_pdfs"
    output_dir.mkdir(parents=True, exist_ok=True)
    # Base filenames for chunked outputs
    base_landscape = "characters_tarot_120x70mm_2x2_landscape"
    base_scaled = "characters_scaled_height_90mm_1x2_portrait"
    base_tight = "characters_native_pixel_size_1up"

    if not images_dir.is_dir():
        raise SystemExit(f"Images directory not found: {images_dir}")
    if not names_file.is_file():
        raise SystemExit(f"Names file not found: {names_file}")

    names = read_names_in_order(names_file)
    # Build mapping and also allow sorting independently of input order
    images_all = build_ordered_image_paths(names, images_dir)
    if not images_all:
        raise SystemExit("No images matched the names list. Nothing to do.")

    # Create name->path for those that exist, then sort by name
    matching_names = [n for n in names if (images_dir / f"{n}_wide_card_with_text.png").exists()]
    name_to_path = {n: images_dir / f"{n}_wide_card_with_text.png" for n in matching_names}
    sorted_names = sorted(matching_names, key=str.casefold)

    # Chunk into 5 near-equal groups
    def split_into_chunks(seq, num_chunks):
        n = len(seq)
        base = n // num_chunks
        rem = n % num_chunks
        chunks = []
        idx = 0
        for i in range(num_chunks):
            size = base + (1 if i < rem else 0)
            chunks.append(seq[idx : idx + size])
            idx += size
        return chunks

    chunks_names = split_into_chunks(sorted_names, 5)

    # Helper to compute label from a chunk
    def first_alpha_lower(s: str) -> str:
        for ch in s:
            if ch.isalpha():
                return ch.lower()
        return "misc"

    # Precompute grid settings
    landscape_settings = dict(
        page_size=landscape(letter),
        columns=2,
        rows=2,
        image_width_pt=120 * mm,
        image_height_pt=70 * mm,
        gutter_x_pt=5 * mm,
        gutter_y_pt=5 * mm,
        title="Character Wide Cards (Tarot 120x70mm, 2x2 Landscape)",
        preserve_aspect=False,
    )

    scale = 90.0 / 70.0
    scaled_width_pt = (120.0 * scale) * mm
    scaled_height_pt = 90.0 * mm
    portrait_settings = dict(
        page_size=portrait(letter),
        columns=1,
        rows=2,
        image_width_pt=scaled_width_pt,
        image_height_pt=scaled_height_pt,
        gutter_x_pt=5 * mm,
        gutter_y_pt=5 * mm,
        title="Character Wide Cards (Scaled to 90mm Height, 1x2 Portrait)",
        preserve_aspect=False,
    )

    # Generate 5 chunked PDFs for each layout
    for _, chunk in enumerate(chunks_names, start=1):
        if not chunk:
            continue
        start_label = first_alpha_lower(chunk[0])
        end_label = first_alpha_lower(chunk[-1])
        range_label = f"{start_label}-{end_label}"

        images_chunk = [name_to_path[n] for n in chunk]

        # Landscape 2x2 exact size
        out_landscape = output_dir / f"{base_landscape}_{range_label}.pdf"
        generate_pdf_with_grid(images_chunk, out_landscape, **landscape_settings)
        print(f"Wrote PDF: {out_landscape}")

        # Portrait 1x2 scaled height
        out_scaled = output_dir / f"{base_scaled}_{range_label}.pdf"
        generate_pdf_with_grid(images_chunk, out_scaled, **portrait_settings)
        print(f"Wrote PDF: {out_scaled}")

        # Tight 1:1 pages
        out_tight = output_dir / f"{base_tight}_{range_label}.pdf"
        generate_pdf_one_per_image_tight_page(images_chunk, out_tight)
        print(f"Wrote PDF: {out_tight}")


if __name__ == "__main__":
    main()


