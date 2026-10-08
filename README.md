# ⚔ RXP Reforge

Re-forge your RestedXP guides for all your BattleTags — straight from the terminal.

**made by SirRadi**

No browser, no `npm install`, no self-built `.exe`, no Python install — fully portable.
It brings its own Python in `runtime\` (official embeddable package, signed by the Python Software Foundation).

## Start

Open PowerShell in this folder (Explorer → address bar → `powershell` → Enter):

```
.\rxp
```

The menu opens:

| Key | Menu item | What it does |
|---|---|---|
| `1` | Enter BattleTag(s) | Add/remove the BattleTags of your accounts (saved) |
| `2` | Select Guides | Tick guides: ↑↓ + Space, `Y` all, `N` none, or type `1,3,5` / `2-4` |
| `3` | ⚔ Reforge! | Forge all selected guides for all BattleTags |
| `4` | Copy guide to clipboard | Pick BattleTag + guide → paste in-game with Ctrl+V |
| `5` | Source overview | All source guides with guide count |
| `6` | Settings | Change source/output folder |
| `7` | Open output folder | Opens `output\` in Explorer |
| `0` / Esc | Exit | |

## Quick mode (without menu)

```
.\rxp "Schattenwolf#2234"                      # all guides for one BattleTag
.\rxp "Tag#1111" "Tag#2222" --only mop,tbc     # several tags, some guides
.\rxp run                                      # BattleTags + guides saved in the menu
.\rxp list                                     # show source guides
.\rxp --help
```

## Folders

```
source_guides\   your original guide files:  <guide>_guide_<Name>_<Number>.txt
                 e.g. mop_guide_player_1234.txt — the source BattleTag is read from the name
output\<Tag>\    forged guides, e.g. output\Schattenwolf_2234\mop_guide_Schattenwolf_2234.txt
config.json      your saved BattleTags, guide selection and folders (created automatically)
```

Bought a new guide? Drop it into `source_guides\` with that name pattern — done.

## Portable

Everything is relative to this folder. Copy the whole folder to another PC (USB stick, OneDrive)
and run `.\rxp` — nothing to install, no PATH, no admin rights.

```
runtime\         portable Python 3.13 (embeddable package from python.org)
setup.cmd        (re)downloads runtime\ and checks its SHA-256 — only needed after a fresh git clone
```

`rxp.cmd` uses `runtime\python.exe`; if that folder is missing it falls back to an installed Python.

Why 3.13 and not 3.14: from 3.14 on, Python for Windows ships zlib-ng, which compresses differently.
The files would still be valid, but 3.13's classic zlib keeps the output byte-identical to the
original tool that is proven to work in-game.

The guide files, `output\`, `runtime\` and `config.json` are in `.gitignore` — only the code goes into git.

## Project layout

```
rxp.cmd             launcher (UTF-8 console, runtime\python.exe → rxp.py)
setup.cmd/.ps1      downloads the portable runtime (pinned version + SHA-256)
rxp.py              menu + quick mode
reforge/crypto.py   RXP format: BattleTag key → RC4, zlib, Adler-32, base64
reforge/guides.py   source scanning, config, re-encrypt job
reforge/tui.py      colors, banner, arrow-key menus (stdlib only)
```
