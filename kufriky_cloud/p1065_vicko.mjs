// Víko (čiré, lehce zakouřené): sukně se šikmým horním pásmem a dlaždicemi, deska s osmiúhelníkovými prolisy, čepičky spon, očko,
// žebra čela, články pantu, těsnění – model 4932471065. Víko je samostatná skupina s pivotem na ose pantu (osa +X: kladný úhel otevírá).
// Díly se staví v souřadnicích zavřeného modelu. Měření: c06/c03 (půdorys), c07 rektifikace (boky, čelo), viz poznámky.
import { Group, Part, roundPoly, ccw, loftSolid, ext, bx, zc, ZC } from './p1065_zaklad.mjs';
import { loftRings } from './jadro/mesh.js';
import { extrude, offsetPoly, insetRounded, rectPoly, rrect, circlePoly, cylX } from './pomocne.mjs';
import { kapsa } from './p1065_kapsy.mjs';
import { latchFrame } from './p1065_celo.mjs';
import { K } from './p1065_korpus.mjs';

export const V = {
  hw: 117.9, yB: -190,
  zSeam: 28.15, zWall: 39.5, zTop: 64, tPlate: 3,       // svislá spodní část sukně 28,15..39,5, šikmé pásmo do z' 62, vodorovná deska 61..64
  dInc: 11, dTop: 14.5,                                  // vodorovný průmět šikmého pásma, odsazení okraje desky
  pocketDepth: 11, pocketInset: 10,
  pivotY: K.hingeY, pivotZ: K.hingeZ,
};

const LID_PTS = [[-V.hw, V.yB], [V.hw, V.yB], [V.hw, 138.5], [86, 173.5], [52, 155.5], [-52, 155.5], [-86, 173.5], [-V.hw, 138.5]];
const LID_RS = [25, 25, 3, 6, 3, 3, 6, 3];
// na zadní straně (pant) je šikmé pásmo užší (prolisy dosahují těsně k zadní hraně): zadní hrana se pro d > 8 posune ven, aby odsazení nepřesáhlo 8 mm
const lidRing = d => ccw(insetRounded(LID_PTS.map(p => (p[1] === V.yB ? [p[0], V.yB - Math.max(0, d - 8)] : p)), LID_RS, d, 6));
const octaPts = (x0, x1, y0, y1, c) => [[x0 + c, y0], [x1 - c, y0], [x1, y0 + c], [x1, y1 - c], [x1 - c, y1], [x0 + c, y1], [x0, y1 - c], [x0, y0 + c]];
const octa = (x0, x1, y0, y1, c, r) => roundPoly(octaPts(x0, x1, y0, y1, c), r, 3);

