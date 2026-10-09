// Pomocné funkce pro model 4932464082 (vlastní generátor, cloud). Jednotky mm.
// Souřadnice modelu: X = šířka (čelo +X), Y = délka, Z = výška, počátek = střed obálky 386 × 500 × 117.
// Výšky se v kódu zadávají jako z' = výška od nejnižšího bodu (0 .. 117); funkce je převedou na Z modelu (z' - 58.5).
import { Part, Group, loftRings, earClip, box, tube, cylinder, lathe } from './jadro/mesh.js';
export { Part, Group, box, tube, cylinder, lathe };

export const ZC = 58.5;
export const zc = z => z - ZC;

// ---------- 2D polygony (CCW při pohledu shora) ----------
// obdélník x0..x1 × y0..y1 se zaoblenými / zkosenými rohy. rs = [r_(+x+y), r_(-x+y), r_(-x-y), r_(+x-y)] nebo číslo;
// seg = počet úseků oblouku (1 = zkosený roh se stranou r), vždy seg+1 bodů na roh → stejný počet bodů pro všechny vrstvy lofta.
export function rrPoly(x0, x1, y0, y1, rs = 0, seg = 4) {
  const R = Array.isArray(rs) ? rs : [rs, rs, rs, rs];
  const S = Array.isArray(seg) ? seg : [seg, seg, seg, seg];
  const hx = (x1 - x0) / 2, hy = (y1 - y0) / 2;
  const cs = [[x1, y1, 0], [x0, y1, 90], [x0, y0, 180], [x1, y0, 270]];
  const pts = [];
  for (let c = 0; c < 4; c++) {
    const r = Math.max(Math.min(R[c], hx - 1e-4, hy - 1e-4), 1e-3);
    const sx = c === 0 || c === 3 ? -1 : 1, sy = c === 0 || c === 1 ? -1 : 1;
    const cx = cs[c][0] + sx * r, cy = cs[c][1] + sy * r;
    for (let k = 0; k <= S[c]; k++) { const a = (cs[c][2] + 90 * k / S[c]) * Math.PI / 180; pts.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); }
  }
  return pts;
}
export const polyArea = P => { let s = 0; for (let i = 0; i < P.length; i++) { const a = P[i], b = P[(i + 1) % P.length]; s += a[0] * b[1] - b[0] * a[1]; } return s / 2; };
export const polyMove = (P, dx, dy) => P.map(p => [p[0] + dx, p[1] + dy]);
export const polyMirrorY = (P, at = 0) => P.map(p => [p[0], 2 * at - p[1]]).reverse();
export const polyMirrorX = (P, at = 0) => P.map(p => [2 * at - p[0], p[1]]).reverse();

// odsazení polygonu o d dovnitř (d>0) pro CCW polygon – po vrcholech podél os (vhodné pro polygony z rrPoly s malými úhly)
export function polyInset(P, d) {
  const n = P.length, out = [];
  for (let i = 0; i < n; i++) {
    const a = P[(i + n - 1) % n], b = P[i], c = P[(i + 1) % n];
    const e1 = [b[0] - a[0], b[1] - a[1]], e2 = [c[0] - b[0], c[1] - b[1]];
    const l1 = Math.hypot(...e1) || 1, l2 = Math.hypot(...e2) || 1;
    const n1 = [-e1[1] / l1, e1[0] / l1], n2 = [-e2[1] / l2, e2[0] / l2];     // vnitřní normály (CCW → vlevo)
    let bx = n1[0] + n2[0], by = n1[1] + n2[1]; const bl = bx * n1[0] + by * n1[1];
    if (Math.abs(bl) < 1e-6) { out.push([b[0] + n1[0] * d, b[1] + n1[1] * d]); continue; }
    out.push([b[0] + bx / bl * d, b[1] + by / bl * d]);
  }
  return out;
}

const lift = (P, z) => P.map(p => [p[0], p[1], zc(z)]);

