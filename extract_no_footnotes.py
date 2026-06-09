#!/usr/bin/env python3
"""
extract_no_footnotes.py

Converts an OCR'd PDF to a clean text file with footnotes removed.

For each page:
  1. Render the page to an image
  2. Detect the horizontal separator line between body text and footnotes
  3. Crop to the region above the separator
  4. Run Tesseract OCR on the cropped region
  5. Collect all pages into a single output file (form-feed delimited,
     compatible with clean_book_text.py)

Usage:
    python3 extract_no_footnotes.py chapter_ocr.pdf
    python3 extract_no_footnotes.py chapter_ocr.pdf --output clean.txt --dpi 300
    python3 extract_no_footnotes.py chapter_ocr.pdf --debug

Requires: opencv-python, pdf2image, pillow, tesseract (CLI)
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
from pdf2image import convert_from_path


def find_separator_y(image_bgr: np.ndarray, dpi: int) -> int | None:
    """
    Detect the Y coordinate of the footnote separator line, or None if absent.

    The separator is a thin printed horizontal rule in the lower half of the
    page, spanning roughly 10–60% of the page width (not a full-width border).
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # Confine the search to the lower half of the page so we don't
    # accidentally catch column rules or section dividers near the top.
    y0 = int(h * 0.45)
    y1 = int(h * 0.98)
    roi = gray[y0:y1, :]

    # Binarize: dark ink on light paper → invert so lines are white.
    _, binary = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Morphological open with a horizontal kernel isolates horizontal runs of
    # connected dark pixels.  Minimum length = ~10% of page width.
    min_len = max(w // 10, 40)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (min_len, 1))
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # A printed separator is thin (≤ a few pixels) and wide enough to be
    # intentional, but shorter than the full text block width.
    max_thickness = max(5, dpi // 60)   # ~5px at 300 dpi
    max_width = int(w * 0.75)           # ignore full-width page borders

    best_y = None
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        if cw >= min_len and ch <= max_thickness and cw <= max_width:
            abs_y = y0 + y
            if best_y is None or abs_y < best_y:
                best_y = abs_y

    return best_y


def ocr_region(image_bgr: np.ndarray, lang: str) -> str:
    """Write a BGR image to a temp file and return Tesseract's stdout text."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        cv2.imwrite(tmp_path, image_bgr)
        result = subprocess.run(
            [
                "tesseract", tmp_path, "stdout",
                "-l", lang,
                "--oem", "1",   # LSTM only
                "--psm", "6",   # uniform block of text
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"    [warn] Tesseract failed: {e.stderr.strip()}", file=sys.stderr)
        return ""
    finally:
        os.unlink(tmp_path)


def run_clean(raw_txt: Path, clean_txt: Path, script_dir: Path) -> None:
    clean_script = script_dir / "clean_book_text.py"
    if not clean_script.exists():
        print(f"  [warn] clean_book_text.py not found at {clean_script}, skipping clean step",
              file=sys.stderr)
        return
    subprocess.run(
        ["python3", str(clean_script), str(raw_txt), str(clean_txt)],
        check=True,
    )


def process_pdf(
    input_pdf: Path,
    raw_txt: Path,
    clean_txt: Path,
    debug_dir: Path | None,
    dpi: int,
    lang: str,
    script_dir: Path,
) -> None:
    print(f"Rendering {input_pdf.name} at {dpi} DPI...", flush=True)
    pages = convert_from_path(str(input_pdf), dpi=dpi)
    print(f"  {len(pages)} page(s) found")

    if debug_dir:
        debug_dir.mkdir(parents=True, exist_ok=True)
        print(f"  Debug images → {debug_dir}/")

    page_texts: list[str] = []

    for i, pil_page in enumerate(pages, start=1):
        label = f"{i:03d}"
        print(f"  [{label}/{len(pages):03d}] ", end="", flush=True)

        image = cv2.cvtColor(np.asarray(pil_page, dtype=np.uint8), cv2.COLOR_RGB2BGR)
        h, w = image.shape[:2]

        sep_y = find_separator_y(image, dpi)

        if sep_y is not None:
            cropped = image[:sep_y, :]
            print(f"separator y={sep_y}/{h}  ({100*sep_y//h}%)", end="  ", flush=True)
        else:
            cropped = image
            print("no separator", end="  ", flush=True)

        if debug_dir:
            annotated = image.copy()
            if sep_y is not None:
                cv2.line(annotated, (0, sep_y), (w, sep_y), (0, 0, 255), 4)
            cv2.imwrite(str(debug_dir / f"page_{label}_full.png"), annotated)
            cv2.imwrite(str(debug_dir / f"page_{label}_crop.png"), cropped)

        text = ocr_region(cropped, lang=lang)
        word_count = len(text.split())
        print(f"{word_count} words")
        page_texts.append(text)

    combined = "\f".join(page_texts)
    raw_txt.write_text(combined, encoding="utf-8")
    total_words = len(combined.split())
    print(f"\n[2/2] Cleaning text...", flush=True)
    run_clean(raw_txt, clean_txt, script_dir)
    print(f"\nWrote {total_words} raw words → {clean_txt.name}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Extract body text from an OCR'd PDF, cropping out footnotes "
            "by detecting the printed separator line via OpenCV."
        )
    )
    parser.add_argument("input", help="Input OCR'd PDF (e.g. chapter_ocr.pdf)")
    parser.add_argument(
        "--output", "-o",
        help="Output text file (default: <input stem>_nofootnotes.txt beside the PDF)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Save annotated full-page and cropped images for inspection",
    )
    parser.add_argument(
        "--dpi", type=int, default=300,
        help="Rendering resolution in DPI (default: 300)",
    )
    parser.add_argument(
        "--lang", default="eng",
        help="Tesseract language code (default: eng)",
    )
    args = parser.parse_args()

    input_pdf = Path(args.input).resolve()
    if not input_pdf.exists():
        print(f"Error: not found: {input_pdf}", file=sys.stderr)
        sys.exit(1)
    if input_pdf.suffix.lower() != ".pdf":
        print(f"Error: expected a .pdf file, got: {input_pdf.name}", file=sys.stderr)
        sys.exit(1)

    for cmd in ("tesseract",):
        result = subprocess.run(["which", cmd], capture_output=True)
        if result.returncode != 0:
            print(f"Error: '{cmd}' not found on PATH", file=sys.stderr)
            sys.exit(1)

    script_dir = Path(__file__).resolve().parent

    stem = input_pdf.stem
    if args.output:
        clean_txt = Path(args.output).resolve()
    else:
        clean_txt = input_pdf.with_name(stem + "_cleantext.txt")
    raw_txt = input_pdf.with_name(stem + "_nofootnotes_raw.txt")

    debug_dir = input_pdf.with_name(stem + "_debug") if args.debug else None

    print("════════════════════════════════════════")
    print(f"  Input : {input_pdf.name}")
    print(f"  Output: {clean_txt.name}")
    if debug_dir:
        print(f"  Debug : {debug_dir.name}/")
    print("════════════════════════════════════════")
    print()
    print("[1/2] Extracting text (footnotes removed)...")

    process_pdf(input_pdf, raw_txt, clean_txt, debug_dir, args.dpi, args.lang, script_dir)

    print()
    print("════════════════════════════════════════")
    print("  Done!")
    print(f"  Clean text : {clean_txt}")
    if debug_dir:
        print(f"  Debug images: {debug_dir}/")
    print()
    print("  Next step:")
    print(f"    python3 book_to_mp3.py \"{clean_txt.name}\" --output chapter.mp3")
    print("════════════════════════════════════════")


if __name__ == "__main__":
    main()
