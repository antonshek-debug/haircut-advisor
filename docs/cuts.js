// haircut-advisor (Phase 4c): draws a haircut shape over the user's own photo.
// Everything happens on a canvas in the browser. Nothing is uploaded.
//
// The hair shape is built the same way as in tools/make_cuts.py, from the same
// settings (cut-specs.json). The difference: the face comes from the user's
// landmarks instead of a fixed outline.
//
// Settings per cut:
//   tv      height of the hair above the head
//   sv      width of the hair beyond the face at the sides
//   fringe  none | full | soft | side | curtain
//   drop    how far down the fringe comes (fraction of head length)
//   hl      hairline height for fringe "none"
//   end     where the hair ends: null = at the ear (short cut),
//           a number = units below the chin, "bottom" = past the shoulders
//   ends    blunt | layered
//   frame   how much the hair covers the edge of the face
//   flare   extra width (+) or taper (-) at the ends
//
// Units: all sizes are in "face units", where half the cheekbone width is 48.

const UNIT = 48;

// Face outline landmarks (MediaPipe face mesh), from the top centre (10) down
// each side to the chin (152).
const OVAL_A = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152];
const OVAL_B = [10, 109, 67, 103, 54, 21, 162, 127, 234, 93, 132, 58, 172, 136, 150, 149, 176, 148, 152];
const CHEEK_R = 234;
const CHEEK_L = 454;
const TOP = 10;
const CHIN = 152;

// The mesh stops at the upper forehead. The top of the head is estimated at
// this fraction of the mesh face length above landmark 10.
const HEAD_ABOVE_MESH = 0.3;

// Outline texture: wave height and wave length in face units.
const TEXTURE = {
  straight: null,
  wavy: { amp: 2.6, lam: 26, bumps: false },
  curly: { amp: 4.2, lam: 11, bumps: true },
  coily: { amp: 3.0, lam: 7, bumps: true },
};

const OUT_WIDTH = 330; // canvas pixels
const VIEW_WIDTH = 220; // face units shown across the picture
const FALLBACK_COLOUR = [107, 111, 118];

export async function loadSpecs() {
  const response = await fetch("cut-specs.json");
  if (!response.ok) throw new Error(`cut-specs.json: HTTP ${response.status}`);
  return response.json();
}

const smoothstep = (t) => {
  const c = Math.max(0, Math.min(1, t));
  return c * c * (3 - 2 * c);
};

const mirror = (points) => points.map(([x, y]) => [-x, y]);

// Catmull-Rom spline through the points, as a dense list of points.
function spline(points, steps = 12) {
  const n = points.length;
  const out = [];
  for (let i = 0; i < n - 1; i++) {
    const p0 = points[Math.max(i - 1, 0)];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[Math.min(i + 2, n - 1)];
    for (let s = 0; s < steps; s++) {
      const t = s / steps;
      const t2 = t * t;
      const t3 = t2 * t;
      out.push(
        [0, 1].map(
          (k) =>
            0.5 *
            (2 * p1[k] +
              (-p0[k] + p2[k]) * t +
              (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2 +
              (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3)
        )
      );
    }
  }
  out.push(points[n - 1]);
  return out;
}

// Points at even spacing along the line, with weights carried along.
function resample(points, weights, step = 1.5) {
  const outP = [points[0]];
  const outW = [weights[0]];
  let carry = 0;
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i];
    const b = points[i + 1];
    const seg = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (seg === 0) continue;
    let d = step - carry;
    while (d <= seg) {
      const t = d / seg;
      outP.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]);
      outW.push(weights[i] + (weights[i + 1] - weights[i]) * t);
      d += step;
    }
    carry = seg - (d - step);
  }
  outP.push(points[points.length - 1]);
  outW.push(weights[weights.length - 1]);
  return [outP, outW];
}

// Push the line sideways in a wave (wavy) or in bumps (curly, coily).
function displace(points, weights, tex) {
  if (!tex) return points;
  const [pts, ws] = resample(points, weights);
  const out = [];
  let along = 0;
  for (let i = 0; i < pts.length; i++) {
    const a = pts[Math.max(i - 1, 0)];
    const b = pts[Math.min(i + 1, pts.length - 1)];
    const tx = b[0] - a[0];
    const ty = b[1] - a[1];
    const norm = Math.hypot(tx, ty) || 1;
    const nx = ty / norm; // points away from the head
    const ny = -tx / norm;
    if (i) along += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    const wave = tex.bumps
      ? Math.abs(Math.sin((Math.PI * along) / tex.lam))
      : Math.sin((2 * Math.PI * along) / tex.lam);
    const off = tex.amp * wave * ws[i];
    out.push([pts[i][0] + nx * off, pts[i][1] + ny * off]);
  }
  return out;
}

