// Společné pomocné funkce pro opravené modely Milwaukee PACKOUT 4932464078 a 4932478161 (vlastní generátor, jádro kufriky_cloud/jadro).
// Jednotky mm. Díly se tvoří přímo v souřadnicích modelu (počátek = střed obálky); výšky převádí volající (z' - ZC).
// Nic z kufriky_john/ se nepoužívá ani neopisuje.
import { Part, Group, loftRings, earClip, box, tube, cylinder, lathe, prism, roundedBox } from '../kufriky_cloud/jadro/mesh.js';
export { Part, Group, box, tube, cylinder, lathe, prism, roundedBox, earClip, loftRings };

// ---------- 2D polygony (CCW při pohledu shora) ----------
// obdélník x0..x1 × y0..y1 se zaoblenými rohy; rs = číslo nebo [r(+x+y), r(-x+y), r(-x-y), r(+x-y)]; seg = úseků oblouku na roh
export function rrPoly(x0, x1, y0, y1, rs = 0, seg = 4) {
  const R = Array.isArray(rs) ? rs : [rs, rs, rs, rs];
  const hx = (x1 - x0) / 2, hy = (y1 - y0) / 2;
  const cs = [[x1, y1, 0], [x0, y1, 90], [x0, y0, 180], [x1, y0, 270]];
  const pts = [];
  for (let c = 0; c < 4; c++) {
    const r = Math.max(Math.min(R[c], hx - 1e-4, hy - 1e-4), 1e-3);
    const sx = c === 0 || c === 3 ? -1 : 1, sy = c === 0 || c === 1 ? -1 : 1;
    const cx = cs[c][0] + sx * r, cy = cs[c][1] + sy * r;
    for (let k = 0; k <= seg; k++) { const a = (cs[c][2] + 90 * k / seg) * Math.PI / 180; pts.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); }
  }
  return pts;
}
export const polyArea = P => { let s = 0; for (let i = 0; i < P.length; i++) { const a = P[i], b = P[(i + 1) % P.length]; s += a[0] * b[1] - b[0] * a[1]; } return s / 2; };
export const ccw = P => (polyArea(P) < 0 ? P.slice().reverse() : P);

// plné těleso z vrstev [{poly, z}] (stejný počet bodů v každé vrstvě), víčka triangulací
export function loftSolid(mat, name, layers, { crease = 35 } = {}) {
  const p = new Part(name, mat); p.crease = crease;
  loftRings(p, layers.map(L => L.poly.map(q => [q[0], q[1], L.z])), {});
  const cap = (L, up) => {
    const P = L.poly, tris = earClip(P), ids = P.map(q => p.addV(q[0], q[1], L.z));
    for (const [a, b, c] of tris) { if (up) p.addT(ids[a], ids[b], ids[c]); else p.addT(ids[a], ids[c], ids[b]); }
  };
  cap(layers[0], false); cap(layers[layers.length - 1], true);
  return p;
}
export const ext = (mat, name, poly, z0, z1, crease = 25) => loftSolid(mat, name, [{ poly: ccw(poly), z: z0 }, { poly: ccw(poly), z: z1 }], { crease });
// extruze obrysu v rovině YZ podél X: poly = [[y,z]...]
export function extYZ(mat, name, poly, x0, x1, crease = 25) {
  const p = ext(mat, name, poly, x0, x1, crease); p.mapV((u, v, w) => [w, u, v]); return p;
}
// extruze obrysu v rovině XZ podél Y: poly = [[x,z]...]
export function extXZ(mat, name, poly, y0, y1, crease = 25) {
  const p = ext(mat, name, poly, y0, y1, crease); p.mapV((u, v, w) => [u, w, v]); p.flip(); return p;
}
// zaoblená deska (kvádr se zaoblenými rohy a hranami horní/dolní)
export function slab(mat, name, { x0, x1, y0, y1, z0, z1, rs = 0, seg = 4, reT = 0, reB = 0, fs = 3, kT = 1, kB = 1 }) {
  const layers = [];
  reB = Math.min(reB, (z1 - z0) / 2); reT = Math.min(reT, (z1 - z0) / 2);
  const R = Array.isArray(rs) ? rs : [rs, rs, rs, rs];
  const mk = (d, z) => ({ poly: rrPoly(x0 + d, x1 - d, y0 + d, y1 - d, R.map(r => Math.max(r - d, 0.01)), seg), z });
  if (reB > 1e-6) for (let k = 0; k <= fs; k++) { const a = Math.PI / 2 * k / fs; layers.push(mk(kB * (reB - reB * Math.sin(a)), z0 + reB - reB * Math.cos(a))); } else layers.push(mk(0, z0));
  if (reT > 1e-6) for (let k = 0; k <= fs; k++) { const a = Math.PI / 2 * k / fs; layers.push(mk(kT * (reT - reT * Math.cos(a)), z1 - reT + reT * Math.sin(a))); } else layers.push(mk(0, z1));
  return loftSolid(mat, name, layers);
}
// obecná miska otevřená nahoře z prstenců: rings = [{x0,x1,y0,y1,rs,z}] po vnější straně zdola nahoru, pak okraj a vnitřní strana dolů
export function shellRings(mat, name, rings, { seg = 4, crease = 35, capStart = 'down', capEnd = 'up' } = {}) {
  const p = new Part(name, mat); p.crease = crease;
  loftRings(p, rings.map(r => rrPoly(r.x0, r.x1, r.y0, r.y1, r.rs ?? 0, seg).map(q => [q[0], q[1], r.z])), { capStart, capEnd });
  return p;
}
// zrcadlení Part podle y=0 (klon)
export const mirY = (p, suffix = '_m') => { const m = p.clone(p.name + suffix); m.mirror('y', 0); return m; };
export function addSym(g, part) { g.add(part); const m = mirY(part); g.add(m); return part; }

