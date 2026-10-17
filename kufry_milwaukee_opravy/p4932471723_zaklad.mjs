// Společné stavební funkce pro opravené modely Milwaukee PACKOUT 4932471723, 4932471724 a 4932480623 (vlastní generátor, jádro kufriky_cloud/jadro).
// Jednotky mm. Souřadnice modelu: X = šířka (Š), Y = délka (L), Z = výška; počátek = střed obálky. Funkce z kit(V) berou výšky jako z' = výška od země (0..V).
import { Part, Group, loftRings, earClip, roundedBox, prism, cylinder, tube, lathe, box, rrRing } from '../kufriky_cloud/jadro/mesh.js';
import { earcut2 } from './earcut_4932471723.mjs';
export { Part, Group, loftRings, earClip, roundedBox, prism, cylinder, tube, lathe, box, rrRing };

// ---------- 2D obrysy (CCW při pohledu shora) ----------
export const rrPoly = (x0, x1, y0, y1, r, seg = 4) => rrRing((x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2, r, seg);
export function area2(P) { let a = 0; for (let i = 0; i < P.length; i++) { const p = P[i], q = P[(i + 1) % P.length]; a += p[0] * q[1] - q[0] * p[1]; } return a; }
export const ccw = P => area2(P) < 0 ? P.slice().reverse() : P.slice();
export const cw = P => area2(P) > 0 ? P.slice().reverse() : P.slice();
export function ellipsePoly(cx, cy, rx, ry, n = 24) { const P = []; for (let i = 0; i < n; i++) { const a = 2 * Math.PI * i / n; P.push([cx + rx * Math.cos(a), cy + ry * Math.sin(a)]); } return P; }
// obdélník se zkosenými rohy (osmiúhelník)
export function octPoly(x0, x1, y0, y1, c) { return [[x0 + c, y0], [x1 - c, y0], [x1, y0 + c], [x1, y1 - c], [x1 - c, y1], [x0 + c, y1], [x0, y1 - c], [x0, y0 + c]]; }
// zaoblený obdélník s obdélníkovými výřezy v hranách: notches = [{side:'+Y'|'-Y'|'+X'|'-X', a0, a1, d}] (a0<a1 = rozsah podél hrany v mm, d = hloubka dovnitř); počet bodů závisí jen na počtu výřezů
export function planPoly(x0, x1, y0, y1, r, notches = [], seg = 3) {
  r = Math.max(Math.min(r, (x1 - x0) / 2 - 1e-6, (y1 - y0) / 2 - 1e-6), 1e-3);
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, hx = (x1 - x0) / 2, hy = (y1 - y0) / 2;
  const arc = (px, py, a0) => { const o = []; for (let k = 0; k <= seg; k++) { const a = (a0 + 90 * k / seg) * Math.PI / 180; o.push([px + r * Math.cos(a), py + r * Math.sin(a)]); } return o; };
  const N = side => notches.filter(n => n.side === side).sort((a, b) => a.a0 - b.a0);
  const out = [];
  out.push(...arc(cx + hx - r, cy + hy - r, 0));                                                    // roh +X+Y
  for (const n of N('+Y').reverse()) out.push([n.a1, y1], [n.a1, y1 - n.d], [n.a0, y1 - n.d], [n.a0, y1]);   // hrana +Y (jde ve směru -X)
  out.push(...arc(cx - hx + r, cy + hy - r, 90));                                                  // roh -X+Y
  for (const n of N('-X').reverse()) out.push([x0, n.a1], [x0 + n.d, n.a1], [x0 + n.d, n.a0], [x0, n.a0]);    // hrana -X (jde ve směru -Y)
  out.push(...arc(cx - hx + r, cy - hy + r, 180));                                                 // roh -X-Y
  for (const n of N('-Y')) out.push([n.a0, y0], [n.a0, y0 + n.d], [n.a1, y0 + n.d], [n.a1, y0]);           // hrana -Y (jde ve směru +X)
  out.push(...arc(cx + hx - r, cy - hy + r, 270));                                                 // roh +X-Y
  for (const n of N('+X')) out.push([x1, n.a0], [x1 - n.d, n.a0], [x1 - n.d, n.a1], [x1, n.a1]);             // hrana +X (jde ve směru +Y)
  return out;
}
const dedup = ring => { const P = []; ring.forEach(q => { const r = P[P.length - 1]; if (!r || Math.abs(r[0] - q[0]) > 1e-7 || Math.abs(r[1] - q[1]) > 1e-7) P.push([q[0], q[1]]); }); while (P.length > 1 && Math.abs(P[0][0] - P[P.length - 1][0]) < 1e-7 && Math.abs(P[0][1] - P[P.length - 1][1]) < 1e-7) P.pop(); return P; };

export function kit(V) {
  const ZC = V / 2, zc = z => z - ZC;
  const o = {};
  o.zc = zc; o.V = V;
  // víčko polygonu (i konkávního) ve výšce Z modelu
  const capPoly = (part, poly, Z, up) => { const P = dedup(poly); const ids = P.map(q => part.addV(q[0], q[1], Z)); for (const [a, b, c] of earClip(P)) { if (up) part.addT(ids[a], ids[b], ids[c]); else part.addT(ids[a], ids[c], ids[b]); } };
  const capHoles = (part, outer, holes, Z, up) => { const { pts, tris } = earcut2(dedup(outer), holes.map(dedup)); const ids = pts.map(q => part.addV(q[0], q[1], Z)); for (const [a, b, c] of tris) { if (up) part.addT(ids[a], ids[b], ids[c]); else part.addT(ids[a], ids[c], ids[b]); } };
  const wall = (part, ring, z0, z1, flipN = false) => { const n = ring.length; for (let i = 0; i < n; i++) { const j = (i + 1) % n; const a = part.addV(ring[i][0], ring[i][1], z0), b = part.addV(ring[j][0], ring[j][1], z0), c = part.addV(ring[j][0], ring[j][1], z1), d = part.addV(ring[i][0], ring[i][1], z1); if (flipN) part.addQ(a, d, c, b); else part.addQ(a, b, c, d); } };
  // těleso z vrstev: layers = [{z, pts}] (z' zdola nahoru, stejný počet bodů, CCW shora), víčka dole a nahoře
  o.loft = (mat, name, layers, { crease = 35, capB = true, capT = true } = {}) => {
    const p = new Part(name, mat); p.crease = crease;
    const rings = layers.map(L => L.pts.map(q => [q[0], q[1], zc(L.z)]));
    loftRings(p, rings, {});
    if (capB) capPoly(p, rings[0].map(q => [q[0], q[1]]), rings[0][0][2], false);
    if (capT) capPoly(p, rings[rings.length - 1].map(q => [q[0], q[1]]), rings[rings.length - 1][0][2], true);
    return p;
  };
  // deska z obrysu s otvory (otvory = pole obrysů), z0..z1 (z')
  o.slab = (mat, name, outer, holes, z0, z1, { crease = 25 } = {}) => {
    const p = new Part(name, mat); p.crease = crease; const O = ccw(dedup(outer)), H = holes.map(h => cw(dedup(h)));
    const Z0 = zc(z0), Z1 = zc(z1);
    wall(p, O, Z0, Z1); for (const h of H) wall(p, h, Z0, Z1);
    if (H.length) { capHoles(p, O, H, Z1, true); capHoles(p, O, H, Z0, false); } else { capPoly(p, O, Z1, true); capPoly(p, O, Z0, false); }
    return p;
  };
  // zaoblený hranol s volitelným zkosením horní/dolní hrany: horizontální zkosení cT, cB (45°)
  o.blok = (mat, name, { x0, x1, y0, y1, z0, z1, r = 0, cT = 0, cB = 0, seg = 3, crease = 35 }) => {
    const L = [];
    const at = (z, d) => ({ z, pts: rrPoly(x0 + d, x1 - d, y0 + d, y1 - d, Math.max(r - d, 0.3), seg) });
    if (cB > 0) L.push(at(z0, cB)); L.push(at(cB > 0 ? z0 + cB : z0, 0)); if (cT > 0) { L.push(at(z1 - cT, 0)); L.push(at(z1, cT)); } else L.push(at(z1, 0));
    return o.loft(mat, name, L, { crease });
  };
  // ostrý kvádr
  o.bx = (mat, name, x0, x1, y0, y1, z0, z1) => box(mat, name, x0, x1, y0, y1, zc(z0), zc(z1));
  // zaoblený kvádr
  o.rb = (mat, name, a) => roundedBox(mat, name, { ...a, z0: zc(a.z0), z1: zc(a.z1) });
  // válec s osou X, Y nebo Z: ax, poloměr r, rozsah a0..a1 po ose, střed (u,v) v ostatních osách (u,v v pořadí cyklickém: pro X (y,z'), pro Y (z',x)... zjednodušeně zadáváme (c1,c2) = viz níže)
  o.cylX = (mat, name, r, x0, x1, y, z, n = 20) => cylinder(mat, name, r, x0, x1, n, [0, 0]).mapV((u, v, w) => [w, u + y, v + zc(z)]);        // osa X, střed (y, z')
  o.cylY = (mat, name, r, y0, y1, x, z, n = 20) => cylinder(mat, name, r, y0, y1, n, [0, 0]).mapV((u, v, w) => [v + x, w, u + zc(z)]);        // osa Y, střed (x, z')
  o.cylZ = (mat, name, r, z0, z1, x, y, n = 20) => cylinder(mat, name, r, zc(z0), zc(z1), n, [x, y]);                                       // osa Z, střed (x, y)
  // rotační těleso kolem osy Y: prof = [[r, y]...] zdola (od y menšího) po vnější straně, střed (x, z')
  o.latheY = (mat, name, prof, x, z, n = 24) => lathe(mat, name, prof, n, [0, 0, 0]).mapV((u, v, w) => [v + x, w, u + zc(z)]);
  // extruze obrysu v rovině YZ podél X (poly = [[y, z']], x0..x1)
  o.extYZ = (mat, name, poly, x0, x1, { crease = 25 } = {}) => { const P = ccw(poly); const p = prism(mat, name, P.map(([y, z]) => [y, zc(z)]), x0, x1); p.mapV((u, v, w) => [w, u, v]); p.crease = crease; return p; };
  // extruze obrysu v rovině XZ podél Y (poly = [[x, z']], y0..y1)
  o.extXZ = (mat, name, poly, y0, y1, { crease = 25 } = {}) => { const P = ccw(poly); const p = prism(mat, name, P.map(([x, z]) => [x, zc(z)]), y0, y1); p.mapV((u, v, w) => [u, w, v]); p.flip(); p.crease = crease; return p; };
  // extruze obrysu s otvory v rovině YZ podél X (outer, holes = [[y, z']...])
  o.extYZh = (mat, name, outer, holes, x0, x1, { crease = 25 } = {}) => {
    const p = new Part(name, mat); p.crease = crease; const f = P => P.map(([y, z]) => [y, zc(z)]);
    const O = ccw(dedup(f(outer))), H = holes.map(h => cw(dedup(f(h))));
    wall(p, O, x0, x1); for (const h of H) wall(p, h, x0, x1);
    if (H.length) { capHoles(p, O, H, x1, true); capHoles(p, O, H, x0, false); } else { capPoly(p, O, x1, true); capPoly(p, O, x0, false); }
    p.mapV((u, v, w) => [w, u, v]); return p;
  };
  // těleso z vrstev s libovolnými obrysy (polygon se stejným počtem bodů v celé skupině): sloupec = pole {z, pts}
  o.sloupec = (mat, name, layers, opt) => o.loft(mat, name, layers, opt);
  // nosník po cestě (cesta v z')
  o.napis = napisFn(zc);
  o.trubka = (mat, name, path, r, n = 10) => tube(mat, name, path.map(q => [q[0], q[1], zc(q[2])]), r, n);
  return o;
}

// ---------- jednoduché strokové písmo (logo) ----------
// glyphy na mřížce 0..4 (x) × 0..6 (y), polyline = [[x,y],...]; šířka znaku 4, mezera 1.6
const G = {
  M: [[[0, 0], [0, 6], [2, 3], [4, 6], [4, 0]]], I: [[[2, 0], [2, 6]]], L: [[[0, 6], [0, 0], [4, 0]]], W: [[[0, 6], [1, 0], [2, 4], [3, 0], [4, 6]]],
  A: [[[0, 0], [2, 6], [4, 0]], [[0.9, 2.2], [3.1, 2.2]]], U: [[[0, 6], [0, 1], [1, 0], [3, 0], [4, 1], [4, 6]]], K: [[[0, 0], [0, 6]], [[4, 6], [0, 2.5]], [[1.6, 3.7], [4, 0]]],
  E: [[[4, 6], [0, 6], [0, 0], [4, 0]], [[0, 3], [3, 3]]], P: [[[0, 0], [0, 6], [3, 6], [4, 5], [4, 4], [3, 3], [0, 3]]], C: [[[4, 5], [3, 6], [1, 6], [0, 5], [0, 1], [1, 0], [3, 0], [4, 1]]],
  O: [[[1, 0], [0, 1], [0, 5], [1, 6], [3, 6], [4, 5], [4, 1], [3, 0], [1, 0]]], T: [[[0, 6], [4, 6]], [[2, 6], [2, 0]]], 'a': [[[0, 3], [3, 3], [4, 2], [3, 0], [0, 0], [0, 3]]],
};
// text → seznam úseček [[x0,y0,x1,y1]] v jednotkách mm, výška h, počátek vlevo dole; vrací také šířku
export function textSegs(str, h, gap = 1.6) {
  const s = h / 6, segs = []; let x = 0;
  for (const ch of str) {
    if (ch === ' ') { x += 3 * s; continue; }
    const g = G[ch]; if (!g) { x += 5 * s; continue; }
    for (const pl of g) for (let i = 0; i + 1 < pl.length; i++) segs.push([x + pl[i][0] * s, pl[i][1] * s, x + pl[i + 1][0] * s, pl[i + 1][1] * s]);
    x += (4 + gap) * s;
  }
  return { segs, w: x - gap * s };
}
// tahy textu jako tenké hranoly na ploše: plane 'Y+' (čelo +Y), 'Y-', 'X+', 'X-' (čitelné zvenku); u0 = počátek textu vodorovně (ve směru čtení: Y+ → -X, Y- → +X, X+ → +Y, X- → -Y),
// z0 = z' spodní hrany textu, h = výška písma, d = vyvýšení nad plochu `face`, t = tloušťka tahu
export function napisFn(zc) {
  return (mat, name, str, { plane, face, u0, z0, h, d = 0.6, t }) => {
    const { segs } = textSegs(str, h); const tt = t ?? h / 6 * 0.8; const p = new Part(name, mat); p.crease = 5;
    for (const [a, b, c, e] of segs) {
      const dx = c - a, dy = e - b, L = Math.hypot(dx, dy) || 1e-3, nx = -dy / L * tt / 2, ny = dx / L * tt / 2, ex = dx / L * tt / 2, ey = dy / L * tt / 2;
      const q = [[a - ex + nx, b - ey + ny], [c + ex + nx, e + ey + ny], [c + ex - nx, e + ey - ny], [a - ex - nx, b - ey - ny]];
      const poly = ccw(q).map(([u, v]) => [u0 + u, v + z0]);
      const pr = prism(mat, name, poly, 0, d);
      if (plane === 'Y+') pr.mapV((u, z, w) => [-u, face + w, zc(z)]);
      else if (plane === 'Y-') pr.mapV((u, z, w) => [u, face - w, zc(z)]);
      else if (plane === 'X+') pr.mapV((u, z, w) => [face + w, u, zc(z)]);
      else pr.mapV((u, z, w) => [face - w, -u, zc(z)]);
      p.append(pr);
    }
    return p;
  };
}
export const textWidth = (str, h) => textSegs(str, h).w;

// kontrola orientace: znaménkový objem sítě (kladný = normály ven)
export function objem(part) { let v = 0; const P = part.pos, I = part.idx; for (let t = 0; t < I.length; t += 3) { const a = I[t] * 3, b = I[t + 1] * 3, c = I[t + 2] * 3; v += (P[a] * (P[b + 1] * P[c + 2] - P[b + 2] * P[c + 1]) - P[a + 1] * (P[b] * P[c + 2] - P[b + 2] * P[c]) + P[a + 2] * (P[b] * P[c + 1] - P[b + 1] * P[c])) / 6; } return v; }
