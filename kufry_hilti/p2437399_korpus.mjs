// Korpus (spodní díl) Hilti ProKit PKC 18-H (2437399, box s poloviční šířkou): vana s límcem a hladkou dutinou, kapsa madla a kapsa stohovacího zámku v čele,
// pás s logem, dvě patky (kolejnice), černé díly, spodní články pantu. Vnitřek je zjednodušený (prázdná dutina, hladké stěny a dno).
// Míry z čelní fotografie c01 (741 × 800 px; převod px → mm viz p2437399_zaklad.mjs: pY, pZ); co není na fotografii vidět, je v poznámkách označeno „neověřeno“.
import { Group, Part, vanaD, extYZ, bx, rb, cylX, cylinder, prism, zc, pY, pZ } from './p2437399_zaklad.mjs';

export const K = {
  zRim: 240.5,        // horní okraj korpusu = dělicí spára s víkem (spodní hrana lemu víka, c01 py ~150)
  zBand: 168.0,       // horní hrana pásu s logem (c01 py 345)
  floorZ: 16.0,       // horní plocha dna dutiny (spodek středu dna z' 12; vnitřní hloubka ~227 mm měřeno od lemu víka)
  xF: 187, xR: -187,  // čelní / zadní rovina spodní části (hloubka není z čelní fotografie měřitelná – odvozeno z katalogu 389 a z poměrů PKC 35, neověřeno)
  xFc: 188,           // čelní rovina horního pásu a límce (= plášť víka)
  hw: 63,             // polovina šířky kapes madla a zámku (c01 px 201..540)
};
const F = (z, xf, y, yF, cfx, xr = -xf, rr = 8) => ({ z, xf, xr, y0: -y, y1: y, yF, cfx, rr });
// snímky půdorysu (z', přední rovina, polovina šířky, konec rovné části čela, hloubka zkosení rohu čelo→bok); boční obrys z c01 (siluety po řádcích)
export const FRAMES = [
  F(12, 166, 94.5, 80, 14.5), F(18.4, 170, 96.9, 82, 15), F(22.1, 176, 104.3, 86, 18.3), F(25.8, 181, 109.8, 89, 20.8), F(29.5, 184, 113.2, 91, 22.2),
  F(37, K.xF, 115.6, 92, 23.6),
  F(K.zBand - 0.01, K.xF, 117.7, 92, 25.7), F(K.zBand, K.xFc, 117.7, 92, 25.7),
  F(211, K.xFc, 118.4, 92, 26.4), F(222, K.xFc, 131.2, 100, 31.2), F(K.zRim, K.xFc, 131.5, 100, 31.5),
];
// dutina (hladká, nezávislá na vnějším tvaru): vnitřní rozměr 283 × 229 u dna (katalog) a ~291 × 240 u okraje (kóta c03: 24 cm)
const G = (z, x, y) => ({ z, xf: x, xr: -x, y0: -y, y1: y, yF: y - 9, cfx: 9, rr: 9 });
// svislé mělké žlábky v bočních stěnách (c03: čára u px 392 → X ≈ +27 ±5 mm; hloubka a rozsah neověřeny)
export const ENOTCHES = [{ fr: [{ z: 38, x0: 24, x1: 30, d: 1.5 }, { z: 210, x0: 24, x1: 30, d: 1.5 }] }];
export const DUTINA = [G(K.floorZ, 141.5, 114.5), G(K.zRim, 146, 120)];

// výřezy v čelní hraně (zleva doprava podle Y): kapsa madla (pod černým madlem, šikmý nájezd na pás s logem) a kapsa zámku
const nl = fr => ({ fr });
export const NOTCHES = [
  nl([{ z: K.zBand, y0: -K.hw, y1: K.hw, nx: K.xF - 0.5 }, { z: 180.7, y0: -K.hw, y1: K.hw, nx: 159 }, { z: K.zRim, y0: -K.hw, y1: K.hw, nx: 159 }]),
  nl([{ z: 24, y0: -K.hw, y1: K.hw, nx: 169 }, { z: 106, y0: -K.hw, y1: K.hw, nx: 169 }]),
];

// rozměry madla a vyražený obrys (c01: šestiúhelník px (228,108) (513,108) (538,127) (501,195) (240,195) (203,127))
export const MADLO = [[pY(228), pZ(108)], [pY(513), pZ(108)], [pY(538), pZ(127)], [pY(501), pZ(195)], [pY(240), pZ(195)], [pY(203), pZ(127)]];

