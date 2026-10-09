// Milwaukee PACKOUT Slim Organiser 4932471064 (nízký organizér, 10 nádob) – vlastní parametrický generátor podle fotografií výrobce.
// Souřadnice modelu: X = šířka (čelo +X), Y = délka, Z = výška; počátek = střed obálky. Plánové souřadnice z fotografie c04 (pohled shora):
//   xp = vzdálenost od zadního okraje nárazníků (0 … 380), Y = podél délky; model X = xp - XO, model Z = zb - ZO (zb = výška od spodku).
import { Part, Group, roundedBox, hollowBox, box, prism, lathe, cylinder, tube } from './jadro/mesh.js';
import { earcut, ccw, cw, flatFace, wall, at, cornerPoly, rectPoly, prismHoles, area2 } from './pomocne_4932471064.mjs';

export const SKU = '4932471064';
export const OBALKA = { x: 414, y: 500, z: 64 };
export const CELO = 'X';

const XO = 190, ZO = 32;
const X = xp => xp - XO, Z = zb => zb - ZO;
const toXY = (poly) => poly.map(([a, b]) => [X(a), b]);                  // (xp,Y) → [X,Y]

const HF = +(process.env.KUF_HF ?? 0);
export const P = {
  zBot: 5, zFoot: 0, zSeam: 30, zTop: 64, zFloor: 8, zBumpTop: 58,
  lid: { xp0: 14, xp1: 372, y: 240, rc: 26 },
  base: { xp0: 6, xp1: 366, y: 243, rc: 16 },
  pocketDepth: 11,
};

// ---------- pomocné stavitele (xp,Y,zb) ----------
const RB = (mat, name, o) => roundedBox(mat, name, { x0: X(o.xp0), x1: X(o.xp1), y0: o.y0, y1: o.y1, z0: Z(o.z0), z1: Z(o.z1), rc: o.rc ?? 0, re: o.re ?? 0, reB: o.reB, reT: o.reT, seg: o.seg ?? 4, fs: o.fs ?? 2 });

// offset polygonu (mitr) – d>0 ven, d<0 dovnitř; polygon CCW
function offsetPoly(Pl, d) {
  const n = Pl.length, out = [];
  for (let i = 0; i < n; i++) {
    const a = Pl[(i + n - 1) % n], b = Pl[i], c = Pl[(i + 1) % n];
    const t1 = [b[0] - a[0], b[1] - a[1]], t2 = [c[0] - b[0], c[1] - b[1]];
    const l1 = Math.hypot(...t1) || 1, l2 = Math.hypot(...t2) || 1;
    const n1 = [t1[1] / l1, -t1[0] / l1], n2 = [t2[1] / l2, -t2[0] / l2];
    const k = 1 + n1[0] * n2[0] + n1[1] * n2[1];
    out.push([b[0] + d * (n1[0] + n2[0]) / Math.max(k, 0.3), b[1] + d * (n1[1] + n2[1]) / Math.max(k, 0.3)]);
  }
  return out;
}

// ---------- kapsy víka: obrys (rim) a dno (floor) se stejnou topologií (12 vrcholů) ----------
// Lokální souřadnice (a = podél Y, b = podél xp); střed kapsy (yc, bc); w, h = rozměr obrysu
function kapsa(yc, b0, b1, w, o = {}) {
  const hw = w / 2, cf = o.cf ?? 12, cr = o.cr ?? 4, ear = o.ear ?? 16.8, iS = o.iS ?? 10.5, sf = o.sf ?? 11, sr = o.sr ?? 2, bs = b0 + (o.step ?? 27.5), cf2 = o.cf2 ?? 8, cr2 = o.cr2 ?? 3;
  const rim = [[-hw, b0 + cr], [-hw, bs], [-hw, bs], [-hw, b1 - cf], [-hw + cf, b1], [hw - cf, b1], [hw, b1 - cf], [hw, bs], [hw, bs], [hw, b0 + cr], [hw - cr, b0], [-hw + cr, b0]];
  const flr = [[-hw + ear, b0 + sr + cr2], [-hw + ear, bs], [-hw + iS, bs], [-hw + iS, b1 - sf - cf2], [-hw + iS + cf2, b1 - sf], [hw - iS - cf2, b1 - sf], [hw - iS, b1 - sf - cf2], [hw - iS, bs], [hw - ear, bs], [hw - ear, b0 + sr + cr2], [hw - ear - cr2, b0 + sr], [-hw + ear + cr2, b0 + sr]];
  // (b,a) -> (xp, Y): xp = b, Y = yc + a ; orientace: CCW v rovině (xp,Y)? kontrola níže
  const conv = L => L.map(([a, b]) => [b, yc + a]);
  let R = conv(rim), F = conv(flr);
  if (area2(R) < 0) { R = R.reverse(); F = F.reverse(); }
  return { rim: R, floor: F };
}
const kapsaSimple = (yc, b0, b1, w, ch, inset, flrInset) => {      // osmiúhelník (pruh), 8 vrcholů
  const hw = w / 2;
  const mk = (h, d) => { const q = [[-hw + d, b0 + d + ch], [-hw + d + ch, b0 + d], [hw - d - ch, b0 + d], [hw - d, b0 + d + ch], [hw - d, b1 - d - ch], [hw - d - ch, b1 - d], [-hw + d + ch, b1 - d], [-hw + d, b1 - d - ch]]; return q.map(([a, b]) => [b, yc + a]); };
  let R = mk(0, 0), F = mk(0, flrInset);
  if (area2(R) < 0) { R = R.reverse(); F = F.reverse(); }
  return { rim: R, floor: F };
};

