// Pomocné funkce pro modely DeWalt TSTAK IP54 (DWST83346-1 hluboký, DWST83345-1 mělký) – jedna parametrická skořepina, výška H je parametr.
// Jednotky mm. Souřadnice modelu: X = hloubka (čelo se západkami do +X), Y = délka (±220), Z = výška; počátek = střed obálky.
// Výšky se v kódu zadávají jako z' = výška od spodní plochy (0 .. H); funkce je převedou na Z modelu (z' − H/2).
// Vlastní generátor podle fotografií výrobce (dewalt.cz), šablona postupu = Hilti ProKit (kufry_hilti/p2437355_zaklad.mjs).
import { Part, Group, loftRings, rrRing, roundedBox, prism, cylinder, box } from '../kufriky_cloud/jadro/mesh.js';
import { earcut2 } from '../kufry_hilti/earcut2.mjs';
export { Part, Group, roundedBox, prism, cylinder, box };

// H = aktuální výška; zadní strana (neviditelná na fotografiích, odhad): rearBody = zadní stěna korpusu, rearMid/rearTop = zadní hrana víka v z' = H−12 a při temeni; trim = zkrácení zadní strany (jen pro pokusy, v modelu 0)
export const S = { H: 302, trim: 0, rearBody: -158, rearTop: -148, rearMid: -160 };                 // aktuální výška kufru (nastavuje build)
export const zc = z => z - S.H / 2;
export const LID_H = 72;                     // výška víka od spáry (odhad z čelní fotografie c02, viz poznámky)
export const zs = () => S.H - LID_H;         // z' spáry víko/korpus
export const zf = () => S.H - 72;            // referenční výška „spáry“ pro prvky změřené z fotografie (z' = H − 72 = 230 u hlubokého)

// ---------- půdorysný loft ----------
// snímek F = {z, xr, xf, y, rc}: obdélník x∈[xr,xf], y∈[−y,+y] s rohy sraženými o rc (seg = 1 → zkosení, seg ≥ 2 → zaoblení)
const SEG = 1;
export function ring(F, w = 0, seg = SEG) {
  const hx = (F.xf - F.xr) / 2 - w, hy = F.y - w;
  return rrRing((F.xf + F.xr) / 2, 0, hx, hy, Math.max(F.rc - w * 0.4, 0.3), seg).map(p => [p[0], p[1], zc(F.z)]);
}
export function interp(frames, z) {
  const L = frames[frames.length - 1];
  if (z <= frames[0].z) return { ...frames[0], z };
  if (z >= L.z) return { ...L, z };
  for (let i = 0; i < frames.length - 1; i++) {
    const a = frames[i], b = frames[i + 1];
    if (z >= a.z && z <= b.z && b.z - a.z > 1e-9) { const t = (z - a.z) / (b.z - a.z), o = { z }; for (const k of ['xr', 'xf', 'y', 'rc']) o[k] = a[k] + (b[k] - a[k]) * t; return o; }
  }
  return { ...L, z };
}
function cap(part, rg, up) {
  const P = rg.map(p => [p[0], p[1]]), ids = rg.map(p => part.addV(p[0], p[1], p[2]));
  // konvexní prstenec → vějíř od těžiště
  let cx = 0, cy = 0; for (const p of P) { cx += p[0]; cy += p[1]; } cx /= P.length; cy /= P.length;
  const c = part.addV(cx, cy, rg[0][2]);
  for (let i = 0; i < P.length; i++) { const j = (i + 1) % P.length; if (up) part.addT(c, ids[i], ids[j]); else part.addT(c, ids[j], ids[i]); }
}
const strip = (p, rings) => { if (rings.length > 1) loftRings(p, rings); };

