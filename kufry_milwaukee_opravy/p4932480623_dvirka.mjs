// 4932480623 – čelní dvířka: 3 panely 99 / 205 / 99 mm na z' 50–338, odklápěná nahoru dovnitř jako pohyblivý uzel `dvirka` (pivot na horní hraně, osa Y); spona 85×36 mm s tmavým lichoběžníkovým krytem, logo, kruhový otvor.
import { Group, textWidth } from './p4932471723_zaklad.mjs';
import { k, BX, OPEN_Y } from './p4932480623_telo.mjs';
export const PIV = { x: 45, z: 179 };             // virtuální osa otáčení (rovnoběžná s Y) uprostřed dutiny: dvířka se přetočí o 90° do vodorovné polohy pod strop, líc nahoru, dolní hrana vpředu
export function dvirka() {
  const g = new Group('dvirka', { pivot: [PIV.x, 0, k.zc(PIV.z)], extras: { osa: [0, -1, 0], typ: 'otoceni', uhel_otevrene: 90, poznamka: 'Zjednodušená kinematika: dvířka se zvednou nahoru do dutiny a přetočí do vodorovné polohy pod víkem (líc nahoru, dolní hrana se sponou vpředu) – tak je na fotce c03 vidět pruh dvířek s otvorem a sponou pod víkem. Jedna otáčka kolem virtuální osy; vedení v kolejnicích a pant z fotek neověřeny.' } });
  const xp0 = 163.5, xp1 = 172, xf1 = 175.5;        // deska dvířek, líc panelu, líc rámečků
  const z0 = 52, z1 = 336;
  g.add(k.rb('cerna', 'dvirka-deska', { x0: xp0, x1: xp1, y0: -216, y1: 216, z0, z1, rc: 3, re: 1.2 }));
  // rámečky mezi panely (zapuštěné panely 99 / 205 / 99): deska s otvory
  const pan = [[-209, -109], [-104.5, 104.5], [109, 209]];
  g.add(k.extYZh('cerna', 'dvirka-ramy', [[-216, z0], [216, z0], [216, z1], [-216, z1]], pan.map(([a, b]) => [[a, z0 + 5], [b, z0 + 5], [b, z1 - 6], [a, z1 - 6]]), xp1 - 0.5, xf1));
  // tmavý lichoběžníkový kryt spony dole uprostřed (137 mm široký)
  g.add(k.extYZ('cerna_mat', 'kryt-spony', [[-70, z0 + 4], [70, z0 + 4], [70, 114], [56, 132], [-56, 132], [-70, 114]], xp1 - 0.3, xp1 + 5.5));
  // červená spona 85×36 mm (z' 61–99), s žebrováním a značkou
  g.add(k.rb('cervena', 'spona-paka', { x0: xp1 + 5.2, x1: xp1 + 9.6, y0: -42.5, y1: 42.5, z0: 62, z1: 94.5, rc: 2.5, re: 1.2 }));
  g.add(k.bx('cerna_mat', 'spona-drazka', xp1 + 4.8, xp1 + 9.0, -43.5, 43.5, 96, 99));
  g.add(k.extYZ('cerna_mat', 'spona-znacka', [[-3, 75], [3, 75], [0, 80]], xp1 + 9.4, xp1 + 9.9));
  // malý kruhový otvor vlevo dole (průchod kabelu/zámek)
  g.add(k.cylX('cerna_mat', 'dvirka-otvor', 7, xp1, xp1 + 0.6, -97, 76, 16));
  // logo Milwaukee PACKOUT (170 mm široké) – tahy na panelu
  const h1 = 24.5, a1 = 0.83, h2 = 12, a2 = 1.18;
  g.add(k.napis('cervena', 'logo-milwaukee', 'MILWAUKEE', { plane: 'X+', face: xp1, u0: -86, z0: 244, h: h1, d: 0.7, t: 3.0, ax: a1 }));
  g.add(k.napis('cervena', 'logo-packout', 'PACKOUT', { plane: 'X+', face: xp1, u0: -2, z0: 213, h: h2, d: 0.7, t: 2.3, ax: a2 }));
  g.add(k.extYZ('cervena', 'logo-blesk', [[-88, 234], [78, 248], [18, 240], [54, 232], [-72, 229]].map(([y, z]) => [y, z]), xp1, xp1 + 0.7));
  return g;
}
