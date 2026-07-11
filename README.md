# ruler

A free, single-page **on-screen ruler** in centimetres and inches.

- One static file (`index.html`) — no build step, no dependencies.
- Draws mm/inch ticks on a crisp `<canvas>` (device-pixel-ratio aware).
- **Calibration:** a screen only knows its *resolution*, not its physical size, so
  browsers assume a fixed 96 px/inch. Match the on-screen card to a real bank/ID card
  (ISO 7810 ID-1, 85.6 × 53.98 mm) once and the ruler is pinned to true millimetres.
  The value is stored in `localStorage`.

## Local preview

```sh
python3 -m http.server 8080   # then open http://localhost:8080
```

## Deploy — Cloudflare Pages

1. Push this repo to `github.com/useful-static/ruler`.
2. Cloudflare dashboard → **Workers & Pages → Create → Pages → Connect to Git** → pick the repo.
3. Build settings: **Framework preset = None**, **Build command = (empty)**,
   **Build output directory = `/`**. (It's already static — nothing to build.)
4. Deploy. You get a `*.pages.dev` URL.

## Custom domains (ruler.free, ruler.best)

In the Pages project → **Custom domains → Set up a domain**, add each apex domain.
Then point DNS at Cloudflare:

- Easiest: move each domain's nameservers to Cloudflare (Add site → follow the NS change
  at Namecheap). Cloudflare then auto-creates the `CNAME`/apex record and TLS cert.
- Or keep DNS at Namecheap and add the `CNAME` record Cloudflare shows you (apex flattening).
