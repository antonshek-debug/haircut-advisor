// haircut-advisor, page v2 (Phase 4):
// photo -> landmarks -> 4 measurements -> top 2 shapes -> choices -> haircuts
// -> save measurements + shapes + choices + code. The photo is never uploaded.

// Pinned versions (PLAN.md section 7). Do not use @latest.
import {
  FaceLandmarker,
  FilesetResolver,
} from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.2.3/vision_bundle.mjs";
import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.119.0/+esm";
import { SUPABASE_URL, SUPABASE_ANON_KEY } from "./config.js";
import { loadSpecs, renderCut } from "./cuts.js";

const MEDIAPIPE_WASM = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.2.3/wasm";
const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task";

// ---------------------------------------------------------------------------
// Landmark indexes (MediaPipe face mesh, 478 points).
// "Right" and "left" are the person's own right and left.
//
//   TOP          10   top centre of the mesh (upper forehead, NOT the hairline)
//   CHIN         152  bottom of the chin
//   CHEEK        234 / 454   widest points of the face outline, at cheekbone level
//   FOREHEAD     54  / 284   upper corners of the forehead outline
//   JAW          172 / 397   jaw corners on the face outline
//   JAW_UPPER    132 / 361   outline point above each jaw corner (towards the ear)
//
// Measurements:
//   1. length ratio   = dist(10, 152)  / dist(234, 454)
//   2. forehead ratio = dist(54, 284)  / dist(234, 454)
//   3. jaw ratio      = dist(172, 397) / dist(234, 454)
//   4. jaw angle      = angle at the jaw corner between the point above it and
//                       the chin: angle(132, 172, 152) and angle(361, 397, 152),
//                       averaged. Smaller = more angular jaw.
//
// Limit: the mesh stops at the upper forehead, so face length is shorter than
// the true hairline-to-chin length. The shape centres below allow for this.
// Distances use x and y in pixels only (the photo must be front-facing).
// ---------------------------------------------------------------------------
const LM = {
  top: 10,
  chin: 152,
  cheekR: 234,
  cheekL: 454,
  foreheadR: 54,
  foreheadL: 284,
  jawR: 172,
  jawL: 397,
  jawUpperR: 132,
  jawUpperL: 361,
};

// ---------------------------------------------------------------------------
// Shape scoring. Record every change in tests/TESTS.md.
//
// Each shape has a centre: the 4 measurements of a typical face of that shape.
// A face is scored by how close it is to each centre. SPREAD says how far a
// value can be from a centre and still count as close; it is several times
// the photo-to-photo noise measured in Phase 3 (TESTS.md, "Tuning data").
// Jaw angle is the noisiest value, so it has half the weight of the ratios.
// Scores are scaled to add up to 1 across the 7 shapes.
// ---------------------------------------------------------------------------
export const SHAPES = {
  //          length  forehead  jaw    jaw angle
  // Version 2 (2026-11-14): length and jaw-angle centres lowered to fit
  // readings from 8 people. Assumes the average face in that sample is oval.
  oval:     { length: 1.19, forehead: 0.88, jaw: 0.78, angle: 139 },
  round:    { length: 1.13, forehead: 0.88, jaw: 0.82, angle: 144 },
  square:   { length: 1.14, forehead: 0.90, jaw: 0.87, angle: 131 },
  oblong:   { length: 1.27, forehead: 0.88, jaw: 0.80, angle: 138 },
  heart:    { length: 1.19, forehead: 0.93, jaw: 0.72, angle: 143 },
  diamond:  { length: 1.20, forehead: 0.82, jaw: 0.73, angle: 141 },
  triangle: { length: 1.17, forehead: 0.82, jaw: 0.88, angle: 135 },
};
const SPREAD = { length: 0.05, forehead: 0.04, jaw: 0.05, angle: 8 };
const WEIGHT = { length: 1, forehead: 1, jaw: 1, angle: 0.5 };

// Photo-quality limits (first guess).
const MAX_YAW_DEG = 15; // head turned left or right
const MAX_PITCH_DEG = 15; // head tilted up or down
const MAX_ROLL_DEG = 10; // head leaning to one side
const MAX_JAW_OPEN = 0.25; // blendshape score, 0 to 1
const MAX_SMILE = 0.4; // blendshape score, 0 to 1

