# Design

## Visual Theme

Editorial-professional, not SaaS-templated: serif display headings over a sans-serif UI, navy + gold as the entire accent vocabulary, warm off-white paper background rather than pure white or dark mode. Chrome (sidebar, top nav) is solid navy; content areas are warm-white cards on a warm-cream page background.

## Color

Defined as CSS custom properties in `app.py` (`:root` block near the top of the injected `<style>`):

| Token | Value | Role |
|---|---|---|
| `--paper` | `#F8F6EE` | Page background |
| `--paper-2` | `#FCFAF3` | Secondary surface |
| `--card` | `#FFFFFF` | Card background |
| `--ink` | `#14213F` | Primary text, sidebar/nav chrome background |
| `--ink-soft` | `#3F4C63` | Secondary text |
| `--ink-faint` | `#78859C` | Tertiary/muted text |
| `--line` / `--line-strong` | `#E1DCCB` / `#CEC6AE` | Borders |
| `--teal` | `#1D3E72` | Primary accent (buttons, active states, links) — despite the variable name, this is navy, not teal |
| `--teal-bright` | `#2C5590` | Accent hover/active state |
| `--teal-wash` | `#E7ECF4` | Light accent-tinted background wash |
| `--gold` | `#BA8F4E` | Secondary accent — decorative lines, icons, callouts (not button backgrounds; too light for reliable white-text contrast) |
| `--gold-wash` | `#F3E7D2` | Light gold-tinted background wash |
| `--coral` / `--coral-wash` | `#C24A38` / `#F6E6E1` | Error/warning/overdue states |

Per-subject category colors (VR/DM/QR/SJT pills, chart bars) are muted navy/gold-family tints defined in `database.py` `_SUBJECTS`, not the CSS variables above — kept deliberately desaturated so they never outcompete the brand accent.

## Typography

- `--serif`: Charter/Iowan Old Style/Palatino/Georgia stack — page titles and headings (`h1`–`h3`).
- `--sans`: system UI stack — body text and most widget labels.
- `--mono`: ui-monospace stack — small caps labels (e.g. "OVERALL ACCURACY"), numeric figures, countdown/stat emphasis.

## Layout & Components

- Dark navy sidebar (`[data-testid="stSidebar"]`) and a dark navy top nav bar (`.st-key-topnav`) are the two "chrome" surfaces; everything else sits on the warm-cream page background.
- Top nav on mobile (`max-width: 768px`) is a horizontally scrollable single row (not a wrapping grid) — see the mobile-nav comment block in `app.py`.
- Cards: white background, 1px `--line` border, soft shadow (`0 1px 3px rgba(0,0,0,0.08)` for stat/metric containers, slightly heavier for the flashcard face and hero card).
- `.hero-card`: the Dashboard's single high-contrast metric card (navy gradient), holding the one most important number plus inline quick-action buttons — used once per page, not a repeatable pattern.
- Buttons: `kind="primary"` = solid `--teal` (navy) background with white text; `kind="secondary"` = outlined, `--ink` text, `--teal` border/text on hover. Both have `:active { transform: scale(0.97) }` press feedback.
- Entrance motion: `fadeSlideIn` keyframe (fade + 6px translateY, 220ms ease-out) applied to metric containers, the flashcard face, and alert boxes.

## Motion Principles

Per PRODUCT.md: motion confirms, it doesn't entertain. Prefer `ease-out` exponential curves over bounce/elastic. No animation on high-frequency actions. Every animation should degrade gracefully (crossfade or instant) under `prefers-reduced-motion: reduce` — not yet implemented everywhere; new motion work should add it from the start.
