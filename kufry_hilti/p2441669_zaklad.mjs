// Pomocné funkce pro model Hilti ProKit PKC 37-O (2441669, otevřená přepravka bez víka). Jednotky mm.
// Souřadnice modelu: X = hloubka 378 (čelo s logem do +X), Y = délka 545, Z = výška 279; počátek = střed obálky.
// Výšky se v kódu zadávají jako z' = výška od spodní plochy nožek (0 .. 279); funkce je převedou na Z modelu (z' - 139,5).
// Vlastní generátor (stejná myšlenka jako p2437394_zaklad.mjs): "půdorysný loft" - vrstvy půdorysu (osmiúhelník = obdélník se zkosenými rohy)
// po výšce, jen s obecnějšími výřezy: kapsy v LIBOVOLNÉ ze 4 stěn a průchozí otvor (madlo v koncové stěně).
import { Part, Group, loftRings, earClip, roundedBox, prism, cylinder, tube, lathe, box } from '../kufriky_cloud/jadro/mesh.js';
export { Part, Group, roundedBox, prism, cylinder, tube, lathe, box };

export const ZC = 139.5;
export const zc = z => z - ZC;

// ---------- převod souřadnic z čelní fotografie c01 (800 × 410 px, těsně oříznutá na obrys) ----------
// 800 px = 545 mm (rozpětí lemu), 409,6 px = 279 mm (od nožek po horní hranu) - stejné měřítko ve směru x i y
export const SC = 545 / 800;
export const pY = px => (px - 399.5) * SC;          // px (vodorovně) -> Y [mm]
export const pZ = py => (409.6 - py) * SC;          // py (svisle) -> z' [mm]

const lerp = (a, b, t) => a + (b - a) * t;
const EPS = 1e-5;
const BIG = 1e6;                                     // "žádná hloubka" (výřez neaktivní = bod leží na hraně)

// ---------- snímky půdorysu: {z, hx, hy, c} (poloviční rozměry X, Y a zkosení rohů) ----------
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

// ---------- výřezy ----------
// Vlastnosti (feature): {e:'+X'|'+Y'|'-X'|'-Y', s0, s1, z0, z1, at, ring:'o'|'i'|'oi', thru?}
//  e = stěna (+X čelo, -X zadní, +Y/-Y konce); s0..s1 = rozsah podél stěny ve SVĚTOVÝCH souřadnicích (Y u ±X, X u ±Y);
//  z0..z1 = výška z'; at = absolutní poloha dna výřezu (číslo, nebo funkce výšky z' → poloha; mezi z0 a z1 se interpoluje lineárně) (vzdálenost od osy kolmo na stěnu; kapsa sahá od stěny k dnu);
//  ring: 'o' vnější plocha, 'i' vnitřní (dutina), 'oi' obě (průchozí otvor: u thru se plochy dna výřezu odstraní -> otvor je průchozí).
// Z vlastností se pro každou stěnu vytvoří disjunktní buňky (rozsahy s) - to je podmínka platného půdorysu (výřezy se nesmí překrývat).
const EDGE = {
  '+X': { n: [1, 0], u: [0, 1], axisN: 0 },
  '+Y': { n: [0, 1], u: [-1, 0], axisN: 1 },
  '-X': { n: [-1, 0], u: [0, -1], axisN: 0 },
  '-Y': { n: [0, -1], u: [1, 0], axisN: 1 },
};
const EDGE_ORDER = ['+X', '+Y', '-X', '-Y'];
const sgn = e => (e === '+X' || e === '-Y') ? 1 : -1;      // t = sgn * s (poloha podél u z poloh ve světových souřadnicích)

