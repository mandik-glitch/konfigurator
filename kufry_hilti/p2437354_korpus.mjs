// Korpus (spodní díl) Hilti ProKit PKC 61 (2437354, Box na nářadí ProKit XL): vana s límcem, výřezy v čele (kapsa madla, kapsa stohovacího zámku, rámečky západek,
// výřez v soklu), nožky, boční madla na koncích, logo (bílá plocha). Vnitřek je zjednodušený (prázdná dutina, hladké stěny a dno).
// Míry z čelní fotografie c01 (1200 × 913 px, převod px → mm v p2437354_zaklad.mjs: pY, pZ); co z fotografií nejde změřit, je v poznámkách označeno „neověřeno“.
import { Group, Part, vana, extYZ, bx, rb, oct, cylX, zc, pY, pZ, lY, lZ, DZ } from './p2437354_zaklad.mjs';

export const K = {
  zRim: 366.5,        // horní okraj korpusu = dělicí spára s víkem (spodní hrana lemu víka py ~125 → z' 364; lem PKC 35 + DZ 155 → 364,8; okraj o 1,7 výš jako u PKC 35)
  zBand: 293.5,       // spodní hrana horního pásu (římsa pod pásem s kapsou madla, c01 py ~278)
  zPocket: 308.0,     // podlaha kapsy madla (c01 py 245)
  floorZ: 18.0,       // horní plocha dna (vnitřní hloubka 348 mm pod okrajem 366,5)
  xF: 186, xR: -183,  // čelní / zadní rovina spodní části (jako PKC 35; hloubky z čelní fotografie neměřitelné – neověřeno)
  xFc: 187,           // čelní rovina horního pásu a límce (= plášť víka)
  yC: 234,            // konec rovné čelní hrany panelu (c01 px 100 → y = −233,8); dál zkosený roh čelo→bok
  yCL: 243.5,         // totéž pro límec/víko (jako PKC 35 + 2,5 mm)
};
// rámečky západek (černý rámeček c01 px 155..300 a 900..1050) – shodné s PKC 35 (y −208…−140 / +140…+210)
const Y_LATCH = [pY(155), pY(300)];
const Y_LATCH_R = [pY(900), pY(1050)];
export const LATCH = { L: Y_LATCH, R: Y_LATCH_R };
export const Y_HANDLE = 106;                 // polovina šířky kapsy madla (c01 px 375..830 → −105,2…+107,5)

