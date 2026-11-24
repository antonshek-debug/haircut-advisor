# Tests

Expected results come from PLAN.md section 11. Record the actual result after each phase.

## Test cases

| # | Test | Expected | Phase | Status |
|---|---|---|---|---|
| 1 | Same clear front photo, twice | Same shape and same measurements | 3 | pass (2026-11-14) |
| 2 | Photo with no face | "No face found", no crash | 3 | pass (2026-11-14) |
| 3 | Photo with 2 people | Warning, no confident result | 3 | pass (2026-11-14) |
| 4 | Head turned sideways | "Face the camera" warning | 3 | pass (2026-11-14) |
| 5 | `suggest_haircuts("heart", length="short")` | Only short cuts | 7 | pass (2026-11-16) |
| 6 | `suggest_haircuts("blob")` | List of valid shapes | 7 | pass (2026-11-16) |
| 7 | Scan QR on iPhone and Android | Page opens, camera works on both | 5 | pass (2026-11-14) |
| 8 | Camera permission denied | Clear message; gallery still works | 4 | pass (2026-11-14) |
| 9 | Use the anon key to read `results` | Blocked | 2 | pass (2026-11-14) |
| 10 | `get_result("ZZZZZZ")` | "No result with that code" | 7 | pass (2026-11-24) |
| 11 | `get_result(<real code from phone>)` | Same shape the phone showed | 7 | pass (2026-11-24) |
| 12 | Call the Render MCP URL from claude.ai | All 3 tools work | 8 | not run |
| 13 | (removed 2026-11-15 with the haircut drawings) | — | 4b | removed |
| 14 | Open a result on the phone | The result shows my photo next to 3 or 4 people for my shape and style; each has a photo credit and a source link; the page sends no image to any server | 4c | pass (2026-11-15) |

## Run log

### Phase 2 — Supabase

Run 2026-11-14 with `curl` against the Supabase REST API, using the anon key only.

| Check | Expected | Actual | Result |
|---|---|---|---|
| Test 9: anon reads `results` | Blocked | HTTP 401, `42501 permission denied for table results` | pass |
| Anon inserts a valid row into `results` | Accepted | HTTP 201 | pass |
| Anon inserts a row with code `O0I1AA` | Rejected | HTTP 400, `results_code_check` violated | pass |
| Anon deletes from `results` | Blocked | HTTP 401, `42501 permission denied` | pass |
| Anon inserts into `haircuts` | Blocked | HTTP 401, `42501 permission denied` | pass |
| Anon reads `haircuts` | Allowed | 46 rows returned | pass |
| `haircuts` rows per shape | 5–8 each | diamond 7, heart 6, oblong 7, oval 7, round 6, square 7, triangle 6 | pass |

Left behind: one test row in `results` with code `LLDWWQ` (oval/heart, made-up measurements). Delete it in the dashboard before real use.

### Phase 3 — Page v1

Run 2026-11-14. Local preview (`python -m http.server`), page opened on the tester's phone over Wi-Fi. MediaPipe tasks-vision 1.2.3, CPU delegate. Tests 1–4 were run and reported by the tester; the PC checks were run by Claude in the browser pane.

| Check | Expected | Actual | Result |
|---|---|---|---|
| Test 1: same front photo, twice | Same measurements | Same both times: length 1.231, forehead 0.889, jaw 0.798, jaw angle 139.7° | pass |
| Test 2: photo with no face | "No face found", no crash | As expected | pass |
| Test 3: photo with 2 people | Warning, no confident result | As expected | pass |
| Test 4: head turned sideways | "Face the camera" warning | As expected | pass |
| Landmark lines on the photo | On forehead, cheekbones, jaw corners, chin | Lines sit on the intended spots | pass |
| PC: page and model load | No console errors | Status "Ready", no errors | pass |
| PC: generated image with no face | "No face found" | As expected | pass |
| PC: non-image file | Clear message, buttons work again | As expected | pass |

Notes:
- The page has two buttons, "Take photo" (front camera) and "Choose from gallery", because `capture="user"` hides the gallery on most phones.
- Phase 3 does not name a shape yet, so test 1 covers measurements only.

### Phase 4 — Page v2

