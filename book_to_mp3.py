#!/usr/bin/env python3
"""
book_to_mp3.py  --  Convert a .txt or .epub file to an MP3 audiobook using Kokoro TTS

Usage:
    python3 book_to_mp3.py mybook.txt
    python3 book_to_mp3.py mybook.epub --voice bm_george --output mybook.mp3
    python3 book_to_mp3.py mybook.epub --voice af_bella --speed 1.1 --list-voices

Requirements:
    pip install kokoro-onnx soundfile ebooklib beautifulsoup4
    sudo apt install ffmpeg
"""

import argparse
import re
import sys
import tempfile
import os
import subprocess
import numpy as np
from pathlib import Path

# ---------------------------------------------------------------------------
# Voice list (from voices-v1.0.bin)
# ---------------------------------------------------------------------------
VOICES = {
    "American Female (af_)": [
        "af_bella", "af_nicole", "af_sarah", "af_sky",
        "af_alloy", "af_aoede", "af_heart", "af_jadde",
        "af_kore", "af_nova", "af_river",
    ],
    "American Male (am_)": [
        "am_adam", "am_michael", "am_echo", "am_eric",
        "am_fenrir", "am_liam", "am_onyx", "am_puck",
    ],
    "British Female (bf_)": [
        "bf_emma", "bf_isabella", "bf_alice", "bf_lily",
    ],
    "British Male (bm_)": [
        "bm_george", "bm_daniel", "bm_fable", "bm_lewis",
    ],
}

SAMPLE_RATE = 24000
MAX_CHARS = 400      # Conservative limit well under Kokoro's 512-token context
MIN_ITEM_CHARS = 200 # Epub items shorter than this are likely TOC/nav junk


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def load_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_epub(path: Path) -> str:
    try:
        import ebooklib
        from ebooklib import epub
        from bs4 import BeautifulSoup
    except ImportError:
        print("Error: epub support requires ebooklib and beautifulsoup4.")
        print("  pip install ebooklib beautifulsoup4")
        sys.exit(1)

    book = epub.read_epub(str(path))
    chapters = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        if len(text.strip()) >= MIN_ITEM_CHARS:
            chapters.append(text)

    if not chapters:
        print("Warning: no readable content found in epub.")
        sys.exit(1)

    return "\n\n".join(chapters)