export function buildCells(features) {
  const cells = {};
  for (const e of EDGE_ORDER) {
    const fs = features.filter(f => f.e === e);
    if (!fs.length) { cells[e] = []; continue; }
    const bp = [...new Set(fs.flatMap(f => [f.s0, f.s1]))].sort((a, b) => a - b);
    const list = [];
    for (let i = 0; i < bp.length - 1; i++) {
      const a = bp[i], b = bp[i + 1], mid = (a + b) / 2;
      const cov = fs.filter(f => f.s0 <= mid && mid <= f.s1);
      if (!cov.length) continue;
      const mk = ring => {
        const fr = cov.filter(f => f.ring.includes(ring)).sort((p, q) => p.z0 - q.z0);
        for (let k = 1; k < fr.length; k++) if (fr[k].z0 < fr[k - 1].z1 - 1e-9) throw new Error(`výřezy se překrývají (stěna ${e}, s ${a}..${b}, z' ${fr[k].z0})`);
        const frames = [];
        for (const f of fr) {
          const off = ring === 'o' ? BIG : -BIG;                  // "žádná hloubka": vnější plocha → +BIG (kapsa dovnitř), vnitřní → -BIG (kapsa ven do stěny)
          const a0 = typeof f.at === 'function' ? f.at(f.z0) : f.at, a1 = typeof f.at === 'function' ? f.at(f.z1) : f.at;   // at může být funkce výšky (stěna se svažuje)
          frames.push({ z: f.z0, at: off, thru: 0 }, { z: f.z0, at: a0, thru: f.thru ? 1 : 0 }, { z: f.z1, at: a1, thru: f.thru ? 1 : 0 }, { z: f.z1, at: off, thru: 0 });
        }
        return frames;
      };
      list.push({ s0: a, s1: b, o: mk('o'), i: mk('i') });
    }
    cells[e] = list;
  }
  return cells;
}
function cellState(fr, ze) {
  if (!fr.length || ze < fr[0].z || ze > fr[fr.length - 1].z) return { at: null, thru: false };
  const q = interp(fr, ze);
  return { at: q.at, thru: q.thru > 0.999 };
}

// body půdorysného prstence pro snímek P a stavy výřezů; vrací {pts, tags} (tags[i] = true pro body dna průchozího výřezu)
function ringPts(P, cells, ze, which) {
  const out = [], tags = [];
  const push = (x, y, tag = false) => { out.push([x, y]); tags.push(tag); };
  for (const e of EDGE_ORDER) {
    const { n, u, axisN } = EDGE[e];
    const dist = axisN === 0 ? P.hx : P.hy, half = (axisN === 0 ? P.hy : P.hx) - P.c;
    const W = (d, t) => [n[0] * d + u[0] * t, n[1] * d + u[1] * t];
    push(...W(dist, -half));
    const sg = sgn(e);
    const ns = cells[e].map(c => {
      const t0 = Math.max(-half, Math.min(half, sg * c.s0)), t1 = Math.max(-half, Math.min(half, sg * c.s1));
      const st = cellState(which === 'o' ? c.o : c.i, ze);
      const bottom = st.at === null ? dist : which === 'o' ? Math.min(st.at, dist) : Math.max(st.at, dist);
      return { ta: Math.min(t0, t1), tb: Math.max(t0, t1), bottom, thru: st.thru && bottom !== dist };
    }).sort((a, b) => a.ta - b.ta);
    for (const c of ns) {
      push(...W(dist, c.ta)); push(...W(c.bottom, c.ta), c.thru); push(...W(c.bottom, c.tb), c.thru); push(...W(dist, c.tb));
    }
    push(...W(dist, half));
  }
  return { pts: out, tags };
}

// seznam vrstev [{z, pts, tags}]
function layers(frames, cells, which, { zmin = -Infinity, zmax = Infinity } = {}) {
  const zs = new Set(frames.map(f => f.z));
  for (const e of EDGE_ORDER) for (const c of cells[e]) for (const f of (which === 'o' ? c.o : c.i)) zs.add(f.z);
  let list = [...zs].sort((a, b) => a - b);
  zmin = Math.max(zmin, list[0]); zmax = Math.min(zmax, list[list.length - 1]);
  list = list.filter(z => z > zmin + 1e-9 && z < zmax - 1e-9); list.unshift(zmin); list.push(zmax);
  const out = [];
  const mk = (z, side) => { const ze = z + side * EPS; const r = ringPts(interp(frames, ze), cells, ze, which); return { z, pts: r.pts, tags: r.tags }; };
  list.forEach((z, i) => { if (i > 0) out.push(mk(z, -1)); if (i < list.length - 1) out.push(mk(z, +1)); });
  const same = (a, b) => a.z === b.z && a.pts.every((p, i) => Math.abs(p[0] - b.pts[i][0]) < 1e-9 && Math.abs(p[1] - b.pts[i][1]) < 1e-9);
  return out.filter((l, i) => i === 0 || !same(l, out[i - 1]));
}
const toRing = L => L.pts.map(p => [p[0], p[1], zc(L.z)]);

