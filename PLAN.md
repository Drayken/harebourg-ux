# Harebourg UX plan

Last updated: 2026-09-27
Status: Phases 1–3 are wired and working in game, including chat OCR through the built-in Windows OCR from the standard library (no package). Map window over the Dofus client, setup mode, saved profiles, hover outline, mark self, live landing, pin. The formal exit checklists below have not been walked item by item.

This file is the source of truth across sessions. Read it before changing direction. Update the status line and the phase checkboxes when a slice lands.

## Goal

A click-through overlay on the Dofus window. It shows the current Harebourg confusion and which cell a spell will land on. Cast clicks fall through to the game.

## Software type

A Python program the player starts by double-clicking `harebourg.pyw`. The window is a real click-through overlay. There is no console, no PowerShell script, no project executable, and no build.

The one-time setup is Python from python.org, with the py launcher checked so `.pyw` files open in Python. The overlay itself uses the Python standard library and Windows APIs already on the machine (`user32`, `gdi32`). No pip install for the player.

Agents and pull requests edit small Python modules: confusion rules, map data, and drawing. The only module allowed to call Win32 is the window module.

Draw with GDI into a layered window, per-monitor DPI aware before the window exists. Redraw when the hovered cell or the confusion changes, not on every mouse pixel. Diamonds are pixel-aligned so the edges stay sharp.

### Trust invariants

- No network requests. No analytics and no calls to comteharebourg.com.
- No process memory, injection, packet hooks, or clipboard reading.
- No clicks or keystrokes sent into the game.
- Win32 stays in one module: create the window, follow Dofus, read the cursor, register hotkeys, capture the chat rectangle. `ocr.py` only calls the Windows OCR API (combase / WinRT) on pixels it is handed.
- Screen capture is limited to a rectangle the player anchors on the combat log, used only for the confusion OCR. It is not a general screen reader.
- The repo stays text. Dependencies beyond the standard library have to earn a place in the README with a reason.

A topmost overlay can still look suspicious to antivirus tools. The checkable claim is the source: a reader can see it never opens a socket and never opens the game process.

### Setup friction to expect

Double-click fails if Python was installed without the py launcher. The README says to include it. Players do not run a terminal command to start the overlay.

## Decisions

These are settled. Do not reopen them unless playtesting contradicts them.

