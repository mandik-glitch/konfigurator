// Logo Milwaukee / PACKOUT jako ploché červené tahy (zjednodušené písmo) – vlastní zjednodušení, bez převzetí fontu.
import { Part, textYZ, extYZ } from './p4932478162_zaklad.mjs';

// čelní logo XL (rovina X = 188): „Milwaukee“ (šikmé písmo), blesk, „PACKOUT“
export function logoXL(g, { x0 = 188 } = {}) {
  // polohy podle rektifikace c02 (501784) na rovinu X = 190: „Milwaukee“ Y −86…55, z 5…30; PACKOUT Y −16…84, z −34…−21; blesk z −32…15
  g.add(textYZ('cervena', 'logo_milwaukee', 'Milwaukee', { x0, t: 1.2, yc: -15, zb: 5, h: 25, cw: 13.2, gap: 0.1, w: 3.4, skew: 0.26 }));
  g.add(extYZ('cervena', 'logo_blesk', [[-86, -31], [-28, -10], [-34, -4], [57, 16], [12, -6], [20, -13], [-12, -8], [-26, -17]], x0, x0 + 1.2, 20));
  g.add(textYZ('cervena', 'logo_packout', 'PACKOUT', { x0, t: 1.2, yc: 34, zb: -34, h: 13, cw: 10.4, gap: 0.16, w: 3.0 }));
  return g;
}