// Every photo is scaled to this size first, so the same photo always gives
// the same numbers.
const MAX_SIDE = 1024;

// Code alphabet: no 0, O, 1 or I. 32 characters, so one random byte maps evenly.
const CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";

const CUTS_MIN = 3;
const CUTS_MAX = 5;

// ----------------------------- pure functions ------------------------------

// Returns all 7 shapes with scores (0..1, adding up to 1), best first.
export function classify(m) {
  const raw = Object.entries(SHAPES).map(([shape, c]) => {
    let d2 = 0;
    for (const key of ["length", "forehead", "jaw", "angle"]) {
      d2 += WEIGHT[key] * ((m[key] - c[key]) / SPREAD[key]) ** 2;
    }
    return { shape, raw: Math.exp(-d2 / 2) };
  });
  const total = raw.reduce((sum, r) => sum + r.raw, 0) || 1;
  return raw
    .map((r) => ({ shape: r.shape, score: r.raw / total }))
    .sort((a, b) => b.score - a.score || a.shape.localeCompare(b.shape));
}

// Picks 3-5 cuts for the choices. Exact matches first. If there are fewer
// than 3 exact matches, the closest other cuts fill the list and are marked.
export function pickHaircuts(rows, choices) {
  const scored = rows.map((row) => {
    const matches =
      (choices.length === "any" || row.length === choices.length ? 1 : 0) +
      (row.textures.includes(choices.texture) ? 1 : 0) +
      (row.styles.includes(choices.style) ? 1 : 0);
    return { ...row, exact: matches === 3, matches };
  });
  scored.sort((a, b) => b.matches - a.matches || a.id - b.id);
  const exact = scored.filter((r) => r.exact);
  if (exact.length >= CUTS_MIN) return exact.slice(0, CUTS_MAX);
  return scored.slice(0, CUTS_MIN);
}

export function makeCode() {
  const bytes = crypto.getRandomValues(new Uint8Array(6));
  return Array.from(bytes, (b) => CODE_CHARS[b & 31]).join("");
}

const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);

// Angle at point b, in degrees, between the lines b->a and b->c.
function angleAt(a, b, c) {
  const v1 = { x: a.x - b.x, y: a.y - b.y };
  const v2 = { x: c.x - b.x, y: c.y - b.y };
  const cos = (v1.x * v2.x + v1.y * v2.y) / (Math.hypot(v1.x, v1.y) * Math.hypot(v2.x, v2.y));
  return (Math.acos(Math.min(1, Math.max(-1, cos))) * 180) / Math.PI;
}

function measure(p) {
  const cheek = dist(p[LM.cheekR], p[LM.cheekL]);
  const angleR = angleAt(p[LM.jawUpperR], p[LM.jawR], p[LM.chin]);
  const angleL = angleAt(p[LM.jawUpperL], p[LM.jawL], p[LM.chin]);
  // Rounded here, so the numbers shown, scored and saved are the same.
  const round = (value, places) => Number(value.toFixed(places));
  return {
    length: round(dist(p[LM.top], p[LM.chin]) / cheek, 3),
    forehead: round(dist(p[LM.foreheadR], p[LM.foreheadL]) / cheek, 3),
    jaw: round(dist(p[LM.jawR], p[LM.jawL]) / cheek, 3),
    angle: round((angleR + angleL) / 2, 1),
  };
}

// Head pose in degrees from the 4x4 face transformation matrix (column-major).
function headPose(matrix) {
  const m = matrix.data;
  const deg = (rad) => (rad * 180) / Math.PI;
  return {
    yaw: deg(Math.atan2(-m[2], Math.hypot(m[0], m[1]))),
    pitch: deg(Math.atan2(m[6], m[10])),
    roll: deg(Math.atan2(m[1], m[0])),
  };
}

function blendshape(categories, name) {
  const found = categories.find((c) => c.categoryName === name);
  return found ? found.score : 0;
}