Run 2026-11-14. Local preview, page opened on the tester's phone over Wi-Fi. supabase-js 2.119.0. The phone checks were run and reported by the tester; the PC checks were run by Claude in the browser pane. Claude cannot read `results` (anon key is blocked), so the saved row was confirmed by the tester in the dashboard.

| Check | Expected | Actual | Result |
|---|---|---|---|
| Phone: photo → choices → result | 2 shapes, 3–5 cuts, 1 to avoid, caveat, code | As expected | pass |
| A row appears in `results` | Row with the code shown on the phone | Seen in the dashboard | pass |
| Test 8: camera permission denied | Clear message; gallery still works | As expected | pass |
| Test 1, shape part: 4 photos of one person | Same top 2 shapes | oval then round for all 4 | pass |
| PC: all 336 shape and choice combinations | 3–5 cuts each | min 3, max 5 | pass |
| PC: 2,000 generated codes | 6 characters, no 0/O/1/I | All valid | pass |

Notes:
- In 272 of the 336 combinations at least one cut is a "close match, not exact", because there are only 6–7 cuts per shape.
- Test 8 is covered by a permanent hint under the buttons. The page cannot detect a denied camera, because "Take photo" hands off to the phone's camera app.
- A photo with a quality warning gets no shape and is not saved.

### Phase 5 — GitHub Pages and QR #1

Run 2026-11-14. Live page: https://antonshek-debug.github.io/haircut-advisor/ (GitHub Pages, `main` branch, `/docs`). Test 7 was run and reported by the tester; the other checks were run by Claude.

| Check | Expected | Actual | Result |
|---|---|---|---|
| Test 7: scan QR #1 on an iPhone | Page opens, camera works | As expected | pass |
| Test 7: scan QR #1 on an Android phone | Page opens, camera works | As expected | pass |
| Live page loads over HTTPS | No console errors, model loads | Status "Ready", no errors | pass |
| Live page reads `haircuts` | HTTP 200 | HTTP 200, 7 oval rows | pass |
| `tools/qr-page.png` decodes | The live page address | Decoded with zxing-cpp to the live address | pass |
| Tracked files hold no secrets | None | None found; `.env` is not tracked | pass |

### Phase 4b — Haircut drawings

Run 2026-11-14 by Claude in the browser pane, local preview. The phone part of test 13 and the tester's review of the drawings are still open.

| Check | Expected | Actual | Result |
|---|---|---|---|
| Every row in `haircuts` has a drawing | 46 files, names match the page's rule | 46 rows in the live table, 0 missing files | pass |
| Test 13, PC: suggested cuts show drawings | A drawing next to each cut | 3 of 3 real cuts loaded their drawing | pass |
| Test 13, PC: cut with a missing file | Shown without a picture, no error | Shown without a picture; only the browser's own 404 line in the console, no script error | pass |
| Test 13, phone | Every suggested cut shows its drawing | not run | open |

Notes:
- Drawings are made by `tools/make_cuts.py` (added to the plan's file list with the tester's approval): a face outline per shape plus hair parts.
- Each cut is drawn once, in the first texture listed for it.

### Phase 4b — drawings removed (2026-11-15)

The tester asked for the drawings to be removed entirely once the people comparison worked. Removed: the 46 files in `docs/cuts/`, `docs/cut-specs.json`, `tools/make_cuts.py`, and the drawing code, label and styles on the page. Test 13 is removed with them. The Phase 4b results above are kept as a record.

### Phase 4c — first attempt: haircut drawn on the user's photo (dropped)

Built 2026-11-14, checked on the PC with a synthetic face (176 drawings, no errors), tried by the tester on a phone, and dropped on 2026-11-15: it did not look good enough. The code was removed before anything was pushed.

### Phase 4c — People with a similar face shape

Run 2026-11-15 by Claude in the browser pane, local preview. The tester approved the list of 42 people for publishing on 2026-11-15 and ran the phone part of test 14 on the live page.

