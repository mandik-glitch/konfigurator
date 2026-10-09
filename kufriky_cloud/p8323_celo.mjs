// Čelo s madlem (strana +X) a horní pás s roštem (strana s boxy): stěna u madla, střední modul s kapsou, madlo (výklopné), západka,
// štítky PACKOUT – model 4932498323. Rozměry z rektifikace c04 (rovina X=193) a c01 (rovina Z=85), viz poznámky.
import { Group, slab, roundPoly, ccw, extYZ, ext, bx, mirrorInto, voxelSolid, tube, cylinder } from './p8323_zaklad.mjs';
import { K } from './p8323_korpus.mjs';

export const C = {
  XI: 161.5, XP: 185, XT: 193,        // vnitřní líc stěny, zapuštěný panel, čelní rovina (nárazníky, sloupky, lem)
  ZTOP: 73,                           // čelní plocha pásu u madla v prostředku (sníženo oproti rámu Z=85)
  hinge: [177.7, 0, 20.5],              // osa čepu madla (rovnoběžná s Y)
};

// okna roštu (Y intervaly; c01 rektifikace): sedm úzkých + dvě široké, žebra 1,5–2 mm
const OKNA = [[-35, -25.2], [-24, -14.4], [-13, -1.9], [-0.4, 10.2], [11.9, 20.8], [22.6, 32.4], [35, 47], [49.5, 61]];

function stena(g) {
  const { XI, XP, XT, ZTOP } = C;
  // střední modul |y| ≤ 116: sloupky |y| 92…116 po Z -85…73, kapsa pro madlo, rošt |y| < 62 do Z=83
  const holes = [
    [XI - 5, XT + 5, -96, 96, -90, -69],                  // pod tělem jen sloupky (nožičky/patky)
    [169, XT + 5, -92, 92, -50, 66],                      // kapsa pro sklopené madlo
    [XP, XT + 5, -92, 92, -69, -50],                      // zapuštěná plocha pod madlem (X = 185)
    [XI - 5, XT + 5, 62, 120, ZTOP, 90], [XI - 5, XT + 5, -120, -62, ZTOP, 90],   // pás mimo rošt je nižší
  ];
  for (const [a, b] of OKNA) {
    holes.push([165, 188, a, b, 69, 90]);                 // okna roštu shora (c01)
    if (a > -36 && b < 34) holes.push([186, XT + 5, a, b, 72, 82]);   // okna v čele (c04: y -34…33, Z 72…82)
  }
  for (const s of [-1, 1]) holes.push([188, XT + 5, s > 0 ? 100 : -111, s > 0 ? 111 : -100, 36, 62]);   // okénka ve sloupcích
  g.add(...voxelSolid('o8323_cerna', 'stena_modul', [XI, XT, -116, 116, -85, 83], holes, { innerMat: 'o8323_dira' }));
  // boční panely (zapuštěné na X=185) a horní lem, na okraji skos na Z=85 (c04: |y| 161…174)
  for (const s of [1, -1]) {
    const pol = s > 0
      ? [[116, K.ZBP], [202, K.ZBP], [202, 85], [174, 85], [161, 73], [116, 73]]
      : [[-116, K.ZBP], [-116, 73], [-161, 73], [-174, 85], [-202, 85], [-202, K.ZBP]];
    g.add(extYZ('o8323_cerna', 'stena_panel_' + (s > 0 ? 'p' : 'm'), pol, XI, XP));
    const lem = s > 0 ? [[116, 64], [176, 64], [176, 85], [174, 85], [161, 73], [116, 73]] : [[-116, 64], [-116, 73], [-161, 73], [-174, 85], [-176, 85], [-176, 64]];
    g.add(extYZ('o8323_cerna', 'stena_lem_' + (s > 0 ? 'p' : 'm'), lem, XP, XT));
    // vnější část lemu (větrací okna ve čele, c04: y ±[161…212]) – plný kvádr s dvěma kapsami
    const y0 = s > 0 ? 176 : -218, y1 = s > 0 ? 218 : -176;
    const w = s > 0 ? [[176.5, 188], [190.6, 210]] : [[-210, -190.6], [-188, -176.5]];
    g.add(...voxelSolid('o8323_cerna', 'stena_lem_vne_' + (s > 0 ? 'p' : 'm'), [XP, XT, y0, y1, 64, 85], w.map(([a, b]) => [XP + 2, XT + 5, a, b, 66, 81]), { innerMat: 'o8323_dira' }));
  }
  // štítek PACKOUT na pásu (strana s boxy): y -154,4…-65,6; X 165,4…187,4
  g.add(slab('cervena', 'stitek_pas', { x0: 165.4, x1: 187.4, y0: -154.4, y1: -65.6, z0: ZTOP, z1: ZTOP + 1.6, rs: 1.2, seg: 2, reT: 0.5, fs: 1 }));
  // šroub v pásu (c01: y=-49, X=182,8, Ø15)
  g.add(cylinder('o8323_mat', 'sroub_okruzi', 9.4, ZTOP, ZTOP + 1.2, 24, [182.8, -49]));
  g.add(cylinder('ocel', 'sroub_hlava', 5.6, ZTOP + 1.2, ZTOP + 2.0, 20, [182.8, -49]));
  // štítek PACKOUT na čelní ploše (strana s madlem): y ±66, Z 27…68, spodní hrana zkosená
  const pl = roundPoly([[-66, 68], [-66, 38], [-56, 31], [-40, 27], [40, 27], [56, 31], [66, 38], [66, 68]], [1.5, 3, 3, 3, 3, 3, 3, 1.5], 2);
  g.add(extYZ('cervena', 'stitek_celo', ccw(pl), 188.2, XT));
}

