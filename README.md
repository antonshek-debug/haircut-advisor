# haircut-advisor

A phone page measures a selfie, names the closest face shape and suggests haircuts. An MCP server lets Claude read the saved results. The full plan is in [PLAN.md](PLAN.md).

## Phone page (live)

https://antonshek-debug.github.io/haircut-advisor/

GitHub Pages serves the `docs/` folder of the `main` branch. A push to `main` updates the page after about a minute.

QR #1 for this address is `tools/qr-page.png`. To make it again, or to make a QR code for another address:

```bash
uv run tools/make_qr.py https://antonshek-debug.github.io/haircut-advisor/ tools/qr-page.png
```

## People with a similar face shape

`docs/celebrities.json` lists well-known people that style articles describe as having each face shape, with a source link per person. Nobody on the list was measured. Their photos in `docs/celebs/` are freely licensed ones from Wikimedia Commons; the author and licence of each are in the JSON file and shown as a credit on the page.

To change the list, edit `PEOPLE` in `tools/make_celebs.py` and run:

```bash
python tools/make_celebs.py
```

## Phone page (local preview)

The page is in `docs/`. It needs a web server; opening `index.html` as a file does not work.

```bash
python -m http.server 8000 --directory docs
```

- On this PC: open `http://localhost:8000`.
- On a phone: connect it to the same Wi-Fi, then open `http://<PC IP address>:8000`. Find the address with `ipconfig` (IPv4 Address). If Windows Firewall asks, allow Python on private networks.
- The phone needs internet, because the MediaPipe library and the face model load from a CDN.

## MCP server

The server is in `server/`. It uses Python through `uv`. It reads the database with the secret key, so it never hands out single results except by their code.

| Tool | What it does |
|---|---|
| `suggest_haircuts(face_shape, length?, texture?, style?)` | Up to 5 cuts for a face shape, one thing to avoid, and a caveat. The filters are strict. |
| `get_result(code)` | One saved result by its 6-character code: the two closest shapes, the 4 measurements, the person's choices and matching cuts. Case and spaces do not matter. |
| `class_stats()` | Totals only: number of results, date range, and the count and percent per closest shape. |

Set up once:

1. Copy `server/.env.example` to `server/.env` and fill in the two values. `server/.env` is git-ignored. The secret key must never be committed.
2. Install the packages:

```bash
uv sync --directory server
```

Run it by hand (it waits for an MCP client on stdin; stop it with Ctrl+C):

```bash
uv run --directory server server.py
```

Connect the clients:

- **Claude Code:** `.mcp.json` in this folder registers the server for this project. Claude Code asks once whether to trust it.
- **Claude Desktop:** add an entry named `haircut-advisor` to `mcpServers` in `claude_desktop_config.json` (Settings → Developer → Edit Config). Use full paths: `command` is `server\.venv\Scripts\python.exe` inside this folder, and `args` holds the full path of `server\server.py`. Then quit Claude Desktop from the tray and open it again.

### On Render (HTTP)

The same `server.py` runs on Render's free plan. The `MCP_TRANSPORT` setting picks the transport: unset means stdio, `http` means HTTP on Render's `$PORT`.

Web Service settings in the Render dashboard:

- Root Directory: `server`
- Build Command: `pip install uv && uv sync --frozen`
- Start Command: `uv run server.py`
- Environment: `MCP_TRANSPORT=http`, `PYTHON_VERSION=3.13`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` (the secret key lives only here and in `server/.env`)

A push to `main` redeploys it. The MCP address is the service URL plus `/mcp`; add that in claude.ai under Settings → Connectors → Add custom connector.

Live connector URL: `https://haircut-advisor.onrender.com/mcp`. QR #2 for it is `tools/qr-connector.png`.

The free server sleeps after 15 minutes idle and takes about a minute to wake. Before a demo, open the service URL itself in a browser; it shows "haircut-advisor MCP server is running".

Anyone with the URL can call the 3 tools, so they never list single results: one result needs its code, and `class_stats` gives totals only.

The server logs to stderr only. Never add `print()` to it: stdout carries the MCP messages.

## Database

`db/schema.sql` creates the tables and security rules. `db/haircuts_seed.sql` fills the `haircuts` table. Run both in the Supabase SQL Editor, schema first.

## Tests

Test cases and the result of each run are in [tests/TESTS.md](tests/TESTS.md).
