// 4932464078 – víko (samostatný uzel `vicko` s pivotem na zadním pantu), západky (uzly `zapadka_L/P`), kapsy na víku, zadní stupně.
import { Part, Group, box, tube, rrPoly, roundPoly, ccw, ext, extYZ, extXZ, slab, skorepina, polyInset, ringSolid, mirY, loftSolid, cylinder } from './p4932464078_zaklad.mjs';
import { zc, D, H_LID } from './p4932464078_korpus.mjs';
const bx = (mat, name, x0, x1, y0, y1, z0, z1) => box(mat, name, x0, x1, y0, y1, zc(z0), zc(z1));
export const V = { z0: D.zSeva, zTop: H_LID, zFloor: H_LID - 7.5, x0: -232, x1: 231, y: 270 };

export function vicko() {
  const piv = [-228, 0, zc(V.zTop - 10)];                  // pant: osa rovnoběžná s Y, u zadní hrany víka
  const g = new Group('vicko', { pivot: piv, extras: { osa: [0, -1, 0], popis: 'víko; kladný úhel otevírá čelo nahoru kolem zadního pantu (osa Y)' } });
  const P = (inset, r) => rrPoly(V.x0 + inset, V.x1 - inset, -V.y + inset, V.y - inset, r, 4);
  const L = [];
  const add = (poly, z) => L.push({ poly, z: zc(z) });
  add(P(0, 16), V.z0);
  add(P(0, 16), H_LID - 42);
  add(P(5, 20), H_LID - 30);
  add(P(16, 28), H_LID - 17);
  add(P(24, 32), V.zFloor - 1.5);
  add(P(26, 32), V.zFloor);                              // dno kapes (rovina)
  // vnitřní strana víka (dutá)
  add(P(30, 30), V.zFloor - 4);
  add(P(7, 21), H_LID - 40);
  add(P(5, 20), V.z0 + 1);
  g.add(skorepina('cerna', 'vicko_plast', L, { otevreno: 'dolu' }));

  g.add(ext('cerna', 'vicko_deska', P(27, 32), zc(V.zFloor - 5), zc(V.zFloor), 20));
  // ---- horní plocha: okrajový rám + žebra mezi kapsami (výška 387.5 → 395) ----
  const zf = V.zFloor, zt = V.zTop;
  const outer = P(25, 32), inner = P(38, 18);
  g.add(ringSolid('cerna', 'vicko_ram', outer, inner, zc(zf - 0.5), zc(zt), { innerWall: true, outerWall: false }));
  // dvě poloviny (přední X>0 / zadní X<0) po čtyřech kapsách podél Y, mezi nimi podélný žlab (plaketa); v kapsách kulaté výstupky
  const ycs = [-182, -60, 60, 182];                          // středy kapes podél Y
  for (const gy of [-120, 0, 120]) for (const sx of [-1, 1]) g.add(bx('cerna', `vicko_zebro_${sx}_${gy}`, sx > 0 ? 32 : -203, sx > 0 ? 201 : -32, gy - 7, gy + 7, zf - 0.5, zt));
  for (const sx of [-1, 1]) g.add(bx('cerna', 'vicko_hrbet' + (sx > 0 ? 'P' : 'L'), sx > 0 ? 32 : -46, sx > 0 ? 46 : -32, -236, 236, zf - 0.5, zt));
  for (const sx of [-1, 1]) for (const yc of ycs) g.add(slab('cerna_mat', `vicko_tlapka_${sx}_${yc}`, { x0: sx * 116 - 15, x1: sx * 116 + 15, y0: yc - 15, y1: yc + 15, z0: zc(zf), z1: zc(zf + 4.5), rs: 15, seg: 5, reT: 1.5, fs: 2 }));
  // červená plaketa v žlabu
  g.add(slab('cervena', 'vicko_plaketa', { x0: -22, x1: 22, y0: 52, y1: 168, z0: zc(zf), z1: zc(zf + 1.4), rs: 5, reT: 0.4, fs: 1 }));
  // větrací žebra na čelní straně víka
  for (let i = 0; i < 7; i++) g.add(extXZ('cerna_mat', 'vicko_vetrani' + i, [[200, zc(zt - 0.5)], [226, zc(zt - 0.5)], [219, zc(zt - 8)], [193, zc(zt - 8)]], -52 + i * 15 + 0, -52 + i * 15 + 4));
  // čelní lemy víka nad zámky (výstupky)
  for (const s of [-1, 1]) g.add(slab('cerna', 'vicko_zamek_lem' + (s > 0 ? 'P' : 'L'), { x0: 224, x1: 232.0, y0: s * 178 - 54, y1: s * 178 + 54, z0: zc(H_LID - 62), z1: zc(H_LID - 22), rs: 4, reT: 2, reB: 1, fs: 2 }));

  // ---- zadní schody a rohové věže ----
  for (let i = 0; i < 3; i++) g.add(bx('cerna', 'vicko_schod' + i, -236, -222, -266, 266, H_LID - 102 + i * 28 - 8, H_LID - 102 + i * 28 + 6));
  for (const s of [-1, 1]) {
    const nm = s > 0 ? 'P' : 'L';
    g.add(slab('cerna', 'vicko_vez' + nm, { x0: -236, x1: -186, y0: s > 0 ? 236 : -270, y1: s > 0 ? 270 : -236, z0: zc(H_LID - 100), z1: zc(H_LID - 2), rs: 8, reT: 5, fs: 2 }));
    for (let i = 0; i < 4; i++) g.add(bx('cerna_mat', 'vicko_vez_zebro' + nm + i, -233, -179, s > 0 ? 266 : -273, s > 0 ? 273 : -266, H_LID - 92 + i * 20, H_LID - 82 + i * 20));
  }
  // chromový držák (drátěná oka) uprostřed zadní hrany víka
  const dr = [[-232.8, -46, zc(336)], [-232.8, -46, zc(362)], [-232.8, -30, zc(374)], [-232.8, 30, zc(374)], [-232.8, 46, zc(362)], [-232.8, 46, zc(336)]];
  g.add(tube('ocel', 'vicko_drzak', dr, 3.0, 8));
  return g;
}