def load_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return load_txt(path)
    elif suffix == ".epub":
        return load_epub(path)
    else:
        print(f"Error: unsupported file type '{suffix}'. Supported: .txt, .epub")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Text chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str, max_chars: int = MAX_CHARS) -> list:
    """Split text into chunks at sentence boundaries."""
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Split on sentence-ending punctuation
    sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks = []
    current = ""

    for sentence in sentences:
        if len(sentence) > max_chars:
            # Sentence is too long — split on commas as fallback
            parts = sentence.split(', ')
            for part in parts:
                if len(current) + len(part) + 2 <= max_chars:
                    current += (', ' if current else '') + part
                else:
                    if current:
                        chunks.append(current.strip())
                    current = part
        elif len(current) + len(sentence) + 1 <= max_chars:
            current += (' ' if current else '') + sentence
        else:
            if current:
                chunks.append(current.strip())
            current = sentence

    if current:
        chunks.append(current.strip())

    return [c for c in chunks if c.strip()]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert a .txt or .epub book to an MP3 audiobook using Kokoro TTS.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 book_to_mp3.py mybook.txt
  python3 book_to_mp3.py mybook.epub --voice bm_george
  python3 book_to_mp3.py mybook.txt --voice af_heart --speed 1.1 --output listen.mp3
  python3 book_to_mp3.py --list-voices
        """
    )
    parser.add_argument("input", nargs="?", help="Path to .txt or .epub file")
    parser.add_argument("--voice", default="af_bella",
                        help="Voice name (default: af_bella)")
    parser.add_argument("--speed", type=float, default=1.0,
                        help="Speech speed 0.5–2.0 (default: 1.0)")
    parser.add_argument("--output",
                        help="Output MP3 path (default: same name as input with .mp3)")
    parser.add_argument("--model", default="kokoro-v1.0.onnx",
                        help="Path to ONNX model file (default: kokoro-v1.0.onnx)")
    parser.add_argument("--voices-bin", default="voices-v1.0.bin",
                        help="Path to voices .bin file (default: voices-v1.0.bin)")
    parser.add_argument("--silence-ms", type=int, default=300,
                        help="Milliseconds of silence between chunks (default: 300)")
    parser.add_argument("--list-voices", action="store_true",
                        help="Print all available voices and exit")
    args = parser.parse_args()

    # --list-voices
    if args.list_voices:
        print("\nAvailable voices:\n")
        for group, names in VOICES.items():
            print(f"  {group}")
            for name in names:
                marker = " ← recommended" if name in ("af_bella", "af_heart", "bm_george", "bf_emma") else ""
                print(f"    {name}{marker}")
        print()
        sys.exit(0)

    if not args.input:
        parser.print_help()
        sys.exit(1)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}")
        sys.exit(1)

    output_path = Path(args.output) if args.output else input_path.with_suffix(".mp3")

    # Load model
    print(f"Loading Kokoro model from {args.model} ...")
    try:
        from kokoro_onnx import Kokoro
        import soundfile as sf
    except ImportError:
        print("Error: kokoro_onnx or soundfile not installed.")
        print("  pip install kokoro-onnx soundfile")
        sys.exit(1)

    kokoro = Kokoro(args.model, args.voices_bin)

    # Load and chunk text
    print(f"Reading {input_path} ...")
    text = load_text(input_path)
    chunks = chunk_text(text)
    total = len(chunks)
    print(f"  {len(text):,} characters → {total} chunks")
    print(f"  Voice: {args.voice}  Speed: {args.speed}x  Output: {output_path}\n")

    # Generate audio
    silence = np.zeros(int(SAMPLE_RATE * args.silence_ms / 1000))
    all_audio = []
    failed = 0

    for i, chunk in enumerate(chunks, 1):
        preview = chunk[:70] + ("..." if len(chunk) > 70 else "")
        print(f"[{i}/{total}] {preview}")
        try:
            samples, rate = kokoro.create(
                chunk, voice=args.voice, speed=args.speed, lang="en-us"
            )
            all_audio.append(samples)
            all_audio.append(silence)
        except Exception as e:
            print(f"  *** WARNING: chunk {i} failed: {e}")
            failed += 1

    if not all_audio:
        print("Error: no audio was generated.")
        sys.exit(1)

    if failed:
        print(f"\nWarning: {failed} chunk(s) failed and were skipped.")

    # Write audio
    print("\nCombining audio ...")
    combined = np.concatenate(all_audio)

    # Try ffmpeg for MP3
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_wav = tmp.name

    sf.write(tmp_wav, combined, SAMPLE_RATE)

    ffmpeg_ok = subprocess.run(["which", "ffmpeg"], capture_output=True).returncode == 0
    if ffmpeg_ok:
        print(f"Converting to MP3 ...")
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", tmp_wav,
                "-codec:a", "libmp3lame", "-qscale:a", "2",
                str(output_path)
            ],
            capture_output=True
        )
        os.unlink(tmp_wav)
        if result.returncode == 0:
            size_mb = output_path.stat().st_size / 1_000_000
            print(f"\nDone: {output_path}  ({size_mb:.1f} MB)")
        else:
            print("ffmpeg conversion failed. Saving as WAV instead.")
            wav_out = output_path.with_suffix(".wav")
            sf.write(wav_out, combined, SAMPLE_RATE)
            print(f"\nDone: {wav_out}")
    else:
        os.unlink(tmp_wav)
        print("ffmpeg not found — saving as WAV (install ffmpeg for MP3 output).")
        wav_out = output_path.with_suffix(".wav")
        sf.write(wav_out, combined, SAMPLE_RATE)
        size_mb = wav_out.stat().st_size / 1_000_000
        print(f"\nDone: {wav_out}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
