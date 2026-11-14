# haircut-advisor

A phone page measures a selfie, names the closest face shape and suggests haircuts. An MCP server lets Claude read the saved results. The full plan is in [PLAN.md](PLAN.md).

## Phone page (live)

https://antonshek-debug.github.io/haircut-advisor/

GitHub Pages serves the `docs/` folder of the `main` branch. A push to `main` updates the page after about a minute.

QR #1 for this address is `tools/qr-page.png`. To make it again, or to make a QR code for another address:

```bash
uv run tools/make_qr.py https://antonshek-debug.github.io/haircut-advisor/ tools/qr-page.png
```

## Haircut drawings

`docs/cuts/` holds one SVG line drawing per haircut, named `<face shape>-<cut name in lower case with hyphens>.svg`. To make them again after changing the `haircuts` table (needs `.env`):

```bash
python tools/make_cuts.py
```

It also writes `tools/cuts-review.html`, one page with every drawing (not tracked by git).

## Phone page (local preview)

The page is in `docs/`. It needs a web server; opening `index.html` as a file does not work.

```bash
python -m http.server 8000 --directory docs
```

- On this PC: open `http://localhost:8000`.
- On a phone: connect it to the same Wi-Fi, then open `http://<PC IP address>:8000`. Find the address with `ipconfig` (IPv4 Address). If Windows Firewall asks, allow Python on private networks.
- The phone needs internet, because the MediaPipe library and the face model load from a CDN.

## Database

`db/schema.sql` creates the tables and security rules. `db/haircuts_seed.sql` fills the `haircuts` table. Run both in the Supabase SQL Editor, schema first.

## Tests

Test cases and the result of each run are in [tests/TESTS.md](tests/TESTS.md).
