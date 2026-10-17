// Milwaukee PACKOUT Kompaktní box na nářadí 4932471723 – tělo (spodní příruba s nožkami, korpus s prolisy, výřezy na čele).
// Souřadnice: X = šířka 249, Y = délka 411 (čelo se sponou do +Y), z' = výška od země (0..330); počátek modelu = střed obálky.
import { kit, planPoly, rrPoly, Group } from './p4932471723_zaklad.mjs';
export const V = 330, k = kit(V);
export const HX = 124.5, HY = 205.5;          // obálka (lem víka)
export const Z_VICKO = 288;                   // spodní hrana víka (z')

export function telo() {
  const g = new Group('telo');
  const bw = 121.5, bl = 202.0;               // polovina šířky/délky korpusu (lem víka přesahuje o ~3 / 3,5 mm)
  // --- spodní příruba + nožky (podle fotky c01: široká příruba se zaoblenými rohy, 4 nožky) ---
  g.add(k.blok('cerna', 'priruba', { x0: -bw + 4, x1: bw - 4, y0: -bl + 4, y1: bl - 4, z0: 5, z1: 21, r: 22, cT: 2, cB: 2 }));
  for (const sx of [-1, 1]) for (const sy of [-1, 1]) {
    const cx = sx * (bw - 40), cy = sy * (bl - 48);
    g.add(k.blok('cerna', 'nozka', { x0: cx - 26, x1: cx + 26, y0: cy - 32, y1: cy + 32, z0: 0, z1: 8, r: 8, cB: 3 }));
  }
  // --- korpus: pásy půdorysů; čelo má zapuštěný štít sponky (z' 150–288) a sedlo spojky dole (z' 22–74) ---
  const SH = 24, SHD = 6, SK = 36, SKD = 9;   // štít: polovina šířky, hloubka; sedlo spojky: polovina šířky, hloubka
  const mk = (x, y, r, notches) => planPoly(-x, x, -y, y, r, notches, 3);
  const nSh = [{ side: '+Y', a0: -48, a1: 48, d: SHD }];
  const nSk = [{ side: '+Y', a0: -SK, a1: SK, d: SKD }];
  const nNo = [{ side: '+Y', a0: -SK, a1: SK, d: 0.01 }];
  // spodní pás (stupňovitý spodní okraj): z' 21–58, o 1,5 mm užší
  g.add(k.sloupec('cerna', 'korpus-spodek', [
    { z: 21, pts: mk(bw - 4, bl - 4, 20, nSk) }, { z: 28, pts: mk(bw - 2.5, bl - 2.5, 18, nSk) }, { z: 58, pts: mk(bw - 1.5, bl - 1.5, 16, nSk) },
    { z: 74, pts: mk(bw - 1.0, bl - 1.0, 16, nSk) }]));
  // střední pás: z' 74–150 (čelo plné)
  g.add(k.sloupec('cerna', 'korpus-stred', [
    { z: 74, pts: mk(bw - 1.0, bl - 1.0, 16, nNo) }, { z: 150, pts: mk(bw - 0.4, bl - 0.4, 15, nNo) }]));
  // horní pás se štítem: z' 150–290
  g.add(k.sloupec('cerna', 'korpus-horni', [
    { z: 150, pts: mk(bw - 0.4, bl - 0.4, 15, nSh) }, { z: 289, pts: mk(bw, bl, 15, nSh) }]));
  // zapuštěný tmavý štít za sponou (lichoběžník, čelní plocha zapuštěná)
  const yS = bl - SHD;
  g.add(k.bx('cerna_mat', 'stit-sponky', -47.5, 47.5, yS - 0.5, yS + 0.3, 152, 288));
  // zkosený spodní lem štítu (lichoběžníkový kryt dole): hrany štítu
  g.add(k.extXZ('cerna_mat', 'stit-sponky-spodek', [[-48, 152], [48, 152], [38, 138], [-38, 138]], yS - 0.5, bl - 1.2));
  // --- sedlo spojky dole na čele + červený kroužek Ø 42 ---
  const yK = bl - SKD;
  g.add(k.bx('cerna_mat', 'sedlo-spojky', -SK + 0.5, SK - 0.5, yK - 0.5, yK + 0.4, 22, 74));
  g.add(k.latheY('cervena', 'spojka-kruh', [[13, yK], [21, yK], [21, yK + 6.5], [18.5, yK + 7.8], [13, yK + 7.8]], 0, 48, 28));       // červený kroužek Ø 42
  g.add(k.latheY('cerna_mat', 'spojka-otvor', [[0.01, yK + 7.7], [11.5, yK + 7.7], [11.5, yK + 8.1], [0.01, yK + 8.1]], 0, 48, 24));
  g.add(k.bx('cerna_mat', 'sedlo-zebra', -22, 22, yK - 0.5, yK + 1.6, 62, 72));
  // --- boky (dlouhé strany ±X): zapuštěné pole + svislá žebra (stupňovité facety jako na fotce) ---
  for (const sx of [-1, 1]) {
    const xs = sx * (bw - 0.9);
    for (const [ya, yb] of [[-168, -92], [-60, 56], [88, 160]]) g.add(k.bx('cerna', 'bok-zebro', sx > 0 ? xs : xs - 2.4, sx > 0 ? xs + 2.4 : xs, ya, yb, 62, 275));
    g.add(k.bx('cerna', 'bok-lista', sx > 0 ? xs : xs - 2.4, sx > 0 ? xs + 2.4 : xs, -178, 178, 62, 68));
  }
  return g;
}
