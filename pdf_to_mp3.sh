#!/usr/bin/env bash
# pdf_to_mp3.sh
#
# Extracts and cleans text from an OCR'd PDF, then generates an MP3 via TTS.
#
# Usage:
#   ./pdf_to_mp3.sh chapter1_ocr.pdf
#
# Outputs (alongside the input PDF):
#   chapter1_ocr_cleantext.txt
#   chapter1_ocr.mp3
#
# Requires: python3, pdftotext (poppler-utils)
# Python scripts and model files must be in the same directory as this script.

set -euo pipefail

# ── Resolve paths ─────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLEAN_SCRIPT="$SCRIPT_DIR/clean_book_text.py"
TTS_SCRIPT="$SCRIPT_DIR/book_to_mp3.py"
ONNX_MODEL="$SCRIPT_DIR/kokoro-v1.0.onnx"
VOICES_BIN="$SCRIPT_DIR/voices-v1.0.bin"

# ── Validate input ────────────────────────────────────────────────────────────

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <input_ocr.pdf>"
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

for cmd in python3 pdftotext; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Error: '$cmd' not found on PATH"
        exit 1
    fi
done

for f in "$CLEAN_SCRIPT" "$TTS_SCRIPT" "$ONNX_MODEL" "$VOICES_BIN"; do
    if [[ ! -f "$f" ]]; then
        echo "Error: missing program file: $f"
        exit 1
    fi
done

# ── Derive output names ───────────────────────────────────────────────────────

INPUT_DIR="$(dirname "$INPUT_PDF")"
BASENAME="$(basename "$INPUT_PDF" .pdf)"
CLEAN_TXT="$INPUT_DIR/${BASENAME}_cleantext.txt"
MP3_OUT="$INPUT_DIR/${BASENAME}.mp3"

# ── Temp dir for intermediates ────────────────────────────────────────────────

WORK_DIR="$(mktemp -d)"
trap 'echo ""; echo "Cleaning up temp files..."; rm -rf "$WORK_DIR"' EXIT

RAW_TXT="$WORK_DIR/${BASENAME}_text.txt"

# ── Pipeline ──────────────────────────────────────────────────────────────────

echo "════════════════════════════════════════"
echo "  PDF → MP3: $BASENAME"
echo "════════════════════════════════════════"
echo ""

echo "[1/3] Extracting text..."
pdftotext "$INPUT_PDF" "$RAW_TXT"
echo ""

echo "[2/3] Cleaning text..."
python3 "$CLEAN_SCRIPT" "$RAW_TXT" "$CLEAN_TXT"
echo ""

echo "[3/3] Generating MP3..."
python3 "$TTS_SCRIPT" "$CLEAN_TXT" \
    --model "$ONNX_MODEL" \
    --voices "$VOICES_BIN" \
    --output "$MP3_OUT"
echo ""

echo "════════════════════════════════════════"
echo "  Done!"
echo "  Text : $CLEAN_TXT"
echo "  MP3  : $MP3_OUT"
echo "════════════════════════════════════════"
