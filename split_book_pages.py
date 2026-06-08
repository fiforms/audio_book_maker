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


def process_pdf(input_path: str, output_path: str):
    print(f"Input : {input_path}")
    print(f"Output: {output_path}")
    print(f"DPI   : {TARGET_DPI}")

    pages = convert_from_path(input_path, dpi=TARGET_DPI)
    total = len(pages)
    print(f"Pages : {total} input → {total * 2} output\n")

    px = TARGET_DPI  # pixels per inch

    writer = PdfWriter()

    for i, img in enumerate(pages):
        # Step 1: rotate 90° clockwise
        rotated = img.rotate(-90, expand=True)
        w, h = rotated.size

        # Step 2: compute crop bounds in pixels
        top_px    = int(TOP_TRIM_IN    * px)
        bottom_px = h - int(BOTTOM_TRIM_IN * px)

        margin_px     = int(LEFT_MARGIN_IN      * px)
        first_start   = margin_px
        first_end     = first_start + int(LEFT_PAGE_WIDTH_IN  * px)
        second_start  = first_end   + int(GUTTER_WIDTH_IN     * px)
        if RIGHT_PAGE_WIDTH_IN is not None:
            second_end = second_start + int(RIGHT_PAGE_WIDTH_IN * px)
        else:
            second_end = w

        # Step 3: crop
        first_img  = rotated.crop((first_start,  top_px, first_end,  bottom_px))
        second_img = rotated.crop((second_start, top_px, second_end, bottom_px))

        # Step 4: add both crops to output PDF
        for crop in (first_img, second_img):
            buf = io.BytesIO()
            crop.save(buf, format="PDF", resolution=TARGET_DPI)
            buf.seek(0)
            writer.add_page(PdfReader(buf).pages[0])

        if (i + 1) % 5 == 0 or (i + 1) == total:
            print(f"  Processed {i + 1}/{total} pages → {(i + 1) * 2} output pages")

    with open(output_path, "wb") as f:
        writer.write(f)

    size_mb = Path(output_path).stat().st_size / 1_048_576
    print(f"\nDone. File size: {size_mb:.1f} MB")


def main():
    parser = argparse.ArgumentParser(
        description="Rotate CW and split scanned book PDF (two pages per scan)."
    )
    parser.add_argument("input",  help="Input PDF path")
    parser.add_argument("output", help="Output PDF path")
    args = parser.parse_args()
    process_pdf(args.input, args.output)


if __name__ == "__main__":
    main()
