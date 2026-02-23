import subprocess
import sys


def build_linux() -> None:
    if not sys.platform.startswith("linux"):
        raise RuntimeError("build-linux is intended to run on Linux")

    command = [
        "pyinstaller",
        "--onefile",
        "--name",
        "VoyagerSaveManager",
        "--add-data",
        "badge.png:.",
        "--hidden-import",
        "PIL._tkinter_finder",
        "--collect-all",
        "pynput",
        "--clean",
        "save_manager.py",
    ]

    subprocess.run(command, check=True)


if __name__ == "__main__":
    build_linux()
