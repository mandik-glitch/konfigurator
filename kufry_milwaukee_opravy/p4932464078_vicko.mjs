// 4932464078 – víko (samostatný uzel `vicko` s pivotem na zadním pantu), západky (uzly `zapadka_L/P`), kapsy na víku, zadní stupně.
import { Part, Group, box, tube, rrPoly, roundPoly, ccw, ext, extYZ, extXZ, slab, skorepina, polyInset, ringSolid, mirY, loftSolid, cylinder } from './p4932464078_zaklad.mjs';
import { zc, D } from './p4932464078_korpus.mjs';
const bx = (mat, name, x0, x1, y0, y1, z0, z1) => box(mat, name, x0, x1, y0, y1, zc(z0), zc(z1));
export const V = { z0: D.zSeva, zTop: 395, zFloor: 387.5, x0: -232, x1: 236, y: 268 };

export function vicko() {
  const piv = [-228, 0, zc(V.zTop - 10)];                  // pant: osa rovnoběžná s Y, u zadní hrany víka
  const g = new Group('vicko', { pivot: piv, extras: { osa: [0, -1, 0], popis: 'víko; kladný úhel otevírá čelo nahoru kolem zadního pantu (osa Y)' } });
  const P = (inset, r) => rrPoly(V.x0 + inset, V.x1 - inset, -V.y + inset, V.y - inset, r, 4);
  const L = [];
  const add = (poly, z) => L.push({ poly, z: zc(z) });
  add(P(0, 16), V.z0);
  add(P(0, 16), 358);
  add(P(1.5, 17), 366);
  add(P(7, 24), 384);
  add(P(12, 28), V.zFloor - 1.5);
  add(P(14, 28), V.zFloor);                              // dno kapes (rovina)
  // vnitřní strana víka (dutá)
  add(P(18, 26), V.zFloor - 4);
  add(P(7, 21), 358);
  add(P(5, 20), V.z0 + 1);
  g.add(skorepina('cerna', 'vicko_plast', L, { otevreno: 'dolu' }));

  // ---- horní plocha: okrajový rám + žebra mezi kapsami (výška 387.5 → 395) ----
  const zf = V.zFloor, zt = V.zTop;
  const outer = P(13, 26), inner = P(27, 14);
  g.add(ringSolid('cerna', 'vicko_ram', outer, inner, zc(zf - 0.5), zc(zt), { innerWall: true, outerWall: false }));
  const xs = [-210, -104, 2, 108];                         // začátky řad kapes (každá 92 mm dlouhá)
  const x0 = -207, x1 = 213;
  // střední pruh (šíře 60) a příčná žebra
  for (const s of [-1, 1]) g.add(bx('cerna', 'vicko_pruh' + (s > 0 ? 'P' : 'L'), x0 - 2, x1 + 2, s * 30 - (s > 0 ? 0 : 14), s * 30 + (s > 0 ? 14 : 0), zf - 0.5, zt));
  for (let k = 1; k < 4; k++) g.add(bx('cerna', 'vicko_zebro' + k, xs[k] - 14, xs[k], -240, 240, zf - 0.5, zt));
  // zvýšené středové tlapky (kulaté výstupky v kapsách) – jen naznačeno
  for (const s of [-1, 1]) for (let k = 0; k < 4; k++) {
    const xc = xs[k] + 46, yc = s * 136;
    g.add(slab('cerna_mat', `vicko_tlapka${s > 0 ? 'P' : 'L'}${k}`, { x0: xc - 16, x1: xc + 16, y0: yc - 16, y1: yc + 16, z0: zc(zf), z1: zc(zf + 4), rs: 16, seg: 5, reT: 1.5, fs: 2 }));
  }
  // červená plaketa v pruhu u čela
  g.add(bx('cervena', 'vicko_plaketa', 118, 200, -26, 26, zf, zf + 1.2));
  // větrací žebra na čelní straně víka
  for (let i = 0; i < 7; i++) g.add(extXZ('cerna_mat', 'vicko_vetrani' + i, [[200, zc(zt - 0.5)], [226, zc(zt - 0.5)], [219, zc(zt - 8)], [193, zc(zt - 8)]], -52 + i * 15 + 0, -52 + i * 15 + 4));
  // čelní lemy víka nad zámky (výstupky)
  for (const s of [-1, 1]) g.add(slab('cerna', 'vicko_zamek_lem' + (s > 0 ? 'P' : 'L'), { x0: 226, x1: 238.0, y0: s * 150 - 56, y1: s * 150 + 56, z0: zc(348), z1: zc(378), rs: 4, reT: 2, reB: 1, fs: 2 }));

  // ---- zadní schody a rohové věže ----
  for (let i = 0; i < 3; i++) g.add(bx('cerna', 'vicko_schod' + i, -236, -222, -268 + i * 0, 268 - i * 0, 304 + i * 28 - 8, 304 + i * 28 + 6));
  for (const s of [-1, 1]) {
    const nm = s > 0 ? 'P' : 'L';
    g.add(slab('cerna', 'vicko_vez' + nm, { x0: -236, x1: -176, y0: s > 0 ? 236 : -276, y1: s > 0 ? 276 : -236, z0: zc(296), z1: zc(392), rs: 8, reT: 5, fs: 2 }));
    for (let i = 0; i < 4; i++) g.add(bx('cerna_mat', 'vicko_vez_zebro' + nm + i, -233, -179, s > 0 ? 272 : -279, s > 0 ? 279 : -272, 304 + i * 20, 314 + i * 20));
  }
  // chromový držák (drátěná oka) uprostřed zadní hrany víka
  const dr = [[-236, -46, zc(336)], [-236, -46, zc(362)], [-236, -30, zc(374)], [-236, 30, zc(374)], [-236, 46, zc(362)], [-236, 46, zc(336)]];
  g.add(tube('ocel', 'vicko_drzak', dr, 3.0, 8));
  return g;
}