// výška spodní hrany sukně: v čele nad zámkem je víko zvednuté (c07 rektifikace čela: spodní hrana z' ≈ 34)
const smooth = (a, b, x) => { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const zBottom = (x, y) => V.zSeam + 5.85 * smooth(138, 152, y) * (1 - smooth(45, 95, Math.abs(x)));

// prolisy (osmiúhelník, c03: vnější hrana zkosení; popis v poznámkách)
export const POCKETS = [
  { n: 'FL', x0: -99.8, x1: -4.8, y0: 28.5, y1: 124 }, { n: 'FP', x0: 4.8, x1: 99.8, y0: 28.5, y1: 124 },
  { n: 'velky', x0: -99.8, x1: 99.8, y0: -76, y1: 15 },
  { n: 'BL', x0: -99.8, x1: -4.8, y0: -178, y1: -90 }, { n: 'BP', x0: 4.8, x1: 99.8, y0: -178, y1: -90 },
];
const labelPoly = () => roundPoly(rectPoly(-28.5, 28.5, 127.0, 139.8), 3.5, 3);

// extruze polygonu v rovině XZ podél osy Y (poly = [[x, z']...], y0..y1 v souřadnicích modelu)
function extXZ(mat, name, poly, y0, y1) {
  const p = ext(mat, name, ccw(poly.map(([x, z]) => [x, z - ZC])), y0 + ZC, y1 + ZC);
  p.mapV((u, v, w) => [u, w, v]); p.flip(); p.crease = 25;
  return p;
}

export function vicko() {
  const g = new Group('vicko', { pivot: [0, V.pivotY, zc(V.pivotZ)], extras: { osa: [1, 0, 0], max_uhel: 110 } });
  // --- sukně: uzavřený profil (z', odsazení): vnější strana nahoru, hrana, spodek desky, vnitřní strana dolů
  const prof = [[V.zSeam, 0.5], [V.zWall, 0], [62, V.dInc], [63.4, V.dInc + 1.4], [V.zTop, V.dInc + 3], [V.zTop, V.dTop + 0.5], [V.zTop - V.tPlate, V.dTop + 0.5], [V.zTop - V.tPlate, V.dInc + 2], [59.2, V.dInc + 0.6], [V.zWall - 1, 2.1], [V.zSeam, 2.1]];
  const rings = prof.map(([z, d]) => lidRing(d).map(q => [q[0], q[1], zc(z)]));
  const sk = new Part('vicko_sukne', 'vicko_cira'); sk.crease = 40;
  loftRings(sk, rings, { closed: true });
  sk.mapV((x, y, z) => (z <= zc(V.zSeam + 0.01) ? [x, y, zc(zBottom(x, y))] : [x, y, z]));
  g.add(sk);
  // --- deska s otvory pro prolisy a štítek
  const pk = POCKETS.map(p => { const pts = octaPts(p.x0, p.x1, p.y0, p.y1, 8), rs = pts.map(() => 2.5); return { ...p, pts, rs, top: ccw(insetRounded(pts, rs, 0, 3)) }; });
  const plateOut = lidRing(V.dTop + 0.5);
  g.add(extrude('vicko_cira', 'vicko_deska', plateOut, [...pk.map(p => p.top), labelPoly()], zc(V.zTop - V.tPlate), zc(V.zTop), { crease: 30 }));
  // --- prolisy
  for (const p of pk) {
    const skip = p.n === 'velky' ? (q) => q[0] > -64 && q[0] < 64 && q[1] > -64 && q[1] < 7 : null;
    kapsa(g, { pts: p.pts, rs: p.rs, zTop: V.zTop, d: V.pocketDepth, s: V.pocketInset, name: 'vicko_kapsa_' + p.n, skip });
  }
  // plaketa s logem (tenký bílý obrys se zkosenými rohy, c03: X −63..62, Y −63..6; text/logo se nemodeluje)
  { const o = octa(-63, 62, -63, 6, 6, 1.5), zP = V.zTop - V.pocketDepth + 0.2;
    g.add(extrude('bila', 'vicko_plaketa', o, [offsetPoly(o, 0.8)], zc(zP), zc(zP + 0.45), { crease: 30 })); }
  // štítek nad zámkem: mělký zapuštěný obdélník (2,5 mm)
  { const lp = labelPoly(), zq = V.zTop - 2.5;
    const w = new Part('vicko_stitek', 'vicko_cira'); const L2 = [[V.zTop, 0], [zq, 1.5], [zq - 1.2, 2.2], [V.zTop - 1.2, 1.5]];
    loftRings(w, L2.map(([z, d]) => ccw(offsetPoly(lp, d)).map(q => [q[0], q[1], zc(z)])), { closed: true }); g.add(w);
    g.add(extrude('vicko_cira', 'vicko_stitek_dno', offsetPoly(lp, 1.8), [], zc(zq - 1.2), zc(zq), { crease: 30 })); }
  // --- dlaždice (úchopová žebra) na šikmém pásmu obou delších stran, rozteč 19,35 (c06: dělicí rysky), šířka 16,7
  const dl = new Part('vicko_dlazdice', 'vicko_cira'); dl.crease = 25;
  const X = z => V.hw - V.dInc * (z - V.zWall) / (62 - V.zWall), nrm = [0.898, 0.439];
  for (let j = -8; j <= 6; j++) {
    const yc = 16 + 19.35 * j + 9.7; if (yc > 128 || yc < -152) continue;
    for (const sx of [1, -1]) {
      const A = [X(42.5), 42.5], B = [X(60.5), 60.5], h = 0.7;
      const poly = [A, B, [B[0] + nrm[0] * h, B[1] + nrm[1] * h], [A[0] + nrm[0] * h, A[1] + nrm[1] * h]].map(([x, z]) => [sx * x, z]);
      dl.append(extXZ('vicko_cira', 'd', poly, yc - 8.35, yc + 8.35));
    }
  }
  g.add(dl);
  // --- žebra na čelním šikmém pásmu (4 ks, rozteč 16,3; c03/c07): tenká žebra podél čelní stěny a šikmé plochy
  const Yi = z => 155.5 - 11 * (z - V.zWall) / (62 - V.zWall);
  for (const xr of [-24.5, -8.2, 8.2, 24.5]) {
    const poly = [[155.4, 34.8], [157.0, 34.8], [157.0, 40.0], [Yi(55.5) + 1.3, 55.5 + 0.65], [Yi(55.5), 55.5], [155.4, 40.0]];
    g.add(extYZlocal('vicko_cira', 'vicko_zebro_cela', poly, xr - 0.7, xr + 0.7));
  }
  // --- čepičky spon (čirá část západky na úhlopříčném rohu), očko, články pantu, těsnění
  for (const s of [1, -1]) cepicka(g, s);
  g.add(extrude('vicko_cira', 'vicko_oko', offsetPoly(roundPoly([[37.5, 151], [53, 151], [53, 166.5], [37.5, 166.5]], [1, 1, 6.5, 6.5], 4), 0), [circlePoly(43.3, 160.5, 3.6, 18)], zc(40.5), zc(50.6), { crease: 30 }));
  panty(g);
  gasket(g);
  return g;
}

function extYZlocal(mat, name, poly, x0, x1) {   // poly = [[y, z']...] extrudované podél X
  const p = ext(mat, name, ccw(poly.map(([y, z]) => [y, z - ZC])), x0 + ZC, x1 + ZC);
  p.mapV((u, v, w) => [w, u, v]); p.crease = 25;
  return p;
}

function cepicka(g, s) {
  const f = latchFrame(s), L = s > 0 ? 'P' : 'L';
  const lay = (k, z) => { const c = f.at(0.5, 6.8); return { poly: ccw(rrect(c[0], c[1], 40 - 2 * k, 13 - 2 * k, Math.max(5 - k, 0.8), f.rot, 3)), z }; };
  g.add(loftSolid('vicko_cira', 'vicko_cepicka_' + L, [lay(0, 33), lay(0, 46), lay(0.8, 49.2), lay(2.6, 51.4), lay(4.6, 52.0)], { crease: 40 }));
}

function panty(g) {
  // čiré články pantu (c06: středy X = ±24, ±72; šířka 23,4), osa v Y = −196,5, z' = 30,5; noha spojuje článek se zadní stěnou víka
  const zcen = zc(K.hingeZ), y = K.hingeY, r = K.hingeR;
  for (const xc of [-72, -24, 24, 72]) {
    const x0 = xc - 11.7, x1 = xc + 11.7;
    g.add(cylX('vicko_cira', 'vicko_clanek_' + xc, y, zcen, r, x0, x1, 18));
    g.add(bx('vicko_cira', 'vicko_clanek_noha_' + xc, x0, x1, y, V.yB + 1.5, K.hingeZ - r + 1.2, K.hingeZ + r - 0.2));
  }
}

function gasket(g) {
  // těsnění a jeho kryt (tmavý prstenec uvnitř spodní části sukně; c07: spodní pásmo sukně je tmavě šedé, c02/c08: černá smyčka)
  const a = lidRing(5.0), b = lidRing(7.6);
  g.add(extrude('cerna_mat', 'vicko_tesneni', a, [b], zc(27.6), zc(38.5), { crease: 30 }));
}
