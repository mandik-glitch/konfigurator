// Víko Hilti ProKit PKC 35 (2437394): dutý červený plášť s lemem (límec), zkosenou horní hranou, kapsou madla v čele, drážkami nad šrouby;
// černé madlo (lišta + jazyk), šrouby čepů západek a drát západek. Víko je samostatná skupina s pivotem na ose pantu (vzadu).
// Vnitřní žebrování víka je zjednodušeno (nemodelováno) – viz poznámky.
import { Group, vickoPlast, vana, plocha, extYZ, extXZ, bx, rb, cylX, cylinder, tube, zc, pY, pZ } from './p2437394_zaklad.mjs';
import { K, Y_HANDLE, LATCH } from './p2437394_korpus.mjs';

export const V = { zLem0: 209.8, zLem1: 218.4, zBev: 250.2, zP: 258, xPl: 137, xPr: -100, zTop: 267, xLem: 193.5, xSk: 187, ySk: 271.5, yLem: 277, pivot: [-187, 0, zc(K.zRim + 1.5)] };

const F = (z, xf, xr, y, yF, cfx, rr) => ({ z, xf, xr, y0: -y, y1: y, yF, cfx, rr });
const ZR = K.zRim + 1.3;      // spodní okraj skořepiny víka (nad límcem korpusu)
const FRAMES = [
  F(V.zLem0, V.xLem, -V.xSk, V.yLem, 244, 22, 8), F(V.zLem1, V.xLem, -V.xSk, V.yLem, 244, 22, 8),
  F(V.zLem1, V.xSk, -V.xSk, V.ySk, K.yC, 22, 8), F(V.zBev, V.xSk, -V.xSk, V.ySk, K.yC, 22, 8),
  F(V.zP, V.xPl, V.xPr, 259.2, 222, 14, 10),     // horní plocha (plató): vpředu zkosení (šikmá hrana ~52 mm), vzadu pozvolná rampa k pantové hraně
];
// šrouby čepů západek (c01: px 90, 208, 592, 706; py 59) a drážky nad nimi (px 83..99 atd.)
const SCREW_PX = [90, 208, 592, 706];
const SLOTS = [[83, 99], [202, 217], [583, 598], [702, 717]];
const zS = pZ(59);
const NOTCHES = [
  { fr: [{ z: pZ(60), y0: pY(SLOTS[0][0]), y1: pY(SLOTS[0][1]), nx: 185 }, { z: pZ(22), y0: pY(SLOTS[0][0]), y1: pY(SLOTS[0][1]), nx: 185 }] },
  { fr: [{ z: pZ(60), y0: pY(SLOTS[1][0]), y1: pY(SLOTS[1][1]), nx: 185 }, { z: pZ(22), y0: pY(SLOTS[1][0]), y1: pY(SLOTS[1][1]), nx: 185 }] },
  { fr: [{ z: V.zLem0, y0: -Y_HANDLE, y1: Y_HANDLE, nx: 158 }, { z: pZ(68), y0: -Y_HANDLE, y1: Y_HANDLE, nx: 158 }, { z: pZ(51), y0: -Y_HANDLE + 15, y1: Y_HANDLE - 15, nx: 158 }] },
  { fr: [{ z: pZ(60), y0: pY(563), y1: pY(578), nx: 185 }, { z: pZ(22), y0: pY(563), y1: pY(578), nx: 185 }] },
  { fr: [{ z: pZ(60), y0: pY(SLOTS[2][0]), y1: pY(SLOTS[2][1]), nx: 185 }, { z: pZ(22), y0: pY(SLOTS[2][0]), y1: pY(SLOTS[2][1]), nx: 185 }] },
  { fr: [{ z: pZ(60), y0: pY(SLOTS[3][0]), y1: pY(SLOTS[3][1]), nx: 185 }, { z: pZ(22), y0: pY(SLOTS[3][0]), y1: pY(SLOTS[3][1]), nx: 185 }] },
];

function madlo(g) {
  // černé madlo v kapse (c01: lišta px 250..550, py 60..80; jazyk se zkosenými boky do py 105)
  const yb = Y_HANDLE;
  const zb = pZ(80), zt = pZ(59.5);
  g.add(extYZ('cerna', 'madlo_lista', [[-yb, zb], [yb, zb], [yb, zt - 4], [yb - 9, zt], [-yb + 9, zt], [-yb, zt - 4]], 160, 188.8));
  g.add(extYZ('cerna', 'madlo_jazyk', [[pY(298), pZ(81)], [pY(502), pZ(81)], [pY(488), pZ(104.5)], [pY(312), pZ(104.5)]], 168, 183));
}

