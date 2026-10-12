// Společné pomocné funkce pro modely Makita MAKPAC Typ 1–4 (jeden parametrický generátor, výška V jako parametr). Jednotky mm.
// Souřadnice modelu: X = hloubka 295 (čelo se západkami a madlem do +X), Y = délka 395, Z = výška; počátek = střed obálky 295 × 395 × V.
// Výšky se v kódu zadávají jako z' = výška od spodní plochy (0 .. V); funkce je převedou na Z modelu (z' − V/2) – viz nastavVysku(V).
// Základ: "půdorysný loft" – vrstvy půdorysu (obdélník se zaoblenými rohy a obdélníkovými výřezy v čelní/zadní/koncových stěnách) po výšce,
// stejný princip jako u Hilti PKC 35 (kufry_hilti/p2437394_zaklad.mjs), ale všechny čtyři rohy zaoblené a výřezy na všech čtyřech stranách.
import { Part, Group, loftRings, earClip, roundedBox, prism, cylinder, tube, lathe, box } from '../kufriky_cloud/jadro/mesh.js';
import { earcut2 } from './earcut2.mjs';
import { MATERIALY } from '../kufriky_cloud/jadro/glb.js';
export { Part, Group, roundedBox, prism, cylinder, tube, lathe, box };

// ---------- rozměry společné všem typům (z katalogu makita.cz) ----------
export const D = 395, S = 295;            // délka (Y), hloubka (X)
export const XF = S / 2, XR = -S / 2, YH = D / 2;

// ---------- převod výšky ----------
export let ZC = 0;
export const nastavVysku = V => { ZC = V / 2; };
export const zc = z => z - ZC;

// ---------- interpolace snímků ----------
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

