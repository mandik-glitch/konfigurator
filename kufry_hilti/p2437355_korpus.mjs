// Korpus (spodní díl) Hilti ProKit PKC 19 (2437355): vana s límcem, výřez madla v čele, kapsy západek, nožky, černé díly madla.
// Vnitřek je zjednodušený (prázdná hladká dutina, rovné dno). Míry jsou z čelní fotografie L153708 (= c01; měřeno ve velikosti 1200 × 365 px, převod px → mm viz
// p2437355_zaklad.mjs: pY, pZ) a z fotografie ISO L153709 (konec, kamera z landmarků); co na fotografiích není vidět, je v poznámkách označeno „neověřeno“.
import { Group, Part, vana, extYZ, bx, rb, cylX, zc, pY, pZ } from './p2437355_zaklad.mjs';

export const K = {
  zRim: 119.5,        // horní okraj korpusu = dělicí spára s víkem (spodní hrana lemu víka z' 118,2; c01 py 108)
  zSh: 91.0,          // konec rovné spodní stěny, odtud rameno (zkosení) do límce
  zCol: 100.6,        // spodní okraj límce (y ±271,7)
  floorZ: 17.5,       // horní plocha dna (vnitřní hloubka 102 mm pod okrajem 119,5)
  xF: 186, xR: -188,  // čelní / zadní rovina spodní části (hloubky nejsou z čelní fotografie měřitelné – neověřeno)
  xFc: 187, xRc: -191,          // čelní rovina límce a pláště víka
  yC: 245,            // konec rovné čelní hrany límce (zkosený roh čelo→bok začíná v Y = ±245; c01 px 1130 ↔ 70)
  yCl: 238,           // totéž pro spodní stěnu (px 1115 ↔ 85 → Y ±237,8)
};
// kapsa západky vlevo / vpravo (c01 px 154..297 a 903..1046)
const LP = [pY(154), pY(297)], LP_R = [pY(903), pY(1046)];
export const LATCH = { L: LP, R: LP_R };
export const Y_HANDLE = Math.abs(pY(372));    // polovina šířky výřezu madla v lemu víka (px 372..828 → ±105,3)
export const Y_REC = Math.abs(pY(447));       // polovina šířky červené vnitřní kapsy mezi černými sloupky madla (px 447..753 → ±70,6)
export const X_REC = 150;                     // hloubka kapsy madla (zadní stěna kapsy) – neověřeno (odhad)

// snímky půdorysu: z', xf, xr, y (půlšířka), yF (konec rovné čelní hrany), cfx (hloubka zkosení v X), rr (zadní rohy), wx/wy (stěna)
const F = (z, xf, xr, y, yF, cfx = 19, rr = 8, wx = 6, wy = 6) => ({ z, xf, xr, y0: -y, y1: y, yF, cfx, rr, wx, wy });
// profil Y je z obrysu čelní fotografie (půlšířka po 2–3 mm výšky), profil X (xf, xr) u spodního zkosení je odhad (neověřeno)
export const FRAMES = [
  F(12.2, 158, -166, 234.5, 216), F(15, 161, -169, 235.4, 217), F(17.7, 164, -172, 236.8, 218), F(20.5, 169, -177, 241.9, 223),
  F(23.2, 175, -182, 247.2, 228), F(26, 180, -186, 251.6, 233), F(28.8, 184, -188, 254.6, 236), F(31.5, K.xF, K.xR, 255.3, 237), F(37, K.xF, K.xR, 256.4, K.yCl),
  F(65, K.xF, K.xR, 256.8, K.yCl), F(K.zSh - 0.01, K.xF, K.xR, 257.1, K.yCl),
  F(K.zSh, K.xF, K.xR, 257.1, K.yCl, 19, 8, 6, 6),
  F(K.zCol, K.xFc, K.xRc, 271.7, K.yC, 26, 8, 4.5, 13.5), F(K.zRim, K.xFc, K.xRc, 271.7, K.yC, 26, 8, 4.5, 13.5),
];
const nl = (fr) => ({ fr });
// výřezy v čelní hraně (zleva doprava podle Y); nx = X dna výřezu
// spodní (užší) hrana kapsy západky: px 185..270 vlevo, zrcadlově 930..1015 vpravo (zkosené spodní rohy)
const pocketBot = P => P === LP ? [pY(185), pY(270)] : [pY(930), pY(1015)];
const pocket = (P) => nl([
  { z: pZ(175), y0: pocketBot(P)[0], y1: pocketBot(P)[1], nx: 180 },
  { z: pZ(150), y0: P[0], y1: P[1], nx: 180 }, { z: K.zRim - 0.8, y0: P[0], y1: P[1], nx: 180 }]);
export const NOTCHES = [
  pocket(LP),                                                                                        // kapsa západky vlevo
  nl([{ z: 14, y0: -108.5, y1: 108.5, nx: X_REC }, { z: K.zRim - 0.8, y0: -108.5, y1: 108.5, nx: X_REC }]),   // kapsa madla (černé sloupky vyplňují krajní části)
  pocket(LP_R),                                                                                      // kapsa západky vpravo
];
export const CNOTCHES = [];
export const ENOTCHES = [];

