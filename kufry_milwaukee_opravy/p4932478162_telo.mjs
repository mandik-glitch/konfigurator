// Spodní díl (tělo) XL boxu: dutá vana, boční zapuštěná pouzdra s rukojetí, čelní panel, nohy, spodní zámková šachta s červenou rukojetí, vnitřek (vložka, podložky).
import { Part, Group, rrPoly, loftBox, loftVessel, rbox, bx, extYZ, extXZ, cylX, cylY, addSymY, mirY, mirX, extrude, roundPoly, tube } from './p4932478162_zaklad.mjs';
import { HX, HY, HZ, Z_SEAM, Z_BOT, BODY } from './p4932478162_data.mjs';

const W = 4;   // tloušťka stěny (odhad)
const insetL = (L, d, z) => ({ x0: L.x0 + d, x1: L.x1 - d, y0: L.y0 + d, y1: L.y1 - d, r: Math.max(L.r - d, 1), z });

// vnější vrstvy vany (boční plocha |Y| = 222 – boční panely se přidávají zvlášť, aby šla vytvořit pouzdra rukojetí)
const YB = 222;
export const VANA = [
  { z: Z_BOT, x0: -166, x1: 160, y0: -(YB - 14), y1: YB - 14, r: 22 },
  { z: Z_BOT + 8, x0: -176, x1: 174, y0: -(YB - 4), y1: YB - 4, r: 20 },
  { z: Z_BOT + 16, x0: -182, x1: 181, y0: -YB, y1: YB, r: 18 },
  { z: Z_SEAM - 4, x0: -184, x1: 181, y0: -YB, y1: YB, r: 16 },
];

export function vana() {
  const g = new Group('telo');
  const inner = [{ ...insetL(VANA[3], W, Z_SEAM) }, { ...insetL(VANA[2], W, Z_BOT + 16) }, { ...insetL(VANA[1], W, Z_BOT + 8 + 4) }, { ...insetL(VANA[0], W + 1, Z_BOT + 6) }];
  g.add(loftVessel('cerna', 'telo_vana', VANA, inner, { seg: 4 }));
  // horní lem pod švíkem (okraj vany pod víkem), přesah ven
  g.add(loftVessel('cerna', 'telo_lem', [
    { z: Z_SEAM - 14, x0: -190, x1: 190, y0: -(BODY.yw + 6), y1: BODY.yw + 6, r: 17 },
    { z: Z_SEAM - 1, x0: -192, x1: 193, y0: -(BODY.yw + 8), y1: BODY.yw + 8, r: 17 }],
    [{ z: Z_SEAM - 1, x0: -189, x1: 190, y0: -(BODY.yw + 4), y1: BODY.yw + 4, r: 14 }, { z: Z_SEAM - 14, x0: -187, x1: 187, y0: -(BODY.yw + 1), y1: BODY.yw + 1, r: 14 }], { seg: 4 }));
  return g;
}

// boční panely (|Y| 222 → 241) s pouzdrem rukojeti (otevřené nahoře pod víkem)
export function bocniPanely(g) {
  const POC = { x0: -122, x1: 126, z0: 36 };      // pouzdro rukojeti: odhad z c01 (501784) – X od -122 do 126, dno z = 36
  for (const s of [1, -1]) {
    const y0 = s > 0 ? YB - 1 : -BODY.yw, y1 = s > 0 ? BODY.yw : -(YB - 1);
    g.add(rbox('cerna', 'bok_spodni' + (s > 0 ? '' : '_m'), -186, 186, y0, y1, Z_BOT + 14, POC.z0, 9, 2.5));
    g.add(rbox('cerna', 'bok_predni_sloupek' + (s > 0 ? '' : '_m'), POC.x1, 186, y0, y1, POC.z0 - 2, Z_SEAM - 2, 8, 2));
    g.add(rbox('cerna', 'bok_zadni_sloupek' + (s > 0 ? '' : '_m'), -186, POC.x0, y0, y1, POC.z0 - 2, Z_SEAM - 2, 8, 2));
    // dno pouzdra (stěna vany je v |Y| = 222); žebra v pouzdře
    const ys = s > 0 ? [YB, YB + 7] : [-(YB + 7), -YB];
    for (const x of [-60, 0, 60]) g.add(bx('cerna_mat', 'pouzdro_zebro' + (s > 0 ? '' : '_m') + x, x - 2, x + 2, ys[0], ys[1] + 6 * (s > 0 ? 1 : -1) * 0 , 44, 108));
    g.add(bx('cerna_mat', 'pouzdro_zlab' + (s > 0 ? '' : '_m'), POC.x0, POC.x1, s > 0 ? YB : -(YB + 8), s > 0 ? YB + 8 : -YB, POC.z0, POC.z0 + 4));
  }
  return POC;
}