// ---------- tělesa ----------
// plné těleso z vrstev [{poly, z}] (z = z'), stejný počet bodů v každé vrstvě; víčka triangulace (i konkávní polygony)
export function loftSolid(mat, name, layers, { crease = 35 } = {}) {
  const p = new Part(name, mat); p.crease = crease;
  loftRings(p, layers.map(L => lift(L.poly, L.z)), {});
  const cap = (L, up) => {
    const P = L.poly, tris = earClip(P), ids = P.map(q => p.addV(q[0], q[1], zc(L.z)));
    for (const [a, b, c] of tris) { if (up) p.addT(ids[a], ids[b], ids[c]); else p.addT(ids[a], ids[c], ids[b]); }
  };
  cap(layers[0], false); cap(layers[layers.length - 1], true);
  return p;
}
// hranol z polygonu (stěny strmé, ostré hrany)
export function ext(mat, name, poly, z0, z1) {
  return loftSolid(mat, name, [{ poly, z: z0 }, { poly, z: z1 }], { crease: 25 });
}
// zaoblená deska: obdélník s rohy rs, zaoblení horní / dolní hrany reT / reB (poloměry), fs úseků
export function slab(mat, name, { x0, x1, y0, y1, z0, z1, rs = 0, seg = 4, reT = 0, reB = 0, fs = 3, kT = 1, kB = 1 }) {
  const layers = [];
  reB = Math.min(reB, (z1 - z0) / 2); reT = Math.min(reT, (z1 - z0) / 2);
  const rmax = Math.max(...(Array.isArray(rs) ? rs : [rs]));
  const mk = (d, z) => ({ poly: rrPoly(x0 + d, x1 - d, y0 + d, y1 - d, (Array.isArray(rs) ? rs : [rs, rs, rs, rs]).map(r => Math.max(r - d, 0.01)), seg), z });
  if (reB > 1e-6) for (let k = 0; k <= fs; k++) { const a = Math.PI / 2 * k / fs; layers.push(mk(kB * (reB - reB * Math.sin(a)), z0 + reB - reB * Math.cos(a))); } else layers.push(mk(0, z0));
  if (reT > 1e-6) for (let k = 0; k <= fs; k++) { const a = Math.PI / 2 * k / fs; layers.push(mk(kT * (reT - reT * Math.cos(a)), z1 - reT + reT * Math.sin(a))); } else layers.push(mk(0, z1));
  return loftSolid(mat, name, layers);
}
// tenkostěnná miska otevřená nahoře (nebo dolů, pokud z1 < z0 se použije zrcadlení): profil [[z, inset]...] po vnější straně nahoru,
// přes okraj dovnitř a vnitřní stranou dolů. Vrstvy jsou obdélníky se zaoblenými rohy.
export function rrShell(mat, name, { x0, x1, y0, y1, rs = 0, seg = 4, profile, capStart = null, capEnd = null, closed = false, crease = 35 }) {
  const p = new Part(name, mat); p.crease = crease;
  const R = Array.isArray(rs) ? rs : [rs, rs, rs, rs];
  const rings = profile.map(([z, d]) => lift(rrPoly(x0 + d, x1 - d, y0 + d, y1 - d, R.map(r => Math.max(r - d, 0.01)), seg), z));
  loftRings(p, rings, { capStart, capEnd, closed });
  return p;
}
// rámeček (prstenec) obdélníkového obrysu: vnější obrys x0..x1 × y0..y1, šířka w, výška z0..z1
export function rrFrame(mat, name, { x0, x1, y0, y1, z0, z1, w, rs = 0, seg = 4, crease = 35 }) {
  return rrShell(mat, name, { x0, x1, y0, y1, rs, seg, profile: [[z0, 0], [z1, 0], [z1, w], [z0, w]], closed: true, crease });
}
// miska (tray) otevřená nahoru: vnější stěny od z0 do z1, stěna wall, dno floor, zaoblení dna re
export function tray(mat, name, { x0, x1, y0, y1, z0, z1, rs = 3, seg = 3, wall = 1.5, floor = 1.5, re = 1, fs = 2 }) {
  const pr = [];
  re = Math.min(re, (z1 - z0) / 2);
  for (let k = 0; k <= fs; k++) { const a = Math.PI / 2 * k / fs; pr.push([z0 + re - re * Math.cos(a), re - re * Math.sin(a)]); }
  pr.push([z1, 0]); pr.push([z1, wall]);
  const zi = z0 + floor, ri = Math.max(re - wall * 0.3, 0.3);
  pr.push([zi + ri, wall]);
  for (let k = 1; k <= fs; k++) { const a = Math.PI / 2 * k / fs; pr.push([zi + ri - ri * Math.sin(a), wall + ri - ri * Math.cos(a)]); }
  return rrShell(mat, name, { x0, x1, y0, y1, rs, seg, profile: pr, capStart: 'down', capEnd: 'up' });
}
// kvádr v z' (ostré hrany)
export const bx = (mat, name, x0, x1, y0, y1, z0, z1) => box(mat, name, x0, x1, y0, y1, zc(z0), zc(z1));
export const sl = (mat, name, o) => slab(mat, name, o);

// zrcadlení Part podle y=0 (vrací klon) – převrací plochy
export const mirY = p => p.clone().mirror('y', 0);

// přidá do skupiny díl a jeho zrcadlový protějšek (y → -y); název protějšku s příponou _m
export function addSym(g, part) { g.add(part); const m = part.clone(part.name + '_m'); m.mirror('y', 0); g.add(m); return part; }

