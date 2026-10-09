// Vlastní pomocné funkce generátoru (cloud): 2D polygony, zaoblení rohů, offset, extruze s otvory, loft polygonů.
// Nezávislé na jadro/ (jádro se neupravuje); používá jen Part/loftRings z jadro/mesh.js a triangulaci z vendor/three.min.js.
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Part, loftRings, tube } from './jadro/mesh.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
let THREE_ = null;
function three() {
  if (THREE_) return THREE_;
  const ctx = { console }; ctx.self = ctx; ctx.window = ctx; vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(HERE, 'vendor/three.min.js'), 'utf8'), ctx);
  THREE_ = ctx.THREE; return THREE_;
}

// ---------- 2D ----------
export const area2 = (P) => { let a = 0; for (let i = 0; i < P.length; i++) { const p = P[i], q = P[(i + 1) % P.length]; a += p[0] * q[1] - q[0] * p[1]; } return a / 2; };
export const ccw = (P) => area2(P) > 0 ? P.slice() : P.slice().reverse();
export const cw = (P) => area2(P) < 0 ? P.slice() : P.slice().reverse();
export const rectPoly = (x0, x1, y0, y1) => [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
export const circlePoly = (cx, cy, r, n = 24, a0 = 0) => Array.from({ length: n }, (_, i) => { const a = a0 + 2 * Math.PI * i / n; return [cx + r * Math.cos(a), cy + r * Math.sin(a)]; });
export const movePoly = (P, dx, dy) => P.map(p => [p[0] + dx, p[1] + dy]);
export const rotPoly = (P, deg, c = [0, 0]) => { const a = deg * Math.PI / 180, co = Math.cos(a), si = Math.sin(a); return P.map(p => { const x = p[0] - c[0], y = p[1] - c[1]; return [c[0] + x * co - y * si, c[1] + x * si + y * co]; }); };
export const mirrorPolyX = (P) => P.map(p => [-p[0], p[1]]).reverse();

// zaoblení rohů polygonu; r = číslo nebo pole po vrcholech (0 = ostrý roh); seg = počet úseků oblouku
export function roundPoly(P, r, seg = 6) {
  const n = P.length, out = [];
  for (let i = 0; i < n; i++) {
    const A = P[(i + n - 1) % n], B = P[i], C = P[(i + 1) % n];
    const ri = Array.isArray(r) ? r[i] : r;
    if (!ri || ri < 1e-6) { out.push([B[0], B[1]]); continue; }
    let ux = A[0] - B[0], uy = A[1] - B[1], vx = C[0] - B[0], vy = C[1] - B[1];
    const lu = Math.hypot(ux, uy), lv = Math.hypot(vx, vy); ux /= lu; uy /= lu; vx /= lv; vy /= lv;
    const dot = Math.max(-1, Math.min(1, ux * vx + uy * vy)); const phi = Math.acos(dot);
    if (phi < 1e-3 || Math.abs(Math.PI - phi) < 1e-3) { out.push([B[0], B[1]]); continue; }
    let t = ri / Math.tan(phi / 2); const tmax = Math.min(lu, lv) * 0.5; let rr = ri;
    if (t > tmax) { t = tmax; rr = t * Math.tan(phi / 2); }
    const S = [B[0] + ux * t, B[1] + uy * t], E = [B[0] + vx * t, B[1] + vy * t];
    const bx = ux + vx, by = uy + vy, lb = Math.hypot(bx, by); const dC = rr / Math.sin(phi / 2);
    const Cc = [B[0] + bx / lb * dC, B[1] + by / lb * dC];
    let a0 = Math.atan2(S[1] - Cc[1], S[0] - Cc[0]), a1 = Math.atan2(E[1] - Cc[1], E[0] - Cc[0]);
    let d = a1 - a0; while (d > Math.PI) d -= 2 * Math.PI; while (d < -Math.PI) d += 2 * Math.PI;
    for (let k = 0; k <= seg; k++) { const a = a0 + d * k / seg; out.push([Cc[0] + rr * Math.cos(a), Cc[1] + rr * Math.sin(a)]); }
  }
  return out;
}
// offset polygonu (miter): d>0 dovnitř pro CCW polygon, d<0 ven
export function offsetPoly(P, d) {
  const Q = ccw(P), n = Q.length, out = [];
  for (let i = 0; i < n; i++) {
    const A = Q[(i + n - 1) % n], B = Q[i], C = Q[(i + 1) % n];
    let e1x = B[0] - A[0], e1y = B[1] - A[1], e2x = C[0] - B[0], e2y = C[1] - B[1];
    const l1 = Math.hypot(e1x, e1y) || 1, l2 = Math.hypot(e2x, e2y) || 1; e1x /= l1; e1y /= l1; e2x /= l2; e2y /= l2;
    const n1 = [-e1y, e1x], n2 = [-e2y, e2x]; // levá normála = dovnitř pro CCW
    const k = 1 + n1[0] * n2[0] + n1[1] * n2[1];
    const s = d / Math.max(k, 0.2);
    out.push([B[0] + (n1[0] + n2[0]) * s, B[1] + (n1[1] + n2[1]) * s]);
  }
  return out;
}
export const pointInPoly = (p, P) => { let c = false; for (let i = 0, j = P.length - 1; i < P.length; j = i++) { const a = P[i], b = P[j]; if (((a[1] > p[1]) !== (b[1] > p[1])) && (p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0])) c = !c; } return c; };

