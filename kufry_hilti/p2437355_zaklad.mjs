// Pomocné funkce pro model Hilti ProKit PKC 19 (2437355) – kopie šablony PKC 35 (p2437394_zaklad.mjs) upravená na tento model. Jednotky mm.
// Souřadnice modelu: X = hloubka (čelo s madlem do +X), Y = délka, Z = výška; počátek = střed obálky 387 × 554 × 168.
// Výšky se v kódu zadávají jako z' = výška od spodní plochy nožek (0 .. 168); funkce je převedou na Z modelu (z' - 84).
// Vlastní generátor: "půdorysný loft" – vrstvy půdorysu (obdélník se zkosenými rohy a výřezy v čelní hraně) po výšce.
import { Part, Group, loftRings, earClip, roundedBox, prism, cylinder, tube, lathe, box } from '../kufriky_cloud/jadro/mesh.js';
import { earcut2 } from './earcut2.mjs';
export { Part, Group, roundedBox, prism, cylinder, tube, lathe, box };

export const ZC = 84;
export const zc = z => z - ZC;

// ---------- převod souřadnic z čelní fotografie L153708 (= c01, zde měřeno ve velikosti 1200 × 365 px) ----------
// vodorovně: 1200 px = 554 mm (okraj lemu víka až po okraj), svisle: 365 px = 168 mm (nahoře temeno víka, dole nožky); střed Y = 0 v px 599,5
export const SXY = 554 / 1200, SZ = 168 / 365;
export const pY = px => (px - 599.5) * SXY;        // px (vodorovně) → Y [mm]
export const pZ = py => (364.5 - py) * SZ;         // py (svisle) → z' [mm]

// ---------- půdorysný loft ----------
const lerp = (a, b, t) => a + (b - a) * t;
function interp(frames, z) {
  if (z <= frames[0].z) return { ...frames[0] };
  const L = frames[frames.length - 1]; if (z >= L.z) return { ...L };
  for (let i = 0; i < frames.length - 1; i++) {
    const a = frames[i], b = frames[i + 1];
    if (z >= a.z && z <= b.z) {
      if (b.z - a.z < 1e-9) return { ...b };
      const t = (z - a.z) / (b.z - a.z), o = {};
      for (const k of Object.keys(a)) o[k] = typeof a[k] === 'number' && typeof b[k] === 'number' ? lerp(a[k], b[k], t) : a[k];
      return o;
    }
  }
  return { ...L };
}
const EPS = 1e-5;

