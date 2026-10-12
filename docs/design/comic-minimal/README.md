# Handoff: AI Status Monitor — Comic Minimal (translucent)

## Overview
Redesign of **AI Status Monitor**, a small frameless, always-on-top desktop widget (Linux/macOS/Windows). It shows live status of AI coding agents running in terminals (Claude Code CLI, OpenAI Codex CLI). This replaces the previous heavy "comic" skin (thick borders, halftone header, big shadows) with a **minimal comic style** on **translucent glass surfaces**.

Reference screenshot: `screenshots/minimal-dark.png`.

## About the Design Files
`AI Status Monitor Comic Minimal.dc.html` is an **HTML design reference** (prototype), not production code. Recreate it in the widget's existing stack (Electron/Tauri + its UI framework), following the codebase's patterns. All styles in the file are inline, so read exact values from there. The terminal text behind the widget only demonstrates transparency and is **not** part of the app.

## Fidelity
**High-fidelity.** Final colours, type, spacing and radii. The data shown (percentages, projects, times, GIFs) is mock data.

## Window / transparency (important)
- The window must be **transparent and frameless** (Electron: `transparent: true, frame: false, alwaysOnTop: true`; Tauri: `transparent: true, decorations: false, alwaysOnTop: true`).
- Card surface: `rgba(28,29,44,.58)` + `backdrop-filter: blur(16px) saturate(140%)`.
  - `backdrop-filter` only blurs the web content *inside* the window, not the desktop behind it. For a real desktop blur use native vibrancy: macOS `vibrancy: 'hud'` / `'under-window'`; Windows 11 `backgroundMaterial: 'acrylic'` (Electron ≥ 30) or Tauri `window-vibrancy` (`apply_acrylic` / `apply_vibrancy`). On Linux, fall back to the translucent fill with no blur, and raise its alpha to about `.82` if text becomes hard to read.
- Make the alpha a setting (suggested range 0.4–0.95, default 0.58).
- Shadows must stay inside the window bounds: pad the window by about 6px.

## Design tokens
| Token | Value |
|---|---|
| Surface (glass) | `rgba(28,29,44,.58)` + blur 16px, saturate 140% |
| Outline | `1.5px solid rgba(244,238,220,.9)` |
| Divider | `1.5px dashed rgba(244,238,220,.25)` (header), `.2` (between providers) |
| Hard shadow | `3px 3px 0 rgba(0,0,0,.55)` (no blur, the comic accent) |
| Card radius | 10px |
| Text primary | `#F4EEDC` |
| Text secondary | `#A9A6C0` |
| Claude | `#FF9B7A` |
| Codex | `#7DD3FC` |
| Yellow accent | `#FFD23F` |
| Red | `#E63946` |
| Bar OK <75% | fill `#4ADE80`, % `#86EFAC` |
| Bar warn ≥75% | fill `#FB923C`, % `#FDBA74` |
| Bar crit ≥90% | fill `#F43F5E`, % `#FB7185` |
| Bar track | `rgba(0,0,0,.25)`, border `1.5px solid rgba(244,238,220,.7)`, height 6px, pill |

Fonts (bundle them locally):
- **Bangers**: titles, agent names, quota labels, bubbles.
- **Comic Neue 700**: status text.
- **Space Mono 400/700**: badge, percentages, resets, meta.

## Components

### Main card (max-width 340px)
**Header** (padding 9 10 8 12, gap 8, bottom border is the dashed divider):
- Radar logo: an 18px circle with a 1.5px cream border, a coral sweep line 8×1.5px at −40°, and a 4px cream centre dot. The sweep may rotate slowly (about 4s per turn).
- Title "AI Agents Status": Bangers 18px, letter-spacing 1px, `#FF9B7A`.
- Badge (pill, outline only): Space Mono 10px bold, padding 2×7, `1.5px solid <color>`, text in the same colour.
  - `● LIVE` `#4ADE80`
  - `▲ N ALERT` `#FB7185`
  - `● IDLE` `#A9A6C0`
