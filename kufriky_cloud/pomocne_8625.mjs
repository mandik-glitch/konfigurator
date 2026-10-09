// Vlastní pomocné funkce pro organizér 4932478625 (hluboký). Nezávislé na ostatních modelářích.
// Jednotky mm. Plochy s normálou ven z materiálu (stejná konvence jako jadro/mesh.js).
import { Part, loftRings, rrRing, lift, roundedBox } from './jadro/mesh.js';

// ---------- obecná plocha z mřížky bodů ----------
// us, vs = rostoucí pole souřadnic; surf(u,v) -> [x,y,z]; flip = otočit orientaci
export function patch(part, us, vs, surf, flip = false) {
  const id = us.map(u => vs.map(v => { const p = surf(u, v); return part.addV(p[0], p[1], p[2]); }));
  for (let i = 0; i < us.length - 1; i++) for (let j = 0; j < vs.length - 1; j++) {
    const a = id[i][j], b = id[i + 1][j], c = id[i + 1][j + 1], d = id[i][j + 1];
    if (flip) part.addQ(a, d, c, b); else part.addQ(a, b, c, d);
  }
  return id;
}

// Rovnoměrné rozdělení úseku [a,b] s krokem <= h, plus vynucené body (zlomy)
export function rozdel(a, b, h, zlomy = []) {
  const set = new Set([a, b]);
  for (const z of zlomy) if (z > a + 1e-6 && z < b - 1e-6) set.add(+z.toFixed(4));
  const pts = [...set].sort((p, q) => p - q);
  const out = [pts[0]];
  for (let i = 1; i < pts.length; i++) {
    const n = Math.max(1, Math.ceil((pts[i] - pts[i - 1]) / h - 1e-9));
    for (let k = 1; k <= n; k++) out.push(pts[i - 1] + (pts[i] - pts[i - 1]) * k / n);
  }
  return out;
}

// ---------- reliéf (výškové pole) obrácený k +X: x = fn(y,z) >= xb; plné těleso uzavřené zadní plochou x = xb ----------
export function reliefX(mat, name, { y0, y1, z0, z1, hy = 2, hz = 2, zlomyY = [], zlomyZ = [], fn, xb, smer = 1 }) {
  const p = new Part(name, mat);
  const ys = rozdel(y0, y1, hy, zlomyY), zs = rozdel(z0, z1, hz, zlomyZ);
  // přední plocha (normála +X pro smer=1)
  const id = patch(p, ys, zs, (y, z) => [fn(y, z), y, z], smer < 0);
  // zadní plocha
  patch(p, ys, zs, (y, z) => [xb, y, z], smer > 0);
  // boky (skirty): okraje z=z0 (dolů), z=z1 (nahoru), y=y0, y=y1
  const sk = (A, B, flip) => { for (let i = 0; i < A.length - 1; i++) { const a = A[i], b = A[i + 1], c = B[i + 1], d = B[i]; if (flip) p.addQ(a, d, c, b); else p.addQ(a, b, c, d); } };
  const edge = (arrIdx, flip) => { sk(arrIdx.front, arrIdx.back, flip); };
  const rear = (y, z) => p.addV(xb, y, z);
  const fr = (i, j) => id[i][j];
  const mk = (cells) => cells.map(([y, z]) => rear(y, z));
  // dolní okraj (z0), jdou i = 0..n
  { const front = ys.map((y, i) => fr(i, 0)); const back = mk(ys.map(y => [y, z0])); edge({ front, back }, smer > 0 ? false : true); }
  { const front = ys.map((y, i) => fr(i, zs.length - 1)); const back = mk(ys.map(y => [y, z1])); edge({ front, back }, smer > 0 ? true : false); }
  { const front = zs.map((z, j) => fr(0, j)); const back = mk(zs.map(z => [y0, z])); edge({ front, back }, smer > 0 ? true : false); }
  { const front = zs.map((z, j) => fr(ys.length - 1, j)); const back = mk(zs.map(z => [y1, z])); edge({ front, back }, smer > 0 ? false : true); }
  p.crease = 40;
  return p;
}