// Parametry půdorysu P: xf (čelo +X), xr (zadní strana), y0, y1 (okraje Y), yF (konec rovné části čelní hrany – zkosení rohu čelo→bok), cfx (hloubka zkosení v X),
// rr (poloměr zadních rohů). Výřezy v čelní hraně: notches = [{ fr: [{z, y0, y1, nx}] }] – aktivní jen mezi prvním a posledním snímkem.
// w = odsazení dovnitř (stěna). Vrací body CCW při pohledu shora; počet bodů závisí jen na počtu výřezů a nSeg.
const NSEG = 3;
// body podél zkoseného rohu (hrana A→B, +Y strana): výřezy {on,t0,t1,d} – t = podíl délky hrany od čelní strany, d = hloubka kolmo dovnitř
function chamferPts(A, B, cns, wx) {
  const ex = B[0] - A[0], ey = B[1] - A[1], L = Math.hypot(ex, ey) || 1, nx = ey / L, ny = -ex / L;   // vnější normála (CCW)
  const at = t => [A[0] + ex * t, A[1] + ey * t], out = [];
  let last = 0;
  cns.forEach((c, i) => {
    let t0, t1, d;
    if (c.on) { t0 = c.t0; t1 = c.t1; d = c.d + wx * 0.7; }
    else { let nxt = Infinity; for (let j = i + 1; j < cns.length; j++) if (cns[j].on) { nxt = cns[j].t0; break; } t0 = t1 = Math.min(Math.max(c.tc, last), nxt); d = 0; }
    t0 = Math.max(t0, last); t1 = Math.max(t1, t0); last = t1;
    const p0 = at(t0), p1 = at(t1);
    out.push(p0, [p0[0] - nx * d, p0[1] - ny * d], [p1[0] - nx * d, p1[1] - ny * d], p1);
  });
  return out;
}
// výřezy v koncové stěně: stav {on,x0,x1,d,xc}; strana +1 = +Y (X sestupně), -1 = -Y (X vzestupně)
function endPts(ens, yE, side, xHi, xLo, wx, wy) {
  const list = ens.slice().sort((a, b) => side > 0 ? b.xc - a.xc : a.xc - b.xc), out = [];
  let last = side > 0 ? xHi : xLo;
  const dir = side > 0 ? -1 : 1, lim = side > 0 ? xLo : xHi;   // směr pohybu v X
  list.forEach((n, i) => {
    let a, b, d;                                                 // a = první (ve směru pohybu), b = druhý okraj výřezu
    if (n.on) { const lo = n.x0 - wx, hi = n.x1 + wx; a = side > 0 ? hi : lo; b = side > 0 ? lo : hi; d = n.d + wy * 0.7; }
    else {
      let nxt = lim; for (let j = i + 1; j < list.length; j++) if (list[j].on) { nxt = side > 0 ? list[j].x1 + wx : list[j].x0 - wx; break; }
      const c = side > 0 ? Math.max(Math.min(n.xc, last), nxt) : Math.min(Math.max(n.xc, last), nxt); a = b = c; d = 0;
    }
    if (side > 0) { a = Math.min(a, last); b = Math.min(b, a); } else { a = Math.max(a, last); b = Math.max(b, a); }
    last = b;
    const sy = side > 0 ? -1 : 1;                                // dovnitř = k středu
    out.push([a, yE], [a, yE + sy * d], [b, yE + sy * d], [b, yE]);
  });
  return out;
}
function enState(n, zEval) {
  const f = n.fr, zA = f[0].z, zB = f[f.length - 1].z, xc = (f[0].x0 + f[0].x1) / 2;
  if (zEval < zA || zEval > zB) return { on: false, xc };
  const q = interp(f, zEval); return { on: true, x0: q.x0, x1: q.x1, d: q.d, xc };
}
function planPoly(P, ns, w = 0, cns = [], ens = []) {
  const NS = P.ns ?? NSEG;
  const wx = w ? (P.wx ?? w) : 0, wy = w ? (P.wy ?? w) : 0;          // tloušťka stěny v X (čelo/zadek) a v Y (konce); snímky mohou mít vlastní wx, wy
  const xf = P.xf - wx, xr = P.xr + wx, ya = P.y0 + wy, yb = P.y1 - wy;
  const yF = Math.min(P.yF - wy * 0.5, yb - 0.05), yFa = Math.max(-P.yF + wy * 0.5, ya + 0.05);
  const cfx = Math.max(Math.min(P.cfx - wx * 0.3, xf - xr - 1), 0.05);
  const rr = Math.max(Math.min(P.rr - Math.min(wx, wy), (yb - ya) / 2 - 0.1), 0.05);
  const pts = [];
  pts.push([xf, yFa]);
  let lastY = yFa;
  // nejdřív okraje aktivních výřezů, aby neaktivní (sbalené) výřezy zůstaly mezi sousedy ve správném pořadí
  const act = ns.map(n => n.on ? { y0: n.y0 - wy, y1: n.y1 + wy, nx: Math.min(n.nx - wx, xf) } : null);
  ns.forEach((n, i) => {
    let y0, y1, nx;
    if (act[i]) { ({ y0, y1, nx } = act[i]); }
    else {
      let nxt = Infinity; for (let j = i + 1; j < ns.length; j++) if (act[j]) { nxt = act[j].y0; break; }
      y0 = y1 = Math.min(Math.max(n.yc, lastY), nxt); nx = xf;
    }
    y0 = Math.max(y0, lastY); y1 = Math.max(y1, y0); lastY = y1;
    pts.push([xf, y0], [nx, y0], [nx, y1], [xf, y1]);
  });
  const A = [xf, Math.max(yF, lastY)], B = [xf - cfx, yb];
  pts.push(A); for (const q of chamferPts(A, B, cns, wx)) pts.push(q); pts.push(B);
  // koncová stěna +Y (od čela dozadu): výřezy podle X sestupně
  for (const q of endPts(ens, yb, +1, xf - cfx, xr + rr, wx, wy)) pts.push(q);
  // +Y strana → zadní roh (+Y,-X)
  for (let k = 0; k <= NS; k++) { const a = (90 + 90 * k / NS) * Math.PI / 180; pts.push([xr + rr + rr * Math.cos(a), yb - rr + rr * Math.sin(a)]); }
  for (let k = 0; k <= NS; k++) { const a = (180 + 90 * k / NS) * Math.PI / 180; pts.push([xr + rr + rr * Math.cos(a), ya + rr + rr * Math.sin(a)]); }
  // koncová stěna -Y (od zadní strany k čelu): výřezy podle X vzestupně
  for (const q of endPts(ens, ya, -1, xf - cfx, xr + rr, wx, wy)) pts.push(q);
  pts.push([xf - cfx, ya]);
  const mir = chamferPts([xf, -yFa], [xf - cfx, -ya], cns, wx).map(q => [q[0], -q[1]]).reverse();
  for (const q of mir) pts.push(q);
  return pts;
}
function notchState(n, zEval) {
  const f = n.fr, zA = f[0].z, zB = f[f.length - 1].z;
  const yc = (f[0].y0 + f[0].y1) / 2;
  if (zEval < zA || zEval > zB) return { on: false, yc };
  const q = interp(f, zEval); return { on: true, y0: q.y0, y1: q.y1, nx: q.nx, yc };
}
function cnState(n, zEval) {
  const f = n.fr, zA = f[0].z, zB = f[f.length - 1].z, tc = (f[0].t0 + f[0].t1) / 2;
  if (zEval < zA || zEval > zB) return { on: false, tc };
  const q = interp(f, zEval); return { on: true, t0: q.t0, t1: q.t1, d: q.d, tc };
}
// seznam vrstev [{z, pts}] pro dané snímky; w = odsazení; zmin/zmax ořez; cnotches = výřezy ve zkosených rozích (obě strany souměrně)
function layers(frames, notches, { w = 0, zmin = -Infinity, zmax = Infinity, cnotches = [], enotches = [] } = {}) {
  const zs = new Set(frames.map(f => f.z));
  for (const n of notches) for (const f of n.fr) zs.add(f.z);
  for (const n of cnotches) for (const f of n.fr) zs.add(f.z);
  for (const n of enotches) for (const f of n.fr) zs.add(f.z);
  let list = [...zs].sort((a, b) => a - b);
  zmin = Math.max(zmin, list[0]); zmax = Math.min(zmax, list[list.length - 1]);
  list = list.filter(z => z > zmin + 1e-9 && z < zmax - 1e-9); list.unshift(zmin); list.push(zmax);
  const out = [];
  const mk = (z, side) => {
    const ze = z + side * EPS, P = interp(frames, ze);
    return { z, pts: planPoly(P, notches.map(n => notchState(n, ze)), w, cnotches.map(n => cnState(n, ze)), enotches.map(n => enState(n, ze))) };
  };
  list.forEach((z, i) => {
    if (i > 0) out.push(mk(z, -1));
    if (i < list.length - 1) out.push(mk(z, +1));
  });
  // odstranit totožné po sobě jdoucí vrstvy
  const same = (a, b) => a.z === b.z && a.pts.length === b.pts.length && a.pts.every((p, i) => Math.abs(p[0] - b.pts[i][0]) < 1e-9 && Math.abs(p[1] - b.pts[i][1]) < 1e-9);
  return out.filter((l, i) => i === 0 || !same(l, out[i - 1]));
}
const toRing = L => L.pts.map(p => [p[0], p[1], zc(L.z)]);
function cap(part, ring, up) {
  // víčko pro (i konkávní) prstenec; duplicitní body se vynechají
  const idx = [], P = [];
  ring.forEach((q, i) => { const prev = P[P.length - 1]; if (!prev || Math.abs(prev[0] - q[0]) > 1e-7 || Math.abs(prev[1] - q[1]) > 1e-7) { P.push([q[0], q[1]]); idx.push(i); } });
  while (P.length > 1 && Math.abs(P[0][0] - P[P.length - 1][0]) < 1e-7 && Math.abs(P[0][1] - P[P.length - 1][1]) < 1e-7) { P.pop(); idx.pop(); }
  const ids = P.map((q, i) => part.addV(q[0], q[1], ring[idx[i]][2]));
  for (const [a, b, c] of earClip(P)) { if (up) part.addT(ids[a], ids[b], ids[c]); else part.addT(ids[a], ids[c], ids[b]); }
}
// pás mezi sledem prstenců (bez víček)
const strip = (part, rings, closed = false) => { if (rings.length > 1) loftRings(part, rings, { closed }); };

