// Vlastní jádro generátoru (cloud, 2026-10-09): sítě, transformace, prstence, loft.
// Nezávislé na kódu bota John. Jednotky mm. Souřadnice: X = délka/šířka, Y = hloubka, Z = výška (Z nahoru).
// Orientace ploch: normála míří VEN z materiálu; viz pravidlo v loftRings().

export class Part {
  constructor(name, mat) { this.name = name; this.mat = mat; this.pos = []; this.idx = []; this.crease = 35; }
  get nv() { return this.pos.length / 3; }
  get nt() { return this.idx.length / 3; }
  addV(x, y, z) { this.pos.push(x, y, z); return this.pos.length / 3 - 1; }
  addT(a, b, c) { this.idx.push(a, b, c); }
  addQ(a, b, c, d) { this.idx.push(a, b, c, a, c, d); }
  append(o) {
    const off = this.nv;
    for (let i = 0; i < o.pos.length; i++) this.pos.push(o.pos[i]);
    for (let i = 0; i < o.idx.length; i++) this.idx.push(o.idx[i] + off);
    return this;
  }
  clone(name, mat) { const p = new Part(name ?? this.name, mat ?? this.mat); p.pos = this.pos.slice(); p.idx = this.idx.slice(); p.crease = this.crease; return p; }
  bbox() {
    const b = [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity];
    for (let i = 0; i < this.pos.length; i += 3) for (let k = 0; k < 3; k++) { const v = this.pos[i + k]; if (v < b[k]) b[k] = v; if (v > b[k + 3]) b[k + 3] = v; }
    return b;
  }
  // transformace na místě
  mapV(fn) { for (let i = 0; i < this.pos.length; i += 3) { const r = fn(this.pos[i], this.pos[i + 1], this.pos[i + 2]); this.pos[i] = r[0]; this.pos[i + 1] = r[1]; this.pos[i + 2] = r[2]; } return this; }
  move(dx, dy, dz) { for (let i = 0; i < this.pos.length; i += 3) { this.pos[i] += dx; this.pos[i + 1] += dy; this.pos[i + 2] += dz; } return this; }
  scale(sx, sy = sx, sz = sx) { for (let i = 0; i < this.pos.length; i += 3) { this.pos[i] *= sx; this.pos[i + 1] *= sy; this.pos[i + 2] *= sz; } if (sx * sy * sz < 0) this.flip(); return this; }
  // otočení kolem osy procházející bodem (px,py,pz); osa 'x'|'y'|'z'; úhel ve stupních (pravotočivě)
  rot(axis, deg, p = [0, 0, 0]) {
    const a = deg * Math.PI / 180, c = Math.cos(a), s = Math.sin(a);
    return this.mapV((x, y, z) => {
      x -= p[0]; y -= p[1]; z -= p[2];
      let r;
      if (axis === 'x') r = [x, y * c - z * s, y * s + z * c];
      else if (axis === 'y') r = [x * c + z * s, y, -x * s + z * c];
      else r = [x * c - y * s, x * s + y * c, z];
      return [r[0] + p[0], r[1] + p[1], r[2] + p[2]];
    });
  }
  flip() { for (let i = 0; i < this.idx.length; i += 3) { const t = this.idx[i + 1]; this.idx[i + 1] = this.idx[i + 2]; this.idx[i + 2] = t; } return this; }
  // zrcadlení podle roviny osa=hodnota (mění orientaci → převrátí plochy)
  mirror(axis, at = 0) { const k = { x: 0, y: 1, z: 2 }[axis]; for (let i = 0; i < this.pos.length; i += 3) this.pos[i + k] = 2 * at - this.pos[i + k]; return this.flip(); }
}

