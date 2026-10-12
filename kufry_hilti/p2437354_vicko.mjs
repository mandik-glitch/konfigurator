// Víko Hilti ProKit PKC 61 (2437354): dutý červený plášť s lemem (límec), zkosenou horní hranou, kapsou madla v čele, drážkami nad šrouby;
// černé madlo (lišta + jazyk), šrouby čepů západek a drát západek. Víko je samostatná skupina s pivotem na ose pantu (vzadu).
// Víko je tvarem shodné s víkem PKC 35 (c01 obou kufrů: šrouby, západky i madlo sedí na ±3 mm; šířka +5 mm, výška posunuta o DZ = 155 mm); horní plocha je u PKC 61 bez
// otvoru pro držadlo (ISO fotografie L153711: hladká deska), proto zde chybí otvor i třmen. Vnitřní žebrování víka (c02, c03) je zjednodušeno (nemodelováno).
import { Group, vickoPlast, plocha, extYZ, extXZ, bx, rb, cylX, cylinder, tube, zc, pY, pZ, lY, lZ, DZ } from './p2437354_zaklad.mjs';
import { K, Y_HANDLE, LATCH } from './p2437354_korpus.mjs';

export const V = { zLem0: 209.8 + DZ, zLem1: 218.4 + DZ, zBev: 250.2 + DZ, zP: 258 + DZ, xPl: 137, xPr: -100, zTop: 267 + DZ, xLem: 193.5, xSk: 187, ySk: 274, yLem: 279.5, pivot: [-187, 0, zc(K.zRim + 1.5)] };

const F = (z, xf, xr, y, yF, cfx, rr) => ({ z, xf, xr, y0: -y, y1: y, yF, cfx, rr });
const FRAMES = [
  F(V.zLem0, V.xLem, -V.xSk, V.yLem, 246.5, 22, 8), F(V.zLem1, V.xLem, -V.xSk, V.yLem, 246.5, 22, 8),
  F(V.zLem1, V.xSk, -V.xSk, V.ySk, K.yCL, 22, 8), F(V.zBev, V.xSk, -V.xSk, V.ySk, K.yCL, 22, 8),
  F(V.zP, V.xPl, V.xPr, 261.7, 224.5, 14, 10),   // horní plocha (plató): vpředu zkosení, vzadu pozvolná rampa k pantové hraně (c01: obrys nahoře ±245 ve výšce 422)
];
// šrouby čepů západek (c01 PKC 61: px 135, 313, 886, 1064; py 89) a drážky nad nimi (c01 px 128..148, 304..325, 876..898, 1053..1075; py 43..80)
const SCREW_PX = [135, 313, 886, 1064];
const SLOTS = [[126, 148], [303, 325], [875, 898], [1052, 1075]];
const zS = pZ(89);
const slot = ([a, b]) => ({ fr: [{ z: pZ(80), y0: pY(a), y1: pY(b), nx: 185 }, { z: pZ(43), y0: pY(a), y1: pY(b), nx: 185 }] });
const NOTCHES = [
  slot(SLOTS[0]), slot(SLOTS[1]),
  { fr: [{ z: V.zLem0, y0: -Y_HANDLE, y1: Y_HANDLE, nx: 158 }, { z: lZ(68), y0: -Y_HANDLE, y1: Y_HANDLE, nx: 158 }, { z: pZ(72), y0: -Y_HANDLE + 15, y1: Y_HANDLE - 15, nx: 158 }] },
  { fr: [{ z: pZ(100), y0: pY(843), y1: pY(862), nx: 185 }, { z: pZ(38), y0: pY(843), y1: pY(862), nx: 185 }] },   // drážka u zámku víka (vpravo od madla)
  slot(SLOTS[2]), slot(SLOTS[3]),
];

function madlo(g) {
  // černé madlo v kapse (c01: lišta px 380..825, py 88..110 se zkosenými horními rohy; jazyk px 455..745 → 473..722 u py 110 → 160, se zkosenými boky)
  const yb = Y_HANDLE - 3.5;
  const zb = pZ(110), zt = pZ(88);
  g.add(extYZ('cerna', 'madlo_lista', [[-yb, zb], [yb, zb], [yb, zt - 4], [yb - 9, zt], [-yb + 9, zt], [-yb, zt - 4]], 160, 188.8));
  g.add(extYZ('cerna', 'madlo_jazyk', [[pY(455), pZ(111)], [pY(745), pZ(111)], [pY(722), pZ(160)], [pY(473), pZ(160)]], 168, 183));
}

