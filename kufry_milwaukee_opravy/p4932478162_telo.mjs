// Spodní díl (tělo) XL boxu: dutá vana, boční zapuštěná pouzdra s rukojetí, čelní panel, nohy, spodní zámková šachta s červenou rukojetí, vnitřek (vložka, podložky).
import { Part, Group, rrPoly, loftBox, loftVessel, loftHood, rbox, bx, extYZ, extXZ, cylX, cylY, addSymY, mirY, mirX, extrude, roundPoly, tube } from './p4932478162_zaklad.mjs';
import { HX, HY, HZ, Z_SEAM, Z_BOT, BODY } from './p4932478162_data.mjs';

const W = 4;   // tloušťka stěny (odhad)
const insetL = (L, d, z) => ({ x0: L.x0 + d, x1: L.x1 - d, y0: L.y0 + d, y1: L.y1 - d, r: Math.max(L.r - d, 1), z });

// vnější vrstvy vany (boční plocha |Y| = 222 – boční panely se přidávají zvlášť, aby šla vytvořit pouzdra rukojetí)
const YB = 221;
export const VANA = [
  { z: Z_BOT, x0: -152, x1: 160, y0: -(YB - 14), y1: YB - 14, r: 22 },
  { z: Z_BOT + 8, x0: -161, x1: 174, y0: -(YB - 4), y1: YB - 4, r: 20 },
  { z: Z_BOT + 16, x0: -166, x1: 181, y0: -YB, y1: YB, r: 18 },
  { z: Z_SEAM - 4, x0: -168, x1: 181, y0: -YB, y1: YB, r: 16 },
];

export function vana() {
  const g = new Group('telo');
  const inner = [{ ...insetL(VANA[3], W, Z_SEAM) }, { ...insetL(VANA[2], W, Z_BOT + 16) }, { ...insetL(VANA[1], W, Z_BOT + 8 + 4) }, { ...insetL(VANA[0], W + 1, Z_BOT + 6) }];
  g.add(loftVessel('cerna', 'telo_vana', VANA, inner, { seg: 4 }));
  // horní lem pod švíkem (okraj vany pod víkem), přesah ven
  g.add(loftHood('cerna', 'telo_lem', [
    { z: Z_SEAM - 14, x0: -170, x1: 190, y0: -(BODY.yw + 6), y1: BODY.yw + 6, r: 17 },
    { z: Z_SEAM - 1, x0: -172, x1: 193, y0: -(BODY.yw + 8), y1: BODY.yw + 8, r: 17 }],
    [{ z: Z_SEAM - 1, x0: -169, x1: 190, y0: -(BODY.yw + 4), y1: BODY.yw + 4, r: 14 }, { z: Z_SEAM - 14, x0: -167, x1: 187, y0: -(BODY.yw + 1), y1: BODY.yw + 1, r: 14 }], { seg: 4 }));
  return g;
}

