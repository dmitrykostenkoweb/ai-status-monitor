# Handoff: AI Status Monitor — Comic Redesign (Dark + Light)

## Overview
A comic-book visual redesign of **AI Status Monitor**, a small frameless, always-on-top desktop widget (Linux/macOS/Windows). It shows live status for AI coding agents running in terminals (Claude Code CLI, OpenAI Codex CLI): a main card with usage-limit bars, plus one draggable session card per running agent, each with a tilted "polaroid" GIF sticker and a speech bubble.

**Primary target: Dark mode** (`AI Status Monitor Comic Dark.dc.html`). Light mode is included for reference and as an optional theme.

## About the Design Files
The files in this bundle are **design references created in HTML**. They are prototypes that show the intended look and behaviour. They are not production code to copy directly. Recreate them in the app's existing environment (e.g. Electron/Tauri + React/Vue/Svelte, or whatever the widget already uses), following its patterns. Open the `.dc.html` files in a browser to view them; each needs a `support.js` runtime next to it to render, so treat the markup and inline styles as the spec.

## Fidelity
**High-fidelity.** Final colours, typography, borders, shadows and spacing. Recreate them pixel-accurately. The data shown (percentages, projects, times) is mock data.

## Global visual language ("comic")
- Thick ink outlines: `3px solid` on cards, `2.5px` on chips/buttons/circles, `2px` on bars.
- Hard offset shadows with no blur: cards `7px 7px 0`, session cards `6px 6px 0`, buttons/chips `2px 2px 0`, polaroid `5px 5px 0`, bubble `3px 3px 0`.
- Halftone dots via `radial-gradient(<dot> 1.4px, transparent 1.6px)` with a repeating `background-size`.
- Display type: **Bangers** (Google Fonts) with `-webkit-text-stroke` and a hard `text-shadow: 2px 2px 0`.
- Body: **Comic Neue 700**. Metadata/times: **Space Mono 400/700**.
- Pressed state for every button: `transform: translate(2px,2px); box-shadow: 0 0 0` (the button "sinks" into its shadow).

## Design Tokens — Dark (primary)
| Token | Value |
|---|---|
| Desktop bg (preview only) | `#151628` + dots `rgba(255,255,255,.07)` 1.4px / 10px grid |
| Card surface | `#24263A` |
| Inner block / buttons | `#2E3150` |
| Bar track | `#15162A` |
| Outline (ink) | `#F4EEDC` (cream) |
| Hard shadow | `#000` |
| Text primary | `#F4EEDC` |
| Text secondary (resets) | `#A9A6C0` |
| Text tertiary (project · time) | `#C9C6DD` |
| Header fill | `#FF9B7A` (Claude coral) + halftone `rgba(200,40,30,.55)` 1.6px / 7px |
| Claude | `#FF9B7A` |
| Codex | `#7DD3FC` |
| Accent yellow | `#FFD23F` |
| Alert red | `#E63946` |
| Bar OK (<75%) | fill `#4ADE80`, % text `#86EFAC` |
| Bar warn (≥75%) | fill `#FB923C`, % text `#FDBA74` |
| Bar crit (≥90%) | fill `#F43F5E`, % text `#FB7185` |
| Polaroid frame | `#F4EEDC`, border `#0B0B10`, text `#111` |
| Bubble border / tail | `#0B0B10`, text `#111` |

Elements on light/colour fills (initial circles, bubbles, yellow arrow button, badges, status chips) **always use dark text `#111`**.

### Light mode deltas
Card `#FFF8E1`, inner/buttons `#fff`, outline + shadow `#111`, text `#111`, track `#F1EAD2`, secondary text `#555`/`#333`, header `#FFD23F` + dots `rgba(230,57,70,.35)`, desktop `#3A86A8` + dots `rgba(17,17,17,.28)`, % text uses darker inks (`#15803D` / `#C2410C` / `#C1121F`).

## Screens / Components

### 1. Main card (width 420px max, radius 6px, overflow hidden)
**Header** (padding 10×12, gap 10, bottom border 3px):
- Radar logo, 30×30 circle: 2.5px border, white fill, inner ring inset 6px, red sweep line 13×2.5px rotated −40° from the centre, 6px black centre dot. Optionally animate the sweep as a slow rotation.
- Title "AI Agents Status!": Bangers 26px, letter-spacing 1.2px, white fill, 1.5px stroke `#111`, shadow 2px 2px 0 `#111`. Fills the remaining space (flex 1), no wrap.
- Status badge: Bangers 16px, padding 3×9×1, 2.5px border, radius 4, rotated −4°, shadow 2px. Variants:
  - `● LIVE`: bg `#4ADE80`, text `#111`
  - `▲ N ALERT!`: bg `#E63946`, text `#fff`
  - `● IDLE`: bg `#8E8BA6` (dark) / `#D6D3C4` (light), text `#111`
