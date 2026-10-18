// Nerezový plechový kryt: profil v rovině YZ (vpředu vyšší, plató, zaoblený přehyb, šikmý přechod dozadu), zaoblené hrany plechu,
// otvor v temeni, dvě pole svislých šikmých drážek v čelní stěně, černý pryžový lem hran, neutrální plošky (nálepky bez textu).
import { Part, Group, tube, box, roundedBox, extrudeRound, roundPoly, plate, slotRing, rrect, filletPath, cylX, prism, K, zc } from './c_zaklad.mjs';

// profil krytu (y, z') proti směru hodinových ručiček při pohledu z +X; štítek = štítek rovné hrany ZA rohem
export function profilKrytu() {
  const { Yf, ys, yb, Hb, zb, Ht } = K;
  return roundPoly([
    { p: [Yf, zb], r: 12, tag: 'dno' }, { p: [yb, zb], r: 12, tag: 'zad' },
    { p: [yb, Hb], r: 30, tag: 'sikma' }, { p: [ys, Ht], r: 46, tag: 'plato' }, { p: [Yf, Ht], r: 16, tag: 'celo' },
  ], 6);
}
// poloha dírky v rovné hraně se štítkem tag: vrací (A = začátek hrany, e = směr)
function hrana(pr, tag) { const i = pr.tags.indexOf(tag), A = pr.pts[i], B = pr.pts[(i + 1) % pr.pts.length], L = Math.hypot(B[0] - A[0], B[1] - A[1]); return { A, e: [(B[0] - A[0]) / L, (B[1] - A[1]) / L], L }; }

export const OTVOR = { cx: 25, cy: -250, hx: 62.5, hy: 27.5, r: 14 };      // otvor v temeni (zaoblený obdélník 125 × 55) – poloha odhad ±30 mm
export const SLIT = { xc: 120, len: 62, wid: 7.5, ang: 32, z0: 660, dz: 20.4, n: 18 };      // pole drážek v čele (±xc, šikmé, rostou k okraji)

export function kryt() {
  const g = new Group('kryt');
  const pr = profilKrytu();
  // díry: otvor v plató (hrana 'plato' běží od ys k Yf, souřadnice t = ys' − y), drážky v čele (hrana 'celo' běží dolů, t = zA − z)
  const hp = hrana(pr, 'plato'), hc = hrana(pr, 'celo'), o = OTVOR;
  // hrana 'plato' běží od ys k Yf (směr −y): t = A.y − y;  hrana 'celo' běží dolů (směr −z): t = A.z − z; s = x
  const otvorSvet = rrect(o.cx, o.cy, o.hx, o.hy, o.r, 5);                       // (x, y) ve světě
  const otvorPoly = otvorSvet.map(([x, y]) => [x, hp.A[0] - y]);
  const slity = [];
  for (const sg of [-1, 1]) for (let i = 0; i < SLIT.n; i++) {
    const z = SLIT.z0 - i * SLIT.dz;                                             // E stoupá k +x, W zrcadlově; v (x, t) je t = dolů → úhel opačný
    slity.push(slotRing(sg * SLIT.xc, hc.A[1] - z, SLIT.len, SLIT.wid, sg > 0 ? -SLIT.ang : SLIT.ang, 4));
  }
  const body = extrudeRound('nerez', 'kryt_plech', pr.pts, -K.hw, K.hw, { re: 12, seg: 3, tags: pr.tags, mapF: (u, v, w) => [w, u, v], holes: [{ tag: 'plato', polys: [otvorPoly] }, { tag: 'celo', polys: slity }] });
  g.add(body);
  // vnitřek otvoru a drážek (tmavá vložka) – za dírami je tmavý prostor
  g.add(vlozka(otvorSvet));
  g.add(boxTmavy());
  // pryžový lem (guma/páska): U po čelních svislých hranách a horní přední hraně + boční hrany plató a šikmého přechodu
  const e = K.hw - 6.5, f = K.Yf + 6.5, zt = K.Ht - 6.5;
  g.add(tube('guma', 'lem_celo', filletPath([[e, f, K.zb + 6], [e, f, zt], [-e, f, zt], [-e, f, K.zb + 6]], 22, 6).map(p => [p[0], p[1], p[2]]), 6.5, 10, false));
  for (const sg of [-1, 1]) g.add(tube('guma', 'lem_bok', filletPath([[sg * e, f, zt], [sg * e, K.ys, zt], [sg * e, K.yb - 1, K.Hb - 3]], 46, 7), 6, 10, true));
  // plošky (neutrální, bez textu)
  g.add(...plosky());
  return g;
}

