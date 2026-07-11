# Ruler — Requirements

A single static page (`public/index.html`, no dependencies, no build step)
serving a physically-accurate on-screen ruler at **ruler.free** and
**ruler.best** (Cloudflare Workers static assets, auto-deployed from
`master` via `npx wrangler deploy`).

## Core

- **R1 — Physical accuracy.** The ruler measures true centimetres and inches
  on the viewer's screen, to the limit of what the browser can know. Both
  scales are always shown: cm ticked from one edge (1 mm resolution), inches
  from the other (1/16″ resolution).
- **R2 — Browsers cannot report physical size.** No API exposes the panel's
  physical dimensions, native resolution, or true zoom; `devicePixelRatio`
  fuses browser-zoom × OS-scaling and CSS `in`/`cm` units are fixed at
  96 px/in regardless of the real display. Therefore the page must (a) start
  from a sensible estimate, and (b) make calibration easy.
- **R3 — Default calibration by device class.** First visit assumes
  96 ppi on desktop (hover + fine pointer), 160 ppi on phones, 132 ppi on
  tablets (minimum screen side > 550 px).
- **R4 — User calibration.** Three ways, all persisted in `localStorage`:
  - drag a slider until the on-screen credit-card outline matches a real
    ISO 7810 card (85.60 mm);
  - click the DISPLAY SIZE readout and type the diagonal (inches or cm,
    with live unit conversion);
  - click the RESOLUTION readout and type the native W × H (two boxes).
- **R5 — Calibration is stored zoom-invariantly** as *device* px per inch
  (`devPpi`); the live CSS px/in is derived per frame as `devPpi / dpr`.
  Legacy CSS-ppi values are migrated on load. A stored value is sanity-
  guarded to 20–4000 dev-ppi; the derived per-draw value is **never**
  clamped (clamping it breaks high-zoom rendering).

## Zoom behaviour

- **R6 — The whole page is zoom-proof.** Browser zoom must not change the
  ruler's physical size, span, or unit count — a 10 cm object measures
  10 cm at 25 %, 100 % and 500 % zoom — and must not fatten the tick
  lines, borders, or corner radius, nor reflow/clobber the header, info
  readouts, or calibration panel. Implemented as a page-wide counter-zoom
  (`body { zoom: LOAD_DPR / devicePixelRatio }`), which pins every CSS px
  at a constant physical size so the page renders identically at every
  zoom level; a `--z` custom property compensates viewport units
  (`vh`/`vw`/`dvh`), which the body zoom does not reach.
- **R7 — Tick lines stay thin.** Under the counter-zoom, 1 px lines stay
  1 device px (at load scale) at any zoom — zooming in must never produce
  fat marks or edges.
- **R8 — Labels stay legible at any zoom.** Under the counter-zoom the
  label font is a constant 12 px at all zoom levels — never a tiny
  fractional CSS size (e.g. `2.4px`), which font-hinting renders
  blank/illegible on some platforms.
- **R9 — Adaptive label decimation.** When marks crowd (zoomed out, small
  ruler, low ppi), number labels thin to a logical step — cm from
  {1, 2, 5, 10, 20, 50, …}, inches from {1, 2, 3, 6, 12, 24, …} — chosen as
  the smallest step whose mark spacing fits the widest label plus a gap.
  Each scale decimates independently; ticks are never removed.
- **Known limitation — load-while-zoomed.** On a *first* visit with no
  saved calibration, the auto-estimate can't separate browser-zoom from
  OS-scaling inside `devicePixelRatio`, so a page loaded at e.g. 500 % zoom
  misestimates until zoom returns to 100 % or the user calibrates. Saved
  calibrations are immune.

## Layout & interaction

- **R10 — Geometry.** The ruler band is centered and spans 95 % of the
  viewport (width when horizontal, height when vertical) while the
  measuring section (first to last tick) spans 90 %, leaving a 2.5 %
  run-out past the 0 and last mark at each end. The band has a 1 px edge
  line and inset shadow on **all four sides** and rounded ends (16 px
  radius at 100 %, physically constant across zoom) that the ticks never
  enter.
- **R11 — Orientation toggle.** Clicking the ruler (or the header button)
  flips horizontal ↔ vertical; the choice persists. Vertical mode runs the
  ruler top-to-bottom centered, moves the info readouts to the left, and
  puts the calibration panel in a right-hand drawer that widens as the
  card outline grows so the card is never clipped.
- **R12 — Transparency readouts.** The page shows what it detected and how
  trustworthy it is: logical + assumed-native resolution, the fused
  dpr value (labelled as browser-zoom × display-scale, not separable), and
  the estimated physical display size — each editable where calibration
  applies (R4).

## Hosting & repo

- **R13 — Static and self-contained.** One HTML file, no JS dependencies,
  no build step; deployable as Cloudflare Workers static assets
  (`wrangler.jsonc`, assets dir `public/`).
- **R14 — Domains.** ruler.free (canonical) and ruler.best, registered at
  Namecheap, DNS + TLS via Cloudflare; both serve the same Worker.
- **R15 — Authorship.** Commits are authored `Useful Static
  <useful.static@known.name>` with no AI attribution trailers.
