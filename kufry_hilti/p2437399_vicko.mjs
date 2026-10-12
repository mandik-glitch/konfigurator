// Víko Hilti ProKit PKC 18-H (2437399): dutý červený plášť s lemem (límec), zkosenou horní hranou a zkosenými rohy, kapsou madla v čele, drážkami nad šrouby;
// černé madlo (šestiúhelník ze c01), šrouby čepů, boční spona vpravo (c01 px 645..715). Víko je samostatná skupina s pivotem na ose pantu (vzadu).
// Vnitřní žebrování víka a těsnění jsou zjednodušeny (nemodelováno) – viz poznámky.
import { Group, vickoPlast, extYZ, bx, rb, cylX, cylinder, prism, zc, pY, pZ } from './p2437399_zaklad.mjs';
import { K, MADLO } from './p2437399_korpus.mjs';

export const V = { zLem0: 239.0, zLem1: 249.0, zBev: 277, zTop: 295, xLem: 194.5, xSk: 188, yLem: 137.5, ySk: 131.5, yF: 100, pivot: [-188, 0, zc(K.zRim + 1.3)] };

const F = (z, xf, xr, y, yF, cfx, rr) => ({ z, xf, xr, y0: -y, y1: y, yF, cfx, rr });
const FRAMES = [
  F(V.zLem0, V.xLem, -V.xSk, V.yLem, 104, 32, 8), F(V.zLem1, V.xLem, -V.xSk, V.yLem, 104, 32, 8),
  F(V.zLem1, V.xSk, -V.xSk, V.ySk, V.yF, 31, 8), F(V.zBev, V.xSk, -V.xSk, V.ySk, V.yF, 31, 8),
  F(V.zTop, 160, -163, 102, 72, 30, 10),         // horní plocha: zkosení hrany ~17 mm × ~29 mm (c01: obrys ±131 → ±102 mezi z' 277 a 295; zkosení v X odhad)
];
// šrouby čepů (c01 px 175 / 566, py 110) a drážky nad nimi (px 165..192 / 552..580, py 50..85)
const SCREW_PX = [175, 566];
const zS = pZ(110);
const SLOTS = [[165, 192], [552, 580]];
const NOTCHES = [
  // kapsa madla pokračuje ze spodního dílu do víka, nahoře se zužuje (c01: madlo py 108..195)
  { fr: [{ z: V.zLem0, y0: -K.hw, y1: K.hw, nx: 159 }, { z: pZ(127), y0: -K.hw, y1: K.hw, nx: 159 }, { z: pZ(108), y0: -53, y1: 53, nx: 159 }] },
  ...SLOTS.map(([a, b]) => ({ fr: [{ z: pZ(85), y0: pY(a), y1: pY(b), nx: 185 }, { z: pZ(50), y0: pY(a), y1: pY(b), nx: 185 }] })),
];

function madlo(g) {
  // černé madlo (šestiúhelník c01) v kapse; zadní strana 1 mm zapuštěná do dna kapsy (x = 159)
  g.add(extYZ('cerna', 'madlo', MADLO, 158, 188.8));
  // zkosený horní okraj madla (světlejší pás v c01 py 108..125) – jen jemný stupeň
  g.add(extYZ('cerna', 'madlo_rant', [[pY(231), pZ(108)], [pY(510), pZ(108)], [pY(526), pZ(120)], [pY(215), pZ(120)]], 188.6, 189.3));
}

function sroubky(g) {
  for (const px of SCREW_PX) {
    const y = pY(px);
    g.add(cylX('cervena', 'sroub_boss', 5.6, 187, 189.8, y, zS, 20));
    g.add(cylX('cerna', 'sroub_hlava', 3.9, 189.5, 190.9, y, zS, 16));
  }
}

const ccw = P => { let a = 0; for (let i = 0; i < P.length; i++) { const p = P[i], q = P[(i + 1) % P.length]; a += p[0] * q[1] - q[0] * p[1]; } return a < 0 ? P.slice().reverse() : P; };
function spona(g) {
  // boční spona vpravo (+Y) na zkoseném rohu víka (c01 px 645..715, py 90..195, na pravém zkosení); tvar a funkce neověřeny – jen přibližný hranol 5 mm před zkosením + tmavé okénko
  const A = [V.xSk, V.yF], B = [V.xSk - 31, V.ySk], e = [B[0] - A[0], B[1] - A[1]], L = Math.hypot(...e), n = [e[1] / L, -e[0] / L];
  const at = (t, d) => [A[0] + e[0] * t + n[0] * d, A[1] + e[1] * t + n[1] * d];
  g.add(prism('cervena', 'spona_vpravo', ccw([at(0.1, -1), at(0.9, -1), at(0.9, 5), at(0.1, 5)]), zc(pZ(195)), zc(pZ(90))));
  g.add(prism('cerna_mat', 'spona_okenko', ccw([at(0.3, 4.8), at(0.7, 4.8), at(0.7, 5.5), at(0.3, 5.5)]), zc(pZ(137)), zc(pZ(104))));
}

function pant(g) {
  // horní (víkové) články pantu – sudé úseky; neověřeno
  const seg = 230 / 5;
  for (let i = 0; i < 5; i += 2) {
    const y0 = -115 + i * seg + 0.6, y1 = -115 + (i + 1) * seg - 0.6;
    g.add(rb('cervena', 'pant_clanek_vicko', { x0: -194.5, x1: -181, y0, y1, z0: 236, z1: 250.5, rc: 3, re: 2, seg: 2, fs: 2 }));
  }
}

export function vicko() {
  const g = new Group('vicko', { pivot: V.pivot, extras: { osa: [0, -1, 0], max_uhel: 110 } });
  g.add(vickoPlast('cervena', 'vicko_plast', { frames: FRAMES, notches: NOTCHES, wall: 3, topT: 3 }));
  madlo(g); sroubky(g); spona(g); pant(g);
  return g;
}