// snímky půdorysu: z', xf, xr, y0=−y, y1=y, yF (konec rovné čelní hrany), cfx (hloubka zkosení v X), rr (zadní rohy), wx, wy (stěny v X a v Y; z kót výrobce – viz poznámky)
const F = (z, xf, xr, y, yF, cfx = 20, rr = 8, wx = 9, wy = 3.5) => ({ z, xf, xr, y0: -y, y1: y, yF, cfx, rr, wx, wy });
export const FRAMES = [
  // spodní hrana: zkosení ve čtyřech stupních (c01 obrys py 862..912: y ±251,5 → ±237 → ±235)
  F(12, 172, -171, 235.5, 220, 15, 8, 5, 3.5), F(15.3, 175, -174, 237, 222, 15, 8, 5, 3.5), F(19.9, 179, -178, 245.4, 228, 18, 8, 6, 3.5), F(24.5, 184, -182.5, 251.5, 233, 20, 8, 8, 3.5),
  F(30, K.xF, K.xR, 252.2, K.yC),
  // boky se mírně rozbíhají nahoru (c01 obrys: px 62 u py 860 → px 53 u py 340, tj. ±251,6 → ±255,7)
  F(K.zBand - 0.01, K.xF, K.xR, 255.6, K.yC),
  F(K.zBand, K.xFc, -K.xFc, 255.8, K.yC, 20, 8, 11.5, 3.5),
  F(333, K.xFc, -K.xFc, 256.5, K.yC, 20, 8, 11.5, 3.5),             // pod límcem
  F(346, K.xFc, -K.xFc, 274, K.yCL, 22, 8, 11.5, 21),                // límec (rozšíření k lemu víka); wy = 21 → vnitřní šířka 506 mm podle kóty
  F(K.zRim, K.xFc, -K.xFc, 274, K.yCL, 22, 8, 11.5, 21),
];
const nl = fr => ({ fr });
const YL = Y_LATCH, YR = Y_LATCH_R;
// nožky: [y středu, šířka] (c01 spodní okraj: patky px ~150, 445, 760, 1055 → y −210, −72, +75, +213)
const FOOT = [[-211, 38], [-73, 34], [74, 34], [212, 38]];
const gapY = i => [FOOT[i][0] + FOOT[i][1] / 2, FOOT[i + 1][0] - FOOT[i + 1][1] / 2];
const fgap = i => nl([{ z: 12, y0: gapY(i)[0], y1: gapY(i)[1], nx: 160 }, { z: 19, y0: gapY(i)[0], y1: gapY(i)[1], nx: 160 }]);
const pad = (a, b) => nl([{ z: pZ(300), y0: pY(a), y1: pY(b), nx: K.xF - 1.2 }, { z: pZ(620), y0: pY(a), y1: pY(b), nx: K.xF - 1.2 }]);
const latch = Y => nl([{ z: pZ(198), y0: Y[0] + 14, y1: Y[1] - 14, nx: 180 }, { z: pZ(173), y0: Y[0], y1: Y[1], nx: 180 }, { z: K.zRim - 0.8, y0: Y[0], y1: Y[1], nx: 180 }]);
// stohovací zámek v soklu vlevo (c01 px 248..341, py 760..868 → y −164,6…−121,1; z' 21…71), osmiúhelník se zkosenými rohy
const zam = nl([{ z: pZ(868), y0: pY(262), y1: pY(327), nx: 168 }, { z: pZ(855), y0: pY(248), y1: pY(341), nx: 168 }, { z: pZ(775), y0: pY(248), y1: pY(341), nx: 168 }, { z: pZ(760), y0: pY(262), y1: pY(327), nx: 168 }]);
export const NOTCHES = [
  pad(104, 135),                                                      // vtlačený pruh u levého okraje čelní desky (c01 px 100..135)
  latch(YL),                                                          // rámeček západky vlevo
  fgap(0),                                                            // mezera mezi nožkami 1–2
  zam,
  nl([{ z: pZ(850), y0: -67.8, y1: 67.8, nx: 146 }, { z: pZ(668), y0: -67.8, y1: 67.8, nx: 146 }]),   // výřez v soklu (c01 px 455..745, py 668..850) – hloubka neověřena
  nl([{ z: K.zPocket, y0: -Y_HANDLE, y1: Y_HANDLE, nx: 158 }, { z: K.zRim, y0: -Y_HANDLE, y1: Y_HANDLE, nx: 158 }]),   // kapsa madla
  fgap(1),
  fgap(2),
  latch(YR),                                                          // rámeček západky vpravo
  pad(1065, 1096),
];
export const CNOTCHES = [];
export const ENOTCHES = [];

function logo(g) {
  // logo HILTI jako tenká bílá plocha na čelním panelu; obdélníky vyčtené z masky bílé barvy v c01 (px: x0,x1,y0,y1): H = dva svislé + příčka, I, L, T, I
  const R = [[694, 718, 335, 380], [762, 787, 335, 380], [718, 762, 347, 368], [793, 817, 335, 380], [823, 848, 335, 380], [823, 900, 359, 380], [880, 984, 335, 355], [919, 945, 355, 380], [990, 1014, 335, 380]];
  for (const [a, b, c, d] of R) g.add(bx('bila', 'logo_hilti', K.xF - 0.1, K.xF + 0.35, pY(a), pY(b), pZ(d), pZ(c)));
}

function zamekPanel(g) {
  // černý stohovací zámek v kapse vlevo dole (c01 px 258..335, py 770..865); dno kapsy je v x = 168
  g.add(extYZ('cerna_mat', 'zamek_cerny', oct(pY(250), pY(340), pZ(866), pZ(762), 6, 6), 166, 176.5));
  g.add(bx('seda', 'zamek_jazyk', 176.4, 178.4, pY(282), pY(320), pZ(838), pZ(826)));
  // šipka vedle kapsy (px 358, py 800): neověřeno (jen rytý znak)
}

function zapadky(g) {
  for (const s of [-1, 1]) {
    const Y = s < 0 ? Y_LATCH : Y_LATCH_R;
    const yc = (Y[0] + Y[1]) / 2;
    // červený jazyk (c01 px 187..266, py 130..161)
    const j0 = yc - 18.7, j1 = yc + 18.7;
    g.add(bx('cervena', 'zapadka_jazyk', 180.5, 184.4, j0, j1, pZ(161), pZ(130)));
    for (const py of [139, 148]) g.add(bx('cerna_mat', 'zapadka_drazka', 184.3, 184.8, j0 + 1, j1 - 1, pZ(py + 1.5), pZ(py)));
  }
}

