#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Build script for Linux
# Produces a single self-contained binary: dist/VoyagerSaveManager
#
# Requirements (install once):
#   uv (https://docs.astral.sh/uv/)
#
# Optional – needed for global hotkeys on X11:
#   System package: python3-xlib or similar
# ---------------------------------------------------------------------------
set -e

echo "=== Voyager Save Manager — Linux build ==="

# Install Python dependencies using uv
uv sync --group build

# Build single-file binary (no console window suppression needed on Linux)
uv run pyinstaller \
    --onefile \
    --name "VoyagerSaveManager" \
    --add-data "voyager_save_manager/badge.png:." \
    --hidden-import "PIL._tkinter_finder" \
    --collect-all "pynput" \
    --clean \
    voyager_save_manager/__main__.py

echo ""
echo "Done!  Binary is at:  dist/VoyagerSaveManager"
echo "You can copy it anywhere and run it directly."
