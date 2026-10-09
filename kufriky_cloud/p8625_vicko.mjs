// Víko (čiré, lehce zakouřené) hlubokého organizéru 4932478625: deska s kapsami (výškové pole), obvodová sukně, čelní lem,
// žebírka, kopule, pantové články, těsnění, plaketa. Víko je samostatná skupina s pivotem na ose pantu (osa -Y).
// Půdorys a kapsy: c04 (pohled shora, rektifikace roviny vršku, měřítko dorovnáno na obálku); výška: c13 (čelo).
import { Group, Part, rrPoly, ccw, ext, slab, rrFrame, bx, zc, cylinder, tube, ZC } from './p8625_zaklad.mjs';
import { deskaObrys, plastObvodu, rozdel, smooth } from './pomocne_8625.mjs';
import { hexMrizka } from './p8625_kapsy.mjs';
import { PIVOT } from './p8625_korpus.mjs';

export const LID = {
  zSeam: 157.5, zTop: 178,
  xR: -171, xF: 182, xFn: 173, notchY: [-42.5, 51.3],            // zadní hrana, přední hrana, přední hrana ve výřezu uprostřed (c04)
  yS: 241, rc: 18,                                               // poloviční šířka víka, zaoblení rohů
  plat: { x0: -169, x1: 156, y: 230.7 },                         // horní plošina (kapsy); okolo klesající okraj
  D: 17, t: 2.5,                                                 // hloubka kapes, tloušťka plastu
  rows: [[46.4, 137.8], [-55.6, 32.8], [-157.8, -69.4]],         // [x0 (zadní), x1 (přední)] řad A, B, C
  cols: [[-224.4, -133.2], [-121.4, -30.9], [31.4, 121.4], [133.7, 225]],
  slot: { y0: -21.2, y1: 23.1, x0: -149.6, x1: 126.9 },
};
export const kapsyVika = () => {
  const [A, B, C] = LID.rows, [c1, c2, c3, c4] = LID.cols; const out = [];
  for (const r of [A, C]) for (const c of [c1, c2, c3, c4]) out.push({ x0: r[0], x1: r[1], y0: c[0], y1: c[1], big: false });
  out.push({ x0: B[0], x1: B[1], y0: c1[0], y1: c2[1], big: true }, { x0: B[0], x1: B[1], y0: c3[0], y1: c4[1], big: true });
  return out;
};
const cl01 = (v) => Math.max(0, Math.min(1, v));
// hloubka kapsy v bodě (0 mimo): strmá zadní stěna, pozvolná přední, boční 4,5 mm, u zadních rohů široké schody (16 mm)
function pocketDepth(x, y, k) {
  const bevF = 8, bevR = 1.2, bevS = 3.5, bevN = 15, zone = 27, tr = 9;
  const tt = smooth((x - (k.x0 + zone)) / tr);
  const bs = bevN + (bevS - bevN) * tt;
  const f = Math.min(cl01((k.x1 - x) / bevF), cl01((x - k.x0) / bevR), cl01((y - k.y0) / bs), cl01((k.y1 - y) / bs));
  const ch = 8, cb = 6.4;
  const c1 = cl01(((k.x1 - x) + (k.y1 - y) - ch) / cb), c2 = cl01(((k.x1 - x) + (y - k.y0) - ch) / cb), c3 = cl01(((x - k.x0) + (k.y1 - y) - ch) / cb), c4 = cl01(((x - k.x0) + (y - k.y0) - ch) / cb);
  return LID.D * smooth(Math.min(f, c1, c2, c3, c4));
}
function slotDepth(x, y) {
  const s = LID.slot;
  const f = Math.min(cl01((s.x1 - x) / 3), cl01((x - s.x0) / 3), cl01((y - s.y0) / 4), cl01((s.y1 - y) / 4));
  const rib = 1 - smooth((Math.abs(y - (s.y0 + s.y1) / 2) - 3) / 2);
  return LID.D * smooth(f) - 8 * rib * smooth(f);
}
function lidTop(x, y, PK) {
  const L = LID, pl = L.plat;
  const dF = Math.max(0, x - pl.x1), dS = Math.max(0, Math.abs(y) - pl.y), dR = Math.max(0, pl.x0 - x);
  const z = L.zTop - 8 * smooth(dF / 24) - 6 * smooth(dS / 9) - 4 * smooth(dR / 2);
  let d = 0; for (const k of PK) { if (x < k.x0 - 1 || x > k.x1 + 1 || y < k.y0 - 1 || y > k.y1 + 1) continue; d = Math.max(d, pocketDepth(x, y, k)); }
  d = Math.max(d, slotDepth(x, y));
  return z - d;
}

