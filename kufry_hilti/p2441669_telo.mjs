// Tělo Hilti ProKit PKC 37-O (2441669): otevřená přepravka BEZ víka (fotografie c01-c03 žádné víko neukazují; název produktu "-O" = otevřená).
// Vana s podstavcem (soklem), zapuštěnými poli mezi žebry na dlouhých stranách, širokým lemem nahoře (okénka v čele lemu, zkosené rohy,
// zkosené konce s větracími otvory), průchozí madlo v obou koncových stěnách, kapsa stohovacího zámku, nožky, logo.
// Míry: čelní fotografie c01 (převod px -> mm viz p2441669_zaklad.mjs: pY, pZ); hloubky ve směru X z c02/c03 jsou ODHADY (viz poznámky).
// Vnitřek je zjednodušený: hladká dutina (bez dělicí příčky, vnitřních žeber a sloupků).
import { Group, Part, vana, extYZ, bx, box, rb, cylX, zc, pY, pZ } from './p2441669_zaklad.mjs';

// hlavní míry
export const K = {
  xR: 188.8,          // polovina hloubky lemu (čelo +X; logo vyčnívá o 0,4 → celkem 378,0 s ohledem na střed +0,2)
  xW: 165,            // polovina hloubky zapuštěné stěny pod lemem (odhad: lem přečnívá ~ 24 mm, jako na koncích 22 mm podle c01)
  xP: 183,            // polovina hloubky podstavce (soklu) (odhad)
  yR: 272.5,          // polovina délky lemu (c01: 800 px = 545 mm)
  zTop: 279, zFloor: 20, zBot: 10,
  zRimLo: 218.5,      // spodní hrana lemu (c01 py ~88)
};
const C_RIM = 30, C_BODY = 12.5;
const F = (z, hx, hy, c) => ({ z, hx, hy, c });
// vnější půdorys po výškách; hy podle obrysu c01 (konce): z' 27 -> 247; 34 -> 248; 170 -> 250; 205 -> 256; 225 -> 270; 232..252 -> 272,5; horní zkosení 252 -> 244 (z' 279)
export const FRAMES = [
  F(K.zBot, 172, 230, 16), F(20, 180, 237, 16), F(28, K.xP, 246.8, 15), F(34, K.xP, 248.1, 14),
  F(78, K.xP, 248.8, C_BODY),                                  // čelo podstavce (c01 py 295)
  F(105, K.xW, 249.6, C_BODY),                                 // šikmá horní plocha soklu (c01 py 255 .. 295)
  F(170, K.xW, 250.2, C_BODY), F(205, K.xW, 255.8, C_BODY), F(K.zRimLo, K.xW, 260, C_BODY),
  F(K.zRimLo, K.xR, 260, C_RIM),                                // spodní plocha lemu (vodorovná)
  F(225, K.xR, 270, C_RIM), F(231, K.xR, K.yR, C_RIM), F(252, K.xR, K.yR, C_RIM),
  F(258.9, K.xR, 270, C_RIM), F(272.5, K.xR, 252.3, C_RIM), F(K.zTop, K.xR, 244, C_RIM),   // zkosený konec lemu (rampa s větracími otvory)
];
// dutina (vnitřní půdorys): vnitřní 288 × (≈ 480; katalog 498 se s obrysem c01 neslučuje, viz poznámky) × 259, stěny se k dnu mírně zužují
export const INNER = [F(K.zFloor, 138, 234, 14), F(K.zTop, 144, 240, 14)];

// ---------- výřezy ----------
// okénka v čele lemu (c01 py 3..28 → z' 260..277; px rozsahy z jasu řádku py 10..24; hloubka 14 mm - odhad)
export const OKENKA_PX = [[40, 72], [110, 218], [222, 272], [315, 392], [402, 476], [520, 572], [578, 683], [725, 740]];
const ZW0 = pZ(28), ZW1 = pZ(3), W_AT = K.xR - 14;
export const LABEL_PX = [327, 474], LABEL_PY = [41, 77];        // zapuštěný štítek v čele lemu (c01); hloubka 1,2 mm - odhad
export const ZAMEK_PX = [160, 222], ZAMEK_Z = [34, 104];       // kapsa stohovacího zámku v soklu (c01 px 160..222, py 258..360)
export const MADLO = { x: 60, z0: 224, z1: 250, at: 255, zS0: 192 };   // průchozí madlo v koncových stěnách (poloha z c02/c03, odhad ± 10 mm)
export const FEATURES = [];
for (const e of ['+X', '-X']) {
  for (const [a, b] of OKENKA_PX) FEATURES.push({ e, s0: pY(a), s1: pY(b), z0: ZW0, z1: ZW1, at: W_AT, ring: 'o' });
}
FEATURES.push({ e: '+X', s0: pY(LABEL_PX[0]), s1: pY(LABEL_PX[1]), z0: pZ(LABEL_PY[1]), z1: pZ(LABEL_PY[0]), at: K.xR - 1.2, ring: 'o' });
FEATURES.push({ e: '+X', s0: pY(ZAMEK_PX[0]), s1: pY(ZAMEK_PX[1]), z0: ZAMEK_Z[0], z1: ZAMEK_Z[1], at: 150, ring: 'o' });
for (const e of ['+Y', '-Y']) {
  FEATURES.push({ e, s0: -MADLO.x, s1: MADLO.x, z0: MADLO.z0, z1: MADLO.z1, at: MADLO.at, ring: 'oi', thru: true });   // průchozí otvor madla
  FEATURES.push({ e, s0: -MADLO.x, s1: MADLO.x, z0: MADLO.zS0, z1: MADLO.z0, at: 243, ring: 'o' });                // kapsa pod madlem
}