// plné těleso z půdorysných snímků (víčka dole i nahoře)
export function plocha(mat, name, { frames, notches = [], cnotches = [], enotches = [], crease = 35, zmin, zmax }) {
  const p = new Part(name, mat); p.crease = crease;
  const Ls = layers(frames, notches, { zmin, zmax, cnotches, enotches }), R = Ls.map(toRing);
  strip(p, R); cap(p, R[0], false); cap(p, R[R.length - 1], true);
  return p;
}
// vana otevřená nahoře (stěna wall, dno do výšky floorZ nad spodní plochou)
export function vana(mat, name, { frames, notches = [], cnotches = [], enotches = [], wall = 3.5, floorZ, crease = 35 }) {
  const p = new Part(name, mat); p.crease = crease;
  const Lo = layers(frames, notches, { cnotches, enotches }), Li = layers(frames, notches, { w: wall, zmin: floorZ, cnotches, enotches }).reverse();
  const Ro = Lo.map(toRing), Ri = Li.map(toRing);
  strip(p, Ro); strip(p, Ri);
  strip(p, [Ro[Ro.length - 1], Ri[0]]);                  // okraj nahoře (z vnější na vnitřní stranu)
  cap(p, Ro[0], false); cap(p, Ri[Ri.length - 1], true);
  return p;
}
// obrys půdorysu (CCW) pro snímek P (např. otvor v horní ploše víka)
export function planOutline(P, w = 0) { return planPoly(P, [], w, [], []); }
// víčko s dírou (vnější polygon + otvory) triangulované přes earcut2; z = výška v modelu, up = normála nahoru
function capHolePoly(part, outer, holes, z, up) {
  const { pts, tris } = earcut2(outer, holes), ids = pts.map(q => part.addV(q[0], q[1], z));
  for (const [a, b, c] of tris) { if (up) part.addT(ids[a], ids[b], ids[c]); else part.addT(ids[a], ids[c], ids[b]); }
}
// víko: dutý plášť otevřený dolů (stěna wall, horní stěna topT); holes = [{frame, wall}] otvory v horní stěně (obrys = planOutline(frame))
export function vickoPlast(mat, name, { frames, notches = [], cnotches = [], enotches = [], wall = 3, topT = 3, holes = [], crease = 35 }) {
  const p = new Part(name, mat); p.crease = crease;
  const Lo = layers(frames, notches, { cnotches, enotches }), ztop = Lo[Lo.length - 1].z;
  const Li = layers(frames, notches, { w: wall, zmax: ztop - topT, cnotches, enotches }).reverse();
  const Ro = Lo.map(toRing), Ri = Li.map(toRing);
  strip(p, Ro); strip(p, Ri);
  strip(p, [Ri[Ri.length - 1], Ro[0]]);                  // spodní okraj (zevnitř ven, normála dolů)
  const H = holes.map(h => planOutline(h).map(q => [q[0], q[1]]));
  const dedup = ring => { const P = []; ring.forEach(q => { const r = P[P.length - 1]; if (!r || Math.abs(r[0] - q[0]) > 1e-7 || Math.abs(r[1] - q[1]) > 1e-7) P.push([q[0], q[1]]); }); while (P.length > 1 && Math.abs(P[0][0] - P[P.length - 1][0]) < 1e-7 && Math.abs(P[0][1] - P[P.length - 1][1]) < 1e-7) P.pop(); return P; };
  if (!H.length) { cap(p, Ro[Ro.length - 1], true); cap(p, Ri[0], false); }
  else {
    capHolePoly(p, dedup(Ro[Ro.length - 1]), H.map(dedup), Ro[Ro.length - 1][0][2], true);
    capHolePoly(p, dedup(Ri[0]), H.map(dedup), Ri[0][0][2], false);
  }
  return p;
}