// boční panely (|Y| 222 → 241) s pouzdrem rukojeti (otevřené nahoře pod víkem)
export function bocniPanely(g) {
  const POC = { x0: -122, x1: 126, z0: 36 };      // pouzdro rukojeti: odhad z c01 (501784) – X od -122 do 126, dno z = 36
  for (const s of [1, -1]) {
    const y0 = s > 0 ? YB - 1 : -BODY.yw, y1 = s > 0 ? BODY.yw : -(YB - 1);
    g.add(rbox('cerna', 'bok_spodni' + (s > 0 ? '' : '_m'), -168, 186, y0, y1, Z_BOT + 14, POC.z0, 9, 2.5));
    g.add(rbox('cerna', 'bok_predni_sloupek' + (s > 0 ? '' : '_m'), POC.x1, 186, y0, y1, POC.z0 - 2, Z_SEAM - 2, 8, 2));
    g.add(rbox('cerna', 'bok_zadni_sloupek' + (s > 0 ? '' : '_m'), -168, POC.x0, y0, y1, POC.z0 - 2, Z_SEAM - 2, 8, 2));
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
  const poly = [[-218, Z_BOT + 8], [218, Z_BOT + 8], [218, Z_SEAM - 2], [204, Z_SEAM - 2], [204, 25], [122, 25], [122, Z_SEAM - 2], [-122, Z_SEAM - 2], [-122, 25], [-204, 25], [-204, Z_SEAM - 2], [-218, Z_SEAM - 2]];
  const rr = [4, 4, 0.5, 0.5, 5, 5, 0.5, 0.5, 5, 5, 0.5, 0.5];
  g.add(extYZ('cerna', 'celo_panel', roundPoly(poly, rr, 2), XB - 1, XF));
  // střední zvýšený pult pod větráním (lichoběžník se zkosenými boky), rovina X = 192
  g.add(extYZ('cerna', 'celo_pult', [[-74, 62], [68, 62], [68, 105], [62, 150], [-68, 150], [-74, 105]], XF - 1, XF + 4, 22));
  // kapsy sponek: tmavé rámy po obvodu (dno kapsy)
  for (const s of [1, -1]) {
    const yc = s * 163;
    g.add(extYZ('cerna_mat', 'kapsa_ram' + (s > 0 ? '' : '_m'), [[yc - 41, 25], [yc + 41, 25], [yc + 41, 33], [yc - 41, 33]], XB, XB + 6, 22));
  }
}

// nohy a spodní žebra (odhad: přední i zadní pár, klínový tvar jako na c01/c02)
export function nohy(g) {
  for (const sy of [1, -1]) for (const sx of [1, -1]) {
    const x0 = sx > 0 ? 118 : -178, x1 = sx > 0 ? 178 : -118;
    // klínový profil v XZ: noha se zužuje dolů
    const poly = sx > 0 ? [[x0, Z_BOT + 8], [x1, Z_BOT + 8], [x1 - 8, -HZ], [x0 + 14, -HZ]] : [[x0 + 8, -HZ], [x1 - 14, -HZ], [x1, Z_BOT + 8], [x0, Z_BOT + 8]];
    const y0 = sy > 0 ? 108 : -170, y1 = sy > 0 ? 170 : -108;
    g.add(extXZ('cerna', 'noha_' + (sx > 0 ? 'p' : 'z') + (sy > 0 ? '1' : '2'), poly, y0, y1, 30));
  }
  // spodní pás (rám dna) pod vanou
  g.add(rbox('cerna', 'dno_pas', -161, 172, -222, 222, Z_BOT - 2, Z_BOT + 6, 16, 2));
}

// spodní zámková šachta (čelo): rám se žebrováním, červená rukojeť zámku jako samostatný uzel s pivotem na spodním čepu (rozměry z rektifikace c02 na rovinu X = 190)
export function zamekSachta(g) {
  g.add(extYZ('cerna', 'sachta', [[-108, -197], [108, -197], [108, -76], [80, -54], [-80, -54], [-108, -76]], 178, 190.5, 25));
  g.add(extYZ('cerna', 'sachta_vnitrni', [[-98, -192], [98, -192], [98, -84], [74, -64], [-74, -64], [-98, -84]], 190, 193, 25));
  // žebrovaný blok nad rukojetí (svislé štěrbiny) a pod ní
  g.add(bx('cerna', 'sachta_blok_horni', 190, 196.5, -54, 54, -122, -90));
  for (let k = 0; k < 11; k++) { const y = -51 + k * 10; g.add(bx('cerna_mat', 'sachta_stepina', 195.5, 197, y, y + 4.2, -118, -94)); }
  g.add(extYZ('cerna', 'sachta_ram', [[-53, -122], [53, -122], [53, -200], [-53, -200]], 190, 196.5, 22, [[[-47, -126], [-47, -180], [47, -180], [47, -126]]]));
  for (let k = 0; k < 11; k++) { const y = -51 + k * 10; g.add(bx('cerna_mat', 'sachta_zebro', 195.5, 197, y, y + 4.2, -198, -183)); }
  // červená rukojeť zámku = uzel s pivotem (spodní čep, osa Y)
  const rk = new Group('rukojet_zamku', { pivot: [190, 0, -182], extras: { osa: [0, -1, 0], max_uhel: 55, popis: 'červená rukojeť zámku šachty (čelo dole)' } });
  const outer = roundPoly([[-45, -125], [45, -125], [45, -179], [-45, -179]], [10, 10, 10, 10], 4);
  const hole = roundPoly([[-34, -139], [34, -139], [34, -166], [-34, -166]], [8, 8, 8, 8], 4);
  rk.add(extYZ('cervena', 'rukojet_zamku_ram', outer, 190, 197, 30, [hole]));
  rk.add(extYZ('cervena', 'rukojet_zamku_jazyk', [[-20, -198], [20, -198], [20, -210], [-20, -210]], 190, 195, 25));
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