// plné těleso z půdorysných snímků
export function plne(mat, name, frames, { crease = 30 } = {}) {
  const p = new Part(name, mat); p.crease = crease;
  const R = frames.map(f => ring(f)); strip(p, R); cap(p, R[0], false); cap(p, R[R.length - 1], true); return p;
}
// vana otevřená nahoře: stěna wall, dno ve výšce floorZ (z')
export function vana(mat, name, frames, { wall = 4, floorZ = 4, crease = 30 } = {}) {
  const p = new Part(name, mat); p.crease = crease;
  const Ro = frames.map(f => ring(f));
  const inner = frames.filter(f => f.z > floorZ + 1e-6); inner.unshift(interp(frames, floorZ));
  const Ri = inner.map(f => ring(f, wall)).reverse();
  strip(p, Ro); strip(p, Ri); strip(p, [Ro[Ro.length - 1], Ri[0]]);
  cap(p, Ro[0], false); cap(p, Ri[Ri.length - 1], true); return p;
}
// víko: dutý plášť otevřený dolů (stěna wall, strop topT), volitelné otvory v horní stěně (obdélníky {x0,x1,y0,y1})
export function vickoPlast(mat, name, frames, { wall = 3.5, topT = 3.5, holes = [], crease = 30 } = {}) {
  const p = new Part(name, mat); p.crease = crease;
  const zt = frames[frames.length - 1].z;
  const Ro = frames.map(f => ring(f));
  const inner = frames.filter(f => f.z < zt - topT - 1e-6); inner.push(interp(frames, zt - topT));
  const Ri = inner.map(f => ring(f, wall)).reverse();
  strip(p, Ro); strip(p, Ri); strip(p, [Ri[Ri.length - 1], Ro[0]]);
  if (!holes.length) { cap(p, Ro[Ro.length - 1], true); cap(p, Ri[0], false); }
  else {
    const H = holes.map(h => [[h.x0, h.y0], [h.x0, h.y1], [h.x1, h.y1], [h.x1, h.y0]]);        // díra: CW (při pohledu shora)
    const capHole = (rg, up) => {
      const outer = rg.map(q => [q[0], q[1]]), { pts, tris } = earcut2(outer, H), z = rg[0][2];
      const ids = pts.map(q => p.addV(q[0], q[1], z));
      for (const [a, b, c] of tris) { if (up) p.addT(ids[a], ids[b], ids[c]); else p.addT(ids[a], ids[c], ids[b]); }
    };
    capHole(Ro[Ro.length - 1], true); capHole(Ri[0], false);
  }
  return p;
}
// výřez (dutina): dno + 4 stěny (normála do dutiny)
export function vyrez(mat, name, x0, x1, y0, y1, z0, z1) {
  const p = new Part(name, mat); p.crease = 5;
  const a = zc(z0), b = zc(z1), V = (x, y, z) => p.addV(x, y, z);
  const q = (A, B, C, D) => p.addQ(V(...A), V(...B), V(...C), V(...D));
  q([x0, y0, a], [x1, y0, a], [x1, y1, a], [x0, y1, a]);       // dno, normála +z
  q([x0, y0, a], [x0, y1, a], [x1, y1, a], [x1, y0, a]);       // spodní strana dna (normála −z; víko při otevření vidět zespodu)
  q([x0, y0, b], [x0, y0, a], [x0, y1, a], [x0, y1, b]);       // stěna x0, normála +x (do dutiny)
  q([x1, y1, b], [x1, y1, a], [x1, y0, a], [x1, y0, b]);       // stěna x1, normála −x
  q([x1, y0, b], [x1, y0, a], [x0, y0, a], [x0, y0, b]);       // stěna y0, normála +y
  q([x0, y1, b], [x0, y1, a], [x1, y1, a], [x1, y1, b]);       // stěna y1, normála −y
  return p;
}
// kvádr v z'
export const bx = (mat, name, x0, x1, y0, y1, z0, z1) => box(mat, name, x0, x1, y0, y1, zc(z0), zc(z1));
export const rb = (mat, name, o) => roundedBox(mat, name, { ...o, z0: zc(o.z0), z1: zc(o.z1) });
// extruze obrysu v rovině YZ podél osy X: poly = [[y, z']...]
export function extYZ(mat, name, poly, x0, x1, { crease = 25 } = {}) {
  const p = prism(mat, name, poly.map(([y, z]) => [y, zc(z)]), x0, x1);
  p.mapV((u, v, w) => [w, u, v]); p.crease = crease; return p;
}
// extruze obrysu v rovině XZ podél osy Y: poly = [[x, z']...]; y0..y1
export function extXZ(mat, name, poly, y0, y1, { crease = 25 } = {}) {
  let a = 0; for (let i = 0; i < poly.length; i++) { const p = poly[i], q = poly[(i + 1) % poly.length]; a += p[0] * q[1] - q[0] * p[1]; }
  const P = a < 0 ? poly.slice().reverse() : poly;
  const p = prism(mat, name, P.map(([x, z]) => [x, zc(z)]), y0, y1);
  p.mapV((u, v, w) => [u, w, v]); p.flip(); p.crease = crease; return p;
}
// válec s osou Z (svisle) v z'
export const cylZ = (mat, name, r, z0, z1, x, y, n = 18) => cylinder(mat, name, r, zc(z0), zc(z1), n, [x, y]);
export const mirY = (part, name) => part.clone(name).mirror('y', 0);
