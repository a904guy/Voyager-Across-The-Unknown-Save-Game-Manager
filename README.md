# Star Trek Voyager — Across the Unknown · Save Manager

A lightweight save game manager for **Star Trek Voyager: Across the Unknown**.
Quick-save and restore your game at any point, with a full history of backups you can roll back to at any time.

---

## Screenshots

![Voyager Save Manager interface](https://github.com/a904guy/Voyager-Across-The-Unknown-Save-Game-Manager/blob/main/Screenshot.png?raw=true)


## Installation

### Recommended: pipx (Linux/macOS)

Install directly from GitHub using [pipx](https://pipx.pypa.io/):

```bash
pipx install git+https://github.com/a904guy/Voyager-Across-The-Unknown-Save-Game-Manager.git
```

Then run from anywhere:
```bash
voyager-save-manager
```

> **Requirements:** Python 3.12+ and system tkinter package (`python3-tk` on Ubuntu/Debian)

### Alternative: Standalone Binaries

If you prefer standalone executables or don't have Python installed:

1. Go to the [**Releases**](https://github.com/a904guy/Voyager-Across-The-Unknown-Save-Game-Manager/releases/latest) page
2. Download the file for your platform:
   - **Windows** → `VoyagerSaveManager-windows.exe`
   - **Linux** → `VoyagerSaveManager-linux.AppImage`
3. No installation required — just run it

> **Linux:** you may need to mark the file as executable first:
> ```bash
> chmod +x VoyagerSaveManager-linux.AppImage
> ./VoyagerSaveManager-linux.AppImage
> ```
>
> Prefer not to use AppImage? The release also includes a raw binary: `VoyagerSaveManager-linux`.

---

## Setup

On first launch the app will automatically detect your save directory.
Supported locations:

| Platform | Path |
|----------|------|
| Windows (Steam) | `[Steam Library]\steamapps\common\Star Trek Voyager - Across the Unknown\STVoyager\Saved\SaveGames\{SteamID}\` |
| Windows (AppData) | `%LOCALAPPDATA%\STVoyager\Saved\SaveGames\` |
| Linux (Steam) | `~/.local/share/Steam/steamapps/compatdata/2643390/pfx/drive_c/users/steamuser/AppData/Local/STVoyager/Saved/SaveGames/` |
| Linux (Snap Steam) | `~/snap/steam/common/.local/share/Steam/steamapps/compatdata/2643390/pfx/.../STVoyager/Saved/SaveGames/` |

If the directory isn't found automatically (e.g. a custom Steam library location), click **Browse…** to point the app at it manually.

> The game must have been launched and saved at least once before the directory will exist.

---

## Usage

### Quick Save — `F5`

Creates a timestamped snapshot of all your current save files.
Press it as often as you like — every backup is kept.

### Quick Load — `F9`

Instantly restores your **most recent** backup.
After restoring, **reload your save inside the game** to pick up the restored state.

> Both hotkeys work **globally** — you can press them while the game is running in the foreground without alt-tabbing.

### Restoring an older backup

1. Select any entry from the **Saved States** list
2. Click **Restore Selected** (or double-click the entry)
3. Reload your save in-game

### Deleting a backup

Select an entry and click **Delete Selected**.
You will be asked to confirm before anything is removed.

---

## Overlay

When a save or restore is triggered, a small animated overlay appears in the centre of your screen:

- **Clockwise spin** → saving
- **Counter-clockwise spin** → restoring

The overlay fades out automatically after the operation completes.

---

## Backups location

Backups are stored outside the game folder so they are never affected by game updates or Steam cloud sync:

| Platform | Path |
|----------|------|
| Windows | `%APPDATA%\VoyagerSaveManager\backups\` |
| Linux | `~/.local/share/VoyagerSaveManager/backups\` |

Each backup is a folder named by timestamp (e.g. `2026-02-19_14-30-45`) containing a full copy of the save directory at that moment.

---

## Tips

- **Before a hard mission** — hit `F5` so you have a clean checkpoint to return to
- **Always on Top** — tick the checkbox to keep the manager visible over the game window
- The manager and the game's own save system are completely independent; using one does not affect the other
