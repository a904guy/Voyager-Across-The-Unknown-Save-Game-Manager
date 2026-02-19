@echo off
REM ---------------------------------------------------------------------------
REM Build script for Windows
REM Produces a single self-contained executable: dist\VoyagerSaveManager.exe
REM
REM Requirements:
REM   Python 3.10+ must be installed and on PATH
REM   Run this script once from a regular Command Prompt (not elevated).
REM ---------------------------------------------------------------------------

echo === Voyager Save Manager - Windows build ===

REM Install Python dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

REM Build single-file Windows GUI executable (no console window)
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "VoyagerSaveManager" ^
    --add-data "badge.png;." ^
    --hidden-import "PIL._tkinter_finder" ^
    --collect-all "pynput" ^
    --clean ^
    save_manager.py

echo.
echo Done!  Executable is at:  dist\VoyagerSaveManager.exe
echo You can copy it anywhere and double-click to run.
pause
