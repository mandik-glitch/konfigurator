// Společné pomocné funkce pro kufry Hilti 495 × 395 × 149 (2329229 "2-tools (S)" a 2294834 "TE 6-22"). Jednotky mm.
// Souřadnice modelu: X = hloubka (čelo s madlem a západkami do +X), Y = délka 495 (pantová hrana je na zadní straně, X < 0), Z = výška 149 (víko nahoře);
// počátek = střed obálky 395 × 495 × 149. Výšky se v kódu zadávají jako z' = výška nad spodní plochou (0 .. 149); funkce je převedou na Z modelu (z' − 74,5).
// Fotografie c01 jsou POHLEDY SHORA na zavřený kufr s čelem nahoře: vodorovně px → −Y (vpravo na fotografii = −Y), svisle py → X (nahoře = čelo = +X).
// Tvar vzniká "půdorysným loftem": vrstvy půdorysného polygonu (odsazení po vrcholech – mitr) nad sebou; víko = dutý plášť, spodek = vana.
// Tohle je KOPIE přístupu z p2437394_zaklad.mjs (ProKit) upravená pro obecný polygonový půdorys; sdílené soubory se nemění.
import { Part, Group, loftRings, earClip, prism, cylinder, tube, lathe, box, roundedBox } from '../kufriky_cloud/jadro/mesh.js';
export { Part, Group, prism, cylinder, tube, lathe, box, roundedBox };

export const ZC = 74.5;
export const zc = z => z - ZC;

// ---------- převod pixelů fotografie c01 (pohled shora) na mm ----------
// W, H = rozměr fotografie; silueta kufru vyplňuje celou fotografii (bbox 0..W-1, 0..H-1), normalizováno na obálku katalogu 495 × 395.
export function conv(W, H) {
  const sy = 495 / (W - 1), sx = 395 / (H - 1);
  return {
    Y: px => -(px - (W - 1) / 2) * sy,          // vpravo na fotografii = −Y
    X: py => 197.5 - py * sx,                   // nahoře na fotografii = čelo = +X
    pt: ([px, py]) => [197.5 - py * sx, -(px - (W - 1) / 2) * sy],   // [X, Y]
    sy, sx,
  };
}
// pravá polovina polygonu v px (zleva doprava = po směru od středu čela dolů k středu zadní hrany) → zrcadlením vznikne celý polygon (px)
export function mirrorFull(right, W) {
  const cx = (W - 1) / 2, left = right.slice().reverse().map(([x, y]) => [2 * cx - x, y]);
  // pořadí: pravá polovina shora dolů, pak levá zdola nahoru; body přesně na ose (x = cx) se nezdvojují
  const R = right.slice();
  const dropAxis = (arr) => arr.filter(([x]) => Math.abs(x - cx) > 1e-6);
  return [...R, ...dropAxis(left)].filter((p, i, a) => i === 0 || Math.abs(p[0] - a[i - 1][0]) > 1e-9 || Math.abs(p[1] - a[i - 1][1]) > 1e-9);
}

