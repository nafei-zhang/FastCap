# FastCap — Portable Screenshot and Annotation Tool

English | [中文文档](README.zh-CN.md)

## Overview
- Lightweight, portable tool for screen capture and quick annotation.
- Focuses on the common workflows similar to FastStone Capture, implemented from scratch and free to use.

## Core Features
- Region capture: drag to select any area and enter the editor immediately.
- Full-screen capture: one click to grab the entire screen.
- Editor tools: rectangle, arrow, text, freehand brush; configurable color and stroke width.
- Export: save as PNG or copy to clipboard.
- Pin image: keep a captured image floating on top; draggable window.
- Scrolling capture: auto-scroll and stitch long images for scrollable pages (experimental).
- Screen recording: record a selected region to MP4 (supports H.264/MPEG‑4).

## Requirements
- Windows 10/11
- Python 3.10+ (recommend 3.11/3.12)

## Installation
```
python -m pip install -r requirements.txt
```

## Run
```
python fastcap.py
```
- An icon appears in the Windows system tray; use the tray menu to start captures.

## Portable Build (single-file EXE)
Install PyInstaller and build:
```
python -m pip install pyinstaller
pyinstaller --onefile --noconsole --name FastCap fastcap.py
```
- The generated `dist/FastCap.exe` can be copied and used directly.
- For a fully self-contained build, include Qt resources:
```
pyinstaller --onefile --noconsole --name FastCap --collect-all PySide6 fastcap.py
```

## Usage Tips
- Drag to select a region; release to open the editor.
- Use the toolbar to switch tools and set color/width; supports `Ctrl+Z` undo.
- Export to a file or copy the final image to the clipboard.
- Pin: click “Pin” in the editor, or choose “Pin (Region)” from the tray.
- Scrolling capture: choose from the tray, select a region; keeping the target window active and scrolled to the top helps stitching quality.
- Screen recording: choose “Record (Region)” in the tray, select save path, then start/stop.

## Shortcuts
- Tray (global, Windows):
  - Region `Ctrl+Alt+R`
  - Full screen `Ctrl+Alt+F`
  - Scrolling capture `Ctrl+Alt+S`
  - Record (region) `Ctrl+Alt+V`
  - Pin (region) `Ctrl+Alt+P`
  - Exit `Ctrl+Alt+Q`
- Editor:
  - Tool switch: Rectangle `R`, Arrow `A`, Text `T`, Brush `B`
  - Copy to clipboard `Ctrl+C`
  - Save PNG `Ctrl+S`
  - Close editor `Esc` or `Ctrl+W`

Note: Global tray shortcuts work on Windows. If registration fails due to conflicts, a tray notification appears. Try closing the conflicting app or change to another combo (e.g. `Alt+F9`).

## Notes
- Scrolling capture is a generic solution based on auto-scrolling and image stitching; complex pages may require manual touch-up in the editor.
- Recording depends on available codecs (`ffmpeg`/`imageio-ffmpeg`); falls back to MPEG‑4 if H.264 is not available.
- Multi-monitor and high‑DPI scenarios are handled via the virtual desktop; please report any coordinate offsets for further refinement.

## Statement
This is an independent open-source tool aiming to deliver an experience similar to common screenshot utilities. It does not include any third‑party commercial code or assets. Do not present it as a copy of “FastStone Capture”; if you need identical features/UX, please extend this project accordingly.
