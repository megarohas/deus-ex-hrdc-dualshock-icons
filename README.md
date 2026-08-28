# DXHR DC — DualShock Button Icons

PlayStation (DualShock) button icons for **Deus Ex: Human Revolution —
Director's Cut** (PC). Replaces every Xbox 360 button texture in the game
with PS equivalents: ✕ ○ □ △ faces, DS4-style d-pad, L1/R1/L2/R2 bumpers
and triggers, L3/R3 stick-clicks, SHARE/OPTIONS pills — plus the
controller-layout screen now shows the (previously unused, shipped in the
game files) Sony DualShock 3 render instead of the Xbox 360 pad.

503 texture instances across 25 DRM files are patched: the global HUD /
menu Scaleform databases, the tutorial icon library, and every in-world
interactive screen (keypads, computers, ebooks, newspaper dispensers...).

## Install

1. You need the [Gibbed DXHRDC ModHook](https://github.com/gibbed/DXHRDC-ModHook)
   (`DFEngine.dll` replacement). If you already run the Russian
   localisation mod, it is already installed.
2. Drop `dist/DS4ICONS.000` into `<game>\mods\`.
3. Play with any pad the game sees as XInput (DS4Windows, Steam Input).

Uninstall: delete `mods\DS4ICONS.000`.

## Установка

1. Нужен [Gibbed DXHRDC ModHook](https://github.com/gibbed/DXHRDC-ModHook)
   (подменённый `DFEngine.dll`). Если стоит русификатор звука — он уже есть.
2. Положить `dist/DS4ICONS.000` в `<игра>\mods\`.
3. Играть с геймпадом через DS4Windows / Steam Input (игра понимает только
   XInput). Удаление — стереть `mods\DS4ICONS.000`.

## Build

Pure-python toolchain (no pip deps; text is rasterised via ffmpeg):

```
python tools/scan_all.py    # index every PCD9 texture in the bigfile
python tools/build_mod.py   # draw art + patch DRMs + pack DS4ICONS.000
python tools/verify_mod.py  # re-parse the archive, decode samples
```

`tools/dxhr.py` documents the BigArchive V2 / CDRM / DRM v21 / PCD9
formats (ported from Rick Gibbed's zlib-licensed C# sources). The icon art
is `tools/icons.py`: face buttons and d-pad are drawn procedurally (SDF
rasteriser in `tools/draw.py`), the silver pills/triggers/sticks reuse the
game's own pixels with the labels surgically replaced (`tools/retex.py`).

Not covered on purpose: `textures/dualscreen/xbox/*` (SmartGlass
second-screen images — never shown on PC) and analog-stick pictograms
(platform-neutral art).