function pouzdra(g) {
  // černé pouzdro západky (patří k víku, zasahuje do kapsy v límci): obrys z c01 (px 155..300 / 900..1050, py 125..198) s oknem pro červený jazyk
  for (const Y of [LATCH.L, LATCH.R]) {
    const yc = (Y[0] + Y[1]) / 2, w0 = yc - 20.6, w1 = yc + 20.6, zw0 = lZ(112), zw1 = lZ(86), zt = lZ(80), zb = pZ(198);
    const X0 = 178.5, X1 = 181.6;
    g.add(extYZ('cerna_mat', 'pouzdro_horni', [[Y[0] + 0.5, zw1], [Y[1] - 0.5, zw1], [Y[1] - 0.5, zt], [Y[0] + 0.5, zt]], X0, X1));
    g.add(extYZ('cerna_mat', 'pouzdro_dolni', [[Y[0] + 0.5, zw0], [Y[1] - 0.5, zw0], [Y[1] - 0.5, pZ(172)], [Y[1] - 0.5 - 7, zb], [Y[0] + 0.5 + 9, zb], [Y[0] + 0.5, pZ(172)]], X0, X1));
    g.add(extYZ('cerna_mat', 'pouzdro_bok', [[Y[0] + 0.5, zw0], [w0, zw0], [w0, zw1], [Y[0] + 0.5, zw1]], X0, X1));
    g.add(extYZ('cerna_mat', 'pouzdro_bok', [[w1, zw0], [Y[1] - 0.5, zw0], [Y[1] - 0.5, zw1], [w1, zw1]], X0, X1));
  }
}

function sroubky(g) {
  for (const px of SCREW_PX) {
    const y = pY(px);
    g.add(cylX('cervena', 'sroub_boss', 5.6, 187, 189.2, y, zS, 20));
    g.add(cylX('cerna', 'sroub_hlava', 3.9, 189, 190.3, y, zS, 16));
  }
}

function dratSpony(g) {
  // drátová západka (černý třmen) – jen přibližně: čepy ve šroubech, příčka v rámečku západky (vnitřní stavba neověřena)
  for (const s of [-1, 1]) {
    const ya = pY(s < 0 ? SCREW_PX[0] : SCREW_PX[2]), yb = pY(s < 0 ? SCREW_PX[1] : SCREW_PX[3]);
    g.add(tube('cerna_mat', 'dratova_zapadka', [[183, ya, zc(zS)], [184.5, ya, zc(zS - 8)], [182.5, ya, zc(K.zRim - 1.5)], [182.5, yb, zc(K.zRim - 1.5)], [184.5, yb, zc(zS - 8)], [183, yb, zc(zS)]], 1.2, 8));
  }
}

function zamekHore(g) {
  // horní část svislého čepu zámku víka (c01 px 845..862, py 35..100); vyložení neověřeno
  g.add(bx('cervena', 'zamek_vika_horni', 187, 190.5, pY(845), pY(862), pZ(100), pZ(38)));
}

function pant(g) {
  // horní (víkové) články pantu – sudé úseky; neověřeno
  const seg = 500 / 7;
  for (let i = 0; i < 7; i += 2) {
    const y0 = -250 + i * seg + 0.6, y1 = -250 + (i + 1) * seg - 0.6;
    g.add(rb('cervena', 'pant_clanek_vicko', { x0: -193.5, x1: -181, y0, y1, z0: 205 + DZ, z1: 219.5 + DZ, rc: 3, re: 2, seg: 2, fs: 2 }));
  }
}
function cylinderY(mat, name, r, y0, y1, x, z, n = 18) {
  return cylinder(mat, name, r, y0, y1, n, [0, 0]).mapV((u, v, w) => [u + x, w, v + zc(z)]).flip();
}
// ---------- zadní (pantová) hrana víka: páteř, klínové bloky s okénky, kolík (jako PKC 35; zadní strana na fotografiích nevidět, v ISO L153711 jsou klínové bloky patrné) ----------
function pantHrana(g) {
  const fy = (z, y) => ({ z, xf: -170, xr: -187, y0: -y, y1: y, yF: y - 0.2, cfx: 0.2, rr: 0.5, ns: 1 });
  g.add(plocha('cervena', 'pant_patere', { frames: [fy(V.zBev, V.ySk), fy(V.zTop, 245)] }));
  for (const yc of [-217.5, -72.5, 72.5, 217.5]) {
    const ya = Math.max(yc - 40, -240), yb = Math.min(yc + 40, 240);
    g.add(extXZ('cervena', 'pant_klin', [[-175, V.zTop], [V.xPr, V.zP], [V.xPr, V.zP - 8], [-175, V.zP - 12]], ya, yb));
    g.add(bx('cerna_mat', 'pant_okenko', -150, -146, yc - 17, yc + 17, V.zP + 2, V.zP + 7));
  }
  g.add(cylinderY('cerna', 'pant_kolik', 2.6, -250, 250, -180, V.zP + 4, 10));
}

export function vicko() {
  const g = new Group('vicko', { pivot: V.pivot, extras: { osa: [0, -1, 0], max_uhel: 110 } });
  g.add(vickoPlast('cervena', 'vicko_plast', { frames: FRAMES, notches: NOTCHES, wall: 3, topT: 3 }));
  pantHrana(g); zamekHore(g);
  madlo(g); pouzdra(g); sroubky(g); dratSpony(g); pant(g);
  return g;
}
