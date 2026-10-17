// Pevné tělo boxu: duté tělo otevřené do čela (zásuvkové šachty), pevné kolejnice, zvednuté dno, přední sokl s nohami a červenými svorkami třmenu,
// rohové bloky a čtyři volně stojící hliníková boční madla (trubky ≈ 22 mm, délka ≈ 237 mm). Rozměry: viz zdroje/*_poznamky.md.
import { Group, rbx, prism, cylinder, extYZ, cylX, G } from './p4932472129_zaklad.mjs';

export const T = {
  xZad: -200, xCelo: 196, yBok: 258, zDno: -163, zStrop: 148,    // tělo (vana): yBok = polovina šířky u čela v horní části (z čelní fotografie 258 → dole 250)
  trubka: { z0: -123, z1: 113.5, r: 10.5, cx: 194.5, cy: 268 },   // hliníková madla (z čelního pohledu: −123,3 … +114; střed y ±268, x z 3/4 pohledu)
};

// kuželovitost těla: boky se směrem dolů zužují (258 → 250 mm, čelní fotografie c01 u 3189: hrana těla −257 při z=100, −250 při z=−100)
// a směrem dozadu (≈ −5 %; průhled mezi zadní trubkou a tělem na fotce c02)
const tap = part => part.mapV((x, y, z) => [x, y * (1 - 0.031 * (T.zStrop - z) / 311) * (1 - 0.05 * (198 - x) / 398), z]);

export function telo(faces, { stredCerveny = false } = {}) {
  const g = new Group('telo');
  const { xZad, xCelo, yBok, zDno, zStrop } = T;
  const T_ = (p) => { g.add(tap(p)); };
  // stěny vany (otevřená do čela): zadní stěna, dvě bočnice (236 … 258), dno a strop
  T_(rbx('cerna', 'telo_zada', xZad, xZad + 14, -yBok, yBok, zDno, zStrop, 9, 3, 4, 2));
  for (const sy of [1, -1]) {
    const y0 = sy > 0 ? 236 : -yBok, y1 = sy > 0 ? yBok : -236;
    T_(rbx('cerna', 'telo_bok', xZad, xCelo, y0, y1, zDno, zStrop, 8, 3.5, 4, 2));
    // lisovaná žebra na bočnici (R9)
    for (const xr of [-120, -40, 40, 120]) T_(rbx('cerna', 'telo_zebro', xr - 5, xr + 5, sy > 0 ? yBok - 0.6 : -yBok - 1.2, sy > 0 ? yBok + 1.2 : -yBok + 0.6, -140, 120, 1, 1, 2, 2));
  }
  T_(rbx('cerna', 'telo_dno', xZad, xCelo, -yBok, yBok, zDno, -146, 8, 3.5, 4, 2));
  T_(rbx('cerna', 'telo_strop', xZad, xCelo, -yBok, yBok, 140, zStrop, 8, 2, 4, 2));
  // rám čela kolem zásuvek: horní a dolní pruh (hrana čela v x = 198)
  T_(rbx('cerna', 'celo_horni', 186, G.FACE_X, -yBok, yBok, faces[0].z1 + 0.5, zStrop + 0.5, 3, 1.5, 3, 2));
  T_(rbx('cerna', 'celo_dolni', 186, G.FACE_X, -yBok, yBok, -150, faces[faces.length - 1].z0 - 0.5, 3, 1.5, 3, 2));
  // police mezi zásuvkami (3 mm) a pevné kolejnice (vnější člen teleskopu) v šachtách
  for (let i = 0; i < faces.length - 1; i++) {
    const zs = (faces[i].z0 + faces[i + 1].z1) / 2;
    g.add(rbx('cerna', 'telo_police', xZad + 12, xCelo, -237, 237, zs - 1.5, zs + 1.5, 1, 0.5, 2, 1));
  }
  for (const f of faces) {
    const zc = (f.z0 + f.z1) / 2;
    for (const sy of [1, -1]) g.add(rbx('cerna_mat', 'kolejnice_pevna', -185, 190, sy > 0 ? 232 : -236, sy > 0 ? 236 : -232, zc - 8, zc + 8, 0.8, 0.5, 2, 1));
  }
  // výrazný stupeň u soklu na bočnicích (R9): dolní pruh o 3 mm širší
  for (const sy of [1, -1]) T_(rbx('cerna', 'telo_stupen', xZad, xCelo, sy > 0 ? 244 : -yBok - 3, sy > 0 ? yBok + 3 : -244, zDno, -146, 4, 2.2, 3, 2));
  // rohové bloky u dna (4×) – navazují na trubky
  for (const [sx, sy] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) {
    const x0 = sx > 0 ? 155 : -207, x1 = sx > 0 ? 206.4 : -155, y0 = sy > 0 ? 236 : -282, y1 = sy > 0 ? 282 : -236;
    g.add(rbx('cerna', 'telo_roh_dolni', x0, x1, y0, y1, -156, -123, 9, 2.4, 4, 2));
    if (sx > 0) g.add(cylX('seda', 'telo_srub', 4.2, 205.6, 207, sy * 268, -134, 16));   // šroub v čele dolního rohového bloku
  }
  // zvednuté dno: tělo končí na z = −163; nejníž (−181,5) sahá jen přední sokl se dvěma širokými nohami (y ±(80…152)); uprostřed černý blok (západka)
  const profilSokl = [[-168, -163], [-152, -181.5], [-80, -181.5], [-74, -172], [-62, -168.5], [62, -168.5], [74, -172], [80, -181.5], [152, -181.5], [168, -163], [168, -146], [-168, -146]];
  g.add(extYZ('cerna', 'sokl_noha', profilSokl, 96, 205, 30));
  g.add(rbx('cerna_mat', 'sokl_stred', 140, 205, -31, 31, -177, -148, 4, 2, 3, 2));
  // u 2- a 3zásuvkových boxů (fotky c01/c02) je ve střední západce červený jazýček (u 3189/3190 je střed černý)
  if (stredCerveny) g.add(rbx('cervena', 'sokl_stred_jazyk', 188, 205, -24, 24, -176, -157, 3, 2, 3, 2));
  // červené svorky třmenu na soklu
  for (const sy of [1, -1]) g.add(rbx('cervena', 'svorka_trmenu', 193, 206, sy > 0 ? 72 : -104, sy > 0 ? 104 : -72, -160, -143, 3, 2.2, 3, 2));
  return g;
}

// hliníková boční madla: 4 volně stojící trubky (válce Ø ≈ 21 mm, z čelní fotografie šířka 20–22 mm; ve 3/4 pohledu je vidět válcový tvar),
// délka z −123 do +113,5 mm; mezi trubkou a tělem zůstává průhled.
export function madla() {
  const g = new Group('madla');
  const { z0, z1, r, cx, cy } = T.trubka;
  for (const [sx, sy] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) {
    g.add(cylinder('ocel', 'madlo_trubka', r, z0, z1, 28, [sx * cx, sy * cy]));
    // černé koncovky (hlavice nahoře, patka dole) navazují na rohové bloky
    g.add(cylinder('cerna_mat', 'madlo_hlavice', r - 0.5, z1 - 0.3, z1 + 4.5, 20, [sx * cx, sy * cy]));
    g.add(cylinder('cerna_mat', 'madlo_patka', r - 0.5, z0 - 4.5, z0 + 0.3, 20, [sx * cx, sy * cy]));
  }
  return g;
}