const capital = (word) => word[0].toUpperCase() + word.slice(1);
const percent = (score) => `${Math.round(score * 100)}%`;

// --------------------------------- page ------------------------------------

const el = (id) => document.getElementById(id);
const statusEl = el("status");
const canvas = el("preview");
const ctx = canvas.getContext("2d");
const warningsEl = el("warnings");
const choicesEl = el("choices");
const formEl = el("choices-form");
const showCutsBtn = el("show-cuts");
const resultEl = el("result");
const measurementsEl = el("measurements");
const saveStatusEl = el("save-status");
const retrySaveBtn = el("retry-save");
const inputs = [el("camera"), el("gallery")];

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
});

// Clean copy of the photo (no measurement lines), used to draw haircuts on.
// It stays in the page's memory and is never uploaded.
const photo = document.createElement("canvas");

// Hair-shape settings per cut. If they do not load, cuts show the neutral
// drawings from docs/cuts/ instead.
let cutSpecs = null;
loadSpecs()
  .then((specs) => (cutSpecs = specs))
  .catch((err) => console.error(err));

let landmarker = null;
let current = null; // { m, top2, points } for the photo on screen
let pendingRow = null; // row that still has to be saved

async function loadModel() {
  try {
    const fileset = await FilesetResolver.forVisionTasks(MEDIAPIPE_WASM);
    landmarker = await FaceLandmarker.createFromOptions(fileset, {
      // CPU gives the same result on every run and every phone.
      baseOptions: { modelAssetPath: MODEL_URL, delegate: "CPU" },
      runningMode: "IMAGE",
      numFaces: 2, // 2 is enough to detect "more than one face"
      outputFaceBlendshapes: true,
      outputFacialTransformationMatrixes: true,
    });
    statusEl.textContent = "Ready. Take a photo or choose one.";
    inputs.forEach((input) => (input.disabled = false));
  } catch (err) {
    console.error(err);
    statusEl.textContent =
      "The face model did not load. Check your internet connection and reload the page.";
  }
}

// Draw the photo on the canvas, scaled down. The photo never leaves the phone.
async function drawPhoto(file) {
  const url = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.src = url;
    await img.decode();
    const scale = Math.min(1, MAX_SIDE / Math.max(img.naturalWidth, img.naturalHeight));
    canvas.width = Math.round(img.naturalWidth * scale);
    canvas.height = Math.round(img.naturalHeight * scale);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    photo.width = canvas.width;
    photo.height = canvas.height;
    photo.getContext("2d", { willReadFrequently: true }).drawImage(canvas, 0, 0);
    canvas.hidden = false;
  } finally {
    URL.revokeObjectURL(url);
  }
}

// Landmarks are 0..1 of the image width and height; convert to pixels.
function toPixels(landmarks) {
  return landmarks.map((p) => ({ x: p.x * canvas.width, y: p.y * canvas.height }));
}

function drawLines(p) {
  ctx.lineWidth = Math.max(2, canvas.width / 250);
  ctx.strokeStyle = "#00e0ff";
  const line = (a, b) => {
    ctx.beginPath();
    ctx.moveTo(p[a].x, p[a].y);
    ctx.lineTo(p[b].x, p[b].y);
    ctx.stroke();
  };
  line(LM.top, LM.chin);
  line(LM.cheekR, LM.cheekL);
  line(LM.foreheadR, LM.foreheadL);
  line(LM.jawR, LM.jawL);
  line(LM.jawUpperR, LM.jawR);
  line(LM.jawR, LM.chin);
  line(LM.jawUpperL, LM.jawL);
  line(LM.jawL, LM.chin);
}

function showWarnings(list) {
  warningsEl.replaceChildren(
    ...list.map((text) => {
      const li = document.createElement("li");
      li.textContent = text;
      return li;
    })
  );
  warningsEl.hidden = list.length === 0;
}

function reset() {
  current = null;
  pendingRow = null;
  showWarnings([]);
  choicesEl.hidden = true;
  resultEl.hidden = true;
  measurementsEl.hidden = true;
  measurementsEl.open = false;
  retrySaveBtn.hidden = true;
  showCutsBtn.disabled = false;
}