// Face model in face units. x = 0 is the middle of the face, y grows downwards.
function faceModel(points) {
  const r = points[CHEEK_R];
  const l = points[CHEEK_L];
  const cheekPx = Math.hypot(l.x - r.x, l.y - r.y);
  const k = cheekPx / 2 / UNIT; // image pixels per face unit
  const ux = { x: (l.x - r.x) / cheekPx, y: (l.y - r.y) / cheekPx }; // across the face
  const uy = { x: -ux.y, y: ux.x }; // down the face
  const origin = { x: (r.x + l.x) / 2, y: (r.y + l.y) / 2 };

  const raw = (p) => [
    ((p.x - origin.x) * ux.x + (p.y - origin.y) * ux.y) / k,
    ((p.x - origin.x) * uy.x + (p.y - origin.y) * uy.y) / k,
  ];
  const x0 = (raw(points[TOP])[0] + raw(points[CHIN])[0]) / 2; // midline
  const local = (p) => {
    const [x, y] = raw(p);
    return [x - x0, y];
  };

  const meshTop = local(points[TOP])[1];
  const chin = local(points[CHIN])[1];
  const meshLen = chin - meshTop;
  const top = meshTop - HEAD_ABOVE_MESH * meshLen; // estimated top of the head
  const len = chin - top;
  const y = (fraction) => top + fraction * len;

  const sides = [OVAL_A, OVAL_B].map((ids) => ids.map((i) => local(points[i])).map(([x, yy]) => [Math.abs(x), yy]));
  const sideWidth = (side, py) => {
    for (let i = 0; i < side.length - 1; i++) {
      const [xa, ya] = side[i];
      const [xb, yb] = side[i + 1];
      if (yb > ya && py >= ya && py <= yb) return xa + ((xb - xa) * (py - ya)) / (yb - ya);
    }
    return 0;
  };
  const meshHw = (py) => (sideWidth(sides[0], py) + sideWidth(sides[1], py)) / 2;

  // Above the brow the mesh outline curves in over the forehead, so the head
  // is drawn as a dome from the brow level up to the estimated top.
  const yBrow = meshTop + 0.2 * meshLen;
  const domeHalf = meshHw(yBrow);
  const hw = (py) => {
    if (py < top || py > chin) return 0;
    if (py < yBrow) {
      const u = (yBrow - py) / (yBrow - top);
      return domeHalf * Math.sqrt(Math.max(0, 1 - u * u));
    }
    return meshHw(py);
  };

  // Right half of the head outline, from the top centre down to the chin.
  const right = [];
  for (let i = 0; i <= 16; i++) {
    const a = (i / 16) * (Math.PI / 2);
    right.push([domeHalf * Math.sin(a), yBrow - (yBrow - top) * Math.cos(a)]);
  }
  for (let py = yBrow + 2; py <= chin; py += 2) right.push([meshHw(py), py]);

  return { k, ux, uy, origin, x0, top, chin, len, meshTop, meshLen, y, hw, right };
}