function logo(g) {
  // logo HILTI jako tenká bílá plocha na pásu (c01: rozklad na obdélníky px; písmena H I L T I)
  const R = [[210, 235, 392, 436], [278, 303, 392, 436], [210, 303, 403, 425], [309, 333, 392, 436], [340, 364, 392, 436], [340, 416, 416, 436], [396, 500, 392, 412], [436, 460, 392, 436], [506, 531, 392, 436]];
  for (const [a, b, c, d] of R) g.add(bx('bila', 'logo_hilti', K.xF - 0.1, K.xF + 0.35, pY(a), pY(b), pZ(d), pZ(c)));
}

function klinSte(g) {
  // šikmé boky kapsy madla (kapsa se k dnu zužuje: otvor ±63, dno ±48 – tmavé pásy po stranách v c01); trojboký hranol v půdorysu
  const wedge = (s) => {
    const P = [[159, 48 * s], [159, 63 * s], [K.xFc, 63 * s]];
    let a = 0; for (let i = 0; i < 3; i++) { const p = P[i], q = P[(i + 1) % 3]; a += p[0] * q[1] - q[0] * p[1]; }
    return prism('cervena', 'kapsa_klin', a < 0 ? P.slice().reverse() : P, zc(180.7), zc(224));
  };
  g.add(wedge(1)); g.add(wedge(-1));
}

function zamek(g) {
  // černý stohovací zámek v kapse (c01: černé tělo py ~630..730, žebrovaná horní část py 575..640, osa souměrnosti px 370,5); dno kapsy x = 169
  g.add(extYZ('cerna_mat', 'zamek_cerny', [[-26.5, 26], [26.5, 26], [29.5, 29], [29.5, 60], [-29.5, 60], [-29.5, 29]], 167, 178.5));
  g.add(extYZ('cerna_mat', 'zamek_zebra', [[-29, 60], [29, 60], [25, 82], [-25, 82]], 167, 175.5));
  for (let i = 0; i < 6; i++) { const y = -21 + i * 8.4; g.add(extYZ('seda', 'zamek_zebro', [[y, 61], [y + 3, 61], [y + 6.5, 81], [y + 3.5, 81]], 175.4, 176.1)); }
  g.add(bx('cerna_mat', 'zamek_zaves', 176, 179.5, -29.5, 29.5, 57.5, 60));
}

function nozky(g) {
  // dvě patky (kolejnice ve směru X) pod rohy dna: Y |46,6 .. 90| u země, zkosená vnější strana (c01: spodní hrana po sloupcích); délka v X a spodní strana neověřeny
  for (const s of [-1, 1]) {
    const P = [[46.6, 0], [90, 0], [96.5, 14.8], [97.2, 18], [97.2, 18.4], [46.6, 18.4]].map(([y, z]) => [s * y, z]);
    g.add(extYZ('cervena', 'nozka', P, -166, 169));
    // černé gumové dorazy (c01 px ~145..235 / 515..605, py 765..790)
    g.add(bx('cerna_mat', 'nozka_doraz', 168.5, 170.2, Math.min(s * 83.5, s * 50), Math.max(s * 83.5, s * 50), 5, 14));
  }
}

function pant(g) {
  // spodní články pantu na zadní straně (liché úseky z 5); osa Y, střed x = -188; neověřeno (zadní strana na fotografiích není vidět jinak než zevnitř v c02/c03)
  const seg = 230 / 5;
  for (let i = 0; i < 5; i++) {
    if (i % 2 === 0) continue;
    const y0 = -115 + i * seg + 0.6, y1 = -115 + (i + 1) * seg - 0.6;
    g.add(rb('cervena', 'pant_clanek', { x0: -194.5, x1: -181, y0, y1, z0: 234.5, z1: 249, rc: 3, re: 2, seg: 2, fs: 2 }));
  }
  g.add(cylinder('ocel', 'pant_kolik', 2.4, -115, 115, 14, [0, 0]).mapV((u, v, w) => [u - 188, w, v + zc(241.8)]).flip());
}

export function korpus() {
  const g = new Group('korpus');
  g.add(vanaD('cervena', 'korpus_vana', { outer: { frames: FRAMES, notches: NOTCHES, enotches: ENOTCHES }, inner: { frames: DUTINA } }));
  logo(g); klinSte(g); zamek(g); nozky(g); pant(g);
  return g;
}
