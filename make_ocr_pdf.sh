#!/usr/bin/env bash
# make_ocr_pdf.sh
#
# Splits a scanned book PDF and runs OCR to produce a searchable PDF.
#
# Usage:
#   ./make_ocr_pdf.sh chapter1.pdf [--rotation cw|ccw|invert|none|DEGREES] [--boundaries MARGIN,LEFT,GUTTER,RIGHT] [--skip N] [--limit N]
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

# ── Parse arguments ───────────────────────────────────────────────────────────

ROTATION_ARG=""
BOUNDARIES_ARG=""
SKIP_ARG=""
LIMIT_ARG=""
INPUT_PDF=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --rotation)
            ROTATION_ARG="--rotation $2"
            shift 2
            ;;
        --boundaries)
            BOUNDARIES_ARG="--boundaries $2"
            shift 2
            ;;
        --skip)
            SKIP_ARG="--skip $2"
            shift 2
            ;;
        --limit)
            LIMIT_ARG="--limit $2"
            shift 2
            ;;
        -*)
            echo "Unknown option: $1"
            echo "Usage: $0 <input.pdf> [--rotation cw|ccw|invert|none|DEGREES] [--boundaries MARGIN,LEFT,GUTTER,RIGHT] [--skip N] [--limit N]"
            exit 1
            ;;
        *)
            if [[ -n "$INPUT_PDF" ]]; then
                echo "Unexpected argument: $1"
                echo "Usage: $0 <input.pdf> [--rotation cw|ccw|invert|none|DEGREES] [--boundaries MARGIN,LEFT,GUTTER,RIGHT] [--skip N] [--limit N]"
                exit 1
            fi
            INPUT_PDF="$1"
            shift
            ;;
    esac
done

if [[ -z "$INPUT_PDF" ]]; then
    echo "Usage: $0 <input.pdf> [--rotation cw|ccw|invert|none|DEGREES] [--boundaries MARGIN,LEFT,GUTTER,RIGHT] [--skip N] [--limit N]"
    exit 1
fi

INPUT_PDF="$(realpath "$INPUT_PDF")"

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
# shellcheck disable=SC2086
python3 "$SPLIT_SCRIPT" "$INPUT_PDF" "$SPLIT_PDF" $ROTATION_ARG $BOUNDARIES_ARG $SKIP_ARG $LIMIT_ARG
echo ""

echo "[2/2] Running OCR..."
ocrmypdf -d -i --remove-vectors "$SPLIT_PDF" "$OCR_PDF"
echo ""

echo "════════════════════════════════════════"
echo "  Done!"
echo "  OCR PDF : $OCR_PDF"
echo "════════════════════════════════════════"
