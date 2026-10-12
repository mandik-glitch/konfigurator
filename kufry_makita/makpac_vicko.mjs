// Víko Makita MAKPAC Typ 1–4: tyrkysový dutý plášť (26 mm) s prstovou jamkou v čele, vnořenou kapsou madla a vyhloubenou plochou loga; skupina `vicko` s pivotem na pantové hraně.
// Madlo = vnořená skupina `madlo` (pivot na ose čepů, výchozí poloha sklopené do kapsy směrem dozadu; pose madlo=90° = vztyčené).
import { Group, vana, vickoPlast, plocha, extXY, bx, zc, XF, XR } from './makpac_zaklad.mjs';
import { par, LID } from './makpac_par.mjs';
import { madlo } from './makpac_madlo.mjs';
import { logo } from './makpac_logo.mjs';

export const KAPSA = { xf: 20, xr: -86, y0: -128, y1: 128, rf: 16, rr: 16, hloubka: 20 };
export const LEDGE = { xf: 118, xr: -134, rf: 6, rr: 6, hloubka: 5 };   // rameno nad západkou (stohování): Y 140..181 na obou koncích, 5 mm pod horní plochou
export const LOGO = { xf: 128, xr: 66, y0: -110, y1: 110, rf: 3, rr: 3 };

export function vicko(V) {
  const p = par(V);
  const g = new Group('vicko', { pivot: [XR + 4, 0, zc(p.zS + 1)], extras: { osa: [0, -1, 0], max_uhel: 110 } });
  const kap = { ...KAPSA }, lg = { ...LOGO };
  const ledges = [-1, 1].map(s => ({ ...LEDGE, y0: s < 0 ? -181 : 140, y1: s < 0 ? -140 : 181 }));
  g.add(vickoPlast('tyrkys', 'vicko_plast', { frames: p.frames, notches: p.notches, wall: 3, topT: 3, zmin: p.zS, zmax: V, holes: [kap, lg, ...ledges] }));
  // kapsa madla: vana s dnem V−hloubka; vnější stěna = obrys otvoru, vnitřní o 3 mm menší
  g.add(vana('tyrkys', 'kapsa_madla', { frames: [{ ...kap, z: V - KAPSA.hloubka - 3 }, { ...kap, z: V }], wall: 3, floorZ: V - KAPSA.hloubka }));
  // plocha loga: tenká deska zapuštěná 0,8 mm pod horní plochou
  g.add(plocha('tyrkys', 'logo_plocha', { frames: [{ ...lg, z: V - 3 }, { ...lg, z: V - 0.8 }] }));
  for (const e of ledges) g.add(vana('tyrkys', 'rameno_stohovani', { frames: [{ ...e, z: V - LEDGE.hloubka - 3 }, { ...e, z: V - 0.01 }], wall: 0.8, floorZ: V - LEDGE.hloubka }));
  g.addGroup(madlo(V));
  g.add(...logo(V));
  return g;
}
