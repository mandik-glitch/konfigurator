// Čelní strana (+X): červená U-rukojeť (pohyblivý uzel), západky s drátěným třmenem (pohyblivé uzly), kroužek s otvorem, logo, kanál s červeným jazýčkem.
// Čelní rovina vany je X = xF (190); prvky vystupují max. do X = 205 (obálka 205,5).
import { tekst, Group, Part, roundPoly, ccw, extYZ, extXZ, slab, bx, cylX, cylY, prstenX, tube, zc, loftSolid, rrPoly } from './p4932464079_zaklad.mjs';

// ---------- červená U-rukojeť ----------
export function rukojet(V) {
  const xf = V.xF, zT = V.handlePivot, zB = zT - V.handleH;
  const g = new Group('drzadlo_cervene', { pivot: [xf + 3, 0, zc(zT - 9)], extras: { osa: [0, -1, 0], max_uhel: 55, poznamka: 'výklopné držadlo: otáčí se kolem čepů v horní části sloupků; kladný úhel = spodní okraj ven (+X)' } });
  const yo = V.yHandle, yi = yo - 34;
  for (const s of [-1, 1]) {
    const ya = s > 0 ? yi : -yo, yb = s > 0 ? yo : -yi;
    // sloupek: tělo + 3 prsty nahoře
    g.add(extYZ('cervena', 'rukojet_sloupek_' + (s > 0 ? 'P' : 'L'), roundPoly([[ya, zB], [yb, zB], [yb, zT - 22], [ya, zT - 22]], [4, 4, 0, 0], 3), xf - 0.5, xf + 11));
    for (let k = 0; k < 3; k++) {
      const a = ya + k * 13, b = a + 8;
      g.add(extYZ('cervena', 'rukojet_prst', roundPoly([[a, zT - 23], [b, zT - 23], [b, zT], [a, zT]], [0, 0, 2.5, 2.5], 2), xf + 1, xf + 9));
    }
  }
  // čepy (ocelové) skrz prsty sloupků
  for (const s of [-1, 1]) g.add(cylY('ocel', 'rukojet_cep', 2.4, s > 0 ? yi - 1 : -yo - 1, s > 0 ? yo + 1 : -yi + 1, xf + 5, zT - 9, 12));
  // spodní příčka (červená, vystupuje dopředu) a černý úchop se žebry
  g.add(slab('cervena', 'rukojet_pricka', { x0: xf - 0.5, x1: xf + 14, y0: -yo, y1: yo, z0: zB, z1: zB + 14, rs: 2, seg: 2, reT: 1.2, reB: 3.5, fs: 3 }));
  g.add(slab(V.gripMat || 'cerna_mat', 'rukojet_uchop', { x0: xf + 3, x1: xf + 14.8, y0: -(yi - 8), y1: yi - 8, z0: zB + 11, z1: zB + 41, rs: 4, seg: 3, reT: 12, reB: 5, fs: 4 }));
  for (let k = 0; k < 20; k++) { const y = -(yi - 8) + 5 + k * ((2 * (yi - 8) - 10) / 19); g.add(slab(V.gripMat ? 'cervena' : 'cerna', 'rukojet_vroubek', { x0: xf + 3, x1: xf + 15.4, y0: y - 1.4, y1: y + 1.4, z0: zB + 13, z1: zB + 39.5, rs: 0.8, seg: 1, reT: 8, reB: 3, fs: 3 })); }
  return g;
}

