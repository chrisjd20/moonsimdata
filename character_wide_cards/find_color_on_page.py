"""Utility to inspect colors on the first page of the character cards PDF.

Goal: Find any fill / stroke / text or image pixels close to a target green (#43a83b)
and dump their bounding boxes plus the PDF drawing operators that produce them.

Approach:
1. Use PyMuPDF (fitz) to load the PDF and get page 0.
2. Extract text spans (they carry color in span["color"] & span["fill"] etc.).
3. Extract the raw display list -> list of drawing commands; iterate to capture
   fill / stroke colors of vector objects (paths, rectangles etc.).
4. Rasterize the page at moderate zoom and do a pixel search for near-matching
   green to ensure we don't miss image-based color (in case it's embedded in a
   larger sprite sheet image).
5. Print a concise report ranked by deltaE (simple Euclidean in RGB) to the
   target color. Also save optional debug PNGs for any matches.

Run:
	python character_wide_cards/find_color_on_page.py \
		--pdf character_wide_cards/character-cards-all-June-2025.pdf \
		--page 0
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass, asdict
from typing import Iterable, List, Tuple, Dict, Any

import fitz  # PyMuPDF
from PIL import Image

# Default single target (legacy behaviour)
DEFAULT_TARGET_HEX = "#43a83b"
BLUEHEX="#009ee4" # just storing these here
REDHEX="#e6007d" # just storing these here


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
	hex_color = hex_color.strip().lstrip("#")
	if len(hex_color) == 3:  # short form
		hex_color = ''.join(c*2 for c in hex_color)
	return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
	return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def rgb_distance(a: Tuple[int, int, int], b: Tuple[int, int, int]) -> float:
	return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


@dataclass
class ColorHit:
	kind: str  # text-span / vector-path / vector-rect / image-pixel
	rgb: Tuple[int, int, int]
	distance: float
	bbox: Tuple[float, float, float, float]
	extra: str = ""
	target: Tuple[int, int, int] | None = None  # which target it matched best

	def to_row(self) -> str:
		(x0, y0, x1, y1) = self.bbox
		target_hex = rgb_to_hex(self.target) if self.target else "-"
		return (
			f"{self.kind:12} rgb={self.rgb} -> {target_hex} d={self.distance:6.2f} "
			f"bbox=({x0:6.1f},{y0:6.1f},{x1:6.1f},{y1:6.1f}) {self.extra}"
		)


def iter_text_colors(page: fitz.Page, targets: List[Tuple[int,int,int]], threshold: float) -> Iterable[ColorHit]:
	text = page.get_text("rawdict")
	for block in text.get("blocks", []):
		if block.get("type") != 0:  # text
			continue
		for line in block.get("lines", []):
			for span in line.get("spans", []):
				col = span.get("color")
				rgb = decode_span_rgb(col)
				if not rgb:
					continue
				# find closest target
				best_t = None
				best_d = 10**9
				for t in targets:
					dd = rgb_distance(rgb, t)
					if dd < best_d:
						best_d = dd
						best_t = t
				if best_d < threshold:
					bbox = tuple(span.get("bbox", (0, 0, 0, 0)))  # type: ignore
					yield ColorHit("text-span", rgb, best_d, bbox, span.get("text", "")[:30], target=best_t)


def iter_vector_colors(page: fitz.Page, targets: List[Tuple[int,int,int]], threshold: float) -> Iterable[ColorHit]:
	"""Iterate over vector drawing objects (paths, rectangles, lines).

	page.get_drawings() returns a list of dicts, each may have 'color' (stroke)
	and 'fill' (fill) as RGB floats (0..1). We examine both.
	"""
	for idx, d in enumerate(page.get_drawings()):
		bbox = d.get("rect")
		if not bbox:
			# compute from items maybe, skip for now
			continue
		for kind_key, label in [("color", "stroke"), ("fill", "fill")]:
			col = d.get(kind_key)
			if not col:
				continue
			try:
				rgb = tuple(int(round(x * 255)) for x in col[:3])  # floats 0-1
			except Exception:
				continue
			# pick best target
			best_t = None
			best_d = 10**9
			for t in targets:
				dd = rgb_distance(rgb, t)
				if dd < best_d:
					best_d = dd
					best_t = t
			if best_d < threshold:
				extra = f"vect_id={idx} {label} has {len(d.get('items', []))} subpaths"
				yield ColorHit(f"vector-{label}", rgb, best_d, (bbox.x0, bbox.y0, bbox.x1, bbox.y1), extra, target=best_t)


def collect_all_vectors(page: fitz.Page) -> List[Dict[str, Any]]:
	vectors = []
	for idx, d in enumerate(page.get_drawings()):
		bbox = d.get("rect")
		rec = {
			"id": idx,
			"bbox": (bbox.x0, bbox.y0, bbox.x1, bbox.y1) if bbox else None,
			"stroke_color": tuple(int(round(c * 255)) for c in d.get("color", [])[:3]) if d.get("color") else None,
			"fill_color": tuple(int(round(c * 255)) for c in d.get("fill", [])[:3]) if d.get("fill") else None,
			"width": d.get("width"),
			"closePath": d.get("closePath"),
			"items_len": len(d.get("items", [])),
		}
		# dimension helpers
		if rec["bbox"]:
			x0, y0, x1, y1 = rec["bbox"]
			rec["w"] = x1 - x0
			rec["h"] = y1 - y0
			rec["area"] = rec["w"] * rec["h"]
			# classification heuristics
			w = rec["w"]
			h = rec["h"] if rec["h"] else 0.0001  # avoid zero division
			ratio = w / h if h else 0
			rec["aspect"] = ratio
			# Determine if square-ish (X badge squares) vs tall pill badges
			is_squareish = abs(w - h) / h < 0.20 and 4.5 <= w <= 8.0 and 4.5 <= h <= 8.0
			is_tall_pill = rec["items_len"] == 8 and 0.6 <= ratio <= 0.8 and h > w and h >= 6 and w <= 5
			if is_squareish and rec["items_len"] in (4,8):
				rec["shape_class"] = "xbadge"  # colored square with X glyph overlay (white X rendered separately)
			elif is_tall_pill:
				rec["shape_class"] = "badge"
			else:
				rec["shape_class"] = "other"
			# center point
			rec["cx"] = x0 + w / 2
			rec["cy"] = y0 + h / 2
		vectors.append(rec)
	return vectors


def decode_span_rgb(col_value) -> Tuple[int, int, int] | None:
	"""Decode a span['color'] which may be:
	- int (0xRRGGBB)
	- list/tuple of floats 0..1
	- list/tuple 0..255
	Returns RGB or None.
	"""
	if col_value is None:
		return None
	if isinstance(col_value, int):
		if col_value < 0:
			return None
		r = (col_value >> 16) & 0xFF
		g = (col_value >> 8) & 0xFF
		b = col_value & 0xFF
		return (r, g, b)
	if isinstance(col_value, (list, tuple)):
		if len(col_value) < 3:
			return None
		first = col_value[0]
		if 0 <= first <= 1:  # assume floats 0..1
			return tuple(int(round(x * 255)) for x in col_value[:3])  # type: ignore
		else:  # assume already 0..255 ints
			return tuple(int(x) for x in col_value[:3])  # type: ignore
	return None


def scan_image_pixels(page: fitz.Page, targets: List[Tuple[int,int,int]], threshold: float, zoom: float = 2.0, max_hits: int = 40) -> List[ColorHit]:
	mat = fitz.Matrix(zoom, zoom)
	pix = page.get_pixmap(matrix=mat, alpha=False)
	img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
	hits: List[ColorHit] = []
	# convert to list of pixels w/ coordinates; sample every n pixels to keep speed
	sample_step = 1
	threshold = 35  # tighter threshold on raster search
	for y in range(0, img.height, sample_step):
		row = img.crop((0, y, img.width, y + 1))
		px = row.tobytes()
		for x in range(img.width):
			r = px[3 * x]
			g = px[3 * x + 1]
			b = px[3 * x + 2]
			rgb = (r, g, b)
			# compute best target
			best_t = None
			best_d = 10**9
			for t in targets:
				dd = rgb_distance(rgb, t)
				if dd < best_d:
					best_d = dd
					best_t = t
			if best_d < threshold:
				# Map back to PDF coordinate space (divide by zoom)
				bbox = (x / zoom, y / zoom, (x + 1) / zoom, (y + 1) / zoom)
				hits.append(ColorHit("image-pixel", rgb, best_d, bbox, target=best_t))
				if len(hits) >= max_hits:
					return hits
	return hits



def analyze_page(
	pdf_path: str,
	page_num: int,
	include_raster: bool = True,
	targets: List[Tuple[int,int,int]] | None = None,
	threshold: float = 80.0,
) -> Tuple[List[ColorHit], List[Dict[str, Any]]]:
	doc = fitz.open(pdf_path)
	page = doc[page_num]
	hits: List[ColorHit] = []
	if targets is None:
		targets = [hex_to_rgb(DEFAULT_TARGET_HEX)]
	hits.extend(iter_text_colors(page, targets, threshold))
	hits.extend(iter_vector_colors(page, targets, threshold))
	if include_raster:
		hits.extend(scan_image_pixels(page, targets, min(threshold/2, threshold)))
	# sort by distance
	hits.sort(key=lambda h: h.distance)
	vectors = collect_all_vectors(page)
	return hits, vectors


def main():
	parser = argparse.ArgumentParser(description="Find objects whose colors match target hex codes on a PDF page")
	parser.add_argument("--pdf", required=True, help="Path to PDF")
	parser.add_argument("--page", type=int, default=0, help="Page number (0-based)")
	parser.add_argument("--limit", type=int, default=80, help="Max rows to print")
	parser.add_argument("--no-raster", action="store_true", help="Skip raster pixel scan (vector + text only)")
	parser.add_argument("--dump-json", help="Write JSON file with detailed vector objects near the target", nargs="?", const="vector_debug.json")
	parser.add_argument("--save-debug", action="store_true", help="Save debug PNG with highlighted hits")
	parser.add_argument("--vector-id", type=int, help="Show detailed drawing commands for this vector id")
	parser.add_argument("--crop-out", action="store_true", help="When used with --vector-id, also save a cropped PNG of just that object")
	parser.add_argument("--colors", help="Comma-separated hex colors to search (e.g. '#43a83b,#009ee4,#e6007d')")
	parser.add_argument("--threshold", type=float, default=80.0, help="RGB Euclidean distance threshold (default 80; lower= stricter)")
	parser.add_argument("--filter-shape", choices=["any","badge","circle","xbadge"], default="any", help="Limit reported vector hits to a shape classification")
	parser.add_argument("--only-x-badges", action="store_true", help="Shortcut: same as --filter-shape xbadge and tight color threshold (40) if higher")
	parser.add_argument("--expected-count", type=int, help="Warn if filtered hits != this count")
	parser.add_argument("--badge-aspect", default="0.6,0.8", help="Aspect ratio (w/h) min,max band for badge classification (default 0.6,0.8)")
	parser.add_argument("--find-x", action="store_true", help="Also collect colored text spans containing just 'X' as X markers")
	args = parser.parse_args()

	if args.colors:
		target_hexes = [c.strip() for c in args.colors.split(',') if c.strip()]
	else:
		target_hexes = [DEFAULT_TARGET_HEX]
	# apply shortcut
	if args.only_x_badges:
		args.filter_shape = "xbadge"
		if args.threshold > 40:
			args.threshold = 40

	# allow user to tweak badge aspect band
	try:
		bmin, bmax = [float(x) for x in args.badge_aspect.split(',')]
	except Exception:
		bmin, bmax = 0.6, 0.8

	target_rgbs = [hex_to_rgb(h) for h in target_hexes]
	hits, vectors = analyze_page(args.pdf, args.page, include_raster=not args.no_raster, targets=target_rgbs, threshold=args.threshold)
	print(f"Targets: {', '.join(target_hexes)} (threshold {args.threshold}). Total hits={len(hits)}")
	for h in hits[: args.limit]:
		print(h.to_row())

	# Aggregate by target
	by_target: Dict[str, List[ColorHit]] = {}
	for h in hits:
		thex = rgb_to_hex(h.target) if h.target else rgb_to_hex(h.rgb)
		by_target.setdefault(thex.lower(), []).append(h)
	print("\nSummary by target:")
	for th in target_hexes:
		arr = by_target.get(th.lower(), [])
		print(f"  {th}: {len(arr)} hits")
		for hh in arr[:10]:
			print(f"    - {hh.kind} id?{hh.extra} bbox={tuple(round(v,1) for v in hh.bbox)} d={hh.distance:.2f}")
		if len(arr) > 10:
			print("    ...")

	# Shape-filtered vector hits (focus on symbol badges)
	badge_band = (bmin, bmax)
	filtered_vectors = []
	for v in vectors:
		if v.get("fill_color") is None:
			continue
		# check if vector color matched one of targets
		if not any(rgb_distance(v["fill_color"], t) < args.threshold for t in target_rgbs):
			continue
		shape = v.get("shape_class")
		# recompute badge classification with user aspect band
		if shape == "badge":
			ratio = v.get("aspect", 0)
			if not (badge_band[0] <= ratio <= badge_band[1]):
				shape = "other"
		if args.filter_shape != "any" and shape != args.filter_shape:
			continue
		filtered_vectors.append(v)

	print(f"\nFiltered vectors (shape={args.filter_shape}, colors in targets): {len(filtered_vectors)}")
	for v in filtered_vectors:
		print(
			f" id={v['id']:>3} shape={v['shape_class']:<6} fill={rgb_to_hex(v['fill_color']) if v['fill_color'] else None} "
			f"bbox=({v['bbox'][0]:.2f},{v['bbox'][1]:.2f},{v['bbox'][2]:.2f},{v['bbox'][3]:.2f}) "
			f"center=({v['cx']:.2f},{v['cy']:.2f}) w={v['w']:.2f} h={v['h']:.2f} aspect={v['aspect']:.2f}"
		)

	# Optionally gather colored text 'X' glyphs (these might represent inline X markers)
	text_x = []
	if args.find_x:
		# Build spatial index of vector fills for background color inference
		vec_fills = [v for v in vectors if v.get('fill_color') and v.get('bbox')]
		for h in hits:
			if h.kind != 'text-span':
				continue
			txt = h.extra if h.extra else ''
			if txt.strip() != 'X':
				continue
			# Determine underlying colored square (if any) by bbox containment with small padding
			(x0,y0,x1,y1) = h.bbox
			cx = (x0+x1)/2; cy=(y0+y1)/2
			bg_color = None
			for v in vec_fills:
				vb = v['bbox']
				if vb and (vb[0]-0.5) <= cx <= (vb[2]+0.5) and (vb[1]-0.5) <= cy <= (vb[3]+0.5):
					bg_color = v['fill_color']
					shape = v.get('shape_class')
					break
			if bg_color is None:
				continue  # skip X not on colored box
			# Match bg color to targets
			best_t=None; best_d=10**9
			for t in target_rgbs:
				d=rgb_distance(bg_color, t)
				if d<best_d:
					best_d=d; best_t=t
			if best_d < args.threshold:
				text_x.append({
					'type':'text-X',
					'fill': rgb_to_hex(bg_color),
					'bbox': h.bbox,
					'center': (cx, cy),
					'bg_match': rgb_to_hex(best_t) if best_t else None,
					'shape': shape,
				})
	print(f"\nText X markers: {len(text_x)}" if args.find_x else "")
	if args.find_x:
		for tx in text_x:
			print(f" text-X fill={tx['fill']} bbox=({tx['bbox'][0]:.2f},{tx['bbox'][1]:.2f},{tx['bbox'][2]:.2f},{tx['bbox'][3]:.2f}) center=({tx['center'][0]:.2f},{tx['center'][1]:.2f})")

	if args.find_x and args.expected_count is not None:
		total_x = len(filtered_vectors) + len(text_x)
		if total_x != args.expected_count:
			print(f"WARNING: expected total X markers {args.expected_count}, found {total_x} (vector badges {len(filtered_vectors)} + text X {len(text_x)})")
		else:
			print(f"Total X markers match expected_count={args.expected_count}")

	if args.expected_count is not None and len(filtered_vectors) != args.expected_count:
		print(f"WARNING: expected {args.expected_count} filtered vectors, found {len(filtered_vectors)}")

	if args.dump_json:
		# Filter vectors that involve our color (within threshold)
		cand_vectors = []
		for v in vectors:
			near = []
			for role in ["stroke_color", "fill_color"]:
				col = v.get(role)
				if col:
					for t in target_rgbs:
						d = rgb_distance(col, t)
						if d < args.threshold:
							near.append({"role": role, "distance": d, "rgb": col, "target": rgb_to_hex(t)})
			if near:
				vcopy = dict(v)
				vcopy["near_matches"] = near
				cand_vectors.append(vcopy)
		out_obj = {
			"targets": target_hexes,
			"page": args.page,
			"vectors_matching": cand_vectors,
		}
		with open(args.dump_json, "w", encoding="utf-8") as f:
			json.dump(out_obj, f, indent=2)
		print(f"Wrote vector debug JSON -> {args.dump_json} (matches={len(cand_vectors)})")

	if args.save_debug and hits:
		doc = fitz.open(args.pdf)
		page = doc[args.page]
		zoom = 2
		mat = fitz.Matrix(zoom, zoom)
		pix = page.get_pixmap(matrix=mat, alpha=False)
		img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
		# draw simple rectangles (red) around top hits
		try:
			from PIL import ImageDraw

			draw = ImageDraw.Draw(img)
			for h in hits[:50]:
				(x0, y0, x1, y1) = h.bbox
				draw.rectangle([
					x0 * zoom,
					y0 * zoom,
					x1 * zoom,
					y1 * zoom,
				], outline=(255, 0, 0))
			out_path = os.path.splitext(args.pdf)[0] + f"_page{args.page}_green_debug.png"
			img.save(out_path)
			print(f"Saved debug image {out_path}")
		except Exception as e:  # pragma: no cover
			print("Could not draw debug image:", e)

	# Detailed vector inspection
	if args.vector_id is not None:
		vec = next((v for v in vectors if v["id"] == args.vector_id), None)
		if not vec:
			print(f"Vector id {args.vector_id} not found on page {args.page}")
		else:
			print(f"\nVector {args.vector_id} detail:")
			for k, v in vec.items():
				print(f"  {k}: {v}")
			# Access raw drawing dict again to dump item commands
			doc2 = fitz.open(args.pdf)
			page2 = doc2[args.page]
			draw = page2.get_drawings()[args.vector_id]
			print("  items (truncated to first 20):")
			for i, it in enumerate(draw.get("items", [])[:20]):
				print(f"    {i}: {it}")
			if args.crop_out and vec.get("bbox"):
				(x0, y0, x1, y1) = vec["bbox"]
				zoom = 8  # high zoom for clarity
				mat = fitz.Matrix(zoom, zoom)
				clip = fitz.Rect(x0, y0, x1, y1)
				pix = page2.get_pixmap(matrix=mat, clip=clip, alpha=False)
				out_path = f"vector_{args.vector_id}_crop.png"
				Image.frombytes("RGB", [pix.width, pix.height], pix.samples).save(out_path)
				print(f"  Saved crop -> {out_path} (zoom {zoom}x)")


if __name__ == "__main__":  # pragma: no cover
	main()
