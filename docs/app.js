// haircut-advisor, page v1 (Phase 3):
// photo -> face landmarks -> 4 measurements on screen. Nothing is saved or uploaded.

// Pinned versions (PLAN.md section 7). Do not use @latest.
const MEDIAPIPE = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.2.3";
const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task";

import {
  FaceLandmarker,
  FilesetResolver,
} from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.2.3/vision_bundle.mjs";

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
// the true hairline-to-chin length. Phase 4 tunes the cut-offs around this.
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

// Photo-quality limits (first guess; tune in Phase 4).
const MAX_YAW_DEG = 15; // head turned left or right
const MAX_PITCH_DEG = 15; // head tilted up or down
const MAX_ROLL_DEG = 10; // head leaning to one side
const MAX_JAW_OPEN = 0.25; // blendshape score, 0 to 1
const MAX_SMILE = 0.4; // blendshape score, 0 to 1

// Every photo is scaled to this size first, so the same photo always gives
// the same numbers.
const MAX_SIDE = 1024;

const el = (id) => document.getElementById(id);
const statusEl = el("status");
const canvas = el("preview");
const ctx = canvas.getContext("2d");
const warningsEl = el("warnings");
const resultEl = el("result");
const inputs = [el("camera"), el("gallery")];

let landmarker = null;

async function loadModel() {
  try {
    const fileset = await FilesetResolver.forVisionTasks(`${MEDIAPIPE}/wasm`);
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
    canvas.hidden = false;
  } finally {
    URL.revokeObjectURL(url);
  }
}

// Landmarks are 0..1 of the image width and height; convert to pixels.
function toPixels(landmarks) {
  return landmarks.map((p) => ({ x: p.x * canvas.width, y: p.y * canvas.height }));
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
  return {
    lengthRatio: dist(p[LM.top], p[LM.chin]) / cheek,
    foreheadRatio: dist(p[LM.foreheadR], p[LM.foreheadL]) / cheek,
    jawRatio: dist(p[LM.jawR], p[LM.jawL]) / cheek,
    jawAngle: (angleR + angleL) / 2,
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

function clearResult() {
  showWarnings([]);
  resultEl.hidden = true;
}

async function analyse(file) {
  clearResult();
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

  el("m-length").textContent = m.lengthRatio.toFixed(3);
  el("m-forehead").textContent = m.foreheadRatio.toFixed(3);
  el("m-jaw").textContent = m.jawRatio.toFixed(3);
  el("m-angle").textContent = `${m.jawAngle.toFixed(1)}°`;
  el("details").textContent = details.join(" · ");
  el("reliability").textContent =
    warnings.length > 0
      ? "Not reliable. Fix the warning above and take the photo again."
      : "Photo checks passed.";
  showWarnings(warnings);
  resultEl.hidden = false;
  statusEl.textContent = warnings.length > 0 ? "Photo needs to be retaken." : "Done.";
}

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