// Lower edge of the hair on the forehead, from the right temple to the left.
function hairline(face, spec, xtAt) {
  const { y } = face;
  const kind = spec.fringe;

  if (kind === "none") {
    const hl = spec.hl;
    const yt = y(hl + 0.15);
    const xt = xtAt(yt);
    const line = spline([
      [xt, yt],
      [0.6 * xt, y(hl + 0.035)],
      [0, y(hl)],
      [-0.6 * xt, y(hl + 0.035)],
      [-xt, yt],
    ]);
    return { line, ytR: yt, ytL: yt };
  }

  if (kind === "full" || kind === "soft") {
    const drop = spec.drop ?? (kind === "full" ? 0.37 : 0.29);
    const yt = y(drop + 0.03);
    const xt = xtAt(yt);
    let line = spline([
      [xt, yt],
      [0.82 * xt, y(drop)],
      [0, y(drop) + 1.5],
      [-0.82 * xt, y(drop)],
      [-xt, yt],
    ]);
    if (kind === "soft") {
      // broken, choppy edge
      [line] = resample(line, line.map(() => 1), 4.5);
      line = line.map(([px, py], i) => [px, py + (i > 0 && i < line.length - 1 ? (i % 2 ? 2.6 : -2.6) : 0)]);
    }
    return { line, ytR: yt, ytL: yt };
  }

  if (kind === "side") {
    const drop = spec.drop ?? 0.42;
    const partY = 0.14;
    const ytR = y(drop);
    const ytL = y(0.3);
    const xr = xtAt(ytR);
    const xl = xtAt(ytL);
    const part = [-0.45 * xl, y(partY)];
    const at = (f) => y(partY + (drop - partY) * f);
    const seg1 = spline([[xr, ytR], [0.55 * xr, at(0.74)], [0.05 * xr, at(0.4)], part]);
    const seg2 = spline([part, [-0.78 * xl, y(0.2)], [-xl, ytL]]);
    return { line: [...seg1, ...seg2.slice(1)], ytR, ytL };
  }

  // curtain: centre part, hair falls to both temples
  const drop = spec.drop ?? 0.42;
  const yt = y(drop);
  const xt = xtAt(yt);
  const at = (f) => y(0.13 + (drop - 0.13) * f);
  const seg = spline([[xt, yt], [0.6 * xt, at(0.62)], [0.22 * xt, at(0.25)], [0, y(0.13)]]);
  return { line: [...seg, ...mirror(seg).reverse().slice(1)], ytR: yt, ytL: yt };
}

// The hair as one closed outline, plus the parting line if there is one.
function buildHair(face, spec, textureName) {
  const tex = TEXTURE[textureName] ?? null;
  const { y, hw } = face;
  const short = spec.end === null;
  const yT = y(0.27);
  const yC = y(0.5);
  const { tv, sv, frame } = spec;

  let sideEnd;
  if (short) sideEnd = sv < 5 ? y(0.47) : y(0.56);
  else if (spec.end === "bottom") sideEnd = face.chin + 0.6 * face.len;
  else sideEnd = face.chin + spec.end;

  // Where the outline texture applies: curls on a short cut sit on top,
  // waves show in the hanging part, curls on longer hair are everywhere.
  const texWeight = (py) => {
    if (!tex) return 0;
    if (short) return tex.bumps ? 1 - smoothstep((py - yT) / (0.1 * face.len)) : 0;
    if (tex.bumps) return 1;
    return smoothstep((py - yT) / (yC - yT));
  };

  // Outer edge of the hair, right side, from the top centre down.
  const wc = hw(yC) + sv;
  let lowerMax = 0;
  for (let py = yC; py < face.chin; py += 1) lowerMax = Math.max(lowerMax, hw(py));
  const wEnd = Math.max(wc, lowerMax + sv) + spec.flare;
  const outerBelow = (py) =>
    Math.max(hw(py) + sv, wc + ((wEnd - wc) * (py - yC)) / Math.max(sideEnd - yC, 1));

  let outer = [];
  const weights = [];
  const limit = Math.min(sideEnd, yC);
  for (const [px, py] of face.right) {
    if (py > limit) break;
    const s = smoothstep((py - face.top) / (yT - face.top));
    outer.push([px + sv * s, py - tv * (1 - s)]);
    weights.push(texWeight(py));
  }
  if (sideEnd > yC) {
    for (let py = yC + 2; py < sideEnd; py += 2) {
      outer.push([outerBelow(py), py]);
      weights.push(texWeight(py));
    }
    outer.push([outerBelow(sideEnd), sideEnd]);
  } else {
    outer.push([hw(sideEnd) + sv, sideEnd]);
  }
  weights.push(texWeight(sideEnd));
  outer = displace(outer, weights, tex);
  const outerEndX = outer[outer.length - 1][0];

  // Inner edge of the hair next to the face.
  const inner = (py) =>
    py <= yC ? hw(py) - frame : Math.max(hw(py) - frame, hw(yC) - frame - 0.12 * (py - yC));

  let { line, ytR, ytL } = hairline(face, spec, inner);
  if (tex && tex.bumps && (spec.fringe === "full" || spec.fringe === "none")) {
    line = displace(line, line.map(() => 0.6), { ...tex, amp: tex.amp * 0.8 });
  }

  const innerEnd = sideEnd - (spec.ends === "layered" && !short ? 10 : 0);
  const innerEdge = (yFrom) => {
    const pts = [];
    for (let py = innerEnd; py > yFrom; py -= 2) {
      pts.push([py > yC ? Math.min(inner(py), outerEndX - 3) : inner(py), py]);
    }
    return pts;
  };

  const hair = [
    ...mirror(outer).reverse(), // left side, bottom -> top centre
    ...outer.slice(1), // right side, top centre -> bottom
    ...innerEdge(ytR), // right inner edge, bottom -> temple
    ...line, // hairline, right temple -> left temple
    ...mirror(innerEdge(ytL)).reverse(), // left inner edge, temple -> bottom
  ];

  let part = null;
  if (spec.fringe === "side") {
    const px = -0.45 * inner(ytL);
    const tx = px * 0.8;
    const side = mirror(outer);
    const nearest = side.reduce((best, p) => (Math.abs(p[0] - tx) < Math.abs(best[0] - tx) ? p : best));
    part = [[px, y(0.14)], [tx, nearest[1] + 4]];
  } else if (spec.fringe === "curtain") {
    part = [[0, y(0.13)], [0, face.top - tv + 4]];
  }

  return { hair, part };
}

