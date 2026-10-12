// Víko kufru Hilti řady SF – ZAVŘENÁ verze, vnější pohled: dutá skořepina (stěna 3 mm) s plochým čelem, čelní reliéf (horní zkosení, pás s logem, spodní zkosení a prohlubeň,
// 4 polštáře), bílé logo HILTI (jen plošné písmena), horní půlka černého držadla. Samostatná skupina `vicko`, pivot na pantové hraně (spodní hrana, rovina dělení), osa Y.
import { Group, Part, vickoSkorapka, deska, celniDeska, jehlan } from './p2284143_zaklad.mjs';
import { RAM_HORNI, RAM_SPODNI, px2mm, ramDrzadla } from './p2284143_korpus.mjs';

const POLSTARE = [[52, 280, 213, 265], [919, 1147, 213, 265], [52, 280, 648, 700], [919, 1147, 648, 700]];   // [px0, px1, py0, py1]
const LOGO = {
  H: [[161, 394], [227, 394], [227, 427], [347, 427], [347, 394], [413, 394], [413, 517], [347, 517], [347, 484], [227, 484], [227, 517], [161, 517]],
  I: [[430, 394], [496, 394], [496, 517], [430, 517]],
  L: [[514, 394], [580, 394], [580, 461], [722, 461], [722, 517], [514, 517]],
  T: [[669, 394], [953, 394], [953, 456], [844, 456], [844, 517], [778, 517], [778, 456], [669, 456]],
  I2: [[970, 394], [1036, 394], [1036, 517], [970, 517]],
};

export function celniPanel(K) {
  const p = new Part('celo_panel', 'cervena'); p.crease = 14;
  const extra = [K.zTI, K.pZ(128), K.pZ(315), K.pZ(345), K.pZ(568), K.pZ(600), K.pZ(860), K.pZ(900), K.biteTop, K.pZ(865)];
  celniDeska(p, K, { zA: 0, zB: K.zTI, front: K.panelFront, xb: K.xC - 0.5, bite: true, extra });
  return p;
}
export function polstare(K) {
  const out = [];
  POLSTARE.forEach(([a, b, c, d], i) => {
    const p = new Part('polstar_' + (i + 1), 'cervena'); p.crease = 20;
    jehlan(p, K, K.pY(a), K.pY(b), K.pZ(d), K.pZ(c), K.F0 - 0.3, K.F0 + K.pad, 35 * K.sy, 9 * K.sz);
    out.push(p);
  });
  return out;
}
export function logo(K) {
  const p = new Part('logo_hilti', 'bila'); p.crease = 30;
  const xl = K.F0 - K.band;
  for (const poly of Object.values(LOGO)) deska(p, K, px2mm(K, poly), xl - 0.3, xl + 0.5);
  return p;
}
export function vicko(K) {
  const g = new Group('vicko', { pivot: [K.xs, 0, K.zc(5)], extras: { osa: [0, 1, 0], max_uhel: 100 } });
  g.add(vickoSkorapka(K), celniPanel(K), ...polstare(K), logo(K));
  g.add(ramDrzadla(K, 'drzadlo_vicko', K.xl, z => K.frontSurface(z) + 1.2));
  return g;
}
