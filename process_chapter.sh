#!/usr/bin/env bash
# process_chapter.sh
#
# Converts a scanned book PDF to MP3 via split → OCR → text clean → TTS.
# Runs make_ocr_pdf.sh then pdf_to_mp3.sh in sequence.
#
# Usage:
#   ./process_chapter.sh chapter1.pdf
#
# Outputs (alongside the input PDF):
#   chapter1_ocr.pdf
#   chapter1_ocr_cleantext.txt
#   chapter1_ocr.mp3

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <input.pdf>"
    exit 1
fi

INPUT_PDF="$(realpath "$1")"
INPUT_DIR="$(dirname "$INPUT_PDF")"
BASENAME="$(basename "$INPUT_PDF" .pdf)"
OCR_PDF="$INPUT_DIR/${BASENAME}_ocr.pdf"

"$SCRIPT_DIR/make_ocr_pdf.sh" "$INPUT_PDF"
echo ""
"$SCRIPT_DIR/pdf_to_mp3.sh" "$OCR_PDF"
