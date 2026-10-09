# GIF sticker — status reactions for AI Agents Status widget

Design source: Claude Design canvas "AI Agents Status – GIF moods", artboard **C · Naklejka wyskakuje**.
Working visual reference: `reference.html` in this folder (open it in a browser, click the status pills).

## Idea

The widget itself stays as it is. When an agent **changes status**, a tilted "sticker" with a GIF
pops out of the widget's top-right corner, together with a short speech bubble. After a few seconds
it tucks away. It's a reaction, not permanent decoration.

## Layout (widget width 400px)

| Element | Spec |
|---|---|
| Sticker frame | 150 × 104 px, padding 5px, background `#f4f1ea`, radius 10px, `rotate(6deg)`, shadow `0 10px 24px rgba(0,0,0,.55)` |
| GIF inside | fills the frame, radius 6px, `object-fit: cover` |
| Position | absolutely positioned over the widget: `top: -78px; right: -18px`, z-index above the widget card |
| Speech bubble | left of the sticker, `margin-top: 14px`, max-width 150px, JetBrains Mono 12px/600, text `#0e1218` on the status color, radius `12px 12px 2px 12px`, `rotate(-3deg)` |
| Status dot in the agent row | 9px circle in the status color + `box-shadow: 0 0 10px <color>` |
| Status label | JetBrains Mono 13px in the status color, next to the agent name |

The window needs ~80px of transparent space above the card so the sticker isn't clipped
(or render the sticker in its own transparent overlay window/layer).

## Colors / tokens

```
--bg-card:   #0e1218
--border:    #232a35
--divider:   #1c222c
--text:      #e6edf3
--muted:     #7d8590
--claude:    #e8825f
--sticker:   #f4f1ea
fonts: "IBM Plex Sans" (UI), "JetBrains Mono" (labels, numbers)
```

## Statuses

| key | color | when | GIF ideas (pool folder) | bubble text (random from list) |
|---|---|---|---|---|
| `analyzing` | `#f5c542` | reading files, thinking, planning | counting eyes, floating formulas | "hmm… 2 + 2 = ?", "chwila, liczę…" |
| `coding` | `#60a5fa` | Edit / Write / Bash running | cat smashing keyboard, hacker in hoodie | "piszę, piszę!", "klepię kod, nie przeszkadzać" |
| `waiting` | `#c084fc` | asks for permission / question to user | skeleton on a bench, dog at the door | "Dima? Halo?", "halo? jest tam kto?" |
| `done` | `#4ade80` | task finished (Stop) | victory dance, standing ovation | "gotowe!", "należy mi się kawa" |
| `error` | `#f87171` | failing test, non-zero exit, exception | calm in a burning room, lab explosion | "jest dobrze. chyba.", "wszystko jest w porządku." |
| `limit` | `#fb923c` | 5h or weekly usage ≥ 90% | battery 1%, empty tank | "oszczędzaj tokeny, bracie" |
| `idle` | `#8b93a1` | no activity for > 10 min | sleeping cat, tumbleweed | "zzz…" |

Map the statuses the app already detects onto these keys. `limit` and `idle` are derived:
`limit` from the usage bars, `idle` from time since the last event.

## GIF pool

- Folder: `gifs/<status>/*.{gif,webp,png}` (user-configurable base dir, e.g. `~/.config/ai-status-monitor/gifs`).
- Pick randomly, never the same file twice in a row for a status.
- Missing folder / empty → show the sticker with a striped placeholder in the status color (see reference) or skip the sticker; never crash.
- Seed: `gifs/analyzing/eyes.png`, `gifs/analyzing/math.png` are included here.

## Behaviour / motion

1. Status change → sticker **pops in**: from `scale(.6) rotate(0deg); opacity 0` to `scale(1) rotate(6deg); opacity 1`,
   260ms `cubic-bezier(.34,1.56,.64,1)`. Bubble follows 80ms later with the same curve.
2. Sticker stays **4 s** (GIF playing).
3. Then it **tucks away**: `translateY(40px) scale(.9); opacity 0`, 200ms ease-in.
4. Hovering the agent row brings the current sticker back while hovered.
5. Rapid status changes: debounce 500ms; a new status replaces the current sticker (restart the timer).
6. Several agents: the sticker belongs to the agent whose status changed most recently.
7. `waiting` and `error` stay visible until the status changes (they need attention).
8. `prefers-reduced-motion` → no pop/tuck animation, just fade.
9. **Serious mode** toggle (settings / tray): no stickers at all, only the colored dot and label. Good for meetings.

## Acceptance

- Matches `reference.html` visually at 100% zoom.
- Every status above can be triggered manually in a dev/debug mode to check the look.
- No layout shift of the widget card when the sticker appears/disappears.