function kapsaMadla(g) {
  // černé sloupky madla (px 365..447 a 753..835, py 123..327 → Y ±70,6..108,5, z' 14..119) a spodní příčka s úchopem (py 280..338)
  for (const s of [-1, 1]) {
    const a = 70.6, b = 108.5;
    g.add(extYZ('cerna_mat', 'madlo_sloupek', [[s * a, 24], [s * b, 24], [s * b, 119], [s * a, 119]], X_REC + 1, 184.5));
    // světlejší (plastové) žebro na vnitřní hraně sloupku (jen drobná plocha)
    g.add(bx('cerna', 'madlo_sloupek_lista', 183.5, 185, s * (a + 1), s * (b - 1), 24, 100));
  }
  // černý jazyk uprostřed kapsy (px 540..660, py 222..282 → Y ±27,7, z' 38..65)
  g.add(extYZ('cerna', 'madlo_jazyk_kapsa', [[-27.7, 38], [27.7, 38], [27.7, 62], [23, 65], [-23, 65], [-27.7, 62]], X_REC, 164));
  // spodní úchop: kulatá lišta přes celou šířku kapsy (py 282..338 → z' 38..12), přední hrana vystupuje před čelo
  g.add(extYZ('cerna', 'madlo_uchop', [[-93, 12.5], [93, 12.5], [108.5, 29], [108.5, 36], [-108.5, 36], [-108.5, 29]], 160, 190.5));
  g.add(extYZ('cerna', 'madlo_uchop_nahore', [[-102, 36], [102, 36], [96, 42], [-96, 42]], 168, 189));
}

function zapadky(g) {
  for (const P of [LP, LP_R]) {
    const yc = (P[0] + P[1]) / 2;
    // černé dno kapsy (obrys = výřez) a červený jazyk (c01 px 190..265, py 112..150)
    const [b0, b1] = pocketBot(P);
    g.add(extYZ('cerna_mat', 'zapadka_dno', [[P[0], pZ(150)], [b0, pZ(175)], [b1, pZ(175)], [P[1], pZ(150)], [P[1], K.zRim - 0.8], [P[0], K.zRim - 0.8]], 176, 181));
    const j0 = P === LP ? pY(190) : pY(1200 - 265), j1 = P === LP ? pY(265) : pY(1200 - 190);
    g.add(bx('cervena', 'zapadka_jazyk', 180.5, 184.4, j0, j1, pZ(150), pZ(112)));
    for (const z of [pZ(122), pZ(130)]) g.add(bx('cerna_mat', 'zapadka_drazka', 184.3, 184.8, j0 + 2, j1 - 2, z - 0.8, z));
  }
}

function nozky(g) {
  // 4 nožky; Y středy a šířky z čelní fotografie (px 148, 450, 750, 1052; šířka 44–48 mm). Hloubka v X: z ISO (L153709) je u konce vidět blok jen v X ≈ −125..+66,
  // před ním (a za ním) je nožka nižší – tvar spodní strany je neověřený odhad. Čelní patka (černá) je z čelní fotografie.
  for (const yc of [-208.7, -69.3, 69.3, 208.7]) {
    const prof = (h) => [[yc - 21.5, 0], [yc + 21.5, 0], [yc + 21.5 + (24 - 21.5) * h / 12.8, h], [yc - 21.5 - (24 - 21.5) * h / 12.8, h]];
    g.add(extYZ('cervena', 'nozka', prof(12.8), -125, 66));
    g.add(extYZ('cervena', 'nozka_predni', prof(12.8), 100, 156));
    g.add(extYZ('cervena', 'nozka_most', [[yc - 21, 6], [yc + 21, 6], [yc + 22, 12.8], [yc - 22, 12.8]], 60, 104));
    g.add(extYZ('cervena', 'nozka_zadni', [[yc - 21, 6], [yc + 21, 6], [yc + 22, 12.8], [yc - 22, 12.8]], -150, -120));
    g.add(bx('cerna_mat', 'nozka_patka', 148, 158, yc - 9, yc + 9, 0, 11.5));
  }
}

function pant(g) {
  // spodní články pantu na zadní straně (liché úseky); osa Y, střed x = -187, z' = 118,5; neověřeno (zadní strana na fotografiích není)
  const seg = 500 / 7;
  for (let i = 0; i < 7; i++) {
    if (i % 2 === 0) continue;
    const y0 = -250 + i * seg + 0.6, y1 = -250 + (i + 1) * seg - 0.6;
    g.add(rb('cervena', 'pant_clanek', { x0: -193.5, x1: -181, y0, y1, z0: 111, z1: 125.5, rc: 3, re: 2, seg: 2, fs: 2 }));
  }
}

function logo(g) {
  // logo HILTI (bílá plocha) na koncové stěně +Y – poloha z ISO fotografie L153709 zpětnou projekcí na rovinu Y = 256,5: X +41,4 … −46,5, z' 71 … 83 (±3 mm);
  // tvar písmen = obdélníky podle logoty z čelní fotografie PKC 35 (px 462..676 × 205..235), přeškálované na 88 × 12,2 mm
  const R = [[462, 478, 205, 235], [508, 524, 205, 235], [478, 508, 213, 227], [528, 544, 205, 235], [548, 565, 205, 235], [548, 599, 222, 235], [587, 656, 205, 219], [613, 629, 219, 235], [660, 676, 205, 235]];
  const X = px => 41.4 - (px - 462) / 214 * 88, Z = py => 83.2 - (py - 205) / 30 * 12.2;
  for (const [a, b, c, d] of R) g.add(bx('bila', 'logo_hilti', X(b), X(a), 256.75, 257.45, Z(d), Z(c)));
}

export function korpus() {
  const g = new Group('korpus');
  g.add(vana('cervena', 'korpus_vana', { frames: FRAMES, notches: NOTCHES, cnotches: CNOTCHES, enotches: ENOTCHES, wall: 3.5, floorZ: K.floorZ }));
  kapsaMadla(g); zapadky(g); logo(g); nozky(g); pant(g);
  return g;
}