// ---------- desková skořepina z výškových polí: horní plocha z=top(x,y), spodní z=top-t(x,y) ----------
// oblast je obdélník xs×ys; okraj se zaoblí promítnutím uzlů mimo zaoblený obdélník rc na obvod
export function deskaVyska(mat, name, { xs, ys, top, t, rc = 0, cx = 0, cy = 0, hx, hy, spodek = true }) {
  const p = new Part(name, mat);
  const proj = (x, y) => {
    if (rc <= 0) return [x, y];
    const qx = Math.abs(x - cx), qy = Math.abs(y - cy);
    const ix = hx - rc, iy = hy - rc;
    if (qx <= ix || qy <= iy) return [x, y];
    const dx = qx - ix, dy = qy - iy, d = Math.hypot(dx, dy);
    if (d <= rc) return [x, y];
    const k = rc / d;
    return [cx + Math.sign(x - cx) * (ix + dx * k), cy + Math.sign(y - cy) * (iy + dy * k)];
  };
  patch(p, xs, ys, (x, y) => { const q = proj(x, y); return [q[0], q[1], top(q[0], q[1])]; }, false);
  if (spodek) patch(p, xs, ys, (x, y) => { const q = proj(x, y); return [q[0], q[1], top(q[0], q[1]) - t(q[0], q[1])]; }, true);
  p.crease = 40;
  return p;
}

// ---------- hranol z polygonu v rovině (y,z) vytažený podél X od x0 do x1 ----------
export function prismYZ(mat, name, polyYZ, x0, x1, crease = 25) {
  const n = polyYZ.length; const p = new Part(name, mat);
  let area = 0; for (let i = 0; i < n; i++) { const a = polyYZ[i], b = polyYZ[(i + 1) % n]; area += a[0] * b[1] - b[0] * a[1]; }
  const P = area < 0 ? polyYZ.slice().reverse() : polyYZ.slice();
  const tris = earClipSafe(P);
  const A = P.map(q => p.addV(x0, q[0], q[1])), B = P.map(q => p.addV(x1, q[0], q[1]));
  // (y,z) CCW při pohledu z +X → normála +X pro vršek x1
  for (const [a, b, c] of tris) { p.addT(B[a], B[b], B[c]); p.addT(A[a], A[c], A[b]); }
  for (let i = 0; i < n; i++) { const j = (i + 1) % n; const a = p.addV(x0, P[i][0], P[i][1]), b = p.addV(x0, P[j][0], P[j][1]), c = p.addV(x1, P[j][0], P[j][1]), d = p.addV(x1, P[i][0], P[i][1]); p.addQ(a, b, c, d); }
  p.crease = crease; return p;
}
// polygon v rovině (x,z) vytažený podél Y od y0 do y1 (normála plochy y1 = +Y)
export function prismXZ(mat, name, polyXZ, y0, y1, crease = 25) {
  const n = polyXZ.length; const p = new Part(name, mat);
  let area = 0; for (let i = 0; i < n; i++) { const a = polyXZ[i], b = polyXZ[(i + 1) % n]; area += a[0] * b[1] - b[0] * a[1]; }
  const P = area < 0 ? polyXZ.slice().reverse() : polyXZ.slice();   // CCW v (x,z)
  const tris = earClipSafe(P);
  const A = P.map(q => p.addV(q[0], y0, q[1])), B = P.map(q => p.addV(q[0], y1, q[1]));
  for (const [a, b, c] of tris) { p.addT(B[a], B[c], B[b]); p.addT(A[a], A[b], A[c]); }
  for (let i = 0; i < n; i++) { const j = (i + 1) % n; const a = p.addV(P[i][0], y0, P[i][1]), b = p.addV(P[j][0], y0, P[j][1]), c = p.addV(P[j][0], y1, P[j][1]), d = p.addV(P[i][0], y1, P[i][1]); p.addQ(a, d, c, b); }
  p.crease = crease; return p;
}
function earClipSafe(P) {
  const n = P.length, idx = [...Array(n).keys()], out = [];
  const ar = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  const inT = (p, a, b, c) => ar(a, b, p) >= -1e-9 && ar(b, c, p) >= -1e-9 && ar(c, a, p) >= -1e-9;
  let g = 0;
  while (idx.length > 3 && g++ < 5000) {
    let cl = false;
    for (let i = 0; i < idx.length; i++) {
      const ia = idx[(i + idx.length - 1) % idx.length], ib = idx[i], ic = idx[(i + 1) % idx.length];
      const a = P[ia], b = P[ib], c = P[ic];
      if (ar(a, b, c) <= 1e-9) continue;
      let ok = true; for (const j of idx) { if (j === ia || j === ib || j === ic) continue; if (inT(P[j], a, b, c)) { ok = false; break; } }
      if (!ok) continue;
      out.push([ia, ib, ic]); idx.splice(i, 1); cl = true; break;
    }
    if (!cl) { out.push([idx[0], idx[1], idx[2]]); idx.splice(1, 1); }
  }
  if (idx.length === 3) out.push([idx[0], idx[1], idx[2]]);
  return out;
}

