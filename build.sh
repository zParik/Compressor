#!/usr/bin/env bash
set -e

echo "============================================"
echo " SquishIt - Build Script (Linux/Mac)"
echo "============================================"
echo

# Install Python deps
echo "[1/3] Installing Python dependencies..."
pip install flask pyinstaller --quiet

# Download ffmpeg if not present
if [ ! -f "ffmpeg/ffmpeg" ]; then
    echo "[2/3] Downloading ffmpeg..."
    mkdir -p ffmpeg

    OS=$(uname -s)
    if [ "$OS" = "Darwin" ]; then
        if command -v brew &>/dev/null; then
            brew install ffmpeg --quiet
            cp "$(which ffmpeg)" ffmpeg/
            cp "$(which ffprobe)" ffmpeg/
        else
            echo "ERROR: Homebrew not found. Install it from https://brew.sh then re-run."
            exit 1
        fi
    else
        # Linux — download a static build (works across distros)
        ARCH=$(uname -m)
        URL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-${ARCH}-static.tar.xz"
        echo "    Fetching $URL"
        curl -L "$URL" -o ffmpeg_tmp.tar.xz
        mkdir -p ffmpeg_extracted
        tar -xf ffmpeg_tmp.tar.xz -C ffmpeg_extracted --strip-components=1
        cp ffmpeg_extracted/ffmpeg ffmpeg/
        cp ffmpeg_extracted/ffprobe ffmpeg/
        rm -rf ffmpeg_tmp.tar.xz ffmpeg_extracted
    fi
    chmod +x ffmpeg/ffmpeg ffmpeg/ffprobe
    echo "    ffmpeg downloaded."
else
    echo "[2/3] ffmpeg already present, skipping download."
fi

# Build
echo "[3/3] Building SquishIt (single file)..."
pyinstaller squishit.spec --noconfirm --clean --onefile

echo
echo "============================================"
echo " BUILD COMPLETE!"
echo "============================================"
echo
echo " Binary: dist/SquishIt"
echo " Share that single file - no installs needed."
echo
