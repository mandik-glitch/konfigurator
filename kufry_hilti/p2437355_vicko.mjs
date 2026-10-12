// Víko Hilti ProKit PKC 19 (2437355): dutý červený plášť s lemem, zkosenou horní hranou, výřezem madla v čele, drážkami nad šrouby;
// černá horní příčka madla, šrouby čepů západek, zadní (pantová) hrana. Víko je samostatná skupina s pivotem na ose pantu (vzadu).
// Vnitřní žebrování víka je zjednodušeno (nemodelováno) – viz poznámky.
import { Group, vickoPlast, plocha, extYZ, extXZ, bx, rb, cylX, cylinder, tube, zc, pY, pZ } from './p2437355_zaklad.mjs';
import { K, Y_HANDLE, X_REC } from './p2437355_korpus.mjs';

// zLem0/1 = lem víka (c01 py 88..108 → z' 118,2..127,3, plná šířka ±277), zBev = horní hrana svislého pláště (py 40 → 149,4), zTop = temeno (c01 py 0 → 167,8)
export const V = { zLem0: 118.1, zLem1: 127.9, zBev: 149.4, zP: 160, zTop: 168, xPl: 160, xPr: -118, xLem: 193.5, xSk: 187, xRr: -191, ySk: 271.5, yLem: 277, pivot: [-187, 0, zc(K.zRim + 1.5)] };

const F = (z, xf, xr, y, yF, cfx, rr) => ({ z, xf, xr, y0: -y, y1: y, yF, cfx, rr });
// zkosení konců víka: y 271 (z' 149,4) → 243,1 (z' 167,8), sklon 1,52 mm/mm (c01 obrys); u zP = 160 je y = 254,9; zkosení čela a zadní rampa jsou odhad (neověřeno)
const FRAMES = [
  F(V.zLem0, V.xLem, V.xRr, V.yLem, 244, 22, 8), F(V.zLem1, V.xLem, V.xRr, V.yLem, 244, 22, 8),
  F(V.zLem1, V.xSk, V.xRr, V.ySk, K.yC, 26, 8), F(V.zBev, V.xSk, V.xRr, V.ySk, K.yC, 26, 8),
  F(V.zP, V.xPl, V.xPr, 254.9, 220, 20, 10),
];
// šrouby čepů západek (c01 px 135, 311, 889, 1065; py 72) a drážky nad nimi (7 mm široké, z' 140,6..148,5)
const SCREW_PX = [135, 311, 889, 1065];
const zS = pZ(72);
const slot = px => ({ fr: [{ z: 140.6, y0: pY(px) - 3.7, y1: pY(px) + 3.7, nx: 184 }, { z: 148.5, y0: pY(px) - 3.7, y1: pY(px) + 3.7, nx: 184 }] });
const NOTCHES = [
  slot(135), slot(311),
  { fr: [{ z: V.zLem0, y0: -Y_HANDLE, y1: Y_HANDLE, nx: X_REC }, { z: 129, y0: -Y_HANDLE, y1: Y_HANDLE, nx: X_REC }, { z: 139, y0: -92, y1: 92, nx: X_REC }] },   // výřez madla (horní hrana se zkosenými konci, c01 py 62)
  slot(889), slot(1065),
];

function pricka(g) {
  // černá horní příčka madla (c01: px 372..828, py 75..140; vodorovná část py 75..108, uprostřed pod ní deska s logem do py 140); vrchní plocha mírně šikmo
  const yb = Y_HANDLE, zt = pZ(75);
  g.add(extYZ('cerna', 'madlo_pricka', [[-yb, pZ(110)], [yb, pZ(110)], [yb - 4, zt - 1], [yb - 9, zt], [-yb + 9, zt], [-yb + 4, zt - 1]], X_REC + 1, 189.2));
  g.add(extYZ('cerna', 'madlo_deska', [[pY(452), pZ(110)], [pY(748), pZ(110)], [pY(738), pZ(140)], [pY(462), pZ(140)]], X_REC + 1, 187));
  // tmavé pole s logem HILTI (černé na černém) – jen tenká deska
  g.add(bx('cerna_mat', 'madlo_logo_pole', 186.9, 187.4, pY(540), pY(662), pZ(128), pZ(104)));
}

function sroubky(g) {
  for (const px of SCREW_PX) {
    const y = pY(px);
    g.add(cylX('cervena', 'sroub_boss', 7.4, 186, 189.4, y, zS, 22));
    g.add(cylX('cerna', 'sroub_hlava', 5.2, 189, 190.4, y, zS, 18));
  }
  // svislé červené žebro vpravo od madla (c01 px 842..861, py 33..140) – spona zámku víka, hloubka neověřena
  g.add(bx('cervena', 'zamek_zebro', 186, 190.4, pY(842), pY(861), pZ(140), pZ(33)));
}

function pant(g) {
  // horní (víkové) články pantu – sudé úseky; neověřeno
  const seg = 500 / 7;
  for (let i = 0; i < 7; i += 2) {
    const y0 = -250 + i * seg + 0.6, y1 = -250 + (i + 1) * seg - 0.6;
    g.add(rb('cervena', 'pant_clanek_vicko', { x0: -193.5, x1: -181, y0, y1, z0: 113, z1: 127.5, rc: 3, re: 2, seg: 2, fs: 2 }));
  }
}

function cylinderY(mat, name, r, y0, y1, x, z, n = 18) {
  return cylinder(mat, name, r, y0, y1, n, [0, 0]).mapV((u, v, w) => [u + x, w, v + zc(z)]).flip();
}
// ---------- zadní (pantová) hrana víka: páteř, klínové bloky (kloubová oka) s okénky, kolík ----------
function pantHrana(g) {
  // páteř pantové hrany: šikmé konce navazují na zkosení konců víka (c01: obrys nahoře ±243 ve výšce 168)
  const fy = (z, y) => ({ z, xf: -168, xr: -191, y0: -y, y1: y, yF: y - 0.2, cfx: 0.2, rr: 0.5, ns: 1 });
  g.add(plocha('cervena', 'pant_patere', { frames: [fy(V.zBev, 271.5), fy(V.zTop, 243.1)] }));
  for (const yc of [-217.5, -72.5, 72.5, 217.5]) {
    const ya = Math.max(yc - 40, -238), yb = Math.min(yc + 40, 238);          // krajní bloky ořezané zkosením konců víka
    g.add(extXZ('cervena', 'pant_klin', [[-152, V.zTop], [V.xPr, V.zP], [V.xPr, V.zP - 6], [-152, V.zTop - 8]], ya, yb));
    g.add(bx('cerna_mat', 'pant_okenko', -146, -142, yc - 17, yc + 17, V.zTop - 6, V.zTop - 2));
  }
  g.add(cylinderY('cerna', 'pant_kolik', 2.6, -238, 238, -180, 162, 10));
}

export function vicko() {
  const g = new Group('vicko', { pivot: V.pivot, extras: { osa: [0, -1, 0], max_uhel: 110 } });
  g.add(vickoPlast('cervena', 'vicko_plast', { frames: FRAMES, notches: NOTCHES, wall: 3, topT: 3 }));
  pantHrana(g); pricka(g); sroubky(g); pant(g);
  return g;
}