async function analyse(file) {
  reset();
  statusEl.textContent = "Measuring…";

  try {
    await drawPhoto(file);
  } catch (err) {
    console.error(err);
    canvas.hidden = true;
    statusEl.textContent = "This file could not be opened as a photo. Try another one.";
    return;
  }

  let found;
  try {
    found = landmarker.detect(canvas);
  } catch (err) {
    console.error(err);
    statusEl.textContent = "The photo could not be measured. Try another one.";
    return;
  }

  const faces = found.faceLandmarks ?? [];

  if (faces.length === 0) {
    statusEl.textContent = "No face found.";
    showWarnings(["No face found. Use a clear photo of your face, from the front, in good light."]);
    return;
  }

  if (faces.length > 1) {
    statusEl.textContent = "More than one face found.";
    showWarnings(["More than one face found. Use a photo with only you in it."]);
    return;
  }

  const points = toPixels(faces[0]);
  const m = measure(points);
  const warnings = [];
  const details = [];

  const matrix = found.facialTransformationMatrixes?.[0];
  if (matrix) {
    const pose = headPose(matrix);
    details.push(
      `Head: turn ${pose.yaw.toFixed(0)}°, up/down ${pose.pitch.toFixed(0)}°, lean ${pose.roll.toFixed(0)}°`
    );
    if (
      Math.abs(pose.yaw) > MAX_YAW_DEG ||
      Math.abs(pose.pitch) > MAX_PITCH_DEG ||
      Math.abs(pose.roll) > MAX_ROLL_DEG
    ) {
      warnings.push("Face the camera. Your head is turned or tilted.");
    }
  }

  const shapes = found.faceBlendshapes?.[0]?.categories;
  if (shapes) {
    const jawOpen = blendshape(shapes, "jawOpen");
    const smile = (blendshape(shapes, "mouthSmileLeft") + blendshape(shapes, "mouthSmileRight")) / 2;
    details.push(`Mouth open ${jawOpen.toFixed(2)}, smile ${smile.toFixed(2)}`);
    if (jawOpen > MAX_JAW_OPEN || smile > MAX_SMILE) {
      warnings.push("Close your mouth and keep a neutral face. A smile or an open mouth changes the jaw.");
    }
  }

  drawLines(points);

  el("m-length").textContent = m.length.toFixed(3);
  el("m-forehead").textContent = m.forehead.toFixed(3);
  el("m-jaw").textContent = m.jaw.toFixed(3);
  el("m-angle").textContent = `${m.angle.toFixed(1)}°`;
  el("details").textContent = details.join(" · ");
  measurementsEl.hidden = false;
  showWarnings(warnings);

  if (warnings.length > 0) {
    // No shape and no save for a photo that failed a check.
    el("reliability").textContent = "Not reliable. Fix the warning above and take the photo again.";
    measurementsEl.open = true;
    statusEl.textContent = "Photo needs to be retaken.";
    return;
  }

  el("reliability").textContent = "Photo checks passed.";
  current = { m, top2: classify(m).slice(0, 2), points };
  choicesEl.hidden = false;
  statusEl.textContent = "Photo measured. Now pick your choices below.";
}

// File name part: lower case, hyphens. Same rule as slug() in tools/make_cuts.py.
export const slug = (text) => text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

// Drawing for a cut: docs/cuts/<face shape>-<cut name>.svg. The database
// holds no file names. If the file is missing, the cut shows without a picture.
function cutDrawing(shape, cut) {
  const img = document.createElement("img");
  img.className = "cut-drawing";
  img.alt = `Drawing of the cut: ${cut.name}`;
  img.width = 200;
  img.height = 260;
  img.addEventListener("error", () => img.remove());
  img.src = `cuts/${slug(shape)}-${slug(cut.name)}.svg`;
  return img;
}

// The cut drawn over the user's own photo, or null if that is not possible.
function cutOnPhoto(cut, texture) {
  const spec = cutSpecs?.[cut.name];
  if (!spec || !current?.points || !photo.width) return null;
  try {
    const picture = renderCut(photo, current.points, spec, texture);
    picture.className = "cut-photo";
    picture.setAttribute("role", "img");
    picture.setAttribute("aria-label", `Sketch of the cut on your photo: ${cut.name}`);
    return picture;
  } catch (err) {
    console.error(err);
    return null;
  }
}

