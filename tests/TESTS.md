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
| 7 | Scan QR on iPhone and Android | Page opens, camera works on both | 5 | not run |
| 8 | Camera permission denied | Clear message; gallery still works | 4 | pass (2026-11-14) |
| 9 | Use the anon key to read `results` | Blocked | 2 | pass (2026-11-14) |
| 10 | `get_result("ZZZZZZ")` | "No result with that code" | 7 | not run |
| 11 | `get_result(<real code from phone>)` | Same shape the phone showed | 7 | not run |
| 12 | Call the Render MCP URL from claude.ai | All 3 tools work | 8 | not run |

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
