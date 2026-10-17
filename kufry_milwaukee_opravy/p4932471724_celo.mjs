// 4932471724 – čelo (+X): sedlo spojky s červenou kulatou spojkou Ø ≈ 45 mm, červený jazýček pod spodní hranou, logo Milwaukee PACKOUT.
import { Group, textWidth } from './p4932471723_zaklad.mjs';
import { k, HX, CX, Z_PODL } from './p4932471724_telo.mjs';
export function celo() {
  const g = new Group('celo');
  // sedlo: výběžek (YZ polygon) z jádra až na obálku, z' 22–96, zkosené horní rohy
  const Y0 = -8;           // osa spojky (Y) – podle fotky mírně vlevo od středu čela
  g.add(k.extYZ('cerna', 'sedlo', [[Y0 - 72, 24], [Y0 + 72, 24], [Y0 + 66, 74], [Y0 + 48, 96], [Y0 - 48, 96], [Y0 - 66, 74]], CX - 2, HX - 2.5));
  // úzký žebrovaný blok kolem spojky (z' 20–100), vystupuje až k obálce
  g.add(k.extYZ('cerna', 'sedlo-blok', [[Y0 - 33, 20], [Y0 + 33, 20], [Y0 + 33, 86], [Y0 + 24, 100], [Y0 - 24, 100], [Y0 - 33, 86]], CX - 1, HX - 1.0));
  // žebrování nad spojkou
  for (let i = 0; i < 6; i++) g.add(k.bx('cerna', 'sedlo-zebro', HX - 1.6, HX - 0.4, Y0 - 17 + i * 6.8, Y0 - 17 + i * 6.8 + 3.2, 80, 98));
  // červená kulatá spojka Ø 45 (kroužek) v kruhovém sedle, osa X
  g.add(k.latheX('cerna_mat', 'spojka-sedlo', [[0.01, HX - 3.2], [27, HX - 3.2], [27, HX - 0.9], [0.01, HX - 1.8]], Y0, 62, 28));
  g.add(k.latheX('cervena', 'spojka-kruh', [[13.5, HX - 6], [22.5, HX - 6], [22.5, HX - 3.0], [21, HX - 0.7], [13.5, HX - 0.7]], Y0, 62, 28));
  g.add(k.latheX('cerna_mat', 'spojka-otvor', [[0.01, HX - 0.8], [12.5, HX - 0.8], [12.5, HX - 0.5], [0.01, HX - 0.5]], Y0, 62, 24));
  // červený jazýček pod spodní hranou přírub (z' 4–18)
  g.add(k.bx('cervena', 'jazycek', HX - 26, HX - 1.5, Y0 - 24, Y0 + 24, 3, 22));
  // logo
  const h1 = 17, a1 = 0.7, w1 = textWidth('MILWAUKEE', h1, a1), h2 = 8.5, a2 = 0.75, w2 = textWidth('PACKOUT', h2, a2);
  g.add(k.napis('cervena', 'logo-milwaukee', 'MILWAUKEE', { plane: 'X+', face: CX + 0.01, u0: -58, z0: 178, h: h1, d: 0.7, t: 2.4, ax: a1 }));
  g.add(k.napis('cervena', 'logo-packout', 'PACKOUT', { plane: 'X+', face: CX + 0.01, u0: -58 + w1 - w2 + 6, z0: 160, h: h2, d: 0.7, t: 1.6, ax: a2 }));
  return g;
}