// ---------- zaoblení rohů libovolného polygonu ----------
export function roundPoly(pts, rs, n = 4) {
  const N = pts.length, out = [];
  for (let i = 0; i < N; i++) {
    const p = pts[i], r = rs[i] ?? 0;
    if (!(r > 1e-6)) { out.push([p[0], p[1]]); continue; }
    const a = pts[(i + N - 1) % N], b = pts[(i + 1) % N];
    let u = [a[0] - p[0], a[1] - p[1]], v = [b[0] - p[0], b[1] - p[1]];
    const lu = Math.hypot(...u), lv = Math.hypot(...v); u = [u[0] / lu, u[1] / lu]; v = [v[0] / lv, v[1] / lv];
    const cosT = Math.max(-1, Math.min(1, u[0] * v[0] + u[1] * v[1])), th = Math.acos(cosT);
    let t = r / Math.tan(th / 2); const tmax = Math.min(lu, lv) * 0.49; let rr = r;
    if (t > tmax) { t = tmax; rr = t * Math.tan(th / 2); }
    const p1 = [p[0] + u[0] * t, p[1] + u[1] * t], p2 = [p[0] + v[0] * t, p[1] + v[1] * t];
    let bis = [u[0] + v[0], u[1] + v[1]]; const lb = Math.hypot(...bis) || 1; bis = [bis[0] / lb, bis[1] / lb];
    const cd = rr / Math.sin(th / 2), c = [p[0] + bis[0] * cd, p[1] + bis[1] * cd];
    let a1 = Math.atan2(p1[1] - c[1], p1[0] - c[0]), a2 = Math.atan2(p2[1] - c[1], p2[0] - c[0]);
    let da = a2 - a1; while (da > Math.PI) da -= 2 * Math.PI; while (da < -Math.PI) da += 2 * Math.PI;
    for (let k = 0; k <= n; k++) { const aa = a1 + da * k / n; out.push([c[0] + rr * Math.cos(aa), c[1] + rr * Math.sin(aa)]); }
  }
  return out;
}

