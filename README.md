# ruler

A free, single-page **on-screen ruler** in centimetres and inches.

- One static file (`public/index.html`) — no build step, no dependencies.
- Draws mm/inch ticks on a crisp `<canvas>` (device-pixel-ratio aware).
- **Calibration:** a screen only knows its *resolution*, not its physical size, so
  browsers assume a fixed 96 px/inch. Match the on-screen card to a real bank/ID card
  (ISO 7810 ID-1, 85.6 × 53.98 mm) once and the ruler is pinned to true millimetres.
  The value is stored in `localStorage`.

## Local preview

```sh
python3 -m http.server 8080 --directory public   # then open http://localhost:8080
```

## Smoke tests — run before every push

```sh
python3 tests/smoke.py                    # local public/index.html
python3 tests/smoke.py --url https://ruler.free   # verify a live deploy
```

Headless-Chromium suite (no pip deps) asserting the invariants that have
broken before: sane default sizes, physical zoom-invariance (25–500 %),
reload-while-zoomed consistency, estimate self-healing, calibration
round-trips (slider / click-to-set / ↺ resets), visible number labels, and
orientation persistence. A change to `public/index.html` is not pushable
until `tests/smoke.py` exits 0.

## Deploy — Cloudflare Workers (static assets)

Served as an **assets-only Worker**: `wrangler.jsonc` points at
`public/`, so a plain `wrangler deploy` uploads the static files — no Worker script,
no build step. The repo is connected to a Cloudflare Worker with Git builds, so a
push to `master` auto-deploys; to deploy from a local checkout instead:

```sh
npx wrangler deploy      # build command: (empty)
```

## Custom domains (ruler.free, ruler.best)

In the Worker → **Settings → Domains & Routes → Add → Custom domain**, add each apex
domain. Point DNS at Cloudflare:

- Easiest: move each domain's nameservers to Cloudflare (Add site → follow the NS
  change at Namecheap). Cloudflare then auto-creates the apex record and TLS cert.
- Or keep DNS at Namecheap and add the record Cloudflare shows you (apex flattening).
