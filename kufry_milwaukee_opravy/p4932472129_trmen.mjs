// Třmen (bail): ocelový drát Ø 4,6 mm ve vzdálenosti ±62,5 mm (z čelní fotografie), nahoře příčka pod červeným zámkem na víku,
// dole zahnuté konce zasunuté do červených svorek na soklu. Pohyblivý uzel „trmen“: osa Y u svorek (extras.osa, pivot).
// Sklopená poloha: z fotografií (c03 u 3189/3190, c02 u 2129/2130) je ve sklopené poloze vidět jen příčka mezi svorkami, nohy nejsou vidět –
// jak přesně se nohy sklopí, z fotek nelze určit (neověřeno); model je sklápí dozadu (−90° kolem osy svorek) do dna.
import { Group, tube, zaoblenaCesta } from './p4932472129_zaklad.mjs';

export const B = { x: 203, zPiv: -150.5, yNoha: 62.5, zHor: 167.5, r: 2.3 };

export function trmen() {
  const g = new Group('trmen', { pivot: [B.x, 0, B.zPiv], extras: { osa: [0, 1, 0], typ: 'rotace', rozsah_deg: [-90, 0], poznamka: 'sklopení dozadu je neověřené (z fotek vidět jen příčka mezi svorkami)' } });
  const { x, zPiv, yNoha: yn, zHor, r } = B;
  const pts = [[x, -88, zPiv], [x, -74, zPiv], [x, -yn, zPiv + 12], [x, -yn, zHor - 10], [x, -yn + 2, zHor], [x, 0, zHor], [x, yn - 2, zHor], [x, yn, zHor - 10], [x, yn, zPiv + 12], [x, 74, zPiv], [x, 88, zPiv]];
  const cesta = zaoblenaCesta(pts, [10, 14, 10, 10, 14, 10], 5);
  g.add(tube('ocel', 'trmen_drat', cesta, r, 10, true));
  return g;
}