// ---------- doplňky na tělese ----------
const RIBS_PX = [[211, 229], [386, 404], [562, 580]];            // žebra mezi poli (c01: světlá hrana + čelo + stín vpravo)
function zebra(g) {
  for (const s of [1, -1]) {
    const xa = s > 0 ? K.xW - 2 : -K.xP, xb = s > 0 ? K.xP : -(K.xW - 2);
    for (const [a, b] of RIBS_PX) g.add(bx('cervena', 'zebro', xa, xb, pY(a), pY(b), 80, K.zRimLo + 0.3));
    // vodorovná lišta (c01 py 112..120 → z' 197..203)
    const x0 = s > 0 ? K.xW - 2 : -(K.xW + 14), x1 = s > 0 ? K.xW + 14 : -(K.xW - 2);
    g.add(bx('cervena', 'lista_vodorovna', x0, x1, -246, 246, pZ(120), pZ(112)));
    // očka (c01: tři kroužky pod lemem, px 118 / 398 / 680, py 100)
    for (const px of [118, 398, 680]) {
      const y = pY(px), z = pZ(100);
      g.add(cylX('cervena', 'oko', 5, s > 0 ? K.xW - 1 : -(K.xW + 6), s > 0 ? K.xW + 6 : -(K.xW - 1), y, z, 16));
      g.add(cylX('cerna_mat', 'oko_otvor', 2.3, s > 0 ? K.xW + 5.8 : -(K.xW + 6.2), s > 0 ? K.xW + 6.2 : -(K.xW + 5.8), y, z, 12));
    }
  }
}
function okenkaTmava(g) {
  // dno okének v lemu: tmavá plocha (v fotografii jsou okénka tmavá; skutečná hloubka dna je neověřená)
  for (const s of [1, -1]) for (const [a, b] of OKENKA_PX) {
    const y0 = Math.max(pY(a), -241) + 0.6, y1 = Math.min(pY(b), 241) - 0.6;
    g.add(bx('cerna_mat', 'okenko_dno', s > 0 ? W_AT : -(W_AT + 0.5), s > 0 ? W_AT + 0.5 : -W_AT, y0, y1, ZW0 + 0.6, ZW1 - 0.6));
  }
}
function vetraky(g) {
  // 5 větracích otvorů na zkosené horní hraně každého konce (c02/c03: čtvercové otvory ~15 mm v řadě); tmavé plošky ležící na rampě (odhad polohy)
  const sl = Math.atan2(279 - 258.9, 270 - 244) * 180 / Math.PI;     // sklon rampy
  const yc = 257, zcR = 279 - (yc - 244) * (279 - 258.9) / (270 - 244);
  for (const sY of [1, -1]) for (let k = -2; k <= 2; k++) {
    const p = box('cerna_mat', 'vetrak', -7.2, 7.2, -9, 9, -0.6, 0.45).rot('x', -sl * sY).move(k * 22.5, sY * yc, zc(zcR));
    g.add(p);
  }
}
function logo(g) {
  // logo HILTI: bílé obdélníky přímo z masky c01 (px; písmena H I L T I), mírně vystouplé z čela lemu
  const R = [[606, 616, 49, 69], [635, 645, 49, 69], [606, 645, 55, 64], [648, 658, 49, 69], [661, 671, 49, 69], [661, 693, 60, 69], [686, 728, 49, 58], [703, 712, 58, 69], [733, 742, 49, 69]];
  for (const [a, b, c, d] of R) g.add(bx('bila', 'logo_hilti', K.xR - 0.3, K.xR + 0.4, pY(a), pY(b + 1), pZ(d), pZ(c)));
}
function zamek(g) {
  // černý stohovací zámek v kapse (c01: px 170..214, py 297..357); dno kapsy x = 150
  g.add(extYZ('cerna_mat', 'zamek_cerny', [[pY(170), pZ(357)], [pY(214), pZ(357)], [pY(216), pZ(340)], [pY(216), pZ(300)], [pY(210), pZ(297)], [pY(174), pZ(297)], [pY(168), pZ(300)], [pY(168), pZ(340)]], 149, 168));
  g.add(bx('seda', 'zamek_jazyk', 167.8, 169.4, pY(176), pY(210), pZ(345), pZ(337)));
}
function nozky(g) {
  // 4 nožky (kolejnice ve směru X); Y středy z c01 (px 92, 300, 498, 707), šířka ~44/37 mm; délka v X a spodek jsou neověřené
  for (const px of [92, 300, 498, 707]) {
    const yc = pY(px);
    g.add(extYZ('cervena', 'nozka', [[yc - 18.5, 0], [yc + 18.5, 0], [yc + 22, 12], [yc - 22, 12]], -166, 166));
    g.add(bx('cerna_mat', 'nozka_patka', 146, 172, yc - 11, yc + 11, 0, 14));
    g.add(bx('cerna_mat', 'nozka_patka', -172, -146, yc - 11, yc + 11, 0, 14));
  }
}

export function telo() {
  const g = new Group('telo');
  g.add(vana('cervena', 'telo_vana', { frames: FRAMES, innerFrames: INNER, floorZ: K.zFloor, features: FEATURES }));
  zebra(g); okenkaTmava(g); vetraky(g); logo(g); zamek(g); nozky(g);
  return g;
}