// ---------- 2D prstence (uzavřené, CCW při pohledu shora +Z) ----------
export function rrRing(cx, cy, hx, hy, r, seg = 4) {
  r = Math.max(Math.min(r, hx - 1e-6, hy - 1e-6), 1e-4);
  const pts = [], cs = [[cx + hx - r, cy + hy - r, 0], [cx - hx + r, cy + hy - r, 90], [cx - hx + r, cy - hy + r, 180], [cx + hx - r, cy - hy + r, 270]];
  // poznámka: pořadí rohů CCW začíná u +x/+y rohu: 0°..90° (kolem pravého horního), 90°..180° (levý horní) ...
  for (const [px, py, a0] of cs) for (let k = 0; k <= seg; k++) { const a = (a0 + 90 * k / seg) * Math.PI / 180; pts.push([px + r * Math.cos(a), py + r * Math.sin(a)]); }
  return pts;
}
export function ellipseRing(cx, cy, rx, ry, n = 32, a0 = 0) {
  const pts = []; for (let i = 0; i < n; i++) { const a = a0 + 2 * Math.PI * i / n; pts.push([cx + rx * Math.cos(a), cy + ry * Math.sin(a)]); } return pts;
}
export const lift = (ring, z) => ring.map(p => [p[0], p[1], z]);

// ---------- loft prstenců ----------
// rings: pole prstenců (každý = pole [x,y,z], stejný počet bodů, CCW při pohledu shora).
// Pravidlo orientace: normála = tečna_prstence × směr_postupu_profilem → míří ven z materiálu, když
// se profil prochází "vnější stranou nahoru, přes okraj dovnitř, vnitřní stranou dolů".
// opts: closed (poslední→první), capStart/capEnd: 'up'|'down' (vějíř od těžiště prstence)
export function loftRings(part, rings, opts = {}) {
  const n = rings[0].length;
  const base = rings.map(r => r.map(p => part.addV(p[0], p[1], p[2])));
  const m = rings.length, last = opts.closed ? m : m - 1;
  for (let k = 0; k < last; k++) {
    const A = base[k], B = base[(k + 1) % m];
    for (let i = 0; i < n; i++) { const j = (i + 1) % n; part.addQ(A[i], A[j], B[j], B[i]); }
  }
  const cap = (ringIdx, dir) => {
    const R = rings[ringIdx], ids = base[ringIdx];
    let cx = 0, cy = 0, cz = 0; for (const p of R) { cx += p[0]; cy += p[1]; cz += p[2]; } cx /= n; cy /= n; cz /= n;
    const c = part.addV(cx, cy, cz);
    for (let i = 0; i < n; i++) { const j = (i + 1) % n; if (dir === 'up') part.addT(c, ids[i], ids[j]); else part.addT(c, ids[j], ids[i]); }
  };
  if (opts.capStart) cap(0, opts.capStart);
  if (opts.capEnd) cap(m - 1, opts.capEnd);
  return part;
}

// Obecný plášť: profil = [[z, inset], ...] nad obdélníkem se zaoblenými rohy (rc). Viz pravidlo orientace výše.
export function shell(part, { cx, cy, hx, hy, rc = 0, seg = 4, profile, capStart, capEnd }) {
  const rings = profile.map(([z, d]) => lift(rrRing(cx, cy, Math.max(hx - d, 1e-3), Math.max(hy - d, 1e-3), Math.max(rc - d, 1e-4), seg), z));
  return loftRings(part, rings, { capStart, capEnd });
}

// profil zaoblené hrany: zdola nahoru (celé plné těleso). z0,z1 spodek/vršek; re = poloměr hrany (spodek, vršek)
export function solidProfile(z0, z1, reB, reT, fs = 3) {
  const pr = [];
  reB = Math.min(reB, (z1 - z0) / 2); reT = Math.min(reT, (z1 - z0) / 2);
  if (reB > 1e-6) for (let k = 0; k <= fs; k++) { const a = Math.PI / 2 * k / fs; pr.push([z0 + reB - reB * Math.cos(a), reB - reB * Math.sin(a)]); }
  else pr.push([z0, 0]);
  if (reT > 1e-6) for (let k = 0; k <= fs; k++) { const a = Math.PI / 2 * k / fs; pr.push([z1 - reT + reT * Math.sin(a), reT - reT * Math.cos(a)]); }
  else pr.push([z1, 0]);
  return pr;
}