// zaoblený obdélník v rovině (y,z) – polygon pro prismYZ
export function rrPolyYZ(y0, y1, z0, z1, r, seg = 4) {
  r = Math.min(r, (y1 - y0) / 2 - 1e-6, (z1 - z0) / 2 - 1e-6);
  if (r <= 1e-6) return [[y0, z0], [y1, z0], [y1, z1], [y0, z1]];
  const pts = [], cs = [[y1 - r, z1 - r, 0], [y0 + r, z1 - r, 90], [y0 + r, z0 + r, 180], [y1 - r, z0 + r, 270]];
  for (const [cy, cz, a0] of cs) for (let k = 0; k <= seg; k++) { const a = (a0 + 90 * k / seg) * Math.PI / 180; pts.push([cy + r * Math.cos(a), cz + r * Math.sin(a)]); }
  return pts;
}

// jednoduché hladké funkce
export const smooth = (t) => { t = Math.max(0, Math.min(1, t)); return t * t * (3 - 2 * t); };
export const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
// podepsaná vzdálenost ke zaoblenému obdélníku (záporná uvnitř)
export function sdRR(a, b, a0, a1, b0, b1, r = 0) {
  const cx = (a0 + a1) / 2, cy = (b0 + b1) / 2, hx = (a1 - a0) / 2 - r, hy = (b1 - b0) / 2 - r;
  const dx = Math.abs(a - cx) - hx, dy = Math.abs(b - cy) - hy;
  return Math.hypot(Math.max(dx, 0), Math.max(dy, 0)) + Math.min(Math.max(dx, dy), 0) - r;
}


