// Víko (čiré, lehce zakouřené) 4932471064: sukně + horní deska s 10 kapsami a středním pruhem, plaketa s logem, těsnění, čelní držáky spon,
// žebírka, pantové články. Samostatná skupina s pivotem na ose pantu (osa −Y; kladný úhel víko otevírá).
import { Group, Part, rrPoly, polyInset, ccw, loftSolid, ext, slab, rrFrame, ringSolid, bx, zc, cylinder, ZC } from './p1064_zaklad.mjs';
import { earcut, flatFace } from './pomocne_4932471064.mjs';
import { H, LID, X, seznam, STRIP } from './p1064_data.mjs';
import { kapsaLoops, pruhLoops, hexMrizka } from './p1064_kapsy.mjs';
import { roundPoly } from './p1064_zaklad.mjs';

export const V = {
  tPl: 1.6,            // tloušťka horní desky a kapes
  tSk: 2.2,            // tloušťka sukně
  rFil: 3.0,           // zaoblení horní hrany
  pD: 11,              // hloubka kapes
  pivot: [10, 0, 42],  // (xp, Y, z') osa pantu
};

// pás (stěna) mezi dvěma smyčkami [x,y,z] stejné délky; spodní smyčka A, horní B (obě CCW podle XY); out = normály od středu smyčky
function band(p, A, B, out = true) {
  const n = A.length, a = A.map(q => p.addV(q[0], q[1], q[2])), b = B.map(q => p.addV(q[0], q[1], q[2]));
  for (let i = 0; i < n; i++) { const j = (i + 1) % n; if (out) p.addQ(a[i], a[j], b[j], b[i]); else p.addQ(a[i], b[i], b[j], a[j]); }
}
const L3 = (poly, z) => poly.map(q => [q[0], q[1], zc(z)]);
const toX = poly => poly.map(([a, b]) => [X(a), b]);

// obrys víka (xp, Y): zaoblený obdélník s výřezem čela (držadlo): notch Y −53 … +45
export function obrysVicka() {
  const L = LID;
  const pts = [[L.xp0, -L.y], [L.xp1, -L.y], [L.xp1, -58], [357, -48], [357, 40], [L.xp1, 49], [L.xp1, L.y], [L.xp0, L.y]];
  return roundPoly(pts.map(([a, b]) => [X(a), b]), [L.rc, L.rc, 0, 0, 0, 0, L.rc, L.rc], 6);
}

export function vicko() {
  const [pxp, py, pz] = V.pivot;
  const g = new Group('vicko', { pivot: [X(pxp), py, zc(pz)], extras: { osa: [0, -1, 0], max_uhel: 110 } });
  const T = H.zTop, S = H.zSeam, t = V.tPl;
  const O = ccw(obrysVicka()), I = polyInset(O, V.tSk);
  // kapsy (rim/floor v plánu → model)
  const kaps = seznam().map(n => ({ n, ...kapsaLoops(n) }));
  const pr = pruhLoops(STRIP, 10, 3);
  const all = [...kaps.map(k => ({ rim: k.rim, floor: k.floor, d: V.pD })), { rim: pr.rim, floor: pr.floor, d: 3 }];
  const rimsM = all.map(k => ccw(toX(k.rim))), floorsM = all.map(k => ccw(toX(k.floor)));

  const p = new Part('vicko_plast', 'vicko_cira'); p.crease = 40;
  // vnější plocha: horní deska s otvory + zaoblení + plášť
  const RF = V.rFil, lay = [[T, RF]];
  for (let k = 1; k <= 3; k++) { const a = Math.PI / 2 * k / 3; lay.push([T - RF + RF * Math.cos(a), RF - RF * Math.sin(a)]); }   // z klesá, odsazení klesá k 0
  lay.push([S, 0]);
  const loops = lay.map(([z, d]) => L3(d > 0 ? polyInset(O, d) : O, z));
  flatFace(p, polyInset(O, RF).map(q => [q[0], q[1]]), rimsM, zc(T), true);
  for (let k = 0; k < loops.length - 1; k++) band(p, loops[k + 1], loops[k], true);
  // spodní okraj sukně (prstenec dolů)
  flatFace(p, O, [I], zc(S), false);
  // vnitřní plocha: sukně dovnitř, spodek desky s otvory
  band(p, L3(I, S), L3(I, T - t), false);
  flatFace(p, I, rimsM, zc(T - t), false);
  // kapsy: stěna (vnější, do kapsy), dno (+Z) a podkapsa (stěna ven + dno −Z)
  all.forEach((k, i) => {
    const rim = rimsM[i], flr = floorsM[i], d = k.d;
    band(p, L3(flr, T - d), L3(rim, T), false);            // povrch stěny (normály do kapsy)
    flatFace(p, flr, [], zc(T - d), true);                  // dno shora
    band(p, L3(flr, T - d - t), L3(rim, T - t), true);      // spodní plocha stěny (ven)
    flatFace(p, flr, [], zc(T - d - t), false);             // dno zespodu
  });
  g.add(p);

  // hexové mřížky na dnech kapsy (plán polygony floor, mírně zmenšené)
  all.forEach((k, i) => {
    const poly = k.floor;
    g.add(hexMrizka('bila', 'vicko_hex', poly, T - k.d + 0.12));
  });
  // plaketa s logem na dně velké kapsy (+Y): obrys se zkosenými rohy (text se nemodeluje)
  g.add(rrFrame('bila', 'vicko_plaketa', { x0: X(145), x1: X(211), y0: 68, y1: 187, z0: T - V.pD + 0.2 - ZC + ZC, z1: T - V.pD + 0.7, w: 0.8, rs: 8, seg: 1 }));
  // těsnění (černá guma) pod víkem po obvodu
  g.add(ringSolid('cerna_mat', 'vicko_tesneni', O.map(q => q), polyInset(O, 4.6), S - 1.2, S + 1.0, { innerWall: true, outerWall: false }));
  // čiré háčky nad západkami (součást víka) a pantové články vzadu
  for (const yc of [-148, 148]) g.add(slab('vicko_cira', 'vicko_hacek', { x0: X(360), x1: X(378), y0: yc - 27, y1: yc + 27, z0: 40, z1: 57, rs: 4, seg: 3, reT: 3, reB: 1.5, fs: 3 }));
  for (const yc of [53.5, 103, 152.5, 201.5]) for (const s of [-1, 1]) g.add(slab('vicko_cira', 'vicko_clanek', { x0: X(5.5), x1: X(17), y0: s * yc - 11, y1: s * yc + 11, z0: 40, z1: 58, rs: 2, seg: 2, reT: 3, reB: 3, fs: 3 }));
  return g;
}