// čelní panel (rovina X = 188) s kapsami pro spony; kapsa = zahloubení k rovině vany (X = 181)
export function celniPanel(g) {
  const XB = 181, XF = 188;
  const poly = [[-217, Z_BOT + 8], [217, Z_BOT + 8], [217, Z_SEAM - 2], [205, Z_SEAM - 2], [205, 45], [125, 45], [125, Z_SEAM - 2], [-125, Z_SEAM - 2], [-125, 45], [-205, 45], [-205, Z_SEAM - 2], [-217, Z_SEAM - 2]];
  g.add(extYZ('cerna', 'celo_panel', roundPoly(poly, [4, 4, 0, 0, 3, 3, 0, 0, 3, 3, 0, 0].map((v, i) => [4, 4, 0.5, 0.5, 2, 2, 0.5, 0.5, 2, 2, 0.5, 0.5][i]), 2), XB - 1, XF));
  // střední zvýšený pult pod větráním (lichoběžník), rovina X = 192
  g.add(extYZ('cerna', 'celo_pult', [[-77, 70], [70, 70], [66, 100], [66, 164], [-72, 164], [-77, 100]].map(([y, z]) => [y, z]), XF - 1, XF + 4, 22));
  // kapsy sponek: tmavé rámy po obvodu
  for (const s of [1, -1]) {
    const yc = s * 165;
    g.add(extYZ('cerna_mat', 'kapsa_ram' + (s > 0 ? '' : '_m'), [[yc - 36, 45], [yc + 36, 45], [yc + 36, 56], [yc - 36, 56]], XB, XB + 7, 22));
  }
}

// nohy a spodní žebra (odhad: přední i zadní pár, klínový tvar jako na c01/c02)
export function nohy(g) {
  for (const sy of [1, -1]) for (const sx of [1, -1]) {
    const x0 = sx > 0 ? 118 : -178, x1 = sx > 0 ? 178 : -118;
    // klínový profil v XZ: noha se zužuje dolů
    const poly = sx > 0 ? [[x0, Z_BOT + 5], [x1, Z_BOT + 5], [x1 - 6, -HZ], [x0 + 12, -HZ]] : [[x0 + 6, -HZ], [x1 - 12, -HZ], [x1, Z_BOT + 5], [x0, Z_BOT + 5]];
    const y0 = sy > 0 ? 114 : -158, y1 = sy > 0 ? 158 : -114;
    g.add(extXZ('cerna', 'noha_' + (sx > 0 ? 'p' : 'z') + (sy > 0 ? '1' : '2'), poly, y0, y1, 30));
  }
  // spodní pás (rám dna) pod vanou
  g.add(rbox('cerna', 'dno_pas', -176, 172, -222, 222, -HZ + 11, Z_BOT + 3, 16, 2));
}