// rozložení kapes (měřeno z c04, +Y strana; −Y zrcadlově)
const ROWS = { F: [239, 322], M: [134.6, 221.7], B: [34.6, 119.2] };
function seznamKapes() {
  const L = [];
  for (const s of [1, -1]) {
    const yy = (a, b) => (s > 0 ? [a, b] : [-b, -a]);
    for (const r of ['F', 'B']) {
      const [b0, b1] = ROWS[r];
      let [ya, yb] = yy(133.7, 219.7); L.push({ kind: 'mala', ...kapsa((ya + yb) / 2, b0, b1, yb - ya) });
      [ya, yb] = yy(32.5, 118.5); L.push({ kind: 'mala', ...kapsa((ya + yb) / 2, b0, b1, yb - ya) });
    }
    const [b0, b1] = ROWS.M; const [ya, yb] = yy(29, 217);
    L.push({ kind: 'velka', ...kapsa((ya + yb) / 2, b0, b1, yb - ya, { step: 24 }) });
  }
  return L;
}

// ---------- víko ----------
function vicko() {
  const g = new Group('vicko', { pivot: [X(P.lid.xp0), 0, Z(P.zSeam)], extras: { osa: [0, -1, 0], max_uhel: 110 } });
  const L = P.lid, T = Z(P.zTop), S = Z(P.zSeam);
  // obrys víka v (xp,Y): zaoblený obdélník s výřezem čela (držadlo)
  const pts = [[L.xp0, -L.y], [L.xp1, -L.y], [L.xp1, -58], [357, -48], [357, 40], [L.xp1, 49], [L.xp1, L.y], [L.xp0, L.y]];
  const rad = [L.rc, L.rc, 0, 0, 0, 0, L.rc, L.rc];
  const outline = toXY(cornerPoly(pts, rad, 6));
  const top = offsetPoly(outline, -3);
  const kap = seznamKapes();
  const st = kapsaSimple(0, 44.5, 312.7, 43, 10, 0, 3);
  const rims = [...kap.map(k => toXY(k.rim)), toXY(st.rim)];
  const p = new Part('vicko_plast', 'vicko_cira');
  flatFace(p, top, rims.map(r => ccw(r)), T, true);                       // horní plocha s otvory
  wall(p, at(top, T), at(outline, T - 3), true);                           // zaoblení hrany
  wall(p, at(outline, T - 3), at(outline, S), true);                        // plášť
  const pd = P.pocketDepth;
  for (const k of [...kap, { ...st, plytka: 5 }]) {
    const d = k.plytka ?? pd; const rim = toXY(k.rim), flr = toXY(k.floor);
    wall(p, at(rim, T), at(flr, T - d), false);
    flatFace(p, flr, [], T - d, true);
  }
  g.add(p);
  // čiré háčky nad západkami a pantové jazýčky vzadu
  for (const yc of [-147, 147]) g.add(RB('vicko_cira', 'vicko_hacek', { xp0: 358, xp1: 377, y0: yc - 25, y1: yc + 25, z0: 38, z1: 54, rc: 4, re: 3 }));
  for (const yc of [-201.5, -152.5, -103, -53.5, 53.5, 103, 152.5, 201.5]) g.add(RB('vicko_cira', 'vicko_jazyk', { xp0: 5.5, xp1: 16, y0: yc - 11, y1: yc + 11, z0: 34, z1: 58, rc: 2, re: 1.5 }));
  return g;
}

