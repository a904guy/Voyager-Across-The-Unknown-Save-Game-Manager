#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Build script for Linux
# Produces a single self-contained binary: dist/VoyagerSaveManager
#
# Requirements (install once):
#   pip install -r requirements.txt pyinstaller
#
# Optional – needed for global hotkeys on X11:
#   pip install python-xlib
# ---------------------------------------------------------------------------
set -e

echo "=== Voyager Save Manager — Linux build ==="

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt pyinstaller

# Build single-file binary (no console window suppression needed on Linux)
pyinstaller \
    --onefile \
    --name "VoyagerSaveManager" \
    --add-data "badge.png:." \
    --hidden-import "PIL._tkinter_finder" \
    --collect-all "pynput" \
    --clean \
    save_manager.py

echo ""
echo "Done!  Binary is at:  dist/VoyagerSaveManager"
echo "You can copy it anywhere and run it directly."
