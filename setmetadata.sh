#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 --album <album> --artist <artist> file1.mp3 [file2.mp3 ...]"
    exit 1
}

ALBUM=""
ARTIST=""

# Parse named arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --album)
            ALBUM="${2:-}"
            [[ -z "$ALBUM" ]] && { echo "Error: --album requires a value"; usage; }
            shift 2
            ;;
        --artist)
            ARTIST="${2:-}"
            [[ -z "$ARTIST" ]] && { echo "Error: --artist requires a value"; usage; }
            shift 2
            ;;
        --help|-h)
            usage
            ;;
        --)
            shift
            break
            ;;
        -*)
            echo "Error: Unknown option '$1'"
            usage
            ;;
        *)
            break
            ;;
    esac
done

[[ -z "$ALBUM" ]]  && { echo "Error: --album is required";  usage; }
[[ -z "$ARTIST" ]] && { echo "Error: --artist is required"; usage; }
[[ $# -eq 0 ]]     && { echo "Error: No MP3 files specified"; usage; }

# Verify id3v2 is available
if ! command -v id3v2 &>/dev/null; then
    echo "Error: 'id3v2' is not installed. Install it with:"
    echo "  Debian/Ubuntu: sudo apt install id3v2"
    echo "  macOS:         brew install id3v2"
    exit 1
fi

TRACK=1
TOTAL=$#

for FILE in "$@"; do
    if [[ ! -f "$FILE" ]]; then
        echo "Warning: '$FILE' not found, skipping."
        (( TRACK++ )) || true
        continue
    fi

    if [[ "$FILE" != *.mp3 && "$FILE" != *.MP3 ]]; then
        echo "Warning: '$FILE' does not have an .mp3 extension, skipping."
        (( TRACK++ )) || true
        continue
    fi

    # Derive title from filename: strip directory and .mp3 extension
    BASENAME="$(basename "$FILE")"
    TITLE="${BASENAME%.[Mm][Pp]3}"

    echo "[$TRACK/$TOTAL] $FILE"
    echo "  Title:  $TITLE"
    echo "  Artist: $ARTIST"
    echo "  Album:  $ALBUM"
    echo "  Track:  $TRACK"

    # 1. Strip all existing tags (ID3v1 and ID3v2)
    id3v2 --delete-all "$FILE"

    # 2-4. Set artist, album, title, track
    id3v2 \
        --artist  "$ARTIST" \
        --album   "$ALBUM"  \
        --song    "$TITLE"  \
        --track   "$TRACK"  \
        "$FILE"

    (( TRACK++ )) || true
done

echo "Done."
