---
title: "haircut-advisor — project plan (approved)"
course: "TOOL USING AI AGENTS USING MCP SERVERS (IID2103.01-00)"
author: "Anton Shek"
date: 2026-11-14
status: approved
build: Claude Code tab
---

# haircut-advisor — project plan

## How to use this file (for Claude)
- This plan is approved. Build **one phase at a time**, in order.
- Before each phase: say which files you will create or change, then wait for my "go".
- After each phase: run that phase's checks, show the results, and stop.
- Build only what this plan says. If the plan is wrong, tell me and we change the plan first.
- No secrets in any file that git tracks. Keys go in `.env` (git-ignored) or in the Render dashboard.
- Python servers log to **stderr only**. Never `print()` in the MCP server.

## 1. Purpose
Someone scans a QR code. A page opens on their phone. They take a selfie. The page measures the face, names the closest face shape, and suggests haircuts. The result is saved in the cloud with a short code.

An MCP server lets Claude read those results. Claude can explain one person's result by its code ("My code is K7P2QX") and show stats for the whole class.

Why measure instead of letting Claude look at the photo: the same photo gives the same numbers every time, so the result can be tested. [me]

## 2. Decisions (2026-11-14)
| Question | Decision |
|---|---|
| Where does face analysis run? | In the phone browser (MediaPipe Tasks Vision, JavaScript). The photo is never uploaded. |
| What is stored in the cloud? | The haircut table and anonymous results. **No photos, no names, no device IDs.** |
| Cloud database | Supabase, free plan |
| Phone page hosting | GitHub Pages from a **public** repo |
| MCP server | Python + FastMCP. It runs locally (stdio) first, then on Render (HTTP). Phase 8 is required. |
| Build tool | Claude Code tab |

## 3. Architecture
```
[Printed QR #1] → Phone page (GitHub Pages, HTTPS)
                    │  MediaPipe Face Landmarker runs in the browser
                    │  sends only: 4 measurements + shape + choices + code
                    ▼
                 Supabase
                    ├─ haircuts  (read by the page and the MCP server)
                    └─ results   (the page can only INSERT)
                    ▲
                 MCP server (server.py, same code in both places)
                    ├─ local: stdio  → Claude Desktop / Claude Code
                    └─ Render: HTTP  → Claude on any device   [QR #2 = connector URL]
```

## 4. Folder layout
```
haircut-advisor/
  PLAN.md            this file
  README.md          how to run each part
  .gitignore         .env, .venv, __pycache__
  docs/              GitHub Pages serves this folder
    index.html
    app.js
    style.css
  db/
    schema.sql       tables + Row Level Security rules
    haircuts_seed.sql
  server/
    pyproject.toml
    server.py
    .env.example     key names only, no values
  tools/
    make_qr.py
  tests/
    TESTS.md         test cases + results of each run
```

## 5. Face measurements and shapes
The page calculates 4 values from the MediaPipe landmarks:
1. face length ÷ cheekbone width
2. forehead width ÷ cheekbone width
3. jaw width ÷ cheekbone width
4. jaw angle (degrees)

Shapes: oval, round, square, oblong, heart, diamond, triangle.
- The page returns the **top 2 shapes with scores**. Many faces fall between two shapes.
- The cut-off values are a first guess. Tune them in Phase 4 with test photos, and write each change in `tests/TESTS.md`.
- Which landmark indexes to use: decide in Phase 3 and write them in a code comment.

Photo-quality checks: no face found; more than one face; head turned or tilted; mouth open or smiling. Each one shows a warning and does not give a confident result.

## 6. Supabase
### Tables
**haircuts**: `id`, `face_shape`, `name`, `length` (short/medium/long), `textures` (list), `styles` (masculine/feminine/neutral list), `reason` (1 sentence), `avoid` (1 sentence)
- 5–8 cuts per shape. Claude drafts them from common stylist guidance. **I review them before seeding.**

**results**: `id`, `code` (6 characters, unique), `created_at`, the 4 measurements, `shape_1`, `score_1`, `shape_2`, `score_2`, `length_pref`, `texture`, `style`

### Security (Row Level Security)
| Who | haircuts | results |
|---|---|---|
| Phone page (public anon key) | read | **insert only**, no read |
| MCP server (service key, never in git) | read | read |

- The page makes the 6-character code itself (no 0/O/1/I), so it never needs to read the row back.
- Free-plan catch: Supabase pauses a free project after about 7 days of low activity. Open the dashboard the day before any demo.
- Delete all rows from `results` at the end of the semester.

## 7. Phone page
- One page, works on phones first.
- Step 1: a consent line, shown before the camera: "Your photo stays on your phone. Only 4 measurements and your choices are saved. No name."
- Step 2: a "Take photo" button (`<input type="file" accept="image/*" capture="user">`). It opens the front camera or the gallery.
- Step 3: choices: length, texture, style. **The user picks style. The page never guesses gender, age or ethnicity.**
- Step 4: the result: top 2 shapes, 3–5 cuts with reasons, 1 cut to avoid, the caveat, and the code.
- Caveat text on every result: "Face-shape haircut rules are stylist conventions, not science. Measurements are approximate."
- Pin the MediaPipe library version and the model file URL. Do not use `@latest`.