// ---------- kolo s pneumatikou (osa kola = Y) ----------
// cx, cz = střed; R = vnější poloměr pneumatiky; y0..y1 = rozsah šířky; nBloku = počet bloků běhounu; nSpic = počet paprsků disku
export function kolo(name, { cx, cz, R, y0, y1, nBloku = 28, nSpic = 5, rDisk = null, tvarSpic = 0.55 }) {
  const w = y1 - y0, yc = (y0 + y1) / 2, g = new Group(name, { pivot: [cx, yc, cz] });
  // pneumatika: plášť s oblými boky (lathe kolem osy Z, pak otočit osu Z -> Y)
  const rIn = R * 0.60, rS = R - w * 0.0;
  const prof = [];
  const ph = w / 2;
  const sh = [[rIn, -ph * 0.92], [R * 0.80, -ph], [R * 0.93, -ph * 0.97], [R * 0.985, -ph * 0.70], [R, -ph * 0.35], [R, ph * 0.35], [R * 0.985, ph * 0.70], [R * 0.93, ph * 0.97], [R * 0.80, ph], [rIn, ph * 0.92]];
  const t = lathe('cerna_mat', name + '_pneu', sh.map(([r, z]) => [r, z + ph]), 48, [0, 0, 0]);
  t.move(0, 0, -ph); t.rot('x', 90); t.move(cx, yc, cz);   // osa Z -> Y (rot x 90°: z -> -y ... viz kontrola bbox)
  g.add(t);
  // bloky běhounu
  for (let i = 0; i < nBloku; i++) {
    const a = 2 * Math.PI * i / nBloku, hb = (2 * Math.PI * R / nBloku) * 0.34;
    const b = box('cerna_mat', name + '_blok' + i, -hb, hb, -w * 0.46, w * 0.46, R - 0.6, R + 3.0);
    b.rot('y', (a * 180 / Math.PI)); b.move(cx, yc, cz);
    g.add(b);
  }
  return g;
}

// ---------- odsazení polygonu o d dovnitř (CCW) ----------
export function polyInset(P, d) {
  const n = P.length, out = [];
  for (let i = 0; i < n; i++) {
    const a = P[(i + n - 1) % n], b = P[i], c = P[(i + 1) % n];
    const e1 = [b[0] - a[0], b[1] - a[1]], e2 = [c[0] - b[0], c[1] - b[1]];
    const l1 = Math.hypot(...e1) || 1, l2 = Math.hypot(...e2) || 1;
    const n1 = [-e1[1] / l1, e1[0] / l1], n2 = [-e2[1] / l2, e2[0] / l2];
    let bx = n1[0] + n2[0], by = n1[1] + n2[1]; const bl = bx * n1[0] + by * n1[1];
    if (Math.abs(bl) < 1e-6) { out.push([b[0] + n1[0] * d, b[1] + n1[1] * d]); continue; }
    out.push([b[0] + bx / bl * d, b[1] + by / bl * d]);
  }
  return out;
}
// skořepina z vrstev: layers = [{poly, z}] – vnější strana zdola nahoru, přes okraj dovnitř a vnitřní strana dolů (jako loftRings).
// opts.otevreno = 'nahoru' (miska: víčka dole i na dně vnitřku) | 'dolu' (víko: spodní hrana se uzavře k první vrstvě)
export function skorepina(mat, name, layers, { otevreno = 'nahoru', crease = 35 } = {}) {
  const p = new Part(name, mat); p.crease = crease;
  const rings = layers.map(L => L.poly.map(q => [q[0], q[1], L.z]));
  if (otevreno === 'nahoru') loftRings(p, rings, { capStart: 'down', capEnd: 'up' });
  else loftRings(p, rings, { closed: true });
  return p;
}
// plochý prstenec mezi dvěma polygony stejného počtu bodů (vnější/vnitřní obrys), výška z0..z1; innerWall = vnitřní stěna
export function ringSolid(mat, name, outer, inner, z0, z1, { innerWall = true, outerWall = true, crease = 30 } = {}) {
  const p = new Part(name, mat); p.crease = crease; const n = outer.length;
  const ot = outer.map(q => p.addV(q[0], q[1], z1)), it = inner.map(q => p.addV(q[0], q[1], z1));
  const ob = outer.map(q => p.addV(q[0], q[1], z0)), ib = inner.map(q => p.addV(q[0], q[1], z0));
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    p.addQ(ot[i], ot[j], it[j], it[i]);
    p.addQ(ob[j], ob[i], ib[i], ib[j]);
    if (innerWall) p.addQ(it[i], it[j], ib[j], ib[i]);
    if (outerWall) p.addQ(ob[i], ob[j], ot[j], ot[i]);
  }
  return p;
}
// deska s libovolným polygonem a zaoblením všech rohů (rovné okraje)
export const plate = (mat, name, pts, r, z0, z1, n = 3) => ext(mat, name, roundPoly(ccw(pts), pts.map(() => r), n), z0, z1);

