@echo off
REM ---------------------------------------------------------------------------
REM Build script for Windows
REM Produces a single self-contained executable: dist\VoyagerSaveManager.exe
REM
REM Requirements:
REM   uv (https://docs.astral.sh/uv/)
REM   Run this script once from a regular Command Prompt (not elevated).
REM ---------------------------------------------------------------------------

echo === Voyager Save Manager - Windows build ===

REM Install Python dependencies
uv sync --group build

REM Build single-file Windows GUI executable (no console window)
uv run pyinstaller ^
    --onefile ^
    --windowed ^
    --name "VoyagerSaveManager" ^
    --add-data "voyager_save_manager/badge.png;." ^
    --hidden-import "PIL._tkinter_finder" ^
    --collect-all "pynput" ^
    --clean ^
    voyager_save_manager/__main__.py

echo.
echo Done!  Executable is at:  dist\VoyagerSaveManager.exe
echo You can copy it anywhere and double-click to run.
pause