// tmavá vložka za otvorem: stěny a dno dutiny hloubky 45 mm (smyčka otvoru ve světových (x, y))
function vlozka(pts) {
  const p = new Part('otvor_dutina', 'cerna_mat'); p.crease = 40;
  const zT = K.Ht, zB = K.Ht - 45, n = pts.length;
  const top = pts.map(q => p.addV(q[0], q[1], zT)), bot = pts.map(q => p.addV(q[0], q[1], zB));
  for (let i = 0; i < n; i++) { const j = (i + 1) % n; p.addQ(top[i], bot[i], bot[j], top[j]); p.addQ(top[i], top[j], bot[j], bot[i]); }   // obě strany
  const c = pts.reduce((s, q) => [s[0] + q[0] / n, s[1] + q[1] / n], [0, 0]); const cb = p.addV(c[0], c[1], zB);
  for (let i = 0; i < n; i++) { const j = (i + 1) % n; p.addT(cb, bot[i], bot[j]); p.addT(cb, bot[j], bot[i]); }
  return p;
}
// vnitřní tmavý blok kousek za čelní stěnou (vidět skrz drážky)
function boxTmavy() { return box('cerna_mat', 'kryt_vnitrek_celo', -K.hw + 20, K.hw - 20, K.Yf + 8, K.Yf + 30, 280, 700); }

function plosky() {
  const out = [];
  // 1) tmavá nálepka na čele (≈ 95 × 120, uprostřed; text nemodelován)
  out.push(box('plocha_tmava', 'plosk_celo', -42, 43, K.Yf - 0.8, K.Yf, 575, 680));
  // 2) modrý proužek při horní hraně boků (plóška, bez textu)
  for (const sg of [-1, 1]) out.push(box('plocha_modra', 'plosk_proužek', sg > 0 ? K.hw : -K.hw - 0.8, sg > 0 ? K.hw + 0.8 : -K.hw, -160, -22, 756, 768));
  // 3) plošky na šikmém přechodu (výstražná žlutá, bílá, kulatá modrá)
  const a = Math.atan2(K.Ht - K.Hb, K.yb - K.ys) * 180 / Math.PI;            // úhel sklonu (≈ 48,6°)
  const sl = (mat, name, x0, x1, s0, s1, off = 0.6) => {
    const p = box(mat, name, x0, x1, 0, s1 - s0, 0, off);       // lokálně: y = s (podél sklonu), z = tloušťka
    p.move(0, 0, 0).rot('x', -a, [0, 0, 0]);
    // počátek: bod na přímce sklonu ve vzdálenosti s0 od plató
    const L = Math.hypot(K.yb - K.ys, K.Hb - K.Ht), ux = [(K.yb - K.ys) / L, (K.Hb - K.Ht) / L];
    p.move(0, K.ys + ux[0] * s0, K.Ht + ux[1] * s0 + 0.1);
    return p;
  };
  out.push(sl('plocha_zluta', 'plosk_vystraha', -35, 55, 36, 80));
  out.push(sl('plocha_bila', 'plosk_stitek', 140, 215, 40, 88));
  out.push(sl('plocha_modra', 'plosk_kulata', -218, -190, 24, 52));
  return out;
}