// madlo: červený U-rám s třemi hinge-články (tines) na každém rameni, ocelové čepy a gumový úchop; rozměry z rektifikace c04 (rovina X=183).
// Výchozí poloha sklopená v kapse, rukojet=90 → vyklopeno nahoru (+X, c01). Čep: X=177,7, Z=20,5 (osa rovnoběžná s Y).
function madlo() {
  const [hx, hy, hz] = C.hinge;
  const g = new Group('rukojet', { pivot: [hx, hy, hz], extras: { osa: [0, -1, 0], max_uhel: 90, popis: 'sklopené v kapse na čele; úhel 90° = vyklopeno nahoru (+X), c01' } });
  const X0 = hx - 7, X1 = hx + 7;
  // tělo U (od Z=7 dolů): ramena, spodní příčka s oknem; vnitřní obrys ramene měřen po 5 mm
  const arm = [[-92.3, -42], [92.3, -42], [92.3, 7], [58, 7], [61, 5], [64, 0], [64.5, -5], [62, -10], [57, -14], [53, -15], [-53, -15], [-57, -14], [-62, -10], [-64.5, -5], [-64, 0], [-61, 5], [-58, 7], [-92.3, 7]];
  const rr = [4, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
  g.add(extYZ('cervena', 'madlo_ram', ccw(roundPoly(arm, rr, 3)), X0, X1));
  for (const s of [-1, 1]) {
    for (const [a, b] of [[86, 92.3], [73, 78.5], [58.5, 64.5]]) {
      const y0 = s > 0 ? a : -b, y1 = s > 0 ? b : -a;
      g.add(slab('cervena', 'madlo_clanek', { x0: X0, x1: X1, y0, y1, z0: 6, z1: 33.3, rs: [0.5, 0.5, 0.5, 0.5], seg: 1, reT: 2, reB: 0, fs: 2 }));
    }
    g.add(tube('o8323_ocel', 'madlo_cep', [[hx, s * 55.5, hz], [hx, s * 92.8, hz]], 1.3, 10));
    for (const yy of [s * 55.0, s * 93.2]) g.add(tube('o8323_ocel', 'madlo_cep_hlava', [[hx, yy - 0.5, hz], [hx, yy + 0.5, hz]], 2.7, 14));
  }
  // gumový úchop se žebrováním (c04: y ±52,5, Z -31…-15,5)
  g.add(slab('o8323_mat', 'madlo_guma', { x0: X1, x1: X1 + 3, y0: -52.5, y1: 52.5, z0: -31, z1: -15.5, rs: 2, seg: 2, reT: 1, fs: 2 }));
  for (let k = -6; k <= 6; k++) g.add(bx('o8323_mat', 'madlo_vroubek', X1 + 3, X1 + 3.9, k * 7.6 - 1.1, k * 7.6 + 1.1, -29.5, -17));
  return g;
}

// západka (červený hák pod madlem, c04: y ±22…23, Z -43…-77, kopule nahoře)
function zapadka(g) {
  const hook = roundPoly([[-19.5, -43], [19.5, -43], [21, -62], [23, -77], [-23, -77], [-21, -62]], [8, 8, 1, 3, 3, 1], 4);
  g.add(extYZ('cervena', 'zapadka', ccw(hook), 177, 190.5));
}

// žebra na zadní stěně kapsy madla (tmavá, c04: 9 žeber po 8,3 mm)
function zebraKapsy(g) {
  for (let k = 0; k < 9; k++) { const y = -33.2 + 8.3 * k; g.add(bx('o8323_dira', 'kapsa_zebro', 169, 172.5, y - 1.5, y + 1.5, -12, 18)); }
}

export function celo() {
  const g = new Group('celo');
  stena(g); zapadka(g); zebraKapsy(g);
  g.addGroup(madlo());
  return g;
}