// plné zaoblené těleso (kvádr se zaoblenými rohy a hranami)
export function roundedBox(mat, name, { x0, x1, y0, y1, z0, z1, rc = 0, re = 0, reB, reT, seg = 4, fs = 3 }) {
  const p = new Part(name, mat);
  const hx = (x1 - x0) / 2, hy = (y1 - y0) / 2;
  shell(p, { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, hx, hy, rc, seg, profile: solidProfile(z0, z1, reB ?? re, reT ?? re, fs), capStart: 'down', capEnd: 'up' });
  return p;
}

// ostrý kvádr (plošné stínování; 24 vrcholů)
export function box(mat, name, x0, x1, y0, y1, z0, z1) {
  const p = new Part(name, mat);
  const V = (x, y, z) => p.addV(x, y, z);
  const f = (a, b, c, d) => p.addQ(V(...a), V(...b), V(...c), V(...d));
  f([x0, y0, z0], [x0, y1, z0], [x1, y1, z0], [x1, y0, z0]); // dole
  f([x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]); // nahoře
  f([x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1]); // -y
  f([x1, y1, z0], [x0, y1, z0], [x0, y1, z1], [x1, y1, z1]); // +y
  f([x0, y1, z0], [x0, y0, z0], [x0, y0, z1], [x0, y1, z1]); // -x
  f([x1, y0, z0], [x1, y1, z0], [x1, y1, z1], [x1, y0, z1]); // +x
  p.crease = 5; return p;
}

// dutá nádoba (zaoblená, tenkostěnná, otevřená nahoře) – vnější i vnitřní stěna + okraj
export function hollowBox(mat, name, { x0, x1, y0, y1, z0, z1, rc = 3, re = 1, wall = 1.5, floor = 1.5, seg = 4, fs = 2 }) {
  const p = new Part(name, mat);
  const hx = (x1 - x0) / 2, hy = (y1 - y0) / 2, cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  const pr = [];
  // vnější dno (od středu ven) + hrana + vnější stěna nahoru
  const ob = solidProfile(z0, z1, re, 0, fs).filter((q, i, arr) => i <= fs); // spodní zaoblení
  for (const q of ob) pr.push(q);
  pr.push([z1, 0]);                       // vnější horní hrana
  pr.push([z1, wall]);                    // okraj dovnitř
  const zi = z0 + floor, ri = Math.max(re - wall * 0.3, 0.3);
  // vnitřní stěna dolů a vnitřní dno
  pr.push([zi + ri, wall]);
  for (let k = 1; k <= fs; k++) { const a = Math.PI / 2 * k / fs; pr.push([zi + ri - ri * Math.sin(a), wall + ri - ri * Math.cos(a)]); }
  shell(p, { cx, cy, hx, hy, rc, seg, profile: pr, capStart: 'down', capEnd: 'up' });
  return p;
}

// ---------- rotační těleso kolem osy Z (profil [r,z] zdola nahoru po vnější straně) ----------
export function lathe(mat, name, prof, n = 24, center = [0, 0, 0]) {
  const p = new Part(name, mat);
  const rings = prof.map(([r, z]) => { const R = []; for (let i = 0; i < n; i++) { const a = 2 * Math.PI * i / n; R.push([center[0] + r * Math.cos(a), center[1] + r * Math.sin(a), center[2] + z]); } return R; });
  // profil zdola nahoru po vnější straně: tečna × směr = ven ✓.
  loftRings(p, rings, { capStart: prof[0][0] > 1e-6 ? 'down' : null, capEnd: prof[prof.length - 1][0] > 1e-6 ? 'up' : null });
  return p;
}
export function cylinder(mat, name, r, z0, z1, n = 20, c = [0, 0]) { return lathe(mat, name, [[r, z0], [r, z1]], n, [c[0], c[1], 0]); }

