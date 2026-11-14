# Tests

Expected results come from PLAN.md section 11. Record the actual result after each phase.

## Test cases

| # | Test | Expected | Phase | Status |
|---|---|---|---|---|
| 1 | Same clear front photo, twice | Same shape and same measurements | 3 | pass (2026-11-14) |
| 2 | Photo with no face | "No face found", no crash | 3 | pass (2026-11-14) |
| 3 | Photo with 2 people | Warning, no confident result | 3 | pass (2026-11-14) |
| 4 | Head turned sideways | "Face the camera" warning | 3 | pass (2026-11-14) |
| 5 | `suggest_haircuts("heart", length="short")` | Only short cuts | 7 | not run |
| 6 | `suggest_haircuts("blob")` | List of valid shapes | 7 | not run |
| 7 | Scan QR on iPhone and Android | Page opens, camera works on both | 5 | pass (2026-11-14) |
| 8 | Camera permission denied | Clear message; gallery still works | 4 | pass (2026-11-14) |
| 9 | Use the anon key to read `results` | Blocked | 2 | pass (2026-11-14) |
| 10 | `get_result("ZZZZZZ")` | "No result with that code" | 7 | not run |
| 11 | `get_result(<real code from phone>)` | Same shape the phone showed | 7 | not run |
| 12 | Call the Render MCP URL from claude.ai | All 3 tools work | 8 | not run |
| 13 | Open a result on the phone | Every suggested cut shows its drawing; a cut with a missing file shows without a picture and without an error | 4b | PC part pass; phone not run |

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