function pouzdra(g) {
  // černé pouzdro západky (patří k víku, zasahuje do kapsy v límci): obrys osmiúhelníku z c01 (px 101..198 / 604..698, py 80..131) s oknem pro červený jazyk
  for (const Y of [LATCH.L, LATCH.R]) {
    const yc = (Y[0] + Y[1]) / 2, w0 = yc - 20.6, w1 = yc + 20.6, zw0 = pZ(112), zw1 = pZ(86), zt = pZ(80), zb = pZ(131);
    const X0 = 178.5, X1 = 181.6;
    g.add(extYZ('cerna_mat', 'pouzdro_horni', [[Y[0] + 0.5, zw1], [Y[1] - 0.5, zw1], [Y[1] - 0.5, zt], [Y[0] + 0.5, zt]], X0, X1));
    g.add(extYZ('cerna_mat', 'pouzdro_dolni', [[Y[0] + 0.5, zw0], [Y[1] - 0.5, zw0], [Y[1] - 0.5, pZ(108)], [Y[1] - 0.5 - 7, zb], [Y[0] + 0.5 + 9, zb], [Y[0] + 0.5, pZ(108)]], X0, X1));
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
    g.add(tube('cerna_mat', 'dratova_zapadka', [[183, ya, zc(zS)], [184.5, ya, zc(zS - 8)], [182.5, ya, zc(209.5)], [182.5, yb, zc(209.5)], [184.5, yb, zc(zS - 8)], [183, yb, zc(zS)]], 1.2, 8));
  }
}

function pant(g) {
  // horní (víkové) články pantu – sudé úseky; neověřeno
  const seg = 500 / 7;
  for (let i = 0; i < 7; i += 2) {
    const y0 = -250 + i * seg + 0.6, y1 = -250 + (i + 1) * seg - 0.6;
    g.add(rb('cervena', 'pant_clanek_vicko', { x0: -193.5, x1: -181, y0, y1, z0: 205, z1: 219.5, rc: 3, re: 2, seg: 2, fs: 2 }));
  }
}

// ---------- horní držadlo (L153707): otvor v horní ploše, kapsa s černým sklopným třmenem ----------
// Poloha a rozměr otvoru: rektifikace šikmé fotografie L153707 na rovinu z' = 258 (osmiúhelník X −78..+81, Y −110..+122 → zjednodušeno souměrně), ±8 mm; hloubka kapsy a tvar třmenu neověřeny.
const OT = (g, wl = 0) => ({ z: 0, xf: 81 + wl, xr: -78 - wl, y0: -116 - wl, y1: 116 + wl, yF: 78 + wl, cfx: 20, rr: 30, ns: 1, wx: 3, wy: 3 });
export const OTVOR = { zF: 220 };
function otvor(g) {
  const o = OT(), O3 = OT(0, 3);
  const fr = [{ ...O3, z: OTVOR.zF - 3 }, { ...O3, z: V.zP }];
  g.add(vana('cervena', 'otvor_kapsa', { frames: fr, wall: 3, floorZ: OTVOR.zF }));
  return O3;
}
function drzadloHore(g) {
  // černý třmen (bail) složený do kapsy: úchop (válec podél Y) vzadu, dvě ramena a čepy vpředu; tvar přibližný
  const yg = 78, zg = OTVOR.zF + 22;
  g.add(cylinderY('cerna', 'tremen_uchop', 9, -yg, yg, -42, zg));
  for (const s of [-1, 1]) {
    const yc = s * (yg + 4.5);
    g.add(extXZ('cerna', 'tremen_rameno', [[-50, zg - 8], [-50, zg + 8], [40, OTVOR.zF + 14], [62, OTVOR.zF + 4], [62, OTVOR.zF + 1], [40, OTVOR.zF + 1]], yc - 4.5, yc + 4.5));
    g.add(bx('cerna', 'tremen_cep', 40, 62, yc - 6, yc + 6, OTVOR.zF, OTVOR.zF + 16));
  }
}
function cylinderY(mat, name, r, y0, y1, x, z, n = 18) {
  return cylinder(mat, name, r, y0, y1, n, [0, 0]).mapV((u, v, w) => [u + x, w, v + zc(z)]).flip();
}
// ---------- zadní (pantová) hrana víka: páteř, klínové bloky s okénky, kolík ----------
function pantHrana(g) {
  // páteř pantové hrany: šikmé konce navazují na zkosení konců víka (c01: obrys nahoře ±245 ve výšce 267)
  const fy = (z, y) => ({ z, xf: -170, xr: -187, y0: -y, y1: y, yF: y - 0.2, cfx: 0.2, rr: 0.5, ns: 1 });
  g.add(plocha('cervena', 'pant_patere', { frames: [fy(250.2, 271.5), fy(267, 245)] }));
  for (const yc of [-217.5, -72.5, 72.5, 217.5]) {
    const ya = Math.max(yc - 40, -240), yb = Math.min(yc + 40, 240);          // krajní bloky ořezané zkosením konců víka
    g.add(extXZ('cervena', 'pant_klin', [[-175, 267], [V.xPr, V.zP], [V.xPr, V.zP - 8], [-175, V.zP - 12]], ya, yb));
    g.add(bx('cerna_mat', 'pant_okenko', -150, -146, yc - 17, yc + 17, 260, 265));
  }
  g.add(cylinderY('cerna', 'pant_kolik', 2.6, -250, 250, -180, 262, 10));
}

export function vicko() {
  const g = new Group('vicko', { pivot: V.pivot, extras: { osa: [0, -1, 0], max_uhel: 110 } });
  const O3 = otvor(g);
  g.add(vickoPlast('cervena', 'vicko_plast', { frames: FRAMES, notches: NOTCHES, wall: 3, topT: 3, holes: [{ ...O3, z: V.zP }] }));
  drzadloHore(g); pantHrana(g);
  madlo(g); pouzdra(g); sroubky(g); dratSpony(g); pant(g);
  return g;
}
