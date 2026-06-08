#!/usr/bin/env bash
# make_ocr_pdf.sh
#
# Splits a scanned book PDF and runs OCR to produce a searchable PDF.
#
# Usage:
#   ./make_ocr_pdf.sh chapter1.pdf
#
# Output (alongside the input PDF):
#   chapter1_ocr.pdf
#
# Requires: python3, ocrmypdf
# Python scripts must be in the same directory as this script.

set -euo pipefail

# ── Resolve paths ─────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPLIT_SCRIPT="$SCRIPT_DIR/split_book_pages.py"

# ── Validate input ────────────────────────────────────────────────────────────

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <input.pdf>"
    exit 1
fi

INPUT_PDF="$(realpath "$1")"

if [[ ! -f "$INPUT_PDF" ]]; then
    echo "Error: file not found: $INPUT_PDF"
    exit 1
fi

if [[ "${INPUT_PDF##*.}" != "pdf" ]]; then
    echo "Error: input must be a .pdf file"
    exit 1
fi

for cmd in python3 ocrmypdf; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Error: '$cmd' not found on PATH"
        exit 1
    fi
done

if [[ ! -f "$SPLIT_SCRIPT" ]]; then
    echo "Error: missing program file: $SPLIT_SCRIPT"
    exit 1
fi

# ── Derive output names ───────────────────────────────────────────────────────

INPUT_DIR="$(dirname "$INPUT_PDF")"
BASENAME="$(basename "$INPUT_PDF" .pdf)"
OCR_PDF="$INPUT_DIR/${BASENAME}_ocr.pdf"

# ── Temp dir for intermediates ────────────────────────────────────────────────

WORK_DIR="$(mktemp -d)"
trap 'echo ""; echo "Cleaning up temp files..."; rm -rf "$WORK_DIR"' EXIT

SPLIT_PDF="$WORK_DIR/${BASENAME}_split.pdf"

# ── Pipeline ──────────────────────────────────────────────────────────────────

echo "════════════════════════════════════════"
echo "  OCR: $BASENAME"
echo "════════════════════════════════════════"
echo ""

echo "[1/2] Splitting pages..."
python3 "$SPLIT_SCRIPT" "$INPUT_PDF" "$SPLIT_PDF"
echo ""

echo "[2/2] Running OCR..."
ocrmypdf -d -i --remove-vectors "$SPLIT_PDF" "$OCR_PDF"
echo ""

echo "════════════════════════════════════════"
echo "  Done!"
echo "  OCR PDF : $OCR_PDF"
echo "════════════════════════════════════════"