// ---- západka: červený jazyk + ocelový třmen (drát) otočný kolem vodorovné osy v čelní stěně víka ----
export function zapadky() {
  const out = [];
  for (const s of [-1, 1]) {
    const nm = s > 0 ? 'P' : 'L', yc = s * 178;
    const piv = [233.8, yc, zc(H_LID - 112)];            // čep páčky u dolního konce jazyka (páčka je na vaně, třmen zachytává výstupek víka)                         // čep třmenu na víku
    const g = new Group('zapadka_' + nm, { pivot: piv, extras: { osa: [0, 1, 0], popis: 'západka na vaně; kladný úhel odklopí páčku (a třmen) od čela kolem čepu u dolního konce jazyka (osa Y)' } });
    // třmen: obdélníkový drát Ø 3.4, šířka 58, od čepu dolů ke jazyku
    const w = 35, zT = H_LID - 10, zB = H_LID - 108;
    const wire = [[233.6, yc - w, zc(zB)], [233.8, yc - w, zc(zT - 4)], [234.2, yc - w + 4, zc(zT + 2)], [234.2, yc + w - 4, zc(zT + 2)], [233.8, yc + w, zc(zT - 4)], [233.6, yc + w, zc(zB)]];
    g.add(tube('ocel', 'zapadka_tremen_' + nm, wire, 1.9, 8));
    // červený jazyk (obrys s gumovým rýhováním)
    const jy0 = yc - 30, jy1 = yc + 30;
    g.add(extYZ('cervena', 'zapadka_jazyk_' + nm, roundPoly([[jy0, zc(H_LID - 114)], [jy1, zc(H_LID - 114)], [jy1, zc(H_LID - 56)], [jy0, zc(H_LID - 56)]], [4, 4, 3, 3], 2), 230.5, 234.6));
    for (let i = 0; i < 5; i++) g.add(bx('cervena', 'zapadka_zub_' + nm + i, 231, 236, jy0 + 4 + i * 11, jy0 + 10 + i * 11, H_LID - 66, H_LID - 54));
    g.add(bx('cervena', 'zapadka_spodni_' + nm, 231, 236, jy0 + 2, jy1 - 2, H_LID - 116, H_LID - 108));
    out.push(g);
  }
  return out;
}
