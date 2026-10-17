// Horní nosné držadlo (jen 4932464079): černé rameno ve tvaru U se hliníkovou trubkou a gumovým úchopem, uložené na čepech v oušcích na koncích víka.
// Z fotografie c01 (zvednuté držadlo): čepy ≈ uprostřed hloubky víka (X ≈ 0), ramena ≈ 205 mm dlouhá, rozteč ramen ≈ 510 mm.
// Sklopená poloha (výchozí, v obálce): ramena leží podél koncových ramen víka a hrazda podél předního horního okraje – TVAR SKLOPENÉ POLOHY NENÍ NA FOTKÁCH (odhad).
// Uzel `horni_drzadlo` je dítětem uzlu `vicko`; extras.osa = [0,-1,0] (kladný úhel = nahoru), zvednuté ≈ 92°.
import { Group, slab, cylY, bx, extXZ, zc } from './p4932464079_zaklad.mjs';

export function horniDrzadlo(V, zvednuto = false) {
  const H = V.H, xp = -12, L = 202, yL = 262, zp = H - 17.5;
  const g = new Group('horni_drzadlo', { pivot: [xp, 0, zc(zp)], extras: { osa: [0, -1, 0], max_uhel: 95, poznamka: 'horní držadlo: 0° = sklopené (výchozí), ≈ 92° = zvednuté jako na fotografii c01; tvar sklopené polohy je odhad' } });
  const P = [];
  const xe = xp + L;                                       // osa hrazdy
  for (const s of [-1, 1]) {
    const nm = s > 0 ? 'P' : 'L', ya = s * yL - 7, yb = s * yL + 7;
    P.push(slab('cerna', 'drzadlo_rameno_' + nm, { x0: xp - 12, x1: xe - 12, y0: Math.min(ya, yb), y1: Math.max(ya, yb), z0: zp - 11, z1: zp + 11, rs: 3, seg: 2, reT: 2.5, reB: 2.5, fs: 2 }));
    P.push(slab('cerna', 'drzadlo_loket_' + nm, { x0: xe - 24, x1: xe + 13, y0: Math.min(s * (yL - 21), s * (yL + 9)), y1: Math.max(s * (yL - 21), s * (yL + 9)), z0: zp - 15, z1: zp + 15, rs: 8, seg: 3, reT: 4, reB: 4, fs: 3 }));
    P.push(cylY('ocel', 'drzadlo_cep_' + nm, 4.5, s > 0 ? yL + 6 : -yL - 8, s > 0 ? yL + 9 : -yL - 6, xp, zp, 14));
  }
  P.push(cylY('ocel', 'drzadlo_trubka', 11.5, -(yL - 21) - 1, (yL - 21) + 1, xe, zp, 24));
  P.push(cylY('cerna_mat', 'drzadlo_uchop', 15, -72, 72, xe, zp, 28));
  for (let k = 0; k < 15; k++) { const y = -66 + k * 9.4; P.push(cylY('cerna', 'drzadlo_vroubek', 15.4, y - 1.6, y + 1.6, xe, zp, 24)); }
  for (const p of P) {
    if (zvednuto) p.rot('y', -92, [xp, 0, zc(zp)]);
    g.add(p);
  }
  return g;
}