export function vicko() {
  const L = LID;
  const g = new Group('vicko', { pivot: [PIVOT[0], 0, zc(PIVOT[2])], extras: { osa: [0, -1, 0], max_uhel: 110 } });
  const PK = kapsyVika();
  const bx_ = [L.xR, L.xF, L.xFn, L.plat.x1, L.plat.x1 + 24, L.plat.x0, L.slot.x0, L.slot.x1, L.slot.x0 + 3, L.slot.x1 - 3];
  const by_ = [-L.yS, L.yS, -L.plat.y, L.plat.y, -L.plat.y + 9, L.plat.y - 9, L.slot.y0, L.slot.y1, L.slot.y0 + 4, L.slot.y1 - 4, -4, 4, -1, 1, ...L.notchY, L.notchY[0] - 10, L.notchY[1] + 10];
  for (const k of PK) { bx_.push(k.x0, k.x0 + 1.5, k.x1 - 10, k.x1, k.x0 + 27, k.x0 + 37, k.x1 - 8, k.x0 + 8); by_.push(k.y0, k.y0 + 4.5, k.y0 + 8, k.y0 + 16, k.y1 - 16, k.y1 - 8, k.y1 - 4.5, k.y1); }
  const xs = rozdel(L.xR, L.xF, 7, bx_), ys = rozdel(-L.yS, L.yS, 7, by_);
  const xmax = (y) => { const [a, b] = L.notchY; const dd = Math.max(a - y, y - b, 0); return L.xFn + (L.xF - L.xFn) * smooth(dd / 10); };
  const proj = (x, y) => {
    const cx = (L.xR + L.xF) / 2, hx = (L.xF - L.xR) / 2, hy = L.yS, rcl = L.rc;
    let X = Math.min(x, xmax(y)), Y = y;
    const qx = Math.abs(X - cx), qy = Math.abs(Y), ix = hx - rcl, iy = hy - rcl;
    if (qx > ix && qy > iy) { const dx = qx - ix, dy = qy - iy, d = Math.hypot(dx, dy); if (d > rcl) { const kk = rcl / d; X = cx + Math.sign(X - cx) * (ix + dx * kk); Y = Math.sign(Y) * (iy + dy * kk); } }
    return [X, Y];
  };
  const pl = deskaObrys('cira_tm', 'vicko_deska', { xs, ys, top: (x, y) => lidTop(x, y, PK), t: () => L.t, proj });
  pl.part.move(0, 0, -ZC); g.add(pl.part);
  const skirt = plastObvodu('cira_tm', 'vicko_sukne', pl.loop, { zBottom: L.zSeam, tw: 2.2 });
  skirt.move(0, 0, -ZC); g.add(skirt);

  // šestiúhelníková mřížka na dně kapes (jen v plochém dně; schody u zadních rohů zůstávají hladké)
  const zFloor = L.zTop - L.D + 0.15;
  for (const k of PK) {
    // dno kapsy: u zadních rohů užší (schody 16 mm), vpředu širší (boční svah 4,5 mm), vpředu svah 10 mm
    const bsAt = (x) => 16 + (4.5 - 16) * smooth((x - (k.x0 + 27)) / 10);
    const ok = (x, y) => x > k.x0 + 2 && x < k.x1 - 10.5 && y > k.y0 + bsAt(x) + 0.8 && y < k.y1 - bsAt(x) - 0.8;
    g.add(hexMrizka('bila', 'vicko_hex', { x0: k.x0, x1: k.x1, y0: k.y0, y1: k.y1, z: zFloor, gx: k.x0, gy: k.y0, ok }));
  }
  g.add(hexMrizka('bila', 'vicko_hex_pruh', { x0: L.slot.x0 + 3, x1: L.slot.x1 - 3, y0: L.slot.y0 + 4, y1: L.slot.y1 - 4, z: L.zTop - L.D + 0.15, gx: L.slot.x0, gy: L.slot.y0, ok: (x, y) => Math.abs(y - (L.slot.y0 + L.slot.y1) / 2) > 4.5 }));
  // plaketa s logem na dně velké kapsy (+y): tenký bílý obrys se zkosenými rohy (text a logo se nemodelují)
  g.add(rrFrame('bila', 'vicko_plaketa', { x0: -51.5, x1: 21.9, y0: 61, y1: 183, z0: zFloor, z1: zFloor + 0.5, w: 0.8, rs: 9, seg: 1 }));

  // těsnění (černá guma) pod víkem po obvodu
  g.add(rrFrame('cerna_mat', 'vicko_tesneni', { x0: -166, x1: 178, y0: -236.5, y1: 236.5, z0: L.zSeam - 1.2, z1: L.zSeam + 1.6, w: 2.4, rs: [24, 14, 14, 24], seg: 5 }));

  // čelní lem: žebírka na horní hraně lemu, kopule s černým čepem
  for (let k = -11; k <= 11; k++) {
    const y = 5 + k * 20.4; if (Math.abs(y) > 208 || (y > L.notchY[0] - 6 && y < L.notchY[1] + 6)) continue;
    g.add(bx('cira', 'vicko_zebirko', 181.4, 182.6, y - 0.7, y + 0.7, 160, 170));
  }
  for (const s of [-1, 1]) for (let k = 0; k < 13; k++) {                       // žebírka na koncích víka (c13: pravý konec)
    const x = 145 - k * 24; g.add(bx('cira', 'vicko_zebirko_k', x - 1.2, x + 1.2, s > 0 ? L.yS - 0.3 : -L.yS - 0.7, s > 0 ? L.yS + 0.7 : -L.yS + 0.3, 160, 172));
  }
  g.add(cylinder('cira_tm', 'vicko_kopule', 5.5, 0, 14, 20, [0, 0]).move(177, -41.5, zc(154)));
  g.add(cylinder('cerna_mat', 'vicko_cep', 3.6, 0, 12, 14, [0, 0]).move(177, -41.5, zc(142)));
  // pant: čiré články (středy |y| = 54,4; 104,6; 154,4; 203,8; šířka 22,4) kolem čepu (c04)
  for (const yc of [54.4, 104.6, 154.4, 203.8]) for (const s of [-1, 1]) {
    g.add(slab('cira_tm', 'vicko_clanek', { x0: -187, x1: -171, y0: s * yc - 11.2, y1: s * yc + 11.2, z0: 152.5, z1: 170, rs: 4, seg: 3, reT: 5, reB: 6, fs: 3 }));
  }
  return g;
}
