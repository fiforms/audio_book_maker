#!/usr/bin/env python3
"""
split_book_pages.py

Processes a scanned book PDF where each PDF page contains two book pages
stored sideways (portrait container, landscape content). For each input page:
  1. Renders to image at TARGET_DPI
  2. Rotates 90° clockwise
  3. Crops left book page and right book page
  4. Assembles all pages into a new PDF in reading order

Approach: pixel-based (pdf2image + Pillow) rather than pypdf geometry,
because the scanned pages have no rotation metadata — the content is simply
sideways inside a portrait page.

Usage:
    pip install pdf2image pillow pypdf
    python split_book_pages.py input.pdf output.pdf

Requires poppler on PATH (brew install poppler / apt install poppler-utils).
"""

import argparse
import io
from pathlib import Path

from pdf2image import convert_from_path
from pypdf import PdfReader, PdfWriter

# ── CONFIGURATION ─────────────────────────────────────────────────────────────

# Render DPI. Higher = better quality but larger file and slower processing.
# 200 is a good balance; use 300 for archival quality.
TARGET_DPI = 300

# All measurements in INCHES, left-to-right across the rotated (landscape) image:
#
#   |<-- LEFT_MARGIN -->|<-- first page -->|<-- GUTTER -->|<-- second page -->|
#
LEFT_MARGIN_IN      = 2.375    # dead/black margin at the left edge (discarded)
LEFT_PAGE_WIDTH_IN  = 5.5   # width of the first book page
GUTTER_WIDTH_IN     = 0.375   # gutter between pages (discarded)
RIGHT_PAGE_WIDTH_IN = 5.5   # width of the second book page (None = remainder)

# Trim from top/bottom of each output page (inches).
# Adjust to remove scanner shadow or border bleed along the long edges.
TOP_TRIM_IN    = 0.0
BOTTOM_TRIM_IN = 0.0

# JPEG quality for internal compression (1-95). 85 is a good default.
JPEG_QUALITY = 85

# ── END CONFIGURATION ─────────────────────────────────────────────────────────


ROTATION_ALIASES = {"cw": -90, "ccw": 90, "invert": 180, "none": 0}


def parse_rotation(value: str) -> int:
    lower = value.lower()
    if lower in ROTATION_ALIASES:
        return ROTATION_ALIASES[lower]
    try:
        return int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"--rotation must be a degree value or one of: {', '.join(ROTATION_ALIASES)}"
        )


def parse_boundaries(value: str):
    parts = value.split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            "--boundaries requires exactly 4 comma-separated values: "
            "MARGIN,LEFT_WIDTH,GUTTER,RIGHT_WIDTH"
        )
    try:
        return [float(p) for p in parts]
    except ValueError:
        raise argparse.ArgumentTypeError("--boundaries values must be numbers")


def process_pdf(input_path: str, output_path: str, rotate_degrees: int, boundaries: list,
                skip: int = 0, limit: int = None):
    margin_in, left_width_in, gutter_in, right_width_in = boundaries

    print(f"Input    : {input_path}")
    print(f"Output   : {output_path}")
    print(f"DPI      : {TARGET_DPI}")
    print(f"Rotation : {rotate_degrees}°" if rotate_degrees else "Rotation : none")
    print(f"Boundaries (in): margin={margin_in}, left={left_width_in}, gutter={gutter_in}, right={right_width_in}")

    pages = convert_from_path(input_path, dpi=TARGET_DPI)
    total_in = len(pages)
    total_out = total_in * 2
    expected_out = min(max(total_out - skip, 0), limit) if limit is not None else max(total_out - skip, 0)

    if skip or limit is not None:
        print(f"Pages : {total_in} input ({total_out} output), writing {expected_out} (skip={skip}"
              + (f", limit={limit})" if limit is not None else ")"))
    else:
        print(f"Pages : {total_in} input → {total_out} output")
    print()

    px = TARGET_DPI  # pixels per inch

    writer = PdfWriter()
    out_index = 0   # output pages seen so far (before skip/limit filtering)
    out_written = 0

    for img in pages:
        if limit is not None and out_written >= limit:
            break

        # Step 1: rotate (skip if 0)
        rotated = img.rotate(rotate_degrees, expand=True) if rotate_degrees else img
        w, h = rotated.size

        # Step 2: compute crop bounds in pixels
        top_px    = int(TOP_TRIM_IN    * px)
        bottom_px = h - int(BOTTOM_TRIM_IN * px)

        margin_px    = int(margin_in     * px)
        first_start  = margin_px
        first_end    = first_start + int(left_width_in  * px)
        second_start = first_end   + int(gutter_in      * px)
        second_end   = second_start + int(right_width_in * px)

        # Step 3: crop
        first_img  = rotated.crop((first_start,  top_px, first_end,  bottom_px))
        second_img = rotated.crop((second_start, top_px, second_end, bottom_px))

        # Step 4: emit crops, honouring skip/limit on output pages
        for crop in (first_img, second_img):
            if out_index < skip:
                out_index += 1
                continue
            if limit is not None and out_written >= limit:
                break
            buf = io.BytesIO()
            crop.save(buf, format="PDF", resolution=TARGET_DPI)
            buf.seek(0)
            writer.add_page(PdfReader(buf).pages[0])
            out_index += 1
            out_written += 1

        if out_written > 0 and (out_written % 10 == 0 or out_written == expected_out):
            print(f"  Written {out_written}/{expected_out} output pages")

    with open(output_path, "wb") as f:
        writer.write(f)

    size_mb = Path(output_path).stat().st_size / 1_048_576
    print(f"\nDone. File size: {size_mb:.1f} MB")


def main():
    parser = argparse.ArgumentParser(
        description="Rotate and split scanned book PDF (two pages per scan)."
    )
    parser.add_argument("input",  help="Input PDF path")
    parser.add_argument("output", help="Output PDF path")
    parser.add_argument(
        "--rotation", type=parse_rotation, default=0,
        metavar="DEG|cw|ccw|invert|none",
        help="Rotation before splitting: named alias or degrees (default: none / 0)"
    )
    parser.add_argument(
        "--boundaries", type=parse_boundaries,
        default=[LEFT_MARGIN_IN, LEFT_PAGE_WIDTH_IN, GUTTER_WIDTH_IN, RIGHT_PAGE_WIDTH_IN],
        metavar="MARGIN,LEFT,GUTTER,RIGHT",
        help="Page boundaries in inches: left margin, left page width, gutter, right page width "
             f"(default: {LEFT_MARGIN_IN},{LEFT_PAGE_WIDTH_IN},{GUTTER_WIDTH_IN},{RIGHT_PAGE_WIDTH_IN})"
    )
    parser.add_argument(
        "--skip", type=int, default=0, metavar="N",
        help="Skip the first N input pages (default: 0)"
    )
    parser.add_argument(
        "--limit", type=int, default=None, metavar="N",
        help="Process at most N input pages after skipping (default: all)"
    )
    args = parser.parse_args()
    process_pdf(args.input, args.output, args.rotation % 360, args.boundaries,
                skip=args.skip, limit=args.limit)


if __name__ == "__main__":
    main()