// ---------- deska z výškového pole s libovolným obrysem (proj mapuje uzly mřížky na obrys) ----------
// vrací { part, loop } – loop = obvodové body [x,y,zHorni] proti směru hodinových ručiček (při pohledu shora)
export function deskaObrys(mat, name, { xs, ys, top, t, proj = (x, y) => [x, y] }) {
  const p = new Part(name, mat);
  const nx = xs.length, ny = ys.length;
  const P = xs.map(x => ys.map(y => proj(x, y)));
  const idT = xs.map((x, i) => ys.map((y, j) => p.addV(P[i][j][0], P[i][j][1], top(P[i][j][0], P[i][j][1]))));
  const idB = xs.map((x, i) => ys.map((y, j) => p.addV(P[i][j][0], P[i][j][1], top(P[i][j][0], P[i][j][1]) - t(P[i][j][0], P[i][j][1]))));
  for (let i = 0; i < nx - 1; i++) for (let j = 0; j < ny - 1; j++) {
    p.addQ(idT[i][j], idT[i + 1][j], idT[i + 1][j + 1], idT[i][j + 1]);
    p.addQ(idB[i][j], idB[i][j + 1], idB[i + 1][j + 1], idB[i + 1][j]);
  }
  const loop = [];
  for (let i = 0; i < nx; i++) loop.push([P[i][0][0], P[i][0][1], top(P[i][0][0], P[i][0][1])]);
  for (let j = 1; j < ny; j++) loop.push([P[nx - 1][j][0], P[nx - 1][j][1], top(P[nx - 1][j][0], P[nx - 1][j][1])]);
  for (let i = nx - 2; i >= 0; i--) loop.push([P[i][ny - 1][0], P[i][ny - 1][1], top(P[i][ny - 1][0], P[i][ny - 1][1])]);
  for (let j = ny - 2; j >= 1; j--) loop.push([P[0][j][0], P[0][j][1], top(P[0][j][0], P[0][j][1])]);
  // okrajová stěna mezi horní a spodní plochou (tloušťka t)
  const n = loop.length;
  for (let k = 0; k < n; k++) {
    const a = loop[k], b = loop[(k + 1) % n];
    const ta = t(a[0], a[1]), tb = t(b[0], b[1]);
    const A = p.addV(a[0], a[1], a[2]), B = p.addV(b[0], b[1], b[2]), C = p.addV(b[0], b[1], b[2] - tb), D = p.addV(a[0], a[1], a[2] - ta);
    p.addQ(A, D, C, B);
  }
  p.crease = 40;
  return { part: p, loop };
}

// svislá stěna (plášť) pod obvodem: z horní hrany smyčky dolů do zBottom, spodní lem a vnitřní stěna (tloušťka tw)
export function plastObvodu(mat, name, loop, { zBottom, tw = 2.5, zIn }) {
  const p = new Part(name, mat);
  const n = loop.length;
  // vnitřní obvod: posun dovnitř podél průměrné normály sousedních hran
  const inner = loop.map((q, k) => {
    const a = loop[(k + n - 1) % n], b = loop[(k + 1) % n];
    const e1 = [q[0] - a[0], q[1] - a[1]], e2 = [b[0] - q[0], b[1] - q[1]];
    const n1 = [-e1[1], e1[0]], n2 = [-e2[1], e2[0]];     // levé (vnitřní) normály pro CCW smyčku
    const l1 = Math.hypot(...n1) || 1, l2 = Math.hypot(...n2) || 1;
    let nx = n1[0] / l1 + n2[0] / l2, ny = n1[1] / l1 + n2[1] / l2; const l = Math.hypot(nx, ny) || 1; nx /= l; ny /= l;
    const c = Math.max(0.5, (nx * n1[0] / l1 + ny * n1[1] / l1));
    return [q[0] + nx * tw / c, q[1] + ny * tw / c];
  });
  for (let k = 0; k < n; k++) {
    const kk = (k + 1) % n;
    const a = loop[k], b = loop[kk], ai = inner[k], bi = inner[kk];
    const zia = zIn ? zIn(ai[0], ai[1]) : a[2] - tw, zib = zIn ? zIn(bi[0], bi[1]) : b[2] - tw;
    // vnější stěna
    p.addQ(p.addV(a[0], a[1], a[2]), p.addV(a[0], a[1], zBottom), p.addV(b[0], b[1], zBottom), p.addV(b[0], b[1], b[2]));
    // spodní lem (normála dolů)
    p.addQ(p.addV(a[0], a[1], zBottom), p.addV(ai[0], ai[1], zBottom), p.addV(bi[0], bi[1], zBottom), p.addV(b[0], b[1], zBottom));
    // vnitřní stěna (normála dovnitř = ven z materiálu směrem do dutiny)
    p.addQ(p.addV(ai[0], ai[1], zia), p.addV(bi[0], bi[1], zib), p.addV(bi[0], bi[1], zBottom), p.addV(ai[0], ai[1], zBottom));
  }
  p.crease = 40;
  return p;
}