export function showCuts(cuts, shape, texture) {
  let onPhoto = 0;
  el("cuts").replaceChildren(
    ...cuts.map((cut) => {
      const li = document.createElement("li");
      const picture = cutOnPhoto(cut, texture);
      if (picture) onPhoto++;
      li.append(picture ?? cutDrawing(shape, cut));
      const name = document.createElement("span");
      name.className = "cut-name";
      name.textContent = cut.name;
      const meta = document.createElement("span");
      meta.className = "cut-meta";
      meta.textContent = ` · ${cut.length}${cut.exact ? "" : " · close match, not exact"}`;
      const reason = document.createElement("span");
      reason.className = "cut-reason";
      reason.textContent = cut.reason;
      li.append(name, meta, reason);
      return li;
    })
  );
  el("cuts-note").textContent =
    onPhoto === cuts.length
      ? "A sketch of the cut on your photo. Your photo stays on your phone."
      : "Drawings show the cut, not you.";
}

// Insert only. The page never reads the row back (it has no right to).
async function save() {
  retrySaveBtn.hidden = true;
  saveStatusEl.textContent = "Saving…";
  for (let attempt = 0; attempt < 3; attempt++) {
    const { error } = await supabase.from("results").insert(pendingRow);
    if (!error) {
      el("code").textContent = pendingRow.code;
      saveStatusEl.textContent = "Saved. Keep this code to ask Claude about your result.";
      pendingRow = null;
      return;
    }
    if (error.code === "23505") {
      pendingRow.code = makeCode(); // code already used: make a new one
      continue;
    }
    console.error(error);
    break;
  }
  el("code").textContent = "------";
  saveStatusEl.textContent = "Your result was not saved, so there is no code. Check your connection.";
  retrySaveBtn.hidden = false;
}

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!current) return;
  const form = new FormData(formEl);
  const choices = {
    length: form.get("length"),
    texture: form.get("texture"),
    style: form.get("style"),
  };
  const [first, second] = current.top2;

  showCutsBtn.disabled = true;
  statusEl.textContent = "Finding haircuts…";

  const { data, error } = await supabase
    .from("haircuts")
    .select("id, name, length, textures, styles, reason, avoid")
    .eq("face_shape", first.shape);

  if (error || !data || data.length === 0) {
    console.error(error);
    statusEl.textContent = "The haircut list did not load. Check your connection and try again.";
    showCutsBtn.disabled = false;
    return;
  }

  const cuts = pickHaircuts(data, choices);
  el("shape-1").textContent = `Closest shape: ${capital(first.shape)} (${percent(first.score)})`;
  el("shape-2").textContent = `Second closest: ${capital(second.shape)} (${percent(second.score)})`;
  showCuts(cuts, first.shape, choices.texture);
  el("avoid").textContent = cuts[0].avoid;
  el("code").textContent = "";
  choicesEl.hidden = true;
  resultEl.hidden = false;
  statusEl.textContent = "Done.";

  pendingRow = {
    code: makeCode(),
    length_ratio: current.m.length,
    forehead_ratio: current.m.forehead,
    jaw_ratio: current.m.jaw,
    jaw_angle: current.m.angle,
    shape_1: first.shape,
    score_1: Number(first.score.toFixed(3)),
    shape_2: second.shape,
    score_2: Number(second.score.toFixed(3)),
    length_pref: choices.length,
    texture: choices.texture,
    style: choices.style,
  };
  await save();
});

retrySaveBtn.addEventListener("click", () => {
  if (pendingRow) save();
});

inputs.forEach((input) => {
  input.addEventListener("change", async () => {
    const file = input.files?.[0];
    input.value = ""; // lets the same photo be chosen twice in a row
    if (!file || !landmarker) return;
    inputs.forEach((i) => (i.disabled = true));
    try {
      await analyse(file);
    } finally {
      inputs.forEach((i) => (i.disabled = false));
    }
  });
});

loadModel();
