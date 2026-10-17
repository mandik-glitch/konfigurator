// 4932478161 – víko (uzel `vicko` s pivotem na zadním pantu, osa Y), západky (vnořené uzly `zapadka_L/P`), kapsy, plaketa.
import { Part, Group, box, tube, rrPoly, roundPoly, ccw, ext, extYZ, extXZ, slab, skorepina, polyInset, ringSolid } from './p4932464078_zaklad.mjs';
import { zc, D } from './p4932478161_korpus.mjs';
const bx = (mat, name, x0, x1, y0, y1, z0, z1) => box(mat, name, x0, x1, y0, y1, zc(z0), zc(z1));
export const LATCH = [['L', -280], ['P', 215]];            // středy západek Y (změřeno na c06; ±25 mm)

export function vicko() {
  const piv = [-300, 0, zc(330)];
  const g = new Group('vicko', { pivot: piv, extras: { osa: [0, -1, 0], popis: 'víko; kladný úhel otevírá čelo nahoru kolem zadního pantu (osa Y)' } });
  const P = (x, y0, y1, r) => rrPoly(-x, x, y0, y1, r, 4);
  const L = [], add = (poly, z) => L.push({ poly, z: zc(z) });
  add(P(304.5, -448, 432, 24), D.zSeva);
  add(P(304.5, -447, 431, 25), 336);
  add(P(302, -440, 424, 28), 366);
  add(P(292, -402, 384, 38), 382);
  add(P(284, -358, 336, 44), 392);                        // dno kapes (rovina)
  add(P(278, -352, 330, 44), 387);                        // vnitřní strana víka
  add(P(296, -434, 418, 30), 360);
  add(P(300.5, -444, 428, 24), D.zSeva + 1.5);
  g.add(skorepina('cerna', 'vicko_plast', L, { otevreno: 'dolu' }));

  g.add(ext('cerna', 'vicko_deska', P(281, -355, 333, 44), zc(386), zc(392), 20));
  // žebrování na vnitřní straně víka (viditelné při otevření)
  for (let i = -2; i <= 2; i++) g.add(bx('cerna', 'vicko_vnitrni_zebro_x' + i, i * 100 - 2, i * 100 + 2, -330, 308, 360, 387));
  for (let j = -3; j <= 3; j++) g.add(bx('cerna', 'vicko_vnitrni_zebro_y' + j, -262, 262, j * 105 - 2 - 12, j * 105 + 2 - 12, 360, 387));
  // ---- horní plocha: obvodový lem + žebra mezi kapsami (výška 392 → D.zTop) ----
  const z0 = 391, z1 = D.zTop;
  const outer = P(274, -348, 326, 40), inner = P(262, -336, 314, 30);
  g.add(ringSolid('cerna', 'vicko_lem', outer, inner, zc(z0), zc(z1), { innerWall: true, outerWall: false }));
  // řady kapes podél délky (Y), změřeno na c06 (shora na lících žeber): malé dvojice / velká kapsa; uprostřed pás s plaketou
  const rowsY = [[-346, -280, 1], [-268, -150, 0], [-138, -76, 1], [22, 88, 1], [100, 218, 0], [230, 298, 1]];   // [Y od, Y do, malá dvojice?]
  const gapsY = [-274, -144, 94, 224];                         // příčná žebra mezi řadami (tloušťka 12)
  for (const gy of gapsY) g.add(bx('cerna', 'vicko_zebro_y' + gy, -262, 262, gy - 6, gy + 6, z0, z1));
  g.add(bx('cerna', 'vicko_hrbet', -13, 13, -340, 306, z0, z1));                                            // středový hřbet podél délky
  for (const [ya, yb, mala] of rowsY) if (mala) for (const sx of [-1, 1]) g.add(bx('cerna', `vicko_del_${sx}_${ya}`, sx * 138 - 6, sx * 138 + 6, ya, yb, z0, z1));
  // středový pás s plaketou (kapsy vynechány); červená plaketa s logem ≈ 115 × 45 mm
  g.add(bx('cerna', 'vicko_pas_a', -262, 262, -76, -70, z0, z1)); g.add(bx('cerna', 'vicko_pas_b', -262, 262, 14, 22, z0, z1));
  g.add(slab('cervena', 'vicko_plaketa', { x0: -58, x1: 58, y0: -50, y1: -4, z0: zc(z0 + 0.5), z1: zc(z0 + 3), rs: 9, reT: 1, fs: 2 }));
  // okraj víka přečnívá přes vanu: lišta po obvodu švíku a vroubky nad zámky
  for (const [nm, yc] of LATCH) g.add(slab('cerna', 'vicko_zamek_lem_' + nm, { x0: 291, x1: 304.5, y0: yc - 58, y1: yc + 58, z0: zc(318), z1: zc(372), rs: 6, reT: 3, reB: 1, fs: 2 }));
  // držák (táhlo) na zadní hraně víka
  for (let i = 0; i < 8; i++) g.add(bx('cerna_mat', 'vicko_vetrani' + i, 297, 303, -120 + i * 30 - 4, -120 + i * 30 + 4, 372, 382));
  return g;
}

// ---- západka: červený jazyk ≈ 75 × 65 mm + ocelový třmen (drát Ø 4) otočný kolem vodorovné osy Y u čepu na víku ----
export function zapadky() {
  const out = [];
  for (const [nm, yc] of LATCH) {
    const piv = [301.4, yc, zc(180)];                       // čep páčky u dolního konce jazyka
    const g = new Group('zapadka_' + nm, { pivot: piv, extras: { osa: [0, 1, 0], popis: 'západka na vaně; kladný úhel odklopí páčku (a třmen) od čela kolem čepu u dolního konce jazyka (osa Y)' } });
    const w = 45, zT = 336, zB = 214;
    const wire = [[301.4, yc - w, zc(zB)], [302.0, yc - w, zc(zT - 5)], [302.4, yc - w + 6, zc(zT + 2)], [302.4, yc + w - 6, zc(zT + 2)], [302.0, yc + w, zc(zT - 5)], [301.4, yc + w, zc(zB)]];
    g.add(tube('ocel', 'zapadka_tremen_' + nm, wire, 2.0, 8));
    const jy0 = yc - 33, jy1 = yc + 33;
    g.add(extYZ('cervena', 'zapadka_jazyk_' + nm, roundPoly([[jy0, zc(180)], [jy1, zc(180)], [jy1, zc(250)], [jy0, zc(250)]], [5, 5, 3, 3], 2), 297.5, 301.6));
    for (let i = 0; i < 6; i++) g.add(bx('cervena', 'zapadka_zub_' + nm + i, 298, 303.4, jy0 + 3 + i * 10.4, jy0 + 9 + i * 10.4, 242, 262));
    g.add(bx('cervena', 'zapadka_spodni_' + nm, 298, 303.4, jy0 + 3, jy1 - 3, 176, 184));
    out.push(g);
  }
  return out;
}