// spodní zámková šachta (čelo): rám se žebrováním, červená rukojeť zámku jako samostatný uzel s pivotem na spodním čepu
export function zamekSachta(g) {
  // vystupující šachta (lichoběžník) – trojúhelníkové boky = zkosení
  g.add(extYZ('cerna', 'sachta', [[-115, -64], [113, -64], [97, -205], [-99, -205]].map(([y, z]) => [y, z]), 176, 192, 25));
  g.add(extYZ('cerna', 'sachta_hrana', [[-108, -66], [106, -66], [104, -72], [-106, -72]], 191, 195, 25));
  // žebrovaný pás nad rukojetí
  for (let k = 0; k < 11; k++) { const y = -52 + k * 9.5; g.add(bx('cerna_mat', 'sachta_zebro', 190, 196.5, y, y + 4, -96, -80)); }
  g.add(bx('cerna_mat', 'sachta_pas_h', 189, 196, -54, 56, -80, -76));
  // rám rukojeti (černý, žebrovaný) kolem červeného úchytu
  g.add(extYZ('cerna', 'sachta_ram', [[-52, -118], [54, -118], [54, -204], [-52, -204]], 187, 195.5, 22,
    [[[-40, -127], [-40, -186], [44, -186], [44, -127]]]));
  for (let k = 0; k < 9; k++) { const y = -46 + k * 11; g.add(bx('cerna_mat', 'sachta_ram_zebro', 193, 196.5, y, y + 4.5, -204, -190)); }
  g.add(bx('cerna_mat', 'sachta_zasuvka', 187, 192, -22, 22, -HZ, -190));
  // červená rukojeť zámku = uzel s pivotem (spodní čep, osa Y)
  const rk = new Group('rukojet_zamku', { pivot: [186, 0, -186], extras: { osa: [0, -1, 0], max_uhel: 55, popis: 'červená rukojeť zámku šachty (čelo dole)' } });
  const oval = (cy, cz, a, b, n = 22) => Array.from({ length: n }, (_, i) => { const t = 2 * Math.PI * i / n; return [cy + a * Math.cos(t) * Math.pow(Math.abs(Math.cos(t)), 0.0), cz + b * Math.sin(t)]; });
  const outer = roundPoly([[-44, -124], [47, -124], [47, -188], [-44, -188]], [11, 11, 11, 11], 4);
  const hole = roundPoly([[-31, -143], [34, -143], [34, -170], [-31, -170]], [9, 9, 9, 9], 4);
  rk.add(extYZ('cervena', 'rukojet_zamku_ram', outer, 187, 197, 30, [hole]));
  rk.add(extYZ('cervena', 'rukojet_zamku_jazyk', [[-20, -188], [20, -188], [20, -211], [-20, -211]], 189, 194.5, 25));
  g.addGroup(rk);
}

// vnitřek: podložky dna a vložka (odhad; z Feat_1/Feat_2)
export function vnitrek(g) {
  const zf = Z_BOT + 6 + 0;           // horní plocha dna vany ≈ −187
  for (let k = 0; k < 4; k++) {
    const y0 = -196 + k * 100, y1 = y0 + 92;
    g.add(rbox('cerna_mat', 'dno_podlozka_' + (k + 1), 62, 168, y0, y1, zf, zf + 22, 6, 2.5));
  }
  // odnímatelná vložka (levá polovina, -Y): miska s dělicím žebrem; sedí na zadních a bočních výstupcích
  const vl = new Group('vlozka', { pivot: [0, 0, 0], extras: { popis: 'odnímatelná vložka (levá polovina), odhad rozměrů z Feat_1' } });
  const x0 = -168, x1 = 150, y0 = -225, y1 = -14, z0 = 30, z1 = 112;
  vl.add(loftVessel('seda', 'vlozka_miska', [
    { z: z0, x0: x0 + 8, x1: x1 - 8, y0: y0 + 8, y1: y1 - 8, r: 14 },
    { z: z0 + 10, x0, x1, y0, y1, r: 18 },
    { z: z1, x0, x1, y0, y1, r: 18 }],
    [{ z: z1, x0: x0 + 3, x1: x1 - 3, y0: y0 + 3, y1: y1 - 3, r: 15 },
     { z: z0 + 12, x0: x0 + 3, x1: x1 - 3, y0: y0 + 3, y1: y1 - 3, r: 15 },
     { z: z0 + 4, x0: x0 + 14, x1: x1 - 14, y0: y0 + 14, y1: y1 - 14, r: 10 }], { seg: 4 }));
  vl.add(rbox('seda', 'vlozka_zebro', x0 + 4, x1 - 4, (y0 + y1) / 2 - 5, (y0 + y1) / 2 + 5, z0 + 6, z1 - 12, 3, 2));
  g.addGroup(vl);
}