// víčko pro (i konkávní) prstenec; zdvojené body a zpětné "špičky" (kolineární) se vynechají
function cleanPoly(ring) {
  let P = [];
  for (const q of ring) { const r = P[P.length - 1]; if (!r || Math.abs(r[0] - q[0]) > 1e-7 || Math.abs(r[1] - q[1]) > 1e-7) P.push([q[0], q[1]]); }
  while (P.length > 1 && Math.abs(P[0][0] - P[P.length - 1][0]) < 1e-7 && Math.abs(P[0][1] - P[P.length - 1][1]) < 1e-7) P.pop();
  let ch = true;
  while (ch && P.length > 3) {
    ch = false;
    for (let i = 0; i < P.length; i++) {
      const a = P[(i + P.length - 1) % P.length], b = P[i], c = P[(i + 1) % P.length];
      const cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]);
      if (Math.abs(cr) < 1e-9) { P.splice(i, 1); ch = true; break; }
    }
  }
  return P;
}
function cap(part, ring, up, z) {
  const P = cleanPoly(ring);
  const ids = P.map(q => part.addV(q[0], q[1], z));
  for (const [a, b, c] of earClip(P)) { if (up) part.addT(ids[a], ids[b], ids[c]); else part.addT(ids[a], ids[c], ids[b]); }
}

// vana otevřená nahoře: vnější frames, vnitřní dutina innerFrames od floorZ; features = výřezy (viz výše)
// Průchozí výřezy (thru) se zpracují tak, že se odstraní trojúhelníky dna výřezu (vnější i vnitřní plocha splývají v rovině at).
export function vana(mat, name, { frames, innerFrames, floorZ, features = [], crease = 35 }) {
  const cells = buildCells(features);
  const p = new Part(name, mat); p.crease = crease;
  const Lo = layers(frames, cells, 'o'), Li = layers(innerFrames, cells, 'i', { zmin: floorZ }).reverse();
  const nPts = Lo[0].pts.length;
  if (Li[0].pts.length !== nPts) throw new Error('různý počet bodů vnějšího a vnitřního prstence');
  const tagged = new Set();
  const addStrip = (L) => {
    const off = p.nv, R = L.map(toRing);
    if (R.length > 1) loftRings(p, R);
    else R[0].forEach(q => p.addV(q[0], q[1], q[2]));
    L.forEach((l, k) => l.tags.forEach((t, i) => { if (t) tagged.add(off + k * nPts + i); }));
    return R;
  };
  const Ro = addStrip(Lo), Ri = addStrip(Li);
  loftRings(p, [Ro[Ro.length - 1], Ri[0]]);                      // horní okraj (z vnější na vnitřní stranu)
  cap(p, Ro[0].map(q => [q[0], q[1]]), false, Ro[0][0][2]);
  cap(p, Ri[Ri.length - 1].map(q => [q[0], q[1]]), true, Ri[Ri.length - 1][0][2]);
  if (tagged.size) {
    const keep = [];
    for (let i = 0; i < p.idx.length; i += 3) {
      const a = p.idx[i], b = p.idx[i + 1], c = p.idx[i + 2];
      if (tagged.has(a) && tagged.has(b) && tagged.has(c)) continue;
      keep.push(a, b, c);
    }
    p.idx = keep;
  }
  return p;
}

// plné těleso z půdorysných snímků (víčka dole i nahoře); bez výřezů
export function plocha(mat, name, { frames, crease = 35 }) {
  const cells = buildCells([]);
  const p = new Part(name, mat); p.crease = crease;
  const R = layers(frames, cells, 'o').map(toRing);
  loftRings(p, R); cap(p, R[0].map(q => [q[0], q[1]]), false, R[0][0][2]); cap(p, R[R.length - 1].map(q => [q[0], q[1]]), true, R[R.length - 1][0][2]);
  return p;
}

// ---------- extruze obrysu v rovině YZ podél osy X ----------
// poly = [[y, z']...] (libovolné pořadí), x0..x1 = rozsah po X
export function extYZ(mat, name, poly, x0, x1, { crease = 25 } = {}) {
  let a = 0; for (let i = 0; i < poly.length; i++) { const p = poly[i], q = poly[(i + 1) % poly.length]; a += p[0] * q[1] - q[0] * p[1]; }
  const P = a < 0 ? poly.slice().reverse() : poly;
  const p = prism(mat, name, P.map(([y, z]) => [y, zc(z)]), x0, x1);
  p.mapV((u, v, w) => [w, u, v]); p.crease = crease;
  return p;
}
// kvádr v z' (ostré hrany) a zaoblený kvádr v z'
export const bx = (mat, name, x0, x1, y0, y1, z0, z1) => box(mat, name, x0, x1, y0, y1, zc(z0), zc(z1));
export const rb = (mat, name, o) => roundedBox(mat, name, { ...o, z0: zc(o.z0), z1: zc(o.z1) });
// válec s osou X: střed (y, z'), poloměr r, x0..x1
export function cylX(mat, name, r, x0, x1, y, z, n = 20) {
  return cylinder(mat, name, r, x0, x1, n, [0, 0]).mapV((u, v, w) => [w, u + y, v + zc(z)]);
}
