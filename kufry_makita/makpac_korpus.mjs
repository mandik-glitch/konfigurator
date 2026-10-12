// Korpus (spodní díl) Makita MAKPAC Typ 1–4: tyrkysová vana s vtlačenými panely, kapsami západek a nožek (stohování), černé západky, zuby v nožkových kapsách.
// Vnitřek je hladká dutina (stěna 3 mm, dno 3 mm). Výška V je jediný parametr (viz makpac_par.mjs).
import { Group, vana, extYZ, extXZ, bx } from './makpac_zaklad.mjs';
import { par, Y_ZAP } from './makpac_par.mjs';
import { XF, XR, YH } from './makpac_zaklad.mjs';

export const POCKET_D = 13;      // hloubka kapsy západky (odhad)
const YC_ZAP = (Y_ZAP[0] + Y_ZAP[1]) / 2;      // střed západky 160,5

// černá západka (čelní): polygon v rovině YZ, vytažený v X; yc = střed, V = výška kufru
function zapadkaCelni(g, V, s) {
  const yc = s * YC_ZAP, w = 17.6;                                 // šířka 35,2 mm (c09 px 76..160)
  const zt = V - 7, zb = V - 66;
  const poly = [[yc - w, zb], [yc + w, zb], [yc + w, zt - 3], [yc + w - 4, zt], [yc + 5, zt], [yc, zt - 4], [yc - 5, zt], [yc - w + 4, zt], [yc - w, zt - 3]];
  g.add(extYZ('cerna', 'zapadka_telo', poly, XF - 10.5, XF - 1.6));
  g.add(extYZ('cerna_mat', 'zapadka_zebra', [[yc - 12, zb + 6], [yc + 12, zb + 6], [yc + 12, zb + 12], [yc - 12, zb + 12]], XF - 1.7, XF - 1.2));
}
// černá západka na konci (zadní, u pantu): polygon v rovině XZ, vytažený v Y
function zapadkaKonec(g, V, s) {
  const xc = -106, w = 17.6, zt = V - 7, zb = V - 66;
  const poly = [[xc - w, zb], [xc + w, zb], [xc + w, zt - 3], [xc + w - 4, zt], [xc + 5, zt], [xc, zt - 4], [xc - 5, zt], [xc - w + 4, zt], [xc - w, zt - 3]];
  const y0 = s * (YH - 10.5), y1 = s * (YH - 1.6);
  g.add(extXZ('cerna', 'zapadka_zadni_telo', poly, Math.min(y0, y1), Math.max(y0, y1)));
}
// zuby v nožkových kapsách (dva na kapsu; c09 px ~100 a ~148, šířka ~14 mm)
function zuby(g) {
  for (const s of [-1, 1]) {
    for (const dy of [-12.5, 12.5]) {
      const y = s * YC_ZAP + dy;
      g.add(bx('tyrkys', 'zub_nozky', XF - 12.2, XF - 3.5, y - 6, y + 6, 0, 13));
    }
    for (const dx of [-12.5, 12.5]) {
      const x = -106 + dx;
      g.add(bx('tyrkys', 'zub_nozky_konec', x - 6, x + 6, Math.min(s * (YH - 12.2), s * (YH - 3.5)), Math.max(s * (YH - 12.2), s * (YH - 3.5)), 0, 13));
    }
  }
}
export function korpus(V) {
  const p = par(V), g = new Group('korpus');
  g.add(vana('tyrkys', 'korpus_vana', { frames: p.frames, notches: p.notches, wall: 3, floorZ: 3, zmin: 0, zmax: p.zS }));
  for (const s of [-1, 1]) { zapadkaCelni(g, V, s); zapadkaKonec(g, V, s); }
  zuby(g);
  return g;
}
