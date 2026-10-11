// Korpus (spodní díl) Hilti ProKit PKC 35 (2437394): vana s límcem, výřezy v čele (kapsa madla, kapsa zámku, rámečky západek),
// nožky, logo (bílá plocha), černé díly. Vnitřek je zjednodušený (prázdná dutina, hladké stěny a dno).
// Míry jsou z čelní fotografie c01 (převod px → mm viz p2437394_zaklad.mjs: pY, pZ); co není na fotografii vidět, je v poznámkách označeno „neověřeno“.
import { Group, Part, vana, extYZ, bx, rb, oct, cylX, zc, pY, pZ } from './p2437394_zaklad.mjs';

export const K = {
  zRim: 211.5,        // horní okraj korpusu = dělicí spára s víkem (spodní hrana lemu víka, c01 py 81)
  zBand: 154.0,       // spára mezi čelním panelem a horním pásem (c01 py 165); podlaha kapsy madla z' 155 (py 162)
  floorZ: 16.7,       // horní plocha dna (vnitřní hloubka 195 mm pod okrajem 211,5)
  xF: 186, xR: -183,  // čelní / zadní rovina spodní části (panel s logem o ~1 mm za límcem; hloubky nejsou z čelní fotografie měřitelné – neověřeno)
  xFc: 187,           // čelní rovina horního pásu a límce (= plášť víka)
  yC: 241,            // konec rovné čelní hrany (zkosený roh čelo→bok začíná v Y = ±241; c01 px 748 / 55)
};
const Y_LATCH = [pY(101), pY(198)];          // rámeček západky vlevo (px 101..198)
const Y_LATCH_R = [pY(604), pY(698)];
export const LATCH = { L: Y_LATCH, R: Y_LATCH_R };
export const Y_HANDLE = Math.abs(pY(249));   // polovina šířky kapsy madla (c01 px 249..551, svislé stěny; detail 7× zvětšený)

// snímky půdorysu: z', xf, xr, y0, y1, yF (konec rovné čelní hrany), cfx (hloubka zkosení v X), rr (zadní rohy)
const F = (z, xf, xr, y, yF, cfx = 15, rr = 8, wx = 5, wy = 6) => ({ z, xf, xr, y0: -y, y1: y, yF, cfx, rr, wx, wy });
export const FRAMES = [
  F(8, 170, -169, 232.5, 217.5), F(14, 174, -173, 235.5, 220.5), F(20.5, 179, -178, 243, 228), F(27.4, 184, -182.5, 252.8, 237.8),
  F(36, K.xF, K.xR, 254, K.yC), F(K.zBand - 0.01, K.xF, K.xR, 255.5, K.yC),
  F(K.zBand, K.xFc, -K.xFc, 255.5, K.yC, 15, 8, 6, 6), F(178.7, K.xFc, -K.xFc, 256.2, K.yC, 15, 8, 9, 6), F(191.7, K.xFc, -K.xFc, 271.5, K.yC, 22, 8, 9, 14), F(K.zRim, K.xFc, -K.xFc, 271.5, K.yC, 22, 8, 9, 14),
];
// výřezy v čelní hraně (zleva doprava podle Y)
const nl = (fr) => ({ fr });
const YL = Y_LATCH, YR = Y_LATCH_R;
const FOOT = [[91, 34], [297, 38], [503, 38], [709, 34]];                                 // [px středu nožky v c01, šířka mm]
const gapY = i => [pY(FOOT[i][0]) + FOOT[i][1] / 2, pY(FOOT[i + 1][0]) - FOOT[i + 1][1] / 2];
const fgap = i => nl([{ z: 8, y0: gapY(i)[0], y1: gapY(i)[1], nx: 160 }, { z: 17.5, y0: gapY(i)[0], y1: gapY(i)[1], nx: 160 }]);
const pad = (a, b) => nl([{ z: pZ(337), y0: pY(a), y1: pY(b), nx: K.xF - 1.2 }, { z: pZ(174), y0: pY(a), y1: pY(b), nx: K.xF - 1.2 }]);
export const NOTCHES = [
  pad(63, 87),                                                                             // vtlačený panel u levého okraje čelní desky (c01 px 63..87)
  nl([{ z: pZ(131), y0: pY(120), y1: pY(188), nx: 180 }, { z: pZ(108), y0: YL[0], y1: YL[1], nx: 180 }, { z: K.zRim - 0.8, y0: YL[0], y1: YL[1], nx: 180 }]),   // rámeček západky vlevo
  fgap(0),                                                                                 // mezera mezi nožkami 1-2
  nl([{ z: pZ(361), y0: pY(172), y1: pY(224), nx: 168 }, { z: pZ(345), y0: pY(160), y1: pY(232), nx: 168 }, { z: pZ(292), y0: pY(160), y1: pY(232), nx: 168 }, { z: pZ(277), y0: pY(172), y1: pY(218), nx: 168 }]),   // kapsa zámku
  nl([{ z: 155, y0: -Y_HANDLE, y1: Y_HANDLE, nx: 158 }, { z: K.zRim, y0: -Y_HANDLE, y1: Y_HANDLE, nx: 158 }]),   // kapsa madla
  fgap(1),
  nl([{ z: pZ(140), y0: pY(562), y1: pY(578), nx: 185 }, { z: pZ(100), y0: pY(562), y1: pY(578), nx: 185 }]),    // drážka u zámku víka (vpravo od madla)
  fgap(2),
  nl([{ z: pZ(131), y0: pY(612), y1: pY(680), nx: 180 }, { z: pZ(108), y0: YR[0], y1: YR[1], nx: 180 }, { z: K.zRim - 0.8, y0: YR[0], y1: YR[1], nx: 180 }]),   // rámeček západky vpravo
  pad(712, 737),
];