## 8. MCP tools
| # | Tool | Inputs | Returns |
|---|---|---|---|
| 1 | `suggest_haircuts` | `face_shape`, optional `length`, `texture`, `style` | 3–5 cuts with reasons + 1 to avoid + caveat. If the shape is invalid: the list of valid shapes. |
| 2 | `get_result` | `code` | That result's shapes, measurements and suggestions. Unknown code: "No result with that code." |
| 3 | `class_stats` | none | Count and percent per face shape, total results, date range |

Rules for every tool: `async def`, a clear docstring (Claude reads it), returns a string, logs with `logging.info()`, catches database errors and returns a useful message.

**Public endpoint safety (Phase 8):** no tool lists individual results. You can see one result only if you know its code. `class_stats` returns totals only.

## 9. Dependencies
| Part | Needs |
|---|---|
| Page | `@mediapipe/tasks-vision` (CDN, pinned version), `face_landmarker.task` model, Supabase JS client |
| Server | Python via `uv`, `fastmcp`, `supabase` (Python client), `python-dotenv` |
| QR | `qrcode` (Python) |
| Accounts | GitHub (`antonshek-debug`), Supabase, Render |

Python MediaPipe is **not** needed anymore. The old Python-version risk is gone.

## 10. Risks and limits
- The face mesh stops at the upper forehead, so face length is estimated.
- Fringe or bangs, glasses, a smile or a head tilt change the measurements. The quality checks cover the worst cases.
- Older phones may take a few seconds to load the model.
- Render free plan: the server sleeps after 15 minutes idle and takes about 1 minute to wake. Before a demo, open the server URL once to wake it.
- A phone camera needs HTTPS. GitHub Pages provides it.
- Privacy: photos stay on the phone. I'm not a lawyer; ask the professor if the demo needs a consent form.

## 11. Test cases
Write the expected result before building. Record the actual result after each phase in `tests/TESTS.md`.

| # | Test | Expected |
|---|---|---|
| 1 | Same clear front photo, twice | Same shape and same measurements |
| 2 | Photo with no face | "No face found", no crash |
| 3 | Photo with 2 people | Warning, no confident result |
| 4 | Head turned sideways | "Face the camera" warning |
| 5 | `suggest_haircuts("heart", length="short")` | Only short cuts |
| 6 | `suggest_haircuts("blob")` | List of valid shapes |
| 7 | Scan QR on iPhone and Android | Page opens, camera works on both |
| 8 | Camera permission denied | Clear message; gallery still works |
| 9 | Use the anon key to read `results` | Blocked |
| 10 | `get_result("ZZZZZZ")` | "No result with that code" |
| 11 | `get_result(<real code from phone>)` | Same shape the phone showed |
| 12 | Call the Render MCP URL from claude.ai | All 3 tools work |

## 12. Phases
Each phase ends with its checks passing and a git commit with a short message.

| # | Phase | Done when |
|---|---|---|
| 1 | Plan approved | ✅ 2026-11-14 |
| 2 | Supabase: project, `schema.sql`, security rules, draft `haircuts_seed.sql` → **I review** → seed | Test 9 passes; haircuts table has 5–8 rows per shape |
| 3 | Page v1: photo → landmarks → 4 measurements on screen, nothing saved | Tests 1–4 pass on my phone (local preview) |
| 4 | Page v2: shape + choices + haircuts + save + code; tune cut-offs | A row appears in `results`; test 8 passes |
| 5 | Public GitHub repo, GitHub Pages on `docs/`, `make_qr.py` → QR #1 | Test 7 passes |
| 6 | MCP scaffold: no tools, stdio, connected to Claude Desktop and Claude Code | Server shows in both clients |
| 7 | Tools 1 → 2 → 3, one at a time, each tested in both clients before the next | Tests 5, 6, 10, 11 pass |
| 8 | Render: same `server.py` with HTTP transport (env var picks the transport); service key in Render settings; add the URL as a custom connector in claude.ai; QR #2 = connector URL | Test 12 passes |
| 9 | Compare with existing MCP servers; write the experiment note | Note saved in the course folder |

## Sources (checked 2026-11-14)
- MediaPipe Face Landmarker: https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker
- Supabase free-plan pausing: https://supabase.com/docs/guides/platform/free-project-pausing
- Render free web services: https://render.com/docs/free
- Hugging Face Spaces (compute Spaces need a paid plan): https://huggingface.co/docs/hub/en/spaces-overview
- GitHub Pages on the free plan needs a public repo: https://docs.github.com/en/get-started/learning-about-github/githubs-plans
- PIPA and facial photos: https://www.shinkim.com/eng/media/newsletter/pdf/2585
- Course method: Week 7 walkthrough (plan → scaffold → one tool at a time → test)