| Check | Expected | Actual | Result |
|---|---|---|---|
| List size | 3 masculine and 3 feminine per shape | 42 people, 6 per shape | pass |
| Every person has a source article | A link to an article that names them under that shape | 42 of 42; 40 names were read on the page, 2 (Bradley Cooper, Daniel Craig) come from the article's title because the page did not load | pass |
| Every photo is freely licensed | CC BY, CC BY-SA, CC0 or public domain, from Wikimedia Commons | 42 of 42, each with author and licence recorded | pass |
| Every shape and style gives enough people | 3 (masculine, feminine) or 4 (neutral) | All 21 combinations give 3 or 4 | pass |
| Test 14, PC: section shows on the result | "You" tile plus the people, with credits and links | Shown for oblong/neutral with a stand-in for the user's photo; 4 photos loaded; no console errors | pass |
| Test 14, phone | My photo next to the people | Reported by the tester on the live page: it works | pass |
| Test 14: no image sent to a server | No upload | The user's photo is only copied to a canvas in the page; not yet checked on a phone | open |

Notes:
- Nobody on the list was measured. The face-shape label is the source article's opinion, and articles disagree with each other.
- Only 3 people on the list are Korean or Korean American (Suga, Jennie, Daniel Dae Kim). The search found one usable K-pop source, and it covers round faces only.
- The "often seen with" haircut text is Claude's own short description, not from the source articles. It needs the tester's review.
- `tools/make_celebs.py` (not in the plan's original file list) builds the list and downloads the photos.

### Phase 6 — MCP scaffold

Run 2026-11-16 by Claude. fastmcp 4.2.0, supabase 2.34.1, python-dotenv 1.2.4, Python 3.13. The check in both clients was done by the tester.

| Check | Expected | Actual | Result |
|---|---|---|---|
| Server starts the way Claude Code starts it (`uv run --directory server server.py` from the project folder) | Handshake answers, no tools | Server name `haircut-advisor`, tools `[]`, clean exit | pass |
| Server starts from another folder with full paths (the way Claude Desktop starts it) | Same | Same, with `uv` and with the venv's `python.exe` | pass |
| Path with Cyrillic letters, spaces and brackets | No launch problem | None seen | pass |
| Only MCP messages on stdout | Every stdout line is valid JSON | Yes; log lines go to stderr | pass |
| Settings | Logged as set or missing, never the value | `SUPABASE_URL is set`, `SUPABASE_SERVICE_KEY is set` | pass |
| Secret key stays out of git | `server/.env` ignored | Ignored by `.gitignore` | pass |
| Claude Desktop config | One `haircut-advisor` entry added, nothing else changed | Confirmed by comparing the file before and after | pass |
| Server shows in Claude Desktop | Listed as running | Reported by the tester: shown | pass |
| Server shows in Claude Code | Listed as connected | Reported by the tester: shown. This Claude Code session also lists `haircut-advisor` as a connecting server. | pass |

Note: the tester first saved the settings as `server.env` in the project root, where git did not ignore it. Claude moved it to `server/.env` and added `*.env` to `.gitignore` before any commit. The key was never committed.

### Phase 7 — Tools

#### Tool 1: `suggest_haircuts`

Run 2026-11-16 by Claude: the server started over stdio and called with MCP messages, against the live `haircuts` table. Both clients were then checked by the tester.

| Check | Expected | Actual | Result |
|---|---|---|---|
| Test 5: `suggest_haircuts("heart", length="short")` | Only short cuts | 3 cuts, all short, plus 1 thing to avoid and the caveat | pass |
| Test 6: `suggest_haircuts("blob")` | List of valid shapes | `"blob" is not a valid face shape. Valid shapes: oval, round, square, oblong, heart, diamond, triangle.` | pass |
| Shape with spaces and capitals (`" Oval "`) | Accepted | 5 cuts for oval | pass |
| No filters | At most 5 cuts | 5 of oval's 7 | pass |
| Filters that match nothing (round, long, coily, masculine) | Clear message, no crash | "No cut in the table matches all of these filters. Try again with fewer filters." | pass |
| Invalid filter (`length="tiny"`) | List of valid values | `"tiny" is not a valid length. Valid values: short, medium, long.` | pass |
| `length="any"` | Treated as no length filter | 5 cuts of mixed length | pass |
| Database unreachable (wrong URL on purpose) | Useful message, no crash | "The haircut database could not be reached. …" and the error in the stderr log | pass |
| Logging | One `logging.info` line per call, on stderr | Yes | pass |
| Called from Claude Code | Works | Reported by the tester: works. Claude also called it from a Claude Code session on 2026-11-16: heart/short gave 3 short cuts, and "blob" gave the list of valid shapes. | pass |
| Called from Claude Desktop | Works | Reported by the tester: works | pass |

Note: unlike the phone page, the tool does not fill the list with "close match" cuts. Its filters are strict, so it can return fewer than 3 cuts and says so.

#### Tool 2: `get_result`

Run 2026-11-16 by Claude: the server started over stdio and called with MCP messages, against the live `results` table. CJ663Q is the newest saved row (2026-11-15), used as a real code.

| Check | Expected | Actual | Result |
|---|---|---|---|
| Tools listed | `suggest_haircuts`, `get_result` | Both | pass |
| `get_result("CJ663Q")` | Both shapes with scores, 4 measurements, choices, suggestions | oblong 0.41, oval 0.34; 1.242 / 0.890 / 0.771 / 143.9°; any, straight, feminine; 3 oblong cuts, avoid line, caveat | pass |
| `" cj6 63q "` (lower case, spaces) | Same result as CJ663Q | Same | pass |
| Test 10: `"ZZZZZZ"` (well-formed, not saved) | "No result with that code." | Yes | pass |
| `"hello"`, `"OOOOOO"`, `""` (malformed) | "No result with that code.", no database call needed | Yes | pass |
| Database unreachable (wrong URL on purpose) | Useful message, no crash | "The haircut database could not be reached. …" and the error in the stderr log | pass |
| Logging | One `logging.info` line per call, on stderr | Yes | pass |
| Test 11: shape matches the phone | Same closest shape the phone showed | Reported by the tester: matches | pass |
| Called from Claude Code | Works | Reported by the tester: works. Claude also called it from a Claude Code session on 2026-11-24: "zzzzzz" gave "No result with that code." | pass |
| Called from Claude Desktop | Works | Reported by the tester: works | pass |

Note: the suggestions use the closest shape and the person's saved choices, with the same strict filters as `suggest_haircuts`. A saved length of "any" means no length filter.

#### Tool 3: `class_stats`

Run 2026-11-24 by Claude: the server started over stdio and called with MCP messages, against the live `results` table. Before the run, the tester deleted the old test rows (ids 4–11, scored with version 1 cut-offs); 11 rows remained (ids 12–22).

| Check | Expected | Actual | Result |
|---|---|---|---|
| Tools listed | All 3 tools | `suggest_haircuts`, `get_result`, `class_stats` | pass |
| `class_stats()` | Total, date range, count and percent per shape | 11 results, 2026-11-14 to 2026-11-24; oval 4 (36%), oblong 4 (36%), round 2 (18%), diamond 1 (9%), square, heart, triangle 0; caveat | pass |
| Totals only | No codes, no single rows, no measurements | None in the output | pass |
| Counts add up | Sum equals the total | 4 + 4 + 2 + 1 = 11 | pass |
| Extra argument (`shape="oval"`) | Refused | Refused by FastMCP: "Unexpected keyword argument" | pass |
| Database unreachable (wrong URL on purpose) | Useful message, no crash | "The haircut database could not be reached. …" and the error in the stderr log | pass |
| Logging | One `logging.info` line per call, on stderr | Yes | pass |
| Called from Claude Code | Works | Reported by the tester: works. Claude also called it from a Claude Code session on 2026-11-24: same 11 results and percentages. | pass |
| Called from Claude Desktop | Works | Reported by the tester: works | pass |

Note: rows 12–17 were saved on 2026-11-14, the day the cut-offs changed to version 2. Rows keep the shape the page gave when they were saved.

### Phase 8: Render (HTTP)

#### First deploy, 2026-11-24: failed

Render built commit `7b28f7e` without errors, but that `server.py` always started on stdio. With no client on stdin the server stopped at once, and Render reported "Application exited early" and restarted it in a loop. Fix: `MCP_TRANSPORT=http` now starts the HTTP transport on `0.0.0.0:$PORT` at `/mcp`, and `GET /` gives a plain "running" page for waking the server.

#### Local checks before the second deploy (2026-11-24, by Claude)

| Check | Expected | Actual | Result |
|---|---|---|---|
| HTTP mode: tools listed | All 3 | All 3 | pass |
| HTTP mode: one call per tool | Same answers as stdio | heart/short cuts; "No result with that code."; 11 results | pass |
| HTTP mode: `GET /` | Plain "running" page | 200, "haircut-advisor MCP server is running. …" | pass |
| stdio mode still works (`MCP_TRANSPORT` unset) | Same as Phase 7 | `get_result("CJ663Q")` as before | pass |
| Render deploy stays up | Log says HTTP, no restart loop | Service up at https://haircut-advisor.onrender.com (checked by Claude, 2026-11-24) | pass |
| Live `GET /` | Plain "running" page | 200, "haircut-advisor MCP server is running. …" | pass |
| Live `/mcp`: tools listed and one call per tool (Claude, FastMCP client) | All 3 work | heart/short cuts; "No result with that code."; 11 results | pass |
| QR #2 | Encodes the connector URL | `tools/qr-connector.png` → `https://haircut-advisor.onrender.com/mcp` | pass |
| Test 12: all 3 tools from claude.ai | Work | not run | open |

## Tuning data (for Phase 4)

Readings from the tester's phone, 2026-11-14, all with "Photo checks passed". 4 different photos of the same person (confirmed by the tester).

| Photo | Length | Forehead | Jaw | Jaw angle | Head turn / up-down / lean |
|---|---|---|---|---|---|
| A | 1.231 | 0.889 | 0.798 | 139.7° | not recorded |
| B | 1.256 | 0.885 | 0.802 | 142.9° | -3° / 2° / 1° |
| C | 1.236 | 0.887 | 0.785 | 144.3° | -1° / 7° / 0° |
| D | 1.247 | 0.885 | 0.803 | 141.3° | -2° / 2° / 0° |
| Range | 0.025 | 0.004 | 0.018 | 4.6° | |

Photo-to-photo noise for one person is about ±0.013 for length, ±0.002 for forehead, ±0.009 for jaw and ±2.3° for jaw angle. Cut-offs closer together than this cannot separate shapes reliably.

### Readings from 7 other people (2026-11-14)

Rows 4–10 of `results`, pasted by the tester from the dashboard. Each row is a different person. No shape labels are known for them.

| id | Length | Forehead | Jaw | Jaw angle | Version 1 result |
|---|---|---|---|---|---|
| 4 | 1.192 | 0.887 | 0.785 | 138.9° | round 0.398, oval 0.291 |
| 5 | 1.161 | 0.850 | 0.801 | 138.5° | round 0.518, square 0.157 |
| 6 | 1.204 | 0.880 | 0.801 | 138.1° | round 0.366, oval 0.283 |
| 7 | 1.149 | 0.892 | 0.799 | 138.8° | round 0.562, square 0.253 |
| 8 | 1.164 | 0.877 | 0.750 | 151.8° | round 0.511, oval 0.205 |
| 9 | 1.145 | 0.786 | 0.837 | 128.4° | triangle 0.810, round 0.088 |
| 10 | 1.218 | 0.848 | 0.822 | 136.5° | triangle 0.281, round 0.253 |

All 8 faces (these 7 plus the tester's average): length 1.145–1.242 (mean 1.184), forehead 0.786–0.892 (median 0.879), jaw 0.750–0.837 (mean 0.799), jaw angle 128.4–151.8° (mean 139.1°).

Finding: the version 1 length centres are too high. No face reaches the oval centre (1.30), and the oblong centre (1.42) is far above every face, so 5 of 8 faces come out as round. Cut-offs are not changed yet: without a known shape for at least some faces, moving the centres is a guess.

## Cut-off changes (Phase 4)

### Version 1 — first guess (2026-11-14)

Scoring: each shape has a centre (4 typical measurements). A face is scored by its weighted distance to each centre, and scores are scaled to add up to 1. Values are in `docs/app.js` (`SHAPES`, `SPREAD`, `WEIGHT`).

| Shape | Length | Forehead | Jaw | Jaw angle |
|---|---|---|---|---|
| oval | 1.30 | 0.88 | 0.78 | 142° |
| round | 1.15 | 0.88 | 0.82 | 147° |
| square | 1.18 | 0.90 | 0.87 | 134° |
| oblong | 1.42 | 0.88 | 0.80 | 140° |
| heart | 1.28 | 0.93 | 0.72 | 146° |
| diamond | 1.30 | 0.82 | 0.73 | 144° |
| triangle | 1.25 | 0.82 | 0.88 | 138° |
| Spread | 0.08 | 0.04 | 0.05 | 8° |
| Weight | 1 | 1 | 1 | 0.5 |

Source: common stylist ratios, lowered for length because the mesh stops at the upper forehead. **Only checked against one face.** The centres for the other 6 shapes are untested.

Check with the 4 tuning readings (run in the browser pane):

| Photo | 1st | 2nd |
|---|---|---|
| A | oval 0.388 | round 0.271 |
| B | oval 0.453 | round 0.212 |
| C | oval 0.427 | round 0.258 |
| D | oval 0.424 | round 0.235 |

The top 2 shapes are the same for all 4 photos of the same person. Each centre also classifies as its own shape.

Photo-quality limits are unchanged from Phase 3 (turn 15°, up/down 15°, lean 10°, mouth open 0.25, smile 0.4).

### Version 2 — length and jaw-angle centres lowered (2026-11-14)

Reason: with version 1, no face reached the oval length centre and 5 of 8 faces came out as round (see "Readings from 7 other people"). Approved by the tester.

**Assumption: the average face in the 8-person sample is oval.** No real shape is known for any of the 8 people, so this is a fit to the data, not a check against known shapes.

| Shape | Length (was) | Forehead | Jaw | Jaw angle (was) |
|---|---|---|---|---|
| oval | 1.19 (1.30) | 0.88 | 0.78 | 139° (142°) |
| round | 1.13 (1.15) | 0.88 | 0.82 | 144° (147°) |
| square | 1.14 (1.18) | 0.90 | 0.87 | 131° (134°) |
| oblong | 1.27 (1.42) | 0.88 | 0.80 | 138° (140°) |
| heart | 1.19 (1.28) | 0.93 | 0.72 | 143° (146°) |
| diamond | 1.20 (1.30) | 0.82 | 0.73 | 141° (144°) |
| triangle | 1.17 (1.25) | 0.82 | 0.88 | 135° (138°) |
| Spread | 0.05 (0.08) | 0.04 | 0.05 | 8° |

Forehead and jaw centres, the weights and the photo-quality limits are unchanged.

Check: the scoring code from `docs/app.js`, run with Node on every logged reading.

| Face | Version 1 | Version 2 |
|---|---|---|
| Tester, photo A | oval 0.388, round 0.271 | oblong 0.409, oval 0.375 |
| Tester, photo B | oval 0.453, round 0.212 | oblong 0.621, oval 0.254 |
| Tester, photo C | oval 0.427, round 0.258 | oblong 0.404, oval 0.363 |
| Tester, photo D | oval 0.424, round 0.235 | oblong 0.553, oval 0.296 |
| 4 | round 0.398, oval 0.291 | oval 0.472, round 0.156 |
| 5 | round 0.518, square 0.157 | oval 0.338, round 0.298 |
| 6 | round 0.366, oval 0.283 | oval 0.442, oblong 0.211 |
| 7 | round 0.562, square 0.253 | round 0.384, oval 0.333 |
| 8 | round 0.511, oval 0.205 | oval 0.366, round 0.223 |
| 9 | triangle 0.810, round 0.088 | triangle 0.833, round 0.051 |
| 10 | triangle 0.281, round 0.253 | oval 0.307, oblong 0.274 |

- Mix across the 8 people: 5 oval, 1 round, 1 triangle, 1 oblong.
- Test 1, shape part: the tester's 4 photos still give the same top 2 in the same order (oblong, then oval). Photos A and C are close calls (about 0.04 apart).
- Each centre still classifies as its own shape.
- Not re-run on a phone after the change. Rows already in `results` keep their version 1 shapes.

