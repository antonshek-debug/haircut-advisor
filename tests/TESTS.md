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
| 8 | Camera permission denied | Clear message; gallery still works | 4 | not run |
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

## Cut-off changes (Phase 4)

None yet.
