// Pevné tělo boxu: duté tělo otevřené do čela (zásuvkové šachty), pevné kolejnice, zvednuté dno, přední sokl s nohami a červenými svorkami třmenu,
// rohové bloky a čtyři volně stojící hliníková boční madla (trubky ≈ 22 mm, délka ≈ 237 mm). Rozměry: viz zdroje/*_poznamky.md.
import { Group, rbx, prism, zrcY, G } from './p4932472129_zaklad.mjs';

export const T = {
  xZad: -200, xCelo: 196, yBok: 246, zDno: -163, zStrop: 148,    // tělo (vana)
  trubka: { z0: -123, z1: 113.5, y0: 257, y1: 279, x0: 181, x1: 205 },   // hliníková madla (z čelního pohledu: -123,3 … +114)
};

export function telo(faces) {
  const g = new Group('telo');
  const { xZad, xCelo, yBok, zDno, zStrop } = T;
  // stěny vany (otevřená do čela)
  g.add(rbx('cerna', 'telo_zada', xZad, xZad + 14, -yBok, yBok, zDno, zStrop, 9, 3, 4, 2));
  for (const sy of [1, -1]) {
    const y0 = sy > 0 ? 234 : -yBok, y1 = sy > 0 ? yBok : -234;
    g.add(rbx('cerna', 'telo_bok', xZad, xCelo, y0, y1, zDno, zStrop, 8, 3.5, 4, 2));
    // lisovaná žebra na bočnici (R9): 3 svislé a spodní stupeň u soklu
    for (const xr of [-120, -40, 40, 120]) g.add(rbx('cerna', 'telo_zebro', xr - 5, xr + 5, sy > 0 ? yBok - 0.2 : -yBok - 1.2, sy > 0 ? yBok + 1.2 : -yBok + 0.2, -140, 120, 1, 1, 2, 2));
  }
  g.add(rbx('cerna', 'telo_dno', xZad, xCelo, -yBok, yBok, zDno, -146, 8, 3.5, 4, 2));
  g.add(rbx('cerna', 'telo_strop', xZad, xCelo, -yBok, yBok, 140, zStrop, 8, 2, 4, 2));
  // rám čela kolem zásuvek (horní a dolní pruh, boční sloupky): hrana čela v x = 198
  g.add(rbx('cerna', 'celo_horni', 186, G.FACE_X, -yBok, yBok, faces[0].z1 + 0.5, zStrop + 0.5, 3, 1.5, 3, 2));
  g.add(rbx('cerna', 'celo_dolni', 186, G.FACE_X, -yBok, yBok, -150, faces[faces.length - 1].z0 - 0.5, 3, 1.5, 3, 2));
  for (const sy of [1, -1]) g.add(rbx('cerna', 'celo_sloupek', 186, G.FACE_X, sy > 0 ? 236 : -yBok, sy > 0 ? yBok : -236, -150, zStrop, 2, 1.2, 3, 2));
  // police mezi zásuvkami (3 mm) a pevné kolejnice (vnější člen teleskopu) v šachtách
  for (let i = 0; i < faces.length - 1; i++) {
    const zs = (faces[i].z0 + faces[i + 1].z1) / 2;
    g.add(rbx('cerna', 'telo_police', xZad + 12, xCelo, -236, 236, zs - 1.5, zs + 1.5, 1, 0.5, 2, 1));
  }
  for (const f of faces) {
    const zc = (f.z0 + f.z1) / 2;
    for (const sy of [1, -1]) g.add(rbx('seda', 'kolejnice_pevna', -185, 190, sy > 0 ? 232 : -235.5, sy > 0 ? 235.5 : -232, zc - 8, zc + 8, 0.8, 0.5, 2, 1));
  }
  // rohové bloky u dna (4×) – navazují na trubky
  for (const [sx, sy] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) {
    const x0 = sx > 0 ? 155 : -207, x1 = sx > 0 ? 207 : -155, y0 = sy > 0 ? 236 : -282, y1 = sy > 0 ? 282 : -236;
    g.add(rbx('cerna', 'telo_roh_dolni', x0, x1, y0, y1, -156, -123, 9, 2.4, 4, 2));
  }
  // zvednuté dno: přední deska + sokl (nejníž z = -181,5), dvě nohy, střední blok
  g.add(rbx('cerna', 'sokl_deska', 110, 204, -170, 170, -169, zDno + 8, 6, 3, 4, 2));
  for (const sy of [1, -1]) {
    const noha = prism('cerna', 'sokl_noha', sy > 0 ? [[205, 80], [205, 158], [92, 172], [92, 66]] : [[205, -80], [92, -66], [92, -172], [205, -158]], -181.5, -161);
    noha.crease = 30; g.add(noha);
  }
  g.add(rbx('cerna_mat', 'sokl_stred', 140, 205, -30, 30, -174, -148, 4, 2, 3, 2));
  // červené svorky třmenu na soklu
  for (const sy of [1, -1]) g.add(rbx('cervena', 'svorka_trmenu', 193, 206, sy > 0 ? 72 : -104, sy > 0 ? 104 : -72, -159, -142, 3, 2.2, 3, 2));
  return g;
}

// hliníková boční madla: 4 volně stojící trubky (svislé), vybrání mezi trubkou a tělem ≈ 11 mm
export function madla() {
  const g = new Group('madla');
  const { z0, z1, y0, y1, x0, x1 } = T.trubka;
  for (const [sx, sy] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) {
    const xa = sx > 0 ? x0 : -x1, xb = sx > 0 ? x1 : -x0, ya = sy > 0 ? y0 : -y1, yb = sy > 0 ? y1 : -y0;
    g.add(rbx('ocel', 'madlo_trubka', xa, xb, ya, yb, z0, z1, 4.5, 1.5, 3, 2));
    // tmavé koncovky (černé hlavice) nahoře a dole
    g.add(rbx('cerna_mat', 'madlo_hlavice', xa + 1.5, xb - 1.5, ya + 1.5, yb - 1.5, z1 - 0.3, z1 + 4.5, 3, 1, 3, 2));
    g.add(rbx('cerna_mat', 'madlo_patka', xa + 1.5, xb - 1.5, ya + 1.5, yb - 1.5, z0 - 4.5, z0 + 0.3, 3, 1, 3, 2));
  }
  return g;
}