// ---------- půdorys ----------
// Snímek P: {z, xf, xr, y0, y1, rf, rr}: čelní/zadní rovina, okraje v Y, poloměr předních a zadních rohů.
// Výřez (notch): {side:'F'|'B'|'E', fr:[{z, a0, a1, d}, ...]}: strana F = čelo (+X), B = zadní stěna (−X), E = oba konce (±Y, souměrně);
// a0..a1 = rozsah podél strany (u F/B v Y, u E v X), d = hloubka dovnitř od vnějšího povrchu. Výřez je aktivní jen mezi prvním a posledním snímkem.
// w = odsazení dovnitř (stěna) → vnitřní dutina; výřezy se pak rozšíří o w a mají hloubku d od odsazené strany.
const NSEG = 3;
function stav(n, z) {
  const f = n.fr, zA = f[0].z, zB = f[f.length - 1].z, c = (f[0].a0 + f[0].a1) / 2;
  if (z < zA || z > zB) return { on: false, c };
  const q = interp(f, z); return { on: true, a0: q.a0, a1: q.a1, d: q.d, c };
}
// body podél jedné strany od sA do sB; mk(s, d) → [x, y]
function sidePts(list, sA, sB, w, mk) {
  const dir = sB >= sA ? 1 : -1, out = [];
  const L = list.slice().sort((p, q) => dir * (p.c - q.c));
  const first = n => (dir > 0 ? n.a0 - w : n.a1 + w), second = n => (dir > 0 ? n.a1 + w : n.a0 - w);
  const clampMin = (v, lo, hi) => (dir > 0 ? Math.min(Math.max(v, lo), hi) : Math.max(Math.min(v, lo), hi));
  let last = sA;
  L.forEach((n, i) => {
    let a, b, d;
    if (n.on) { a = clampMin(first(n), last, sB); b = clampMin(second(n), a, sB); d = n.d; }
    else {
      let nxt = sB; for (let j = i + 1; j < L.length; j++) if (L[j].on) { nxt = clampMin(first(L[j]), last, sB); break; }
      a = b = clampMin(n.c, last, nxt); d = 0;
    }
    last = b;
    out.push(mk(a, 0), mk(a, d), mk(b, d), mk(b, 0));
  });
  return out;
}
export function planPoly(P, st, w = 0) {
  const xf = P.xf - w, xr = P.xr + w, ya = P.y0 + w, yb = P.y1 - w;
  const rlim = Math.min((xf - xr) / 2, (yb - ya) / 2) - 0.05;
  const rf = Math.max(Math.min(P.rf - w, rlim), 0.05), rr = Math.max(Math.min(P.rr - w, rlim), 0.05);
  const pts = [];
  const arc = (cx, cy, r, a0) => { for (let k = 0; k <= NSEG; k++) { const a = (a0 + 90 * k / NSEG) * Math.PI / 180; pts.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); } };
  for (const q of sidePts(st.F, ya + rf, yb - rf, w, (s, d) => [xf - d, s])) pts.push(q);         // čelo, y vzestupně
  arc(xf - rf, yb - rf, rf, 0);                                                                  // přední roh (+X,+Y)
  for (const q of sidePts(st.E, xf - rf, xr + rr, w, (s, d) => [s, yb - d])) pts.push(q);         // konec +Y, x sestupně
  arc(xr + rr, yb - rr, rr, 90);                                                                 // zadní roh (−X,+Y)
  for (const q of sidePts(st.B, yb - rr, ya + rr, w, (s, d) => [xr + d, s])) pts.push(q);         // zadní stěna, y sestupně
  arc(xr + rr, ya + rr, rr, 180);                                                                // zadní roh (−X,−Y)
  for (const q of sidePts(st.E, xr + rr, xf - rf, w, (s, d) => [s, ya + d])) pts.push(q);         // konec −Y, x vzestupně
  arc(xf - rf, ya + rf, rf, 270);                                                                // přední roh (+X,−Y)
  return pts;
}
// seznam vrstev [{z, pts}] pro dané snímky
export function layers(frames, notches, { w = 0, zmin = -Infinity, zmax = Infinity } = {}) {
  const zs = new Set(frames.map(f => f.z));
  for (const n of notches) for (const f of n.fr) zs.add(f.z);
  let list = [...zs].sort((a, b) => a - b);
  zmin = Math.max(zmin, list[0]); zmax = Math.min(zmax, list[list.length - 1]);
  list = list.filter(z => z > zmin + 1e-9 && z < zmax - 1e-9); list.unshift(zmin); list.push(zmax);
  const out = [];
  const mk = (z, side) => {
    const ze = z + side * EPS, P = interp(frames, ze);
    const st = { F: [], B: [], E: [] };
    for (const n of notches) st[n.side].push(stav(n, ze));
    return { z, pts: planPoly(P, st, w) };
  };
  list.forEach((z, i) => {
    if (i > 0) out.push(mk(z, -1));
    if (i < list.length - 1) out.push(mk(z, +1));
  });
  const same = (a, b) => a.z === b.z && a.pts.length === b.pts.length && a.pts.every((p, i) => Math.abs(p[0] - b.pts[i][0]) < 1e-9 && Math.abs(p[1] - b.pts[i][1]) < 1e-9);
  return out.filter((l, i) => i === 0 || !same(l, out[i - 1]));
}
const toRing = L => L.pts.map(p => [p[0], p[1], zc(L.z)]);
function cap(part, ring, up) {
  const idx = [], P = [];
  ring.forEach((q, i) => { const prev = P[P.length - 1]; if (!prev || Math.abs(prev[0] - q[0]) > 1e-7 || Math.abs(prev[1] - q[1]) > 1e-7) { P.push([q[0], q[1]]); idx.push(i); } });
  while (P.length > 1 && Math.abs(P[0][0] - P[P.length - 1][0]) < 1e-7 && Math.abs(P[0][1] - P[P.length - 1][1]) < 1e-7) { P.pop(); idx.pop(); }
  const ids = P.map((q, i) => part.addV(q[0], q[1], ring[idx[i]][2]));
  for (const [a, b, c] of earClip(P)) { if (up) part.addT(ids[a], ids[b], ids[c]); else part.addT(ids[a], ids[c], ids[b]); }
}
const strip = (part, rings) => { if (rings.length > 1) loftRings(part, rings, {}); };
const dedup = ring => { const P = []; ring.forEach(q => { const r = P[P.length - 1]; if (!r || Math.abs(r[0] - q[0]) > 1e-7 || Math.abs(r[1] - q[1]) > 1e-7) P.push([q[0], q[1]]); }); while (P.length > 1 && Math.abs(P[0][0] - P[P.length - 1][0]) < 1e-7 && Math.abs(P[0][1] - P[P.length - 1][1]) < 1e-7) P.pop(); return P; };
function capHolePoly(part, outer, holes, z, up) {
  const { pts, tris } = earcut2(outer, holes), ids = pts.map(q => part.addV(q[0], q[1], z));
  for (const [a, b, c] of tris) { if (up) part.addT(ids[a], ids[b], ids[c]); else part.addT(ids[a], ids[c], ids[b]); }
}
// obrys půdorysu (CCW) pro snímek P (např. otvor v horní ploše víka); P = {xf, xr, y0, y1, rf, rr}
export function planOutline(P, w = 0) { return planPoly(P, { F: [], B: [], E: [] }, w); }