// ---------- trubka po cestě (drát, tyč); cesta = body [x,y,z] ----------
export function tube(mat, name, path, r, n = 10, cap = true) {
  const p = new Part(name, mat);
  const N = path.length; const rings = [];
  let prevN = null;
  const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const norm = v => { const l = Math.hypot(...v) || 1; return [v[0] / l, v[1] / l, v[2] / l]; };
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  for (let i = 0; i < N; i++) {
    let t;
    if (i === 0) t = norm(sub(path[1], path[0])); else if (i === N - 1) t = norm(sub(path[N - 1], path[N - 2]));
    else { const a = norm(sub(path[i + 1], path[i])), b = norm(sub(path[i], path[i - 1])); t = norm([a[0] + b[0], a[1] + b[1], a[2] + b[2]]); }
    let nn;
    if (!prevN) { const ref = Math.abs(t[2]) < 0.9 ? [0, 0, 1] : [1, 0, 0]; nn = norm(cross(ref, t)); }
    else { nn = prevN.slice(); const d = dot(nn, t); nn = norm([nn[0] - t[0] * d, nn[1] - t[1] * d, nn[2] - t[2] * d]); }
    prevN = nn; const bb = cross(t, nn);
    const R = [];
    // zaručit CCW při pohledu ve směru +t: normála × bin
    for (let k = 0; k < n; k++) { const a = 2 * Math.PI * k / n; R.push([path[i][0] + r * (Math.cos(a) * nn[0] + Math.sin(a) * bb[0]), path[i][1] + r * (Math.cos(a) * nn[1] + Math.sin(a) * bb[1]), path[i][2] + r * (Math.cos(a) * nn[2] + Math.sin(a) * bb[2])]); }
    rings.push(R);
  }
  loftRings(p, rings, { capStart: cap ? 'down' : null, capEnd: cap ? 'up' : null });
  p.crease = 60;
  return p;
}

// ---------- hranol z libovolného (jednoduchého, neprotínajícího se) polygonu v rovině XY, výška z0..z1 ----------
export function prism(mat, name, poly, z0, z1) {
  const p = new Part(name, mat);
  // zajistit CCW
  let area = 0; for (let i = 0; i < poly.length; i++) { const a = poly[i], b = poly[(i + 1) % poly.length]; area += a[0] * b[1] - b[0] * a[1]; }
  const P = area < 0 ? poly.slice().reverse() : poly.slice();
  const tris = earClip(P);
  const n = P.length;
  const bot = P.map(q => p.addV(q[0], q[1], z0)), top = P.map(q => p.addV(q[0], q[1], z1));
  for (const [a, b, c] of tris) { p.addT(top[a], top[b], top[c]); p.addT(bot[a], bot[c], bot[b]); }
  for (let i = 0; i < n; i++) { const j = (i + 1) % n; const a = p.addV(P[i][0], P[i][1], z0), b = p.addV(P[j][0], P[j][1], z0), c = p.addV(P[j][0], P[j][1], z1), d = p.addV(P[i][0], P[i][1], z1); p.addQ(a, b, c, d); }
  p.crease = 25;
  return p;
}
export function earClip(P) {
  const n = P.length, idx = [...Array(n).keys()], out = [];
  const area2 = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  const inTri = (p, a, b, c) => area2(a, b, p) >= -1e-9 && area2(b, c, p) >= -1e-9 && area2(c, a, p) >= -1e-9;
  let guard = 0;
  while (idx.length > 3 && guard++ < 10000) {
    let clipped = false;
    for (let i = 0; i < idx.length; i++) {
      const ia = idx[(i + idx.length - 1) % idx.length], ib = idx[i], ic = idx[(i + 1) % idx.length];
      const a = P[ia], b = P[ib], c = P[ic];
      if (area2(a, b, c) <= 1e-9) continue;
      let ok = true;
      for (const j of idx) { if (j === ia || j === ib || j === ic) continue; if (inTri(P[j], a, b, c)) { ok = false; break; } }
      if (!ok) continue;
      out.push([ia, ib, ic]); idx.splice(i, 1); clipped = true; break;
    }
    if (!clipped) { out.push([idx[0], idx[1], idx[2]]); idx.splice(1, 1); }
  }
  if (idx.length === 3) out.push([idx[0], idx[1], idx[2]]);
  return out;
}

