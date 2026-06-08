#!/usr/bin/env python3
"""
clean_book_text.py

Cleans up text extracted from OCR'd book PDFs (via pdftotext) for TTS use.
Handles:
  - Hyphenated line breaks (re-joins split words)
  - Standalone page numbers (including OCR misreads like '1z' for '13')
  - Running headers/footers (repeated short lines across the document)
  - Excessive blank lines
  - Soft hyphens and other OCR ligature artifacts

Usage:
    pdftotext ocr_output.pdf raw.txt
    python3 clean_book_text.py raw.txt clean.txt

    # Or pipe directly:
    pdftotext ocr_output.pdf - | python3 clean_book_text.py - clean.txt
"""

import re
import sys
import argparse
from collections import Counter


# ── CONFIGURATION ─────────────────────────────────────────────────────────────

# Lines shorter than this (chars) are candidates for header/footer detection.
SHORT_LINE_THRESHOLD = 40

# A line appearing this many times across the whole document is likely a
# running header or footer — remove all occurrences.
REPEATED_LINE_MIN_COUNT = 3

# ── END CONFIGURATION ─────────────────────────────────────────────────────────


def load_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def find_repeated_lines(lines: list[str]) -> set[str]:
    """Find short lines that repeat across the document (headers/footers)."""
    short = [l.strip() for l in lines if 0 < len(l.strip()) < SHORT_LINE_THRESHOLD]
    counts = Counter(short)
    return {line for line, count in counts.items() if count >= REPEATED_LINE_MIN_COUNT}


# OCR misread patterns: (regex, replacement)
# Applied to every line before other processing.
OCR_FIXES = [
    (r'\b1[zZ]\b', '13'),        # 1z / 1Z → 13
    (r'\b1[lI]\b', '11'),        # 1l / 1I → 11
    (r'\b([0-9])O\b', r'\g<1>0'), # trailing letter-O after digit → 0
]


def fix_ocr_misreads(line: str) -> str:
    for pattern, replacement in OCR_FIXES:
        line = re.sub(pattern, replacement, line)
    return line


def is_page_number(line: str) -> bool:
    """True if the line is nothing but a page number (digits only)."""
    return bool(re.fullmatch(r'\s*\d+\s*', line))


def clean(text: str) -> str:
    lines = text.splitlines()

    # ── Pass 1: identify repeated headers/footers ─────────────────────────────
    repeated = find_repeated_lines(lines)

    # ── Pass 2: drop headers/footers and fix OCR digit misreads ──────────────
    cleaned_lines = []
    for line in lines:
        if line.strip() in repeated:
            continue
        cleaned_lines.append(fix_ocr_misreads(line))

    # ── Pass 3: remove standalone page numbers ────────────────────────────────
    result_lines = [l for l in cleaned_lines if not is_page_number(l)]

    # ── Pass 4: rejoin hyphenated line breaks ─────────────────────────────────
    # "vary-\ning" → "varying"
    # Peeks past blank lines to find the continuation, so that page numbers
    # or headers removed in earlier passes don't leave orphaned hyphens.
    joined = []
    i = 0
    while i < len(result_lines):
        line = result_lines[i]
        if re.search(r'\w-$', line.rstrip()):
            # Look ahead, skipping blank lines, for a lowercase continuation
            j = i + 1
            while j < len(result_lines) and result_lines[j].strip() == '':
                j += 1
            if j < len(result_lines) and re.match(r'\s*[a-z]', result_lines[j]):
                next_line = result_lines[j].lstrip()
                next_words = next_line.split(' ', 1)
                merged = line.rstrip()[:-1] + next_words[0]
                remainder = next_words[1] if len(next_words) > 1 else ''
                joined.append(merged + (' ' + remainder if remainder else ''))
                i = j + 1
                continue
        joined.append(line)
        i += 1

    # ── Pass 5: collapse multiple blank lines to a single paragraph break ──────
    text_out = '\n'.join(joined)
    text_out = re.sub(r'\n{3,}', '\n\n', text_out)

    # ── Pass 6: misc OCR character artifacts ──────────────────────────────────
    replacements = [
        ('\u00ad', ''),    # soft hyphen
        ('\ufb01', 'fi'),  # fi ligature
        ('\ufb02', 'fl'),  # fl ligature
        ('\u2019', "'"),   # curly apostrophe
        ('\u201c', '"'),   # left double quote
        ('\u201d', '"'),   # right double quote
    ]
    for old, new in replacements:
        text_out = text_out.replace(old, new)

    return text_out.strip()


def main():
    parser = argparse.ArgumentParser(
        description="Clean pdftotext output from OCR'd books for TTS."
    )
    parser.add_argument("input",  help="Input .txt file (or - for stdin)")
    parser.add_argument("output", help="Output .txt file")
    args = parser.parse_args()

    raw = load_text(args.input)
    result = clean(raw)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(result)

    in_words  = len(raw.split())
    out_words = len(result.split())
    print(f"Done. {in_words} → {out_words} words ({in_words - out_words} removed)")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
