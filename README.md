# EasyMacro

A Windows desktop auto-clicker / macro tool built on PySide6 (Qt).\
Build multi-step click-and-key sequences in a tree-based **Macro Builder** —
loops, If/Else and While blocks driven by on-screen image conditions,
drag-and-drop reordering, per-macro hotkeys and randomization — then fire them
with a global hotkey. Input is injected through **AutoHotkey**, so timing and
clicks behave like a real user.

> Still under active development — built and tested primarily through the
> Windows/WSL loop described below.

## Features
-   Tree-based Macro Builder — click (left/right/middle, single/double), mouse hold/release/move, key press/hold/release with modifiers, and delay steps, all reorderable by drag-and-drop
-   Loop blocks — nest arbitrarily deep around any selection of sibling steps
-   Screen-condition control flow — If/Else and While blocks that check whether a captured reference image appears in a screen region (AHK ImageSearch, per-channel color tolerance, negate), plus a standalone Wait-for-image step with timeout handling
-   Region capture — two-click point capture (no fullscreen overlay) saves the reference screenshot alongside the macro
-   Add realistic movement — auto-inserts mouse-move steps before clicks whose target differs from the last known cursor position
-   Randomization — click jitter, timing variance and mouse-speed variation, configurable per macro
-   Safety — stop-on-mouse-movement, global stop/pause/resume hotkeys, per-macro start/stop hotkey
-   Stats tracking, undo (step-list), system tray with start-minimized / close-to-tray

## How it works
The Macro Builder's step tree gets compiled before it ever runs:
```
tree of steps/blocks  →  macro_compiler: loops statically unrolled,
                          If/While lowered to Jump/CondJump/WhileHeader
                          instructions with absolute jump targets
      →  macro_engine: a single QTimer-driven step machine walks the
         compiled program with one instruction pointer
      →  each leaf action → AHKService → AutoHotkey (click/move/key/pos)
```
Every action is scheduled through one single-shot `QTimer`, so delays never
block the Qt event loop and infinite loops never recurse — pause, resume,
stop and repeat all work on the same instruction pointer without special
cases for control flow.

## Requirements
-   Windows 10/11
-   Python 3.12+
-   Dependencies from `requirements.txt` (PySide6, `ahk[binary]`, pynput, pydantic, numpy)

## Installation
### 1. Clone and set up a virtual environment
``` bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
Or run `build.bat`, which creates the virtual environment and installs
dependencies for you.

------------------------------------------------------------------------
### 2. Run the app
``` bash
python -m src.main
```
or:
``` bash
build.bat run
```

------------------------------------------------------------------------
### 3. Run the tests
``` bash
build.bat test
```
which is equivalent to:
``` powershell
$env:QT_QPA_PLATFORM = 'offscreen'
python -m pytest -q
```

## Usage
1.  Open **Macros** and click **New Macro** to enter the Builder.
2.  Add steps with **Add step ▾** — clicks, key presses, delays, loops, or If/While/Wait blocks.
3.  For image conditions, use **Capture region** to point at the top-left and bottom-right corners of the area to watch, then tune tolerance and negate as needed.
4.  Select a run count, an optional start/stop hotkey, and randomization/safety options, then save.
5.  Fire the macro from the **Dashboard** or its assigned hotkey; global pause/resume/stop hotkeys work across all running macros.

## Project structure
    src/
    ├── main.py, ui/app.py       # Entry point, Qt bootstrap, system tray
    ├── models/                  # Actions, blocks, Macro, AppSettings, stats
    ├── core/
    │   ├── macro_compiler.py    # Lowers the item tree to a flat instruction list
    │   ├── macro_engine.py      # Timer-driven step machine
    │   ├── hotkey_manager.py    # Global hotkey registry (pynput)
    │   └── config.py, state.py, event_bus.py, ...
    ├── services/
    │   ├── ahk_service.py       # AutoHotkey command layer
    │   ├── image_asset_service.py  # Reference-image storage under data/assets/
    │   ├── macro_service.py     # Macro CRUD + JSON persistence
    │   └── mouse_movement_service.py, stats_service.py, ...
    └── ui/
        ├── pages/               # Dashboard, Macros, Builder, Settings
        └── widgets/             # Capture overlay, region capture, condition form

## Configuration
Settings are persisted to `data/config.json`; macros to `data/macros.json`.

| Setting | Purpose |
|---|---|
| `theme` | UI theme (dark/light/system) |
| `randomization` | Click jitter, timing variance, mouse-speed variation |
| `hotkeys` | Global pause/resume/stop and position-capture hotkeys |
| `stop_on_mouse_movement` / `mouse_movement_threshold` | Safety stop when the user moves the mouse mid-macro |
| `start_minimized` / `close_to_tray` | Tray behavior |
