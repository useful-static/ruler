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
- **R4 — User calibration.** Four ways, all persisted in `localStorage`:
  - drag a slider until the on-screen credit-card outline matches a real
    ISO 7810 card (85.60 mm);
  - click the DISPLAY SIZE readout and type the diagonal (inches or cm,
    with live unit conversion);
  - click the RESOLUTION readout and type the native W × H (two boxes);
  - real-ruler cross-check: type what the site's M cm mark measures on a
    physical ruler — density is corrected by M/R.
- **R4b — Known devices are exact without calibration.** Chrome's UA-CH
  high-entropy `model` hint identifies the device; a small table maps
  models to panel diagonals (mode-invariant), giving the true density as
  `hypot(native res)/diagonal`. Never overrides a user calibration.
  Currently: Galaxy S24 Ultra (SM-S928\*, 6.79″), Galaxy Tab S8 Ultra
  (SM-X900/X906, 14.6″) — extend the table as devices are reported.
- **R5 — Calibration is stored zoom-invariantly** as *device* px per inch
  (`devPpi`); the live CSS px/in is derived per frame as `devPpi / dpr`.
  Legacy CSS-ppi values are migrated on load. A stored value is sanity-
  guarded to 20–4000 dev-ppi; the derived per-draw value is **never**
  clamped (clamping it breaks high-zoom rendering).

## Zoom behaviour

- **R6 — The ruler is zoom-proof; the page around it zooms normally.**
  Browser zoom must not change the ruler's physical size, span, unit
  count, line weights, or corner radius — a 10 cm object measures 10 cm at
  25 %, 100 % and 500 % zoom. The DOM (header, readouts, panel) follows
  the browser's zoom like any web page, so the user can always make the
  text bigger — the page must never counter-zoom the DOM (an earlier
  page-wide `body{zoom}` design made everything unreadably small whenever
  the load-time baseline was captured at a remembered per-site zoom).
- **R7 — Ruler chrome is anchored to the calibration, not to load state.**
  Band thickness, tick lengths, run-out, radius, and label sizes scale by
  `k = ppi/96` — a function of the persisted `devPpi` and live dpr only —
  so the band is the same physical size on every display and at every
  zoom, and no load-time dpr snapshot can bake a wrong baseline. Tick
  positions and widths snap to whole device px (~1 device px lines: thin
  at any zoom).
- **R8 — Labels stay legible at any zoom.** Canvas text renders at an
  integer device-px size through an identity transform — never a tiny
  fractional CSS size (e.g. `2.4px`), which font-hinting renders
  blank/illegible on some platforms.
- **R8b — Readouts track zoom live.** The dpr/zoom readout and ruler
  re-render on every zoom change (resize + a re-arming `resolution`
  media-query watcher; dpr is read inside rAF because resize can dispatch
  before it settles).
- **R8c — Loading at any zoom yields the same physical ruler.** The zoom
  factor is estimated from `outerWidth / innerWidth` (Chrome keeps
  `outerWidth` in OS-scale px), snapped to the browser's discrete zoom
  levels, so the auto-estimates (`DEFAULT × OS-scale`, `screen × OS-scale`)
  are zoom-independent on every load. When the ratio is unrecognizable
  (e.g. devtools docked aside) the persisted last-known-good estimate is
  used, bounded by the OS-scale-≥1 backstop. The ZOOM readout shows the
  recovered split (`≈ N % zoom × M× display-scale`) when known.
- **R8d — Storage is schema-versioned.** All persisted state lives under
  `ruler.*` keys stamped with `ruler.schema`; a schema bump wipes older
  keys once on the next visit, so browsers carrying stale data from
  previous versions self-clean. Stored calibrations are additionally
  sanity-checked at load (impossible values are discarded).
- **R8e — Nothing persists without a user action.** Auto-estimates (ppi,
  native resolution, device-table density) are session-only and
  recomputed on every load; `localStorage` holds only what the user
  explicitly set (calibration, typed resolution, orientation) plus the
  schema stamp. Resets *delete* the stored value rather than writing a
  new one.
- **R9 — Adaptive label decimation.** When marks crowd (zoomed out, small
  ruler, low ppi), number labels thin to a logical step — cm from
  {1, 2, 5, 10, 20, 50, …}, inches from {1, 2, 3, 6, 12, 24, …} — chosen as
  the smallest step whose mark spacing fits the widest label plus a gap.
  Each scale decimates independently; ticks are never removed.
- **Known limitation — unreadable zoom factor.** When the
  `outerWidth/innerWidth` ratio doesn't snap to a standard zoom level
  (devtools docked to a side, exotic window chrome, browsers where
  `outerWidth` zooms too), the estimate falls back to the persisted value
  or assumes 100 % — a load in that state while zoomed can misestimate
  until a load with readable zoom, a ↺ reset, or a real calibration.
  Saved calibrations are immune.

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
- **R16 — Smoke tests gate every change.** `tests/smoke.py` (headless
  Chromium, no deps) must pass before any push touching
  `public/index.html`: default sizes, zoom-invariance, zoomed-reload
  consistency, estimate healing, calibration round-trips, label
  visibility, orientation. Run with `--url https://ruler.free` after a
  deploy to verify production.
