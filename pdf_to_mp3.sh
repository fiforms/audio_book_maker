#!/usr/bin/env bash
# pdf_to_mp3.sh
#
# Extracts and cleans text from an OCR'd PDF, then generates an MP3 via TTS.
#
# Usage:
#   ./pdf_to_mp3.sh chapter1_ocr.pdf [--no-footnotes] [--strip-asterisks]
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
EXTRACT_SCRIPT="$SCRIPT_DIR/extract_no_footnotes.py"
TTS_SCRIPT="$SCRIPT_DIR/book_to_mp3.py"
ONNX_MODEL="$SCRIPT_DIR/kokoro-v1.0.onnx"
VOICES_BIN="$SCRIPT_DIR/voices-v1.0.bin"

# ── Parse arguments ───────────────────────────────────────────────────────────

NO_FOOTNOTES=0
STRIP_ASTERISKS=0
INPUT_PDF=""

USAGE="Usage: $0 <input_ocr.pdf> [--no-footnotes] [--strip-asterisks]"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-footnotes)
            NO_FOOTNOTES=1
            shift
            ;;
        --strip-asterisks)
            STRIP_ASTERISKS=1
            shift
            ;;
        -*)
            echo "Unknown option: $1"
            echo "$USAGE"
            exit 1
            ;;
        *)
            if [[ -n "$INPUT_PDF" ]]; then
                echo "Unexpected argument: $1"
                echo "$USAGE"
                exit 1
            fi
            INPUT_PDF="$1"
            shift
            ;;
    esac
done

if [[ -z "$INPUT_PDF" ]]; then
    echo "$USAGE"
    exit 1
fi

# --strip-asterisks is forwarded to whichever extractor runs; both ultimately
# chain to clean_book_text.py, which implements the actual stripping.
CLEAN_OPTS=()
if [[ "$STRIP_ASTERISKS" -eq 1 ]]; then
    CLEAN_OPTS+=(--strip-asterisks)
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

if [[ "$NO_FOOTNOTES" -eq 1 ]]; then
    for cmd in python3; do
        if ! command -v "$cmd" &>/dev/null; then
            echo "Error: '$cmd' not found on PATH"
            exit 1
        fi
    done
    for f in "$EXTRACT_SCRIPT" "$TTS_SCRIPT" "$ONNX_MODEL" "$VOICES_BIN"; do
        if [[ ! -f "$f" ]]; then
            echo "Error: missing program file: $f"
            exit 1
        fi
    done
else
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
fi

# ── Derive output names ───────────────────────────────────────────────────────

INPUT_DIR="$(dirname "$INPUT_PDF")"
BASENAME="$(basename "$INPUT_PDF" .pdf)"
CLEAN_TXT="$INPUT_DIR/${BASENAME}_cleantext.txt"
MP3_OUT="$INPUT_DIR/${BASENAME}.mp3"

# ── Pipeline ──────────────────────────────────────────────────────────────────

echo "════════════════════════════════════════"
echo "  PDF → MP3: $BASENAME"
if [[ "$NO_FOOTNOTES" -eq 1 ]]; then
    echo "  Mode: footnote removal enabled"
fi
echo "════════════════════════════════════════"
echo ""

if [[ "$NO_FOOTNOTES" -eq 1 ]]; then
    echo "[1/2] Extracting text (removing footnotes)..."
    python3 "$EXTRACT_SCRIPT" "$INPUT_PDF" --output "$CLEAN_TXT" "${CLEAN_OPTS[@]}"
    echo ""

    echo "[2/2] Generating MP3..."
else
    WORK_DIR="$(mktemp -d)"
    trap 'echo ""; echo "Cleaning up temp files..."; rm -rf "$WORK_DIR"' EXIT
    RAW_TXT="$WORK_DIR/${BASENAME}_text.txt"

    echo "[1/3] Extracting text..."
    pdftotext "$INPUT_PDF" "$RAW_TXT"
    echo ""

    echo "[2/3] Cleaning text..."
    python3 "$CLEAN_SCRIPT" "${CLEAN_OPTS[@]}" "$RAW_TXT" "$CLEAN_TXT"
    echo ""

    echo "[3/3] Generating MP3..."
fi

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