1. Vitality percent is not the confusion signal. The state is locked at turn start. Regen, mutilation, and other HP changes during the turn do not move it.
2. Turn start has three states, regardless of the chat wording: 90° clockwise, 180°, 90° counter-clockwise. Melee can also reach 0° (the spell lands where it was aimed). Each melee line adds 90° horaire, modulo 360: 90° horaire → 180° → 90° contre horaire → 0° → 90° horaire. On screen the aim cell moves 90° counter-clockwise per line. A fight confirmed it: 180° at turn start plus one melee hit behaved as 90° contre horaire.
3. Combat chat is the source of truth. The debuff tooltip is the same text and is only a manual resync.
4. OCR runs when the anchored chat region changes, not on a continuous full-chat poll. Hotkeys can always set or bump the state when OCR is wrong.
5. Default aim mode is one position mark plus live forward projection. A pinned inverse highlight is optional.
6. The map overlay is a transparent diamond grid drawn from a cell list (empty / walkable / wall). Do not scrape or bundle [comteharebourg.com](https://www.comteharebourg.com/simulator) assets. Their Edit mode is a reference for the cell list: the guide shows it as copyable text.
7. Alignment is saved once per map and per Dofus window size, relative to that window's client area. Moving the window reuses the profile. Resizing, fullscreen toggle, or interface-scale changes require another profile.
8. Python, not AutoHotkey v2. AHK is shorter for hotkeys and windows, and worse for everything else this project needs: agents edit it less reliably, and a running AutoHotkey process is a known automation host, which cuts against the trust goal.

## Confusion model

Spell landing is a rotation of the clicked cell around the caster.

| Effect | Equivalent chat forms | HP band at turn start only |
|---|---|---|
| 90° clockwise | 90° horaire, 270° contre horaire, horaire 1π/2, contre horaire 3π/2, horaire 2π/4, contre horaire 6π/4 | 100–90% and 29–0% |
| 180° | 180° either direction, 2π/2, 4π/4, either direction | 74–45% |
| 90° counter-clockwise | 90° contre horaire, 270° horaire, contre horaire 1π/2, horaire 3π/2, contre horaire 2π/4, horaire 6π/4 | 89–75% and 44–30% |

Normalize `n Pi/m` to degrees before applying horaire / contre horaire. Examples: `4 Pi/4` contre horaire is 180°. `1 Pi/2` contre horaire is 90° counter-clockwise.

Grid math, in cell coordinates, not screen pixels:

- `landing = rotate(cursorCell - yourCell, confusion) + yourCell`
- `aim = rotate(desiredCell - yourCell, -confusion) + yourCell`

90°, 180°, and 270° map cells onto cells, including off-axis casts. Screen mapping is only for drawing and for picking the cell under the cursor.

"Horaire" matches a clockwise turn on screen. The cheat sheet for 90° horaire (100–90% and 29–0%, including "270° contre horaire") puts the click on the caster's left when the monster is straight above. The other side lands behind the caster. `rotate_offset` follows that. 180° is the same either way. A fight at 4% confirmed the mirrored aim: the spell landed on the far side of the caster from the mob.

Melee rule, separate from the turn-start roll:

- Each damage line dealt in melee to a monster adds 90° horaire to the state. The aim cell moves 90° counter-clockwise on screen.
- A two-line spell uses the old angle on line 1 and the new angle on line 2.
- A monster stops rotating you after it has taken 10 hits. The combat log stops announcing a change. In practice the AP budget never gets there, and the log stays silent anyway, so the overlay does not count hits.
- A melee change prints a confusion line that looks like a turn-start line, but it is relative: it always reads "horaire : 1 Pi/2", whatever the new angle is. The turn-start line is absolute. What tells them apart is the Comtoise cast: at turn start every character casts Comtoise on themselves, and their turn-start confusion line is the entry right below it. The one exception is the very first turn of the fight, for the first character to play: there the line comes right above the cast. The line below wins when there is one on both sides. Every other confusion line from that character is +90° horaire.
- Summons are never confused.

Harebourg's own swap is not confusion. On odd turns the attacker is swung 180° around him. On even turns he is swung 180° around the attacker. An impossible destination wipes the team. Leave this out of v1. Re-mark your cell after a swap, because the pivot is your current cell.

A projected cell that is off the map or on a non-walkable cell is a critical failure. A melee critical failure ends the turn. The overlay should mark that case.

## Interaction

Click-through during play. The overlay never receives the cast click.

- Hotkey on your cell stores the pivot from the cursor.
- Moving the mouse fills the landing cell and outlines the cell under the cursor.
- Sweep until the landing fill sits on the monster, then click in game. The cursor is already on the cell the game needs.
- Optional second hotkey pins a desired cell and leaves the inverse aim cell lit.
- Re-mark yourself after you move.
- HUD, always available even if the map is uncalibrated: one arrow, the degrees, and the map and chat status. No melee counter: every change is announced in chat.
- Hotkeys: Shift+Up / Right / Down / Left set tout droit, 90° horaire, 180°, and 90° contre horaire. Shift+Space adds one melee line (+90° horaire). Mouse button 4 marks self, mouse button 5 pins a target, Shift+Delete clears the pin. Setup modes are the tray icon’s right-click items Régler la carte and Régler le chat, not hotkeys. Masquer / Afficher in the same menu hides only the drawing; chat reading, hotkeys and mouse buttons keep running. No hotkey for it: a Shift+letter would steal capitals from the game chat. The overlay stays off the taskbar.

OCR:

- The player anchors a rectangle on the combat log once.
- Hash the region. OCR only when the pixels change.
- Keep the latest line whose speaker is the configured character name.
- Parser accepts `horaire` / `contre horaire` plus either `90|180|270 degrés` or `n Pi/m`.
- Call the Windows OCR API. Do not add a third-party OCR binary. Done from the standard library with ctypes over combase, so no package is needed.
- Windows OCR misreads seen on rendered chat: π as `TT` / `Tt` / `Ti` / `n`, a small `1` as `I` or `l`, `90°` as `900`, and "Confusion" as "Confflsion". The parser accepts these. On indented lines the timestamp comes out as `117:03]`, `(17:03]` or `+ Cl 7:03]`, and names change case (`Zxsn` / `zxsn`). Entries still split on those timestamps, and characters are matched case-insensitively with l / I / 1 treated alike.
- At some text sizes one scale drops a glyph the other reads, so each change is read at 1× and 2× and the reading that parses is kept. About 10 px text is unreadable at both.
- An angle of 0° or 360° and up is never printed, so it is a misread digit (3π/2 read as 8π/2 or 5π/2) and does not parse.
- A turn-start line that does not parse gives no angle until the next turn start or hotkey. It never falls back to an older line, which would be a stale angle. Melee lines are not parsed: each one is +90° whatever OCR reads.
- Lines are not filtered by character name. Each character keeps its own angle, and the HUD shows the angle of whoever printed the newest confusion line. The next line on the player's turn puts the player's angle back.
- Each OCR frame is lined up against the previous one by its longest overlapping run of entries, so only entries new since the last frame count. Chat scrolling alone never re-applies a melee line. If a frame shares nothing with the previous one, its melee lines are not added. While the turn-start line is on screen the angle is recomputed from it; after it scrolls off, new melee lines are added to the remembered angle. A hotkey replaces the remembered angle, so later melee lines build on the correction.

## Map alignment

Draw faint diamond outlines on walkable cells and a distinct mark on walls. Voids are marked only in setup. During play, keep the grid faint and emphasize the landing cell. The red cross is only the landing under the cursor when that cell is not walkable.

Setup mode turns click-through off, takes focus, and draws the grid in red with a white handle on each corner of its bounds. Drag the grid to move it. Drag a handle to scale it. Escape saves and leaves setup. Align outlines to floor diamonds, with the same panels open as in the fight. Wall sprites extend upward from the floor cell; align to the floor diamond.

Saved profile, relative to the Dofus client area:

- map id
- client width and height the profile was made for
- origin x, origin y
- cell width, cell height

Cell size is expected to be shared across Harebourg maps at one resolution. Origin is not, because each map is centered differently. Scale once, then only place the origin for each map.

If the live window size does not match the profile, do not apply it. Ask for a realignment.

Iso projection once origin and cell size are known:

- `screenX = originX + (x - y) * (cellWidth / 2)`
- `screenY = originY + (x + y) * (cellHeight / 2)`

Dofus cells are 2:1 diamonds. Setup scales width and height together so that ratio stays put. The process must be per-monitor DPI aware before the window exists, or the saved origin will drift.

Cell lists: empty, walkable, wall. Only the main Comte map: lieutenant fights are out of scope. The player can paste a layout. Do not fetch it.

## Repo layout

- `harebourg.pyw` — entry point. Double-click starts the overlay with no console.
- `src/confusion.py` — states, π parser, melee bump
- `src/chat.py` — OCR lines to log entries, speaker filter, Comtoise turn starts, frame-to-frame new-line detection
- `src/ocr.py` — Windows OCR through combase, on a worker thread
- `src/grid.py` — projection and hit testing
- `src/draw.py` — sharp diamond rendering
- `src/overlay.py` — the only module allowed to call Win32
- `src/profiles.py` — alignment profiles in `config/` next to the launcher
- `src/maps/` — one file per fight layout
- `tests/test_confusion.py` — parser and rotation checks, for contributors
- `tests/test_chat.py` — entry joining, speaker filter, new-line detection
- `tests/test_grid.py` — map parsing, projection, and hit-test checks
- `tests/test_profiles.py` — profile save, lookup, and client-size refusal
- `README.md` — the Python install note, how to double-click, and the trust invariants

No package manifest unless OCR later needs the one pinned package.

## Build order

### Phase 0 — plan

- [x] Sanity-check the mechanic and the overlay approach.
- [x] Write this plan.
- [x] Choose a double-clicked Python overlay. No PowerShell, no project executable.

### Phase 1 — confusion core, no map

- [x] HUD: arrow, degrees, status.
- [x] Three-state model, π parser, and checks for every chat form in the table above.
- [x] Hotkeys to set a state and to add one melee line.
- [x] Click-through window over the Dofus client, DPI aware.
- [x] Manual anchor for the chat region, saved locally, OCR on pixel change.

Exit test: sample log lines and a real fight log set the matching arrow. Bump cycles 90° horaire → 180° → 90° contre horaire → 0° → 90° horaire. A click on the game still lands in the game.

### Phase 2 — grid and saved alignment

- [x] Cell-list format and one Comte map.
- [x] Sharp iso grid in the layered window.
- [x] Setup mode: drag, uniform scale, Escape to leave. Play mode: click-through.
- [x] Follow the Dofus window. Save and reload a profile per map and client size.
- [x] Outline the cell under the cursor.

Exit test: at the player's real resolution, the cursor outline stays on the same floor diamond while moving across the Comte map. Resizing the game window refuses the old profile.

### Phase 3 — landing highlight

- [x] Mark-self hotkey.
- [x] Live landing fill from the current confusion.
- [x] Off-map and non-walkable landing warning.
- [x] Optional pin-target hotkey for the inverse aim cell.
- [x] Melee bump updates the live highlight immediately.

Exit test: for each of the three states, a line cast, a diagonal cast, and an off-axis cast. The landing cell matches a hand-checked rotation. A cast aimed off the map is marked before the click.

### Phase 4 — only if the first three hold

Nothing left. Dropped after playtesting:

- Lieutenant maps. Only the Comte fight matters.
- Harebourg 180° swap preview. The player and the Comte already show where the swap goes.
- Line-of-sight dimming. Some spells ignore line of sight, so dimming would mislead.

## Local data

Keep settings in `config/` next to the launcher. That folder is gitignored:

- character name
- chat-region anchor
- hotkeys
- alignment profiles

## Explicitly not in v1

- A project executable or an installer.
- A build step the player has to run.
- Reading the Dofus process or injecting into it.
- Sending keystrokes or clicks into the game.
- Using current HP percent as the confusion source.
- Scraping comteharebourg.com.
- Predicting damage-line count from a spell. The player bumps once per line they know they landed.
- Odd-turn / even-turn Harebourg teleport preview.
- Any network request.