export function planDebug() {
  const kap = seznamKapes(); const L = P.lid;
  const st = kapsaSimple(0, 44.5, 312.7, 43, 10, 0, 3);
  const pts = [[L.xp0, -L.y], [L.xp1, -L.y], [L.xp1, -58], [357, -48], [357, 40], [L.xp1, 49], [L.xp1, L.y], [L.xp0, L.y]];
  const rad = [L.rc, L.rc, 0, 0, 0, 0, L.rc, L.rc];
  const B = P.base;
  return { 'rim': [...kap.map(k => k.rim), st.rim], 'floor': [...kap.map(k => k.floor), st.floor], 'lid': [cornerPoly(pts, rad, 6)],
    'base': [cornerPoly([[B.xp0, -B.y], [B.xp1, -B.y], [B.xp1, B.y], [B.xp0, B.y]], B.rc, 6)] };
}

function korpus() {
  const g = new Group('korpus');
  const B = P.base;
  // obrys základny s výřezem pro průchozí štěrbinu držadla
  const pts = [[B.xp0, -B.y], [B.xp1, -B.y], [B.xp1, -80], [340, -80], [340, 70], [B.xp1, 70], [B.xp1, B.y], [B.xp0, B.y]];
  const rr = toXY(cornerPoly(pts, [B.rc, B.rc, 0, 0, 0, 0, B.rc, B.rc], 6));
  const body = new Part('zaklad', 'cerna');
  wall(body, at(rr, Z(P.zBot)), at(rr, Z(P.zSeam)), true);
  flatFace(body, rr, [], Z(P.zBot), false);
  flatFace(body, rr, [], Z(P.zSeam), true);
  g.add(body);
  for (const sy of [-1, 1]) for (const f of [0, 1]) {
    g.add(RB('cerna', 'naraznik', { xp0: f ? 328 : 0, xp1: f ? 380 : 52, y0: sy > 0 ? 198 : -250, y1: sy > 0 ? 250 : -198, z0: P.zFoot, z1: P.zBumpTop, rc: 22, re: 4, seg: 6 }));
  }
  // držadlo: příčka (trubka) před průchozí štěrbinou + dvě krátké ramena
  g.add(RB('cerna', 'drzadlo_pricka', { xp0: 357 + HF, xp1: 371 + HF, y0: -93, y1: 82, z0: 0, z1: 30, rc: 3, re: 2 }));
  g.add(RB('cerna', 'drzadlo_rameno_L', { xp0: 338, xp1: 371 + HF, y0: -93, y1: -80, z0: 0, z1: 30, rc: 2, re: 1.5 }));
  g.add(RB('cerna', 'drzadlo_rameno_P', { xp0: 338, xp1: 371 + HF, y0: 70, y1: 82, z0: 0, z1: 30, rc: 2, re: 1.5 }));
  g.add(RB('cervena', 'drzadlo_tlacitko', { xp0: 345, xp1: 362, y0: -28, y1: -2, z0: 18, z1: 31, rc: 5, re: 2 }));
  return g;
}

function nadoby() {
  const g = new Group('nadoby');
  for (const k of seznamKapes()) {
    const r = k.rim; let y0 = 1e9, y1 = -1e9, x0 = 1e9, x1 = -1e9;
    for (const [a, b] of r) { x0 = Math.min(x0, a); x1 = Math.max(x1, a); y0 = Math.min(y0, b); y1 = Math.max(y1, b); }
    g.add(hollowBox('cervena', 'nadoba', { x0: X(x0 + 3.5), x1: X(x1 - 3.5), y0: y0 + 3.5, y1: y1 - 3.5, z0: Z(P.zFloor + 0.5), z1: Z(52), rc: 6, re: 1.5, wall: 2, floor: 2, seg: 3, fs: 2 }));
  }
  return g;
}

// západky (2×): černé pouzdro, červený jazyk, ocelový třmen
function celo() {
  const g = new Group('celo');
  for (const yc of [-147, 147]) {
    g.add(RB('cerna', 'zamek_pouzdro', { xp0: 358, xp1: 377, y0: yc - 22, y1: yc + 22, z0: 28, z1: 40, rc: 2, re: 1.5 }));
    g.add(RB('cervena', 'zamek_jazyk', { xp0: 362, xp1: 376, y0: yc - 21, y1: yc + 21, z0: 7, z1: 29, rc: 3, re: 2 }));
    const bl = [[372, yc - 24, 15], [377, yc - 28, 17], [377, yc - 28, 50], [374, yc - 27, 55], [374, yc + 27, 55], [377, yc + 28, 50], [377, yc + 28, 17], [372, yc + 24, 15]];
    g.add(tube('ocel', 'zamek_trmen', bl.map(([a, b, c]) => [X(a), b, Z(c)]), 1.5, 8));
  }
  return g;
}

export function build() {
  const root = new Group(SKU);
  root.addGroup(korpus()); root.addGroup(nadoby()); root.addGroup(celo()); root.addGroup(vicko());
  return root;
}
