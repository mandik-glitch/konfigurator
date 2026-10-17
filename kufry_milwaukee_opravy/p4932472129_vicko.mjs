// Víko boxu se zásuvkami (pevná část těla): vyvýšený rám s 10 zapuštěnými kapsami (2 skupiny po 5), šikmé přechody k okraji,
// rohové bloky (uši), boční vroubkované madlo, zámek třmenu. Souřadnice a rozměry viz p4932472129_zaklad.mjs; měření v zdroje/*_poznamky.md.
import { Group, rbx, loftRR, komplement, cylX } from './p4932472129_zaklad.mjs';

// Rozměry víka (mm): odečteno z čelní fotografie (c01 u 3189/3190: obrys a výšky) a z rektifikace pohledu shora (c04/c05, y po korekci měřítka).
export const V = {
  zDno: 150.5, zUhel: 170, zTop: 181.5, zPodlaha: 167,          // spodní hrana víka v čele, výška uší, plošina, podlaha kapes
  xCeloVicka: 204.5,                                             // čelo víka mezi ušima je o 2,5 mm za ušima (zámek a třmen tak stojí před ním, obálka 207)
  hyVicko: 272,                                                  // víko mezi ušima je užší (uši vystupují do ±282 – přirozené vybrání pro madlo)
  oko: [-175, 166, -219, 219],                                   // vnitřní okraj rámu = vnější hranice kapes (x0,x1,y0,y1)
  uchoX0: 155, uchoY0: 236,                                      // rohový blok: od |x|, |y|
};
// kapsy: [x0,x1,y0,y1] pro skupinu +Y (druhá je zrcadlo). 2 malé vzadu, 1 dlouhá uprostřed, 2 malé vpředu (čelo = +X).
export const KAPSY = [
  [62, 152, 32, 119], [62, 152, 131, 218],      // přední řada (u čela)
  [-38, 36, 32, 218],                           // dlouhá uprostřed
  [-160, -72, 32, 119], [-160, -72, 131, 218],  // zadní řada
];

export function vicko() {
  const g = new Group('vicko');
  const { zDno, zUhel, zTop, zPodlaha } = V;
  // 1) plášť víka + rám (rim) kolem kapes; vnitřek otevřený ke dnu kapes (zPodlaha)
  const dxc = 207 - V.xCeloVicka;
  g.add(loftRR('cerna', 'vicko_plast', {
    hx: 207, hy: V.hyVicko, rc: 20, seg: 5, capStart: 'down', capEnd: 'up',
    profile: [
      // [z, odsazení čela, odsazení boků, poloměr rohu, odsazení zadní hrany]: strmé čelo a záda, dlouhý šikmý přechod ke straně (obrys čelní fotografie c01)
      [zDno, dxc, 0, 20, 0], [zUhel + 1.5, dxc, 0, 20, 0], [172.5, dxc, 3, 19, 0], [176.5, dxc + 1.5, 18, 14, 3], [180.0, dxc + 6, 31, 10, 8], [181.2, dxc + 9, 35.5, 8, 11], [zTop, dxc + 11, 38, 7, 13],
      [zTop, 36, 53, 4, 31], [181.2, 37.5, 54.5, 3, 32.5], [178.5, 38.5, 55.5, 2.5, 33.5], [zPodlaha + 0.3, 39, 56, 2.5, 34],
    ],
  }));
  // 2) žebra mezi kapsami (komplement kapes v otvoru rámu), obě skupiny
  const kapsy = [...KAPSY, ...KAPSY.map(k => [k[0], k[1], -k[3], -k[2]])];
  const oko = V.oko;
  let n = 0;
  for (const r of komplement(oko, kapsy)) {
    g.add(rbx('cerna', 'vicko_zebro' + (++n), r[0] - 0.4, r[1] + 0.4, r[2] - 0.4, r[3] + 0.4, zPodlaha - 0.5, zTop, 1.2, 1.2, 2, 2));
  }
  // 3) červený štítek v dlouhé kapse na straně +Y (na fotkách c04–c06 vidět v pravé velké kapse)
  g.add(rbx('cervena', 'stitek_kapsa', -25, 23, 62, 170, zPodlaha - 0.5, zPodlaha + 2, 4, 0.8, 3, 1));
  g.add(rbx('bila', 'stitek_kapsa_napis', -9, 6, 86, 146, zPodlaha + 1.6, zPodlaha + 2.3, 1, 0.2, 2, 1));
  // 4) rohové bloky (uši): od víka dolů k trubkám, vnější strana až do ±282
  for (const [sx, sy] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) {
    const x0 = sx > 0 ? V.uchoX0 : -207, x1 = sx > 0 ? 206.4 : -V.uchoX0, y0 = sy > 0 ? V.uchoY0 : -282, y1 = sy > 0 ? 282 : -V.uchoY0;
    g.add(rbx('cerna', 'vicko_ucho', x0, x1, y0, y1, 113.5, zUhel, 9, 2.4, 4, 2));
  }
  // 4b) šrouby v čelech uší (z čelní fotografie: kruhový šroub v dolní části ucha)
  for (const sy of [1, -1]) g.add(cylX('seda', 'vicko_srub', 4.2, 205.6, 207, sy * 268, 147.5, 16));
  // 5) boční „sukně“ víka (mezi ušima, dolů k z≈134) a vroubkované madlo na obou bočnicích (vybrání 10 mm mezi ušima)
  for (const sy of [1, -1]) {
    const y0 = sy > 0 ? 250 : -272, y1 = sy > 0 ? 272 : -250;
    g.add(rbx('cerna', 'vicko_suknice', -156, 156, y0, y1, 134, zDno + 4, 3, 1.2, 3, 2));
    for (let k = 0; k < 6; k++) {
      const z0 = 139 + k * 5.2;
      const ya = sy > 0 ? 272 : -277, yb = sy > 0 ? 277 : -272;
      g.add(rbx('cerna_mat', 'madlo_vicka_zebro', -108, 58, ya, yb, z0, z0 + 3, 1, 0.7, 2, 1));
    }
  }
  // 6) zámek třmenu na přední hraně víka (červený 70 × 15 mm) s černým držákem
  g.add(rbx('cerna_mat', 'zamek_drzak', 182, 205.2, -52, 52, 155, 179, 5, 1.8, 3, 2));
  g.add(rbx('cervena', 'zamek_cerveny', 184, 207, -35, 35, 162.5, 177.5, 2.5, 2.4, 3, 3));
  return g;
}