// ---------- 2D polygon ----------
export const area2 = P => { let a = 0; for (let i = 0; i < P.length; i++) { const p = P[i], q = P[(i + 1) % P.length]; a += p[0] * q[1] - q[0] * p[1]; } return a; };
export const ccw = P => area2(P) < 0 ? P.slice().reverse() : P.slice();
export function dedup(P, eps = 1e-3) {
  const o = []; for (const p of P) { const q = o[o.length - 1]; if (!q || Math.hypot(p[0] - q[0], p[1] - q[1]) > eps) o.push(p); }
  while (o.length > 1 && Math.hypot(o[0][0] - o[o.length - 1][0], o[0][1] - o[o.length - 1][1]) <= eps) o.pop();
  return o;
}
// odsazení dovnitř po vrcholech: dfn(i, nx, ny) = vzdálenost (mm) pro vrchol i s vnější normálou (nx, ny); P je CCW
export function inset(P, dfn) {
  const n = P.length, out = [];
  for (let i = 0; i < n; i++) {
    const a = P[(i + n - 1) % n], b = P[i], c = P[(i + 1) % n];
    let e1x = b[0] - a[0], e1y = b[1] - a[1], e2x = c[0] - b[0], e2y = c[1] - b[1];
    const l1 = Math.hypot(e1x, e1y) || 1, l2 = Math.hypot(e2x, e2y) || 1;
    const n1x = e1y / l1, n1y = -e1x / l1, n2x = e2y / l2, n2y = -e2x / l2;
    let mx = n1x + n2x, my = n1y + n2y; const ml = Math.hypot(mx, my);
    if (ml < 1e-6) { mx = n1x; my = n1y; } else { mx /= ml; my /= ml; }
    const cosh = Math.max(mx * n1x + my * n1y, 0.4);
    const d = typeof dfn === 'function' ? dfn(i, mx, my) : dfn;
    out.push([b[0] - mx * d / cosh, b[1] - my * d / cosh]);
  }
  return out;
}
// odsazení s různou hodnotou podle směru vnější normály: čelo (+X), zadní strana (−X), boky (±Y)
export const dirD = (F, S, R) => (i, nx, ny) => { const wF = Math.max(0, nx), wR = Math.max(0, -nx), wS = Math.abs(ny), s = wF + wR + wS || 1; return (wF * F + wR * R + wS * S) / s; };

// ---------- loft ----------
export const toRing = (P, z) => P.map(p => [p[0], p[1], zc(z)]);
export function cap(part, ring, up) {
  const idx = [], P = [];
  ring.forEach((q, i) => { const prev = P[P.length - 1]; if (!prev || Math.abs(prev[0] - q[0]) > 1e-7 || Math.abs(prev[1] - q[1]) > 1e-7) { P.push([q[0], q[1]]); idx.push(i); } });
  while (P.length > 1 && Math.abs(P[0][0] - P[P.length - 1][0]) < 1e-7 && Math.abs(P[0][1] - P[P.length - 1][1]) < 1e-7) { P.pop(); idx.pop(); }
  const ids = P.map((q, i) => part.addV(q[0], q[1], ring[idx[i]][2]));
  for (const [a, b, c] of earClip(P)) { if (up) part.addT(ids[a], ids[b], ids[c]); else part.addT(ids[a], ids[c], ids[b]); }
}
const strip = (part, rings) => { if (rings.length > 1) loftRings(part, rings, {}); };

// vrstvy vnější plochy zdola nahoru: [{z, dfn}] – spodní zaoblení (rB), svislá stěna, horní zaoblení po čtvrtelipse (drop = svislá výška, runs = vodorovné vtažení [čelo, boky, zadek])
export function shellLayers({ z0, z1, rB = 0, drop = 0, runs = [0, 0, 0], N = 5, M = 3 }) {
  const L = [];
  if (rB > 0) for (let k = 0; k <= M; k++) { const t = Math.PI / 2 * k / M; L.push({ z: z0 + rB * (1 - Math.cos(t)), dfn: dirD(rB * (1 - Math.sin(t)), rB * (1 - Math.sin(t)), rB * (1 - Math.sin(t))) }); }
  else L.push({ z: z0, dfn: dirD(0, 0, 0) });
  const zs = z1 - drop;
  if (zs > L[L.length - 1].z + 1e-6) L.push({ z: zs, dfn: dirD(0, 0, 0) });
  for (let k = 1; k <= N && drop > 0; k++) { const t = Math.PI / 2 * k / N, c = 1 - Math.cos(t); L.push({ z: zs + drop * Math.sin(t), dfn: dirD(runs[0] * c, runs[1] * c, runs[2] * c) }); }
  return L;
}
const ringsOf = (P, layers, extra = 0, zShift = null) => layers.map(l => toRing(inset(P, (i, nx, ny) => l.dfn(i, nx, ny) + extra), zShift ? zShift(l.z) : l.z));