// plné těleso z půdorysných snímků (víčka dole i nahoře)
export function plocha(mat, name, { frames, notches = [], crease = 35, zmin, zmax }) {
  const p = new Part(name, mat); p.crease = crease;
  const R = layers(frames, notches, { zmin, zmax }).map(toRing);
  strip(p, R); cap(p, R[0], false); cap(p, R[R.length - 1], true);
  return p;
}
// vana otevřená nahoře (stěna wall, dno do výšky floorZ); zmin/zmax ořezávají (společné snímky pro korpus i víko)
export function vana(mat, name, { frames, notches = [], wall = 3, floorZ, crease = 35, zmin, zmax }) {
  const p = new Part(name, mat); p.crease = crease;
  const Lo = layers(frames, notches, { zmin, zmax }), Li = layers(frames, notches, { w: wall, zmin: floorZ, zmax }).reverse();
  const Ro = Lo.map(toRing), Ri = Li.map(toRing);
  strip(p, Ro); strip(p, Ri);
  strip(p, [Ro[Ro.length - 1], Ri[0]]);
  cap(p, Ro[0], false); cap(p, Ri[Ri.length - 1], true);
  return p;
}
// víko: dutý plášť otevřený dolů; holes = [{frame, floor}]: otvor v horní stěně (obrys = planOutline(frame))
export function vickoPlast(mat, name, { frames, notches = [], wall = 3, topT = 3, holes = [], crease = 35, zmin, zmax }) {
  const p = new Part(name, mat); p.crease = crease;
  const Lo = layers(frames, notches, { zmin, zmax }), ztop = Lo[Lo.length - 1].z;
  const Li = layers(frames, notches, { w: wall, zmin, zmax: ztop - topT }).reverse();
  const Ro = Lo.map(toRing), Ri = Li.map(toRing);
  strip(p, Ro); strip(p, Ri);
  strip(p, [Ri[Ri.length - 1], Ro[0]]);
  const H = holes.map(h => planOutline(h).map(q => [q[0], q[1]]));
  if (!H.length) { cap(p, Ro[Ro.length - 1], true); cap(p, Ri[0], false); }
  else {
    capHolePoly(p, dedup(Ro[Ro.length - 1]), H.map(dedup), Ro[Ro.length - 1][0][2], true);
    capHolePoly(p, dedup(Ri[0]), H.map(dedup), Ri[0][0][2], false);
  }
  return p;
}

// ---------- extruze obrysů ----------
const orient = poly => { let a = 0; for (let i = 0; i < poly.length; i++) { const p = poly[i], q = poly[(i + 1) % poly.length]; a += p[0] * q[1] - q[0] * p[1]; } return a < 0 ? poly.slice().reverse() : poly; };
// obrys v rovině YZ (poly = [[y, z']...]) vytažený podél X od x0 do x1
export function extYZ(mat, name, poly, x0, x1, { crease = 25 } = {}) {
  const p = prism(mat, name, orient(poly).map(([y, z]) => [y, zc(z)]), x0, x1);
  p.mapV((u, v, w) => [w, u, v]); p.crease = crease; return p;
}
// obrys v rovině XZ (poly = [[x, z']...]) vytažený podél Y od y0 do y1
export function extXZ(mat, name, poly, y0, y1, { crease = 25 } = {}) {
  const p = prism(mat, name, orient(poly).map(([x, z]) => [x, zc(z)]), y0, y1);
  p.mapV((u, v, w) => [u, w, v]); p.flip(); p.crease = crease; return p;
}
// obrys v rovině XY (poly = [[x, y]...]) vytažený podél Z od z0' do z1'
export function extXY(mat, name, poly, z0, z1, { crease = 25 } = {}) {
  const p = prism(mat, name, orient(poly), zc(z0), zc(z1)); p.crease = crease; return p;
}
// kvádr v z' (ostré hrany) a zaoblený kvádr v z'
export const bx = (mat, name, x0, x1, y0, y1, z0, z1) => box(mat, name, x0, x1, y0, y1, zc(z0), zc(z1));
export const rb = (mat, name, o) => roundedBox(mat, name, { ...o, z0: zc(o.z0), z1: zc(o.z1) });
// válec s osou X (střed y, z')
export function cylX(mat, name, r, x0, x1, y, z, n = 20) { return cylinder(mat, name, r, x0, x1, n, [0, 0]).mapV((u, v, w) => [w, u + y, v + zc(z)]); }
// válec s osou Y (střed x, z')
export function cylY(mat, name, r, y0, y1, x, z, n = 18) { return cylinder(mat, name, r, y0, y1, n, [0, 0]).mapV((u, v, w) => [u + x, w, v + zc(z)]).flip(); }
// válec s osou Z (střed x, y; z0'..z1')
export function cylZ(mat, name, r, z0, z1, x, y, n = 14) { return cylinder(mat, name, r, zc(z0), zc(z1), n, [x, y]); }

// ---------- barvy (jen v paměti tohoto procesu; glb.js se nemění) ----------
// Makita tyrkys: odstín z fotografií (čelní plocha ~ sRGB 0,115–125,132–145 ve světle fotografie, tj. lineárně ~0,0.17–0.20,0.23–0.28); výchozí `tyrkys` z glb.js (0,0.32,0.38) je výrazně světlejší, proto se zde zpřesňuje.
MATERIALY.tyrkys = { color: [0.0, 0.17, 0.24], metallic: 0.0, roughness: 0.65 };