// ---- západka: červený jazyk + ocelový třmen (drát) otočný kolem vodorovné osy v čelní stěně víka ----
export function zapadky() {
  const out = [];
  for (const s of [-1, 1]) {
    const nm = s > 0 ? 'P' : 'L', yc = s * 150;
    const piv = [236, yc, zc(374)];                         // čep třmenu na víku
    const g = new Group('zapadka_' + nm, { pivot: piv, extras: { osa: [0, 1, 0], popis: 'západka; kladný úhel odklápí jazyk směrem od čela' } });
    // třmen: obdélníkový drát Ø 3.4, šířka 58, od čepu dolů ke jazyku
    const w = 29, zT = 374, zB = 296;
    const wire = [[236, yc - w, zc(zB)], [236 + 1, yc - w, zc(zT - 4)], [236 + 1.5, yc - w + 4, zc(zT + 2)], [236 + 1.5, yc + w - 4, zc(zT + 2)], [236 + 1, yc + w, zc(zT - 4)], [236, yc + w, zc(zB)]];
    g.add(tube('ocel', 'zapadka_tremen_' + nm, wire, 1.9, 8));
    // červený jazyk (obrys s gumovým rýhováním)
    const jy0 = yc - 28, jy1 = yc + 28;
    g.add(extYZ('cervena', 'zapadka_jazyk_' + nm, roundPoly([[jy0, zc(282)], [jy1, zc(282)], [jy1, zc(336)], [jy0, zc(336)]], [4, 4, 3, 3], 2), 232, 241));
    for (let i = 0; i < 5; i++) g.add(bx('cervena', 'zapadka_zub_' + nm + i, 233, 244, jy0 + 4 + i * 11, jy0 + 10 + i * 11, 332, 346));
    g.add(bx('cervena', 'zapadka_spodni_' + nm, 233, 244, jy0 + 2, jy1 - 2, 280, 288));
    out.push(g);
  }
  return out;
}
