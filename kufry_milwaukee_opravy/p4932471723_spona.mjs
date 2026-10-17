// 4932471723 – spona na čele: červená páka ≈ 90 × 95 mm se zuby, kovový třmen, čep nad sponou, tmavý štít (štít je v těle).
import { Group } from './p4932471723_zaklad.mjs';
import { k, HY } from './p4932471723_telo.mjs';
const YS = 204.6 - 6;   // zapuštěná plocha štítu (čelo těla 204,6 mm, štít zapuštěn o 6 mm)
export function spona() {
  const g = new Group('spona');
  // červená páka: desky z' 196–268 (zaoblená) + zuby 268–283
  g.add(k.rb('cervena', 'spona-paka', { x0: -41, x1: 41, y0: YS + 0.2, y1: YS + 6.2, z0: 188, z1: 256, rc: 3, re: 2 }));
  g.add(k.bx('cervena', 'spona-lem', -43, 43, YS + 0.2, YS + 6.6, 188, 196));
  for (let i = 0; i < 7; i++) { const x = -38 + i * 12.7; g.add(k.bx('cervena', 'spona-zub', x, x + 8, YS + 0.2, YS + 5.6, 256, 270)); }
  g.add(k.bx('cerna_mat', 'spona-zub-mezera', -41, 41, YS + 0.2, YS + 5.8, 262, 270));
  // štítek na páce (reliéf)
  g.add(k.bx('cervena', 'spona-reliéf', -30, 30, YS + 6.0, YS + 6.8, 204, 240));
  // kovový třmen: U z drátu Ø 6: horní příčka z' 312 (X ±49), svislá ramena dolů do z' 205
  const y = YS + 3.0;
  g.add(k.trubka('ocel', 'trmen', [[-49, y, 198], [-49, y, 290], [-46, y, 299], [-38, y, 302], [38, y, 302], [46, y, 299], [49, y, 290], [49, y, 198]], 2.8, 8));
  // čep nad sponou (hlava) – osa čepu rámu držadla
  g.add(k.cylY('ocel', 'cep-hlava', 4.5, HY - 7, HY - 4, 0, 306, 16));
  return g;
}