function nozky(g) {
  // 4 nožky (kolejnice ve směru X); Y středy a šířky podle spodního okraje c01; hloubka v X a spodní strana neověřeny
  for (const [yc, w] of FOOT) {
    g.add(extYZ('cervena', 'nozka', [[yc - w / 2 + 2, 0], [yc + w / 2 - 2, 0], [yc + w / 2, 13], [yc - w / 2, 13]], -158, 166));
    g.add(bx('cerna_mat', 'nozka_patka', 160, 170, yc - 7, yc + 7, 2, 20));
  }
}

// boční madla na koncích (c01: černé bloky px 0..55 a 1145..1200, py 200..335 → y ±254…±280,5, z' 267…330; červený držák nad nimi py 125..200 ve stejné šířce)
// Délka madla ve směru X (MAD.x) je jen odhad z šikmých fotografií (c02, c03) – viz poznámky.
export const MAD = { x0: -100, x1: 70, y0: 252, y1: 280.5, zA: pZ(335), zB: pZ(200), zC: pZ(125) };
function madla(g) {
  // černý rám madla: dvě svislé vzpěry na koncích, spodní úchop a horní příčka; v okně rámu je vidět stěna kufru (tvar okna podle c02/c03, neověřeno)
  for (const s of [-1, 1]) {
    const ya = s * MAD.y0, yb = s * MAD.y1, lo = Math.min(ya, yb), hi = Math.max(ya, yb);
    const part = (n, x0, x1, z0, z1) => g.add(rb('cerna', n, { x0, x1, y0: lo, y1: hi, z0, z1, rc: 3, re: 3, seg: 3, fs: 3 }));
    part('madlo_bok_uchop', MAD.x0, MAD.x1, MAD.zA, MAD.zA + 20);
    part('madlo_bok_vzpera', MAD.x1 - 28, MAD.x1, MAD.zA, MAD.zB);
    part('madlo_bok_vzpera', MAD.x0, MAD.x0 + 28, MAD.zA, MAD.zB);
    part('madlo_bok_pricka', MAD.x0, MAD.x1, MAD.zB - 10, MAD.zB);
    g.add(rb('cervena', 'madlo_bok_drzak', { x0: MAD.x0 + 2, x1: MAD.x1 - 2, y0: lo, y1: s < 0 ? hi : hi - 1.5, z0: MAD.zB - 1, z1: K.zRim - 1.5, rc: 3, re: 3, seg: 3, fs: 3 }));
  }
}

function sokl(g) {
  // přechod čelního panelu do soklu: klínová lišta pod spodní hranou panelu (c01: hrana py 628 u konců → py 668 u výřezu, pod ní světlá šikmá plocha); vyložení 2,5 mm je odhad
  for (const s of [-1, 1]) {
    const yE = s * 233.8, yN = s * 67.8, z0 = pZ(628), z1 = pZ(668);
    g.add(extYZ('cervena', 'sokl_klin', [[yE, z0], [yN, z1], [yE, z1]], K.xF - 0.5, K.xF + 2));
  }
}

function zamekVika(g) {
  // svislý červený čep zámku víka vpravo od madla (c01 px 845..862, py 122..215 – dolní část, pokračuje do víka); výška a vyložení neověřeny
  g.add(bx('cervena', 'zamek_vika_dolni', 187, 190, pY(843), pY(862), pZ(215), K.zRim));
}

function pant(g) {
  // spodní články pantu na zadní straně (liché úseky); osa Y, střed x = −187, z' = zRim − 1; neověřeno (zadní strana na fotografiích není)
  const seg = 500 / 7;
  for (let i = 0; i < 7; i++) {
    if (i % 2 === 0) continue;
    const y0 = -250 + i * seg + 0.6, y1 = -250 + (i + 1) * seg - 0.6;
    g.add(rb('cervena', 'pant_clanek', { x0: -193.5, x1: -181, y0, y1, z0: K.zRim - 8.5, z1: K.zRim + 6, rc: 3, re: 2, seg: 2, fs: 2 }));
  }
}

export function korpus() {
  const g = new Group('korpus');
  g.add(vana('cervena', 'korpus_vana', { frames: FRAMES, notches: NOTCHES, cnotches: CNOTCHES, enotches: ENOTCHES, wall: 3.5, floorZ: K.floorZ }));
  logo(g); sokl(g); zamekPanel(g); zapadky(g); nozky(g); madla(g); zamekVika(g); pant(g);
  return g;
}