- Gear and close: 24×24 buttons, radius 6, transparent, colour `#A9A6C0`.
  - Gear hover: bg `rgba(244,238,220,.12)`, text cream.
  - Close (Bangers "X") hover: bg `#E63946`, text white.

**Usage section** (padding 6 12 10): one row per provider (padding 8 0), with a grid of `22px | 1fr`, gap 10. Providers after the first get the dashed top divider.
- Logo: a 20px outline circle in the provider colour. **Use the real Anthropic/OpenAI marks**; the prototype uses letters.
- Each quota window (gap 7 between windows):
  - One line: label (Bangers 13px), then "resets …" (Space Mono 9.5px, secondary, flex 1), then % (Space Mono 11px bold, threshold colour).
  - Below it, the 6px bar (gap 3).

### Session card (one per running agent; gap 14 between cards)
- Glass surface, outline, radius 10, hard shadow, padding 8 12 8 8, gap 9, `cursor: grab`. **Draggable.**
- Jump button "➜": 26×26, radius 7, `1.5px solid rgba(244,238,220,.5)`, transparent. Hover: bg and border `#FFD23F`, text `#111`. Click focuses that agent's terminal.
- Status dot: 8px, with a 3px ring of the same colour at 20% alpha.
  - analyzing/reading: `#FFD23F`
  - coding: `#4ADE80`
  - waiting/error: `#E63946`
  - done: `#7DD3FC`
- Agent name: Bangers 17px in the agent colour. Status: Comic Neue 13px cream, on the same baseline.
- Meta line: `project · HH:MM`, Space Mono 10px secondary, single line with ellipsis.

### GIF sticker + speech bubble
- Anchored above the card's top-right: `position:absolute; right:-6px; bottom:calc(100% - 14px)`, as a flex row (bubble left, polaroid right) with gap 8 and `pointer-events: none`.
- Reserve about 96px above each card that shows a sticker.
- **Polaroid**:
  - Frame: bg `rgba(244,238,220,.92)`, `1.5px solid #111`, radius 3, padding 5 5 16, shadow `3px 3px 0 rgba(0,0,0,.5)`, rotated ±4° (alternating per card).
  - GIF area 96×72, object-fit cover.
  - Caption (sound effect, e.g. "PONDER…") in Bangers 11px `#111`, centred 2px from the bottom.
- **Bubble**:
  - Box: max-width 150, padding 6 10 5, `1.5px solid #111`, radius 14, shadow `2px 2px 0 rgba(0,0,0,.55)`, rotated −3°, Bangers 14px / 1.05, text `#111`.
  - Tail: a 10px square on the right edge at vertical centre, with right and top borders, rotated 45°.
  - Fill by status: analyzing `#FFD23F`, coding `#A7F3D0`, waiting/error `#FFB4BC`, done `#A7F3D0`, near-limit `#FDBA74`.
- Entry animation `pop`: 0.45s `cubic-bezier(.3,1.6,.5,1)`, scale .7 → 1.05 → 1 and opacity 0 → 1, keeping the rotation. Replay it on every status change.

## Behaviour
- The header is the window drag region (excluding its buttons).
- Badge: ALERT (with count) if any session is waiting for approval or errored, LIVE if any session is active, otherwise IDLE.
- Bar thresholds: <75 green, ≥75 orange, ≥90 red. Percentages are integers.
- Sticker GIF, bubble text and caption are chosen by status kind: `coding | analyzing | waiting | error | done | near_limit`.
- Settings: "Show stickers" (boolean) and "Transparency" (alpha).

## Suggested state shape
```ts
type Provider = { id: 'anthropic'|'openai'; name: string; windows: { label: string; pct: number; resetsAt: string }[] };
type Session = { id: string; agent: 'claude'|'codex'; status: string;
  kind: 'coding'|'analyzing'|'waiting'|'error'|'done'|'near_limit';
  project: string; updatedAt: string; terminalRef: string; position?: {x:number;y:number} };
type Settings = { showStickers: boolean; surfaceAlpha: number };
```

## Files
- `AI Status Monitor Comic Minimal.dc.html`: design reference
- `screenshots/minimal-dark.png`: rendered reference