- Gear button and close button: 28×28, radius 4, 2.5px border, 2px shadow. Close uses bg `#E63946` with a white Bangers "X".

**Usage panel** (padding 12×14×14, gap 12): one block per provider.
- Block: grid `44px | 1fr`, gap 12, padding 10×12, 2.5px border, radius 4, bg = inner surface.
- Left column: provider logo in a 38px circle (provider colour fill, 2.5px border, 2px shadow) with an uppercase Space Mono 8px name below it. The prototype shows the letters A/O; **replace them with the real Anthropic / OpenAI logos** from the app's existing assets.
- Right column: one row per quota window, gap 9:
  - Label (Bangers 16px) left, percentage (Bangers 17px, threshold colour) right.
  - Bar: height 12, 2px border, radius 3, track colour. The fill carries halftone dots `rgba(17,17,17,.3)` at 1px / 5px, plus a 2px right border when the value is between 0 and 100%.
  - "resets …": Space Mono 10px, right-aligned, secondary colour.

### 2. Session card (one per running agent, stacked under the main card)
- Container: flex row, centred, gap 11, padding 11×14×11×11, 3px border, radius 6, 6px shadow, `cursor: grab`. **Draggable.**
- Jump button "➜": 34×34, bg `#FFD23F`, text `#111`, Bangers 20px. On hover bg `#FFF3B0`, pressed state as above. Clicking focuses that agent's terminal.
- Agent logo: 30px circle in agent colour, 2.5px border.
- Agent name: Bangers 24px, agent colour fill, 1.3px stroke, 2px hard shadow.
- Status chip: Comic Neue 700 14px, padding 1×7, 2px border, radius 3.
  - analyzing / reading: bg `#FFD23F`, text `#111`
  - coding: bg `#4ADE80`, text `#111`
  - waiting for approval / error: bg `#E63946`, text `#fff`
- Meta line: `project · HH:MM`, Space Mono 11px.
- Vertical gap between cards: 22px, plus about 118px of top space when a sticker is shown so the sticker doesn't overlap the card above.

### 3. GIF sticker + speech bubble (pops out of the card's top-right corner)
- Wrapper: absolute, `right: -14px; bottom: calc(100% - 22px)`, flex row aligned to the bottom, gap 10, `pointer-events: none`.
- **Polaroid**: padding 7×7×22, 3px border, 5px shadow, rotation alternating +5° / −5° per card. Image area 124×96 with a 2px border showing the reaction GIF (in the prototype, a striped placeholder). A Bangers 13px caption (sound effect, e.g. "HMMM…", "CLACK!", "AHEM!") is centred 4px from the bottom.
- Entry animation `pop`: 0.5s `cubic-bezier(.3,1.6,.5,1)`, scale .6→1.08→1 and opacity 0→1, keeping the rotation.
- **Speech bubble**: max-width 170, padding 8×12×7, 3px border, radius 18, 3px shadow, rotated −5°, Bangers 18px / line-height 1.05, margin-bottom 34px (sits above the polaroid's midline). Tail: a 16px square on the right side with right and bottom borders, `rotate(-45deg) skew(12deg,12deg)`, same fill as the bubble.
- Bubble fill per status: analyzing `#FFD23F`, coding `#A7F3D0`, waiting `#FFB4BC`. Add error and near-limit variants in the same spirit, e.g. error `#FFB4BC`, done `#A7F3D0`, near-limit `#FDBA74`.
- Example copy: "plotting a cunning plan…", "tap tap tap — KA-CHUNK!", "psst! need your OK!".

## Interactions & Behaviour
- Window: frameless and always-on-top. The header is the drag region (except its buttons).
- Session cards: each one is an independent draggable window/card.
- ➜ button: focuses the matching terminal.
- Gear: opens settings. X: closes or hides the widget.
- Badge: `ALERT` when any session needs attention (shows the count N), `LIVE` when sessions are active, `IDLE` when there are none.
- Bar colour thresholds: <75% green, ≥75% orange, ≥90% red.
- Sticker GIF and bubble are chosen by status: coding, analyzing, waiting, error, done, near the usage limit. Replay the `pop` animation whenever the status changes.

## State
- `providers[]`: `{ id, name, logo, windows[]: { label, pct, resetsAt } }`
- `sessions[]`: `{ id, agent: 'claude'|'codex', status, statusKind, project, startedAt, terminalRef, position }`
- `theme`: `'dark' | 'light'`
- `showStickers`: boolean

## Assets
- Fonts: Bangers, Comic Neue (700), Space Mono (400/700), all from Google Fonts. Bundle them locally for offline desktop use.
- Anthropic / OpenAI / Claude / Codex logos: use the app's existing assets (the prototype uses letter placeholders).
- Reaction GIFs: use the app's existing GIF source (placeholders in the prototype).

## Files
- `AI Status Monitor Comic Dark.dc.html`: dark mode (primary)
- `AI Status Monitor Comic.dc.html`: light mode