// ---------- extruze obrysu v rovině YZ podél osy X ----------
// poly = [[y, z']...] (CCW při pohledu z +X: y doprava, z' nahoru), x0..x1 = rozsah po X
export function extYZ(mat, name, poly, x0, x1, { crease = 25 } = {}) {
  let a = 0; for (let i = 0; i < poly.length; i++) { const p = poly[i], q = poly[(i + 1) % poly.length]; a += p[0] * q[1] - q[0] * p[1]; }
  const P = a < 0 ? poly.slice().reverse() : poly;
  const p = prism(mat, name, P.map(([y, z]) => [y, zc(z)]), x0, x1);
  p.mapV((u, v, w) => [w, u, v]); p.crease = crease;
  return p;
}
// extruze obrysu v rovině XZ podél osy Y: poly = [[x, z']...] CCW při pohledu z -Y (x doprava, z' nahoru), y0..y1
export function extXZ(mat, name, poly, y0, y1, { crease = 25 } = {}) {
  let a = 0; for (let i = 0; i < poly.length; i++) { const p = poly[i], q = poly[(i + 1) % poly.length]; a += p[0] * q[1] - q[0] * p[1]; }
  const P = a < 0 ? poly.slice().reverse() : poly;
  const p = prism(mat, name, P.map(([x, z]) => [x, zc(z)]), y0, y1);
  p.mapV((u, v, w) => [u, w, v]); p.flip(); p.crease = crease;
  return p;
}
// kvádr v z' (ostré hrany) a zaoblený kvádr v z'
export const bx = (mat, name, x0, x1, y0, y1, z0, z1) => box(mat, name, x0, x1, y0, y1, zc(z0), zc(z1));
export const rb = (mat, name, o) => roundedBox(mat, name, { ...o, z0: zc(o.z0), z1: zc(o.z1) });
// válec s osou X (čelo ve směru +X): střed (y, z'), poloměr r, x0..x1
export function cylX(mat, name, r, x0, x1, y, z, n = 20) {
  return cylinder(mat, name, r, x0, x1, n, [0, 0]).mapV((u, v, w) => [w, u + y, v + zc(z)]);
}
// pozor: cylinder() je osa Z → mapV (u,v,w) = (x,y,z) → nové (x,y,z) = (w, u, v): osa Z → osa X; cyklická permutace zachovává orientaci
// kruhový/zkosený obrys v YZ: osmiúhelník – obdélník y0..y1, z0..z1 s zkosenými rohy c
export function oct(y0, y1, z0, z1, cT = 0, cB = 0) {
  return [[y0 + cB, z0], [y1 - cB, z0], [y1, z0 + cB], [y1, z1 - cT], [y1 - cT, z1], [y0 + cT, z1], [y0, z1 - cT], [y0, z0 + cB]];
}