// Average colour of a small patch of the photo, just above the forehead.
function sampleHairColour(photo, face) {
  try {
    const xu = face.x0;
    const yu = face.meshTop - 0.14 * face.meshLen;
    const px = face.origin.x + face.k * (xu * face.ux.x + yu * face.uy.x);
    const py = face.origin.y + face.k * (xu * face.ux.y + yu * face.uy.y);
    const size = Math.max(4, Math.round(face.k * 6));
    const x = Math.round(px - size / 2);
    const yy = Math.round(py - size / 2);
    if (x < 0 || yy < 0 || x + size > photo.width || yy + size > photo.height) return FALLBACK_COLOUR;
    const data = photo.getContext("2d", { willReadFrequently: true }).getImageData(x, yy, size, size).data;
    const sum = [0, 0, 0];
    for (let i = 0; i < data.length; i += 4) {
      sum[0] += data[i];
      sum[1] += data[i + 1];
      sum[2] += data[i + 2];
    }
    return sum.map((v) => Math.round(v / (data.length / 4)));
  } catch (err) {
    console.error(err);
    return FALLBACK_COLOUR;
  }
}

function trace(ctx, points, close) {
  ctx.beginPath();
  points.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
  if (close) ctx.closePath();
}

// Returns a new canvas: the user's photo, cropped and straightened around the
// head, with the cut drawn on it.
//   photo   canvas with the clean photo
//   points  face landmarks in photo pixels ({x, y})
//   spec    settings for the cut, from cut-specs.json
//   texture straight | wavy | curly | coily (the user's own choice)
export function renderCut(photo, points, spec, texture) {
  const face = faceModel(points);
  const { hair, part } = buildHair(face, spec, texture);

  const scale = OUT_WIDTH / VIEW_WIDTH; // canvas pixels per face unit
  const viewX = -VIEW_WIDTH / 2;
  const viewY = face.top - 45;
  const viewH = face.len + 120;

  const canvas = document.createElement("canvas");
  canvas.width = OUT_WIDTH;
  canvas.height = Math.round(viewH * scale);
  const ctx = canvas.getContext("2d");

  // 1. The photo, rotated and scaled so the face is upright and centred.
  const { k, ux, uy, origin, x0 } = face;
  const f = scale / k;
  ctx.setTransform(
    f * ux.x,
    f * uy.x,
    f * ux.y,
    f * uy.y,
    scale * (-(origin.x * ux.x + origin.y * ux.y) / k - x0 - viewX),
    scale * (-(origin.x * uy.x + origin.y * uy.y) / k - viewY)
  );
  ctx.drawImage(photo, 0, 0);

  // 2. The hair, in face units.
  const [r, g, b] = sampleHairColour(photo, face);
  ctx.setTransform(scale, 0, 0, scale, -viewX * scale, -viewY * scale);
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.lineWidth = 2;
  ctx.strokeStyle = `rgb(${Math.round(r * 0.5)}, ${Math.round(g * 0.5)}, ${Math.round(b * 0.5)})`;
  ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.96)`;
  trace(ctx, hair, true);
  ctx.fill();
  ctx.stroke();
  if (part) {
    trace(ctx, part, false);
    ctx.stroke();
  }

  ctx.setTransform(1, 0, 0, 1, 0, 0);
  return canvas;
}