// výřezy ve zkosených rozích (hluboká svislá kapsa v rohu dole, c01 px 746..766 / 34..54, py 168..354) – hloubka neověřena (odhad 20 mm)
export const CNOTCHES = [{ fr: [{ z: pZ(354), t0: 0.0, t1: 0.78, d: 20 }, { z: pZ(168), t0: 0.0, t1: 0.78, d: 20 }] }];

// svislý žlab v koncových stěnách (zpětná projekce šikmé fotografie L153707: okraje X = -50 a +32, z' 35..178), hloubka neověřena (odhad 4 mm)
export const ENOTCHES = [{ fr: [{ z: 38, x0: -50, x1: 32, d: 4 }, { z: 176, x0: -50, x1: 32, d: 4 }] }];

function logo(g) {
  // logo HILTI jako tenká bílá plocha na čelním panelu (obdélníky podle c01 px; písmena H I L T I)
  const R = [[462, 478, 205, 235], [508, 524, 205, 235], [478, 508, 213, 227], [528, 544, 205, 235], [548, 565, 205, 235], [548, 599, 222, 235], [587, 656, 205, 219], [613, 629, 219, 235], [660, 676, 205, 235]];
  for (const [a, b, c, d] of R) g.add(bx('bila', 'logo_hilti', K.xF - 0.1, K.xF + 0.35, pY(a), pY(b), pZ(d), pZ(c)));
}

function zamekPanel(g) {
  // černý stohovací zámek v kapse vlevo dole (c01: px 172..220, py 283..358); dno kapsy je v x = 168
  g.add(extYZ('cerna_mat', 'zamek_cerny', [[pY(172), pZ(361)], [pY(224), pZ(361)], [pY(232), pZ(345)], [pY(232), pZ(292)], [pY(218), pZ(277)], [pY(172), pZ(277)], [pY(160), pZ(292)], [pY(160), pZ(345)]], 166, 176.5));
  g.add(bx('seda', 'zamek_jazyk', 176.4, 178.4, pY(180), pY(212), pZ(332), pZ(324)));
  // šipka vedle kapsy: neověřeno (jen rytý znak)
}

function zapadky(g) {
  for (const s of [-1, 1]) {
    const Y = s < 0 ? Y_LATCH : Y_LATCH_R;
    const yc = (Y[0] + Y[1]) / 2;
    // černé dno rámečku (osmiúhelník se zkosenými spodními rohy) a červený jazyk (c01 px 123..177, py 88..107)
    const j0 = yc - 18.7, j1 = yc + 18.7;
    g.add(bx('cervena', 'zapadka_jazyk', 180.5, 184.4, j0, j1, pZ(107), pZ(88)));
    for (const py of [94, 101]) g.add(bx('cerna_mat', 'zapadka_drazka', 184.3, 184.8, j0 + 1, j1 - 1, pZ(py + 1), pZ(py)));
  }
}

function nozky(g) {
  // 4 nožky (kolejnice ve směru X); Y středy podle černých patek v c01 (px 91, 297, 503, 709), šířky z c01; hloubka v X a spodní strana neověřeny
  for (const [px, w] of FOOT) {
    const yc = pY(px);
    g.add(extYZ('cervena', 'nozka', [[yc - w / 2 + 2, 0], [yc + w / 2 - 2, 0], [yc + w / 2, 9], [yc - w / 2, 9]], -158, 166));
    g.add(bx('cerna_mat', 'nozka_patka', 160, 170, yc - 6.3, yc + 6.3, 0, 16.5));
  }
}

function pant(g) {
  // spodní články pantu na zadní straně (liché úseky); osa Y, střed x = -187, z' = 210,5; neověřeno (zadní strana na fotografiích není)
  const seg = 500 / 7;
  for (let i = 0; i < 7; i++) {
    if (i % 2 === 0) continue;
    const y0 = -250 + i * seg + 0.6, y1 = -250 + (i + 1) * seg - 0.6;
    g.add(rb('cervena', 'pant_clanek', { x0: -193.5, x1: -181, y0, y1, z0: 203, z1: 217.5, rc: 3, re: 2, seg: 2, fs: 2 }));
  }
}

export function korpus() {
  const g = new Group('korpus');
  g.add(vana('cervena', 'korpus_vana', { frames: FRAMES, notches: NOTCHES, cnotches: CNOTCHES, enotches: ENOTCHES, wall: 3.5, floorZ: K.floorZ }));
  logo(g); zamekPanel(g); zapadky(g); nozky(g); pant(g);
  return g;
}
