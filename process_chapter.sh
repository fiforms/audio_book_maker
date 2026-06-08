#!/usr/bin/env bash
# process_chapter.sh
#
# Converts a scanned book PDF to MP3 via split → OCR → text clean → TTS.
#
# Usage:
#   ./process_chapter.sh chapter1.pdf
#
# Outputs (alongside the input PDF):
#   chapter1_ocr.pdf
#   chapter1_cleantext.txt
#   chapter1.mp3
#
# Intermediates (split PDF, raw text) are written to a temp dir and deleted.
#
# Requires: python3, ocrmypdf, pdftotext (poppler-utils)
# Python scripts and model files must be in a 'program/' subfolder
# relative to this script.

set -euo pipefail

# ── Resolve paths ─────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROGRAM_DIR="$SCRIPT_DIR"

SPLIT_SCRIPT="$PROGRAM_DIR/split_book_pages.py"
CLEAN_SCRIPT="$PROGRAM_DIR/clean_book_text.py"
TTS_SCRIPT="$PROGRAM_DIR/book_to_mp3.py"
ONNX_MODEL="$PROGRAM_DIR/kokoro-v1.0.onnx"
VOICES_BIN="$PROGRAM_DIR/voices-v1.0.bin"

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

# Check dependencies
for cmd in python3 ocrmypdf pdftotext; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Error: '$cmd' not found on PATH"
        exit 1
    fi
done

for f in "$SPLIT_SCRIPT" "$CLEAN_SCRIPT" "$TTS_SCRIPT" "$ONNX_MODEL" "$VOICES_BIN"; do
    if [[ ! -f "$f" ]]; then
        echo "Error: missing program file: $f"
        exit 1
    fi
done

# ── Derive output names ───────────────────────────────────────────────────────

INPUT_DIR="$(dirname "$INPUT_PDF")"
BASENAME="$(basename "$INPUT_PDF" .pdf)"

OCR_PDF="$INPUT_DIR/${BASENAME}_ocr.pdf"
CLEAN_TXT="$INPUT_DIR/${BASENAME}_cleantext.txt"
MP3_OUT="$INPUT_DIR/${BASENAME}.mp3"

# ── Temp dir for intermediates ────────────────────────────────────────────────

WORK_DIR="$(mktemp -d)"
trap 'echo ""; echo "Cleaning up temp files..."; rm -rf "$WORK_DIR"' EXIT

SPLIT_PDF="$WORK_DIR/${BASENAME}_split.pdf"
RAW_TXT="$WORK_DIR/${BASENAME}_text.txt"

# ── Pipeline ──────────────────────────────────────────────────────────────────

echo "════════════════════════════════════════"
echo "  Processing: $BASENAME"
echo "════════════════════════════════════════"
echo ""

echo "[1/5] Splitting pages..."
python3 "$SPLIT_SCRIPT" "$INPUT_PDF" "$SPLIT_PDF"
echo ""

echo "[2/5] Running OCR..."
ocrmypdf -d -i --remove-vectors "$SPLIT_PDF" "$OCR_PDF"
echo ""

echo "[3/5] Extracting text..."
pdftotext "$OCR_PDF" "$RAW_TXT"
echo ""

echo "[4/5] Cleaning text..."
python3 "$CLEAN_SCRIPT" "$RAW_TXT" "$CLEAN_TXT"
echo ""

echo "[5/5] Generating MP3..."
python3 "$TTS_SCRIPT" "$CLEAN_TXT" \
    --model "$ONNX_MODEL" \
    --voices "$VOICES_BIN" \
    --output "$MP3_OUT"
echo ""

echo "════════════════════════════════════════"
echo "  Done!"
echo "  OCR PDF : $OCR_PDF"
echo "  Text    : $CLEAN_TXT"
echo "  MP3     : $MP3_OUT"
echo "════════════════════════════════════════"