// ---------- západka (červený jazyk pevně na vaně + drátěný třmen jako pohyblivý uzel) ----------
export function zapadka(V, s) {
  const nm = s > 0 ? 'P' : 'L', yc = s * V.yLatch, xf = V.xF;
  const zt = V.latchTop, zb = zt - V.latchH, zs = V.H - V.lidH;
  const g = new Group('zapadka_' + nm);
  // červené těleso jazyka (obrys v YZ), mírně zkosený dolní okraj
  const body = roundPoly([[yc - 26, zb + 2], [yc + 26, zb - 1], [yc + 26, zt - 14], [yc - 26, zt - 14]], [9, 9, 0, 0], 3);
  g.add(extYZ('cervena', 'zapadka_telo_' + nm, body, xf - 0.5, xf + 6.5));
  // prsty (4 zuby) nahoře
  for (let k = 0; k < 4; k++) { const a = yc - 24 + k * 13, b = a + 8.4; g.add(extYZ('cervena', 'zapadka_zub', roundPoly([[a, zt - 15], [b, zt - 15], [b, zt], [a, zt]], [0, 0, 2.5, 2.5], 2), xf + 0.5, xf + 5.5)); }
  // střední vyvýšený panel a žebra v dolní části
  g.add(slab('cervena', 'zapadka_panel_' + nm, { x0: xf + 6, x1: xf + 8.6, y0: yc - 19, y1: yc + 19, z0: zb + 14, z1: zt - 20, rs: 3, seg: 2, reT: 0.8, reB: 0.5, fs: 1 }));
  for (let k = 0; k < 3; k++) g.add(slab('cervena', 'zapadka_zebro', { x0: xf + 6, x1: xf + 8, y0: yc - 20, y1: yc + 20, z0: zb + 3 + k * 3.6, z1: zb + 5.2 + k * 3.6, rs: 0.5, seg: 1, reT: 0.5, reB: 0.3, fs: 1 }));
  // černé pouzdro pod víkem (kapsa nad zuby) – součást vany
  g.add(slab('cerna', 'zapadka_pouzdro_' + nm, { x0: xf - 0.5, x1: xf + 7.5, y0: yc - 33, y1: yc + 33, z0: zt + 1, z1: zs - 1, rs: 3, seg: 2, reT: 1.2, reB: 0.5, fs: 2 }));
  // drátěný třmen: otáčí se kolem čepů (osa Y) na spodku jazyka; zavřený = nahoře nad jazykem, otevřený visí dolů
  const zp = zb + 10, xp = xf + 8.5, yl = yc - 38, yr = yc + 38, zTop = Math.min(V.latchTop + 45, zs + (V.capUp || 0) - 3), xw = xf + 13.2;
  const tg = new Group('trmen_' + nm, { pivot: [xp, yc, zc(zp)], extras: { osa: [0, 1, 0], max_uhel: 165, poznamka: 'drátěný třmen západky; kladný úhel = horní příčka ven a dolů (otevřeno ≈ 160°)' } });
  tg.add(tube('ocel', 'trmen_drat_' + nm, [
    [xp - 2, yl + 4.5, zc(zp)], [xp, yl + 1, zc(zp)], [xw - 1.5, yl, zc(zp + 7)], [xw, yl, zc(zp + 14)], [xw, yl, zc(zTop - 8)], [xw - 0.5, yl + 2.5, zc(zTop - 3.5)], [xw - 1.0, yl + 7, zc(zTop - 0.4)],
    [xw - 1.0, yr - 7, zc(zTop - 0.4)], [xw - 0.5, yr - 2.5, zc(zTop - 3.5)], [xw, yr, zc(zTop - 8)], [xw, yr, zc(zp + 14)], [xw - 1.5, yr, zc(zp + 7)], [xp, yr - 1, zc(zp)], [xp - 2, yr - 4.5, zc(zp)]], 2.0, 8));
  g.addGroup(tg);
  return g;
}

// ---------- kroužek, logo, kanál s jazýčkem, žebra nad sloupky rukojeti ----------
export function celoDetaily(V) {
  const L = [], xf = V.xF;
  L.push(prstenX('cerna', 'kruzek_okruzi', { r0: 17, r1: 27, x0: xf - 0.5, x1: xf + 3.2, y: V.ringY ?? 14, z: V.ringZ, fil: 0.8 }));
  L.push(prstenX('cervena', 'kruzek', { r0: 10.4, r1: 18.6, x0: xf + 1, x1: xf + 8.5, y: V.ringY ?? 14, z: V.ringZ, fil: 1.6 }));
  L.push(cylX('cerna', 'kruzek_dno', 10.6, xf - 0.2, xf + 1.2, V.ringY ?? 14, V.ringZ, 24));
  // logo (potisk): „MILWAUKEE“ + blesk + „PACKOUT“ – bitmapové písmo, plochý červený potisk; 4932464080 logo nad rukojetí nemá
  if (V.logoZ != null) { const zl = V.logoZ, yl = V.logoY ?? 8;
    L.push(tekst('cervena', 'logo_milwaukee', 'MILWAUKEE', { xf, y: yl - 2, z: zl + 6, px: 1.25, t: 0.5, sklon: 1 }));
    L.push(tekst('cervena', 'logo_packout', 'PACKOUT', { xf, y: yl + 14, z: zl - 9, px: 0.95, t: 0.5 }));
    L.push(extYZ('cervena', 'logo_blesk', [[yl - 34, zl - 1], [yl + 6, zl + 0.2], [yl - 8, zl - 3], [yl + 12, zl - 6.5], [yl - 12, zl - 2.6], [yl - 26, zl - 4.2]], xf - 0.1, xf + 0.5)); }
  // ribbed channel pod rukojetí + jazýček
  const zb = V.handlePivot - V.handleH;
  for (let k = 0; k < 7; k++) L.push(bx('cerna_mat', 'kanal_zebro', xf - 0.5, xf + 3.6, -14, 50, 24 + k * 3.8, 26 + k * 3.8));
  L.push(slab('cervena', 'jazycek', { x0: xf - 0.5, x1: xf + 8.6, y0: -2, y1: 36, z0: 3, z1: 21, rs: 2, seg: 2, reT: 1, reB: 1.5, fs: 2 }));
  // žebra (kapsy čepů) nad sloupky rukojeti
  for (const s of [-1, 1]) L.push(slab('cerna_mat', 'sloupek_kapsa', { x0: xf - 0.5, x1: xf + 5, y0: s > 0 ? V.yHandle - 36 : -V.yHandle, y1: s > 0 ? V.yHandle : -(V.yHandle - 36), z0: V.handlePivot - 2, z1: Math.max(V.handlePivot + 4, V.H - V.lidH - 6), rs: 2, seg: 2, reT: 1, reB: 0.5, fs: 1 }));
  return L;
}