// dutý plášť víka otevřený dolů (stěna wall); P = půdorys (CCW), z0 = spodní okraj, z1 = vrch
export function lidShell(mat, name, P, { z0, z1, drop = 8, runs = [8, 8, 8], wall = 3, crease = 40 }) {
  const p = new Part(name, mat); p.crease = crease;
  const Lo = shellLayers({ z0, z1, drop, runs });
  const Ro = ringsOf(P, Lo);
  const Ri = ringsOf(P, Lo, wall, z => z > z1 - drop ? z - wall * (z - (z1 - drop)) / drop : z).reverse();
  strip(p, Ro); strip(p, Ri);
  strip(p, [Ri[Ri.length - 1], Ro[0]]);                     // spodní okraj (zevnitř ven, normála dolů)
  cap(p, Ro[Ro.length - 1], true); cap(p, Ri[0], false);
  return p;
}
// vana (spodní díl) otevřená nahoře: stěna wall, dno floor; groove = vtažení horního okraje (dělicí spára)
export function baseTray(mat, name, P, { z1, rB = 2.5, wall = 3, floor = 3, groove = 0.6, crease = 40 }) {
  const p = new Part(name, mat); p.crease = crease;
  const Lo = shellLayers({ z0: 0, z1, rB });
  Lo.push({ z: z1 - 3, dfn: dirD(0, 0, 0) }); Lo.push({ z: z1 - 2.99, dfn: dirD(groove, groove, groove) }); Lo.push({ z: z1, dfn: dirD(groove, groove, groove) });
  const Ro = ringsOf(P, Lo);
  const Li = [{ z: floor, dfn: dirD(0, 0, 0) }, { z: z1, dfn: dirD(0, 0, 0) }];
  const Ri = ringsOf(P, Li, wall).reverse();
  strip(p, Ro); strip(p, Ri); strip(p, [Ro[Ro.length - 1], Ri[0]]);
  cap(p, Ro[0], false); cap(p, Ri[Ri.length - 1], true);
  return p;
}
// plné těleso z dvou polygonů (spodní Pb v z0, horní Pt v z1; stejný počet a pořadí vrcholů), víčka dole i nahoře
export function lofted(mat, name, Pb, Pt, z0, z1, crease = 35) {
  const p = new Part(name, mat); p.crease = crease;
  const rev = area2(Pb) < 0, a = rev ? Pb.slice().reverse() : Pb.slice(), b = rev ? Pt.slice().reverse() : Pt.slice();
  const Rb = toRing(a, z0), Rt = toRing(b, z1);
  strip(p, [Rb, Rt]); cap(p, Rb, false); cap(p, Rt, true);
  return p;
}
// nízký podstavec (pad) se šikmými boky: spodní polygon B (v z0, pokračuje svisle dolů do zDown, aby nevznikla mezera nad zaoblením desky), horní = B odsazené o runs [čelo, boky, zadek]
export function padLoft(mat, name, B, runs, z0, z1, zDown = z0, crease = 35) {
  const P = ccw(B), T = inset(P, dirD(runs[0], runs[1], runs[2]));
  const p = new Part(name, mat); p.crease = crease;
  const R = [toRing(P, zDown), toRing(P, z0), toRing(T, z1)].filter((r, i, a) => i === 0 || r[0][2] !== a[i - 1][0][2]);
  strip(p, R); cap(p, R[0], false); cap(p, R[R.length - 1], true);
  return p;
}
// hranol z polygonu (model X, Y) ve výškách z' z0..z1
export const extrude = (mat, name, P, z0, z1) => prism(mat, name, P, zc(z0), zc(z1));
// kvádr v z'
export const bx = (mat, name, x0, x1, y0, y1, z0, z1) => box(mat, name, x0, x1, y0, y1, zc(z0), zc(z1));
export const rb = (mat, name, o) => roundedBox(mat, name, { ...o, z0: zc(o.z0), z1: zc(o.z1) });
// válec s osou Y: poloměr r, střed (x, z'), y0..y1
export function cylY(mat, name, r, y0, y1, x, z, n = 18) {
  return cylinder(mat, name, r, y0, y1, n, [0, 0]).mapV((u, v, w) => [u + x, w, v + zc(z)]).flip();
}