// ---------- zjednodušený "tahový" font pro loga (plochá červená písmena, tloušťka 0,6 mm; normála +X) ----------
const GL = {
  M: [[[0, 0], [0, 1], [.5, .42], [1, 1], [1, 0]]], I: [[[.5, 0], [.5, 1]]], L: [[[0, 1], [0, 0], [1, 0]]],
  W: [[[0, 1], [.25, 0], [.5, .62], [.75, 0], [1, 1]]], A: [[[0, 0], [.5, 1], [1, 0]], [[.2, .35], [.8, .35]]],
  U: [[[0, 1], [0, .15], [.3, 0], [.7, 0], [1, .15], [1, 1]]], K: [[[0, 0], [0, 1]], [[1, 1], [0, .45], [1, 0]]],
  E: [[[1, 1], [0, 1], [0, 0], [1, 0]], [[0, .5], [.8, .5]]], P: [[[0, 0], [0, 1], [1, 1], [1, .5], [0, .5]]],
  C: [[[1, .88], [.7, 1], [.3, 1], [0, .8], [0, .2], [.3, 0], [.7, 0], [1, .12]]],
  O: [[[.3, 0], [.7, 0], [1, .2], [1, .8], [.7, 1], [.3, 1], [0, .8], [0, .2], [.3, 0]]], T: [[[0, 1], [1, 1]], [[.5, 1], [.5, 0]]],
};
// napis(text, {x, y, z, h, mat, sklon, bok}) – písmena v rovině YZ na ploše X = x; y = střed textu (Y), z = střed výšky (model Z), h = výška písmen; bok = +1 (normála +X) / -1
export function napis(text, { x, y, z, h, mat = 'cervena', sklon = 0.22, tl = 0.17, bok = 1, mezera = 0.38, sirka = 0.62 }) {
  const out = [], cw = h * sirka, gap = h * mezera, tot = text.length * cw + (text.length - 1) * gap;
  let cursor = y - tot / 2;
  for (const ch of text) {
    const strokes = GL[ch];
    if (strokes) for (const st of strokes) for (let k = 0; k + 1 < st.length; k++) {
      const P = st[k], Q = st[k + 1];
      const p = [cursor + (P[0] + sklon * P[1]) * cw, z - h / 2 + P[1] * h], q = [cursor + (Q[0] + sklon * Q[1]) * cw, z - h / 2 + Q[1] * h];
      const dy = q[0] - p[0], dz = q[1] - p[1], L = Math.hypot(dy, dz) || 1, ny = -dz / L * h * tl / 2, nz = dy / L * h * tl / 2, ex = dy / L * h * tl / 2, ez = dz / L * h * tl / 2;
      const poly = [[p[0] - ex + ny, p[1] - ez + nz], [q[0] + ex + ny, q[1] + ez + nz], [q[0] + ex - ny, q[1] + ez - nz], [p[0] - ex - ny, p[1] - ez - nz]];
      const part = extYZ(mat, 'logo_' + ch, poly, x, x + 0.7 * bok, 25);
      out.push(part);
    }
    cursor += cw + gap;
  }
  return out;
}
// blesk (zubatý polygon pod nápisem) v rovině YZ: y0..y1 zleva doprava, střed z, výška h
export function blesk(mat, x, y0, y1, z, h, bok = 1) {
  const w = y1 - y0, P = [[0, .55], [.55, .5], [.5, .65], [1, .3], [.45, .4], [.5, .25]].map(([u, v]) => [y0 + u * w, z + (v - .45) * h]);
  return extYZ(mat, 'logo_blesk', P, x, x + 0.7 * bok, 25);
}

// rotační těleso kolem osy Z z UZAVŘENÉHO profilu (poslední bod se napojí na první, bez víček): [r,z] zdola nahoru po vnější straně a zpět po vnitřní
export function latheClosed(mat, name, prof, n = 24, center = [0, 0, 0]) {
  const p = new Part(name, mat);
  const rings = prof.map(([r, z]) => { const R = []; for (let i = 0; i < n; i++) { const a = 2 * Math.PI * i / n; R.push([center[0] + r * Math.cos(a), center[1] + r * Math.sin(a), center[2] + z]); } return R; });
  loftRings(p, rings, { closed: true });
  return p;
}