// ---------- úprava normál + sloučení vrcholů (crease úhel) ----------
export function finalizePart(part) {
  const nv = part.nv, nt = part.nt, P = part.pos, I = part.idx;
  // 1) svaření vrcholů podle polohy
  const key = (x, y, z) => Math.round(x * 500) + ',' + Math.round(y * 500) + ',' + Math.round(z * 500);
  const weld = new Int32Array(nv), map = new Map(); let w = 0;
  for (let i = 0; i < nv; i++) { const k = key(P[3 * i], P[3 * i + 1], P[3 * i + 2]); let g = map.get(k); if (g === undefined) { g = w++; map.set(k, g); } weld[i] = g; }
  // 2) normály ploch
  const fn = new Float32Array(nt * 3), fa = new Float32Array(nt);
  const keep = [];
  for (let t = 0; t < nt; t++) {
    const a = I[3 * t], b = I[3 * t + 1], c = I[3 * t + 2];
    const ux = P[3 * b] - P[3 * a], uy = P[3 * b + 1] - P[3 * a + 1], uz = P[3 * b + 2] - P[3 * a + 2];
    const vx = P[3 * c] - P[3 * a], vy = P[3 * c + 1] - P[3 * a + 1], vz = P[3 * c + 2] - P[3 * a + 2];
    let nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx; const l = Math.hypot(nx, ny, nz);
    fa[t] = l / 2;
    if (l < 1e-10) { fn[3 * t] = fn[3 * t + 1] = fn[3 * t + 2] = 0; continue; }
    fn[3 * t] = nx / l; fn[3 * t + 1] = ny / l; fn[3 * t + 2] = nz / l; keep.push(t);
  }
  // 3) ploch na svařený vrchol
  const adj = Array.from({ length: w }, () => []);
  for (const t of keep) for (let k = 0; k < 3; k++) adj[weld[I[3 * t + k]]].push(t);
  const cosC = Math.cos(part.crease * Math.PI / 180);
  const outPos = [], outNor = [], outIdx = [], dedupe = new Map();
  for (const t of keep) {
    for (let k = 0; k < 3; k++) {
      const vi = I[3 * t + k], g = weld[vi];
      let sx = 0, sy = 0, sz = 0;
      for (const u of adj[g]) { const d = fn[3 * u] * fn[3 * t] + fn[3 * u + 1] * fn[3 * t + 1] + fn[3 * u + 2] * fn[3 * t + 2]; if (d >= cosC) { sx += fn[3 * u] * fa[u]; sy += fn[3 * u + 1] * fa[u]; sz += fn[3 * u + 2] * fa[u]; } }
      const l = Math.hypot(sx, sy, sz) || 1; sx /= l; sy /= l; sz /= l;
      const kk = g + '|' + Math.round(sx * 60) + ',' + Math.round(sy * 60) + ',' + Math.round(sz * 60);
      let o = dedupe.get(kk);
      if (o === undefined) { o = outPos.length / 3; dedupe.set(kk, o); outPos.push(P[3 * vi], P[3 * vi + 1], P[3 * vi + 2]); outNor.push(sx, sy, sz); }
      outIdx.push(o);
    }
  }
  return { name: part.name, mat: part.mat, pos: new Float32Array(outPos), nor: new Float32Array(outNor), idx: new Uint32Array(outIdx) };
}

// ---------- skupiny (uzly) s pivotem ----------
export class Group {
  constructor(name, { pivot = [0, 0, 0], extras = {} } = {}) { this.name = name; this.pivot = pivot; this.extras = extras; this.parts = []; this.children = []; }
  add(...ps) { for (const p of ps) this.parts.push(p); return this; }
  addGroup(g) { this.children.push(g); return g; }
  allParts() { return [...this.parts, ...this.children.flatMap(c => c.allParts())]; }
  bbox() { const b = [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity]; for (const p of this.allParts()) { const q = p.bbox(); for (let k = 0; k < 3; k++) { b[k] = Math.min(b[k], q[k]); b[k + 3] = Math.max(b[k + 3], q[k + 3]); } } return b; }
}