// ---------- zaoblení rohů libovolného polygonu ----------
// pts = vrcholy [x,y] (CCW), rs = poloměr pro každý vrchol (0 = ostrý); n = počet úseků oblouku.
// Počet výstupních bodů závisí jen na tom, které poloměry jsou > 0 → vrstvy lofta se stejnými rs mají stejný počet bodů.
export function roundPoly(pts, rs, n = 4) {
  const N = pts.length, out = [];
  for (let i = 0; i < N; i++) {
    const p = pts[i], r = rs[i] ?? 0;
    if (!(r > 1e-6)) { out.push([p[0], p[1]]); continue; }
    const a = pts[(i + N - 1) % N], b = pts[(i + 1) % N];
    let u = [a[0] - p[0], a[1] - p[1]], v = [b[0] - p[0], b[1] - p[1]];
    const lu = Math.hypot(...u), lv = Math.hypot(...v); u = [u[0] / lu, u[1] / lu]; v = [v[0] / lv, v[1] / lv];
    const cosT = Math.max(-1, Math.min(1, u[0] * v[0] + u[1] * v[1])), th = Math.acos(cosT);      // úhel mezi hranami
    let t = r / Math.tan(th / 2); const tmax = Math.min(lu, lv) * 0.49; let rr = r;
    if (t > tmax) { t = tmax; rr = t * Math.tan(th / 2); }
    const p1 = [p[0] + u[0] * t, p[1] + u[1] * t], p2 = [p[0] + v[0] * t, p[1] + v[1] * t];
    // střed oblouku leží na ose úhlu ve vzdálenosti rr / sin(th/2)
    let bis = [u[0] + v[0], u[1] + v[1]]; const lb = Math.hypot(...bis) || 1; bis = [bis[0] / lb, bis[1] / lb];
    const cd = rr / Math.sin(th / 2), c = [p[0] + bis[0] * cd, p[1] + bis[1] * cd];
    let a1 = Math.atan2(p1[1] - c[1], p1[0] - c[0]), a2 = Math.atan2(p2[1] - c[1], p2[0] - c[0]);
    let da = a2 - a1; while (da > Math.PI) da -= 2 * Math.PI; while (da < -Math.PI) da += 2 * Math.PI;
    for (let k = 0; k <= n; k++) { const aa = a1 + da * k / n; out.push([c[0] + rr * Math.cos(aa), c[1] + rr * Math.sin(aa)]); }
  }
  return out;
}
// polygon z bodů s volitelnou orientací CCW
export const ccw = P => (polyArea(P) < 0 ? P.slice().reverse() : P);

// ploché těleso mezi vnějším a vnitřním polygonem (stejný počet bodů) – deska s otvorem
export function ringSolid(mat, name, outer, inner, z0, z1, { innerWall = true, outerWall = false } = {}) {
  const p = new Part(name, mat); p.crease = 30; const n = outer.length;
  const ot = outer.map(q => p.addV(q[0], q[1], zc(z1))), it = inner.map(q => p.addV(q[0], q[1], zc(z1)));
  const ob = outer.map(q => p.addV(q[0], q[1], zc(z0))), ib = inner.map(q => p.addV(q[0], q[1], zc(z0)));
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    p.addQ(ot[i], ot[j], it[j], it[i]);          // horní plocha
    p.addQ(ob[j], ob[i], ib[i], ib[j]);          // spodní plocha
    if (innerWall) p.addQ(it[i], it[j], ib[j], ib[i]);          // vnitřní stěna (normála do otvoru)
    if (outerWall) p.addQ(ob[i], ob[j], ot[j], ot[i]);          // vnější stěna (normála ven)
  }
  return p;
}


// ---------- extruze obrysu v rovině YZ podél osy X ----------
// poly = [[y, z']...] (CCW při pohledu z +X: y doprava, z' nahoru), x0..x1 = rozsah po X
export function extYZ(mat, name, poly, x0, x1, { crease = 25 } = {}) {
  const P = ccwYZ(poly);
  const p = ext(mat, name, P.map(([y, z]) => [y, z - ZC]), x0 + ZC, x1 + ZC);
  p.mapV((u, v, w) => [w, u, v]); p.crease = crease;
  return p;
}
function ccwYZ(P) { return polyArea(P) < 0 ? P.slice().reverse() : P; }
// zaoblený obrys YZ: vrcholy s poloměry (viz roundPoly)
export function roundYZ(pts, rs, n = 3) { return roundPoly(pts, rs, n); }

// miska s úkosem stěn (zúžení ode dna k okraji o 'taper' mm na každé straně); jinak jako tray()
export function trayT(mat, name, { x0, x1, y0, y1, z0, z1, rs = 3, seg = 3, wall = 1.5, floor = 1.5, re = 1, fs = 2, taper = 3 }) {
  const pr = [], H = z1 - z0; re = Math.min(re, H / 2);
  const tp = z => taper * (1 - (z - z0) / H);               // vnější odsazení ve výšce z
  for (let k = 0; k <= fs; k++) { const a = Math.PI / 2 * k / fs; const zz = z0 + re - re * Math.cos(a); pr.push([zz, tp(zz) + re - re * Math.sin(a)]); }
  pr.push([z1, 0]); pr.push([z1, wall]);
  const zi = z0 + floor, ri = Math.max(re - wall * 0.3, 0.3);
  pr.push([zi + ri, wall + tp(zi + ri)]);
  for (let k = 1; k <= fs; k++) { const a = Math.PI / 2 * k / fs; const zz = zi + ri - ri * Math.sin(a); pr.push([zz, wall + tp(zz) + ri - ri * Math.cos(a)]); }
  return rrShell(mat, name, { x0, x1, y0, y1, rs, seg, profile: pr, capStart: 'down', capEnd: 'up' });
}