// ---------- 3D ----------
// extruze polygonu s otvory mezi z0 a z1 (horní/dolní víčko volitelně)
export function extrude(mat, name, outer, holes = [], z0, z1, { top = true, bottom = true, crease } = {}) {
  const p = new Part(name, mat); if (crease !== undefined) p.crease = crease;
  const O = ccw(outer), H = holes.map(cw);
  const T = three();
  const all = [...O, ...H.flat()];
  const idxTop = [], idxBot = [];
  for (const q of O) { idxTop.push(p.addV(q[0], q[1], z1)); }
  for (const h of H) for (const q of h) idxTop.push(p.addV(q[0], q[1], z1));
  const nAll = all.length;
  for (let i = 0; i < nAll; i++) idxBot.push(p.addV(all[i][0], all[i][1], z0));
  const tris = T.ShapeUtils.triangulateShape(O.map(q => new T.Vector2(q[0], q[1])), H.map(h => h.map(q => new T.Vector2(q[0], q[1]))));
  for (const [a, b, c] of tris) {
    const A = all[a], B = all[b], C = all[c];
    const cr = (B[0] - A[0]) * (C[1] - A[1]) - (B[1] - A[1]) * (C[0] - A[0]);
    if (top) { if (cr > 0) p.addT(idxTop[a], idxTop[b], idxTop[c]); else p.addT(idxTop[a], idxTop[c], idxTop[b]); }
    if (bottom) { if (cr > 0) p.addT(idxBot[a], idxBot[c], idxBot[b]); else p.addT(idxBot[a], idxBot[b], idxBot[c]); }
  }
  // stěny
  const wall = (loop, off) => {
    const m = loop.length;
    for (let i = 0; i < m; i++) {
      const j = (i + 1) % m;
      const a = p.addV(loop[i][0], loop[i][1], z0), b = p.addV(loop[j][0], loop[j][1], z0), c = p.addV(loop[j][0], loop[j][1], z1), d = p.addV(loop[i][0], loop[i][1], z1);
      p.addQ(a, b, c, d);
    }
  };
  wall(O); for (const h of H) wall(h);
  return p;
}
// loft mezi polygony se stejným počtem bodů (každý {poly, z}); vrací Part (víčka volitelně)
export function loftPoly(mat, name, levels, { capStart = 'down', capEnd = 'up', closed = false, crease } = {}) {
  const p = new Part(name, mat); if (crease !== undefined) p.crease = crease;
  const rings = levels.map(l => ccw(l.poly).map(q => [q[0], q[1], l.z]));
  loftRings(p, rings, { capStart, capEnd, closed });
  return p;
}
// otočený (kolem Z) zaoblený kvádr: střed (cx,cy), rozměry sx (po lokální X), sy, výška z0..z1, zaoblení rohů r, otočení rotDeg
export function boxR(mat, name, cx, cy, sx, sy, z0, z1, { r = 0, rot = 0, seg = 4, crease } = {}) {
  let P = rectPoly(-sx / 2, sx / 2, -sy / 2, sy / 2);
  if (r > 0) P = roundPoly(P, r, seg);
  P = rotPoly(P, rot).map(q => [q[0] + cx, q[1] + cy]);
  return extrude(mat, name, P, [], z0, z1, { crease });
}
// drát = trubka po cestě s kruhovým průřezem
export const drat = (name, path3, r = 1.2, n = 8) => tube('ocel', name, path3, r, n, true);
export { Part, tube, loftRings };

// zrcadlení partu podle X (x -> -x) a kopie
export function mirrorCopyX(part, name) { const q = part.clone(name ?? part.name); q.mirror('x', 0); return q; }
// sloučení více Partů do jednoho (stejný materiál)
export function merge(name, mat, parts) { const p = new Part(name, mat); for (const q of parts) p.append(q); return p; }
