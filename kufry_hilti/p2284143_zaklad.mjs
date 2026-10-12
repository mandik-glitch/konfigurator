// Společný základ pro kufry Hilti řady SF (2284143 SF 6(H)-22, 2273022 SF 4(H)-22): jednoúčelový plastový kufr, ZAVŘENÁ verze, vnější pohled.
// Jednotky mm. Souřadnice: X = hloubka kufru D (čelo s logem do +X), Y = délka L (vodorovně v nesené poloze), Z = výška H (nahoru, držadlo nahoře); počátek = střed obálky.
// "z'" = výška od spodní plochy (0 .. H); funkce převádějí na Z modelu (z' - H/2).
// Zdroj tvaru: JEDINÁ čelní fotografie L137214 (1200 × 940 px, generická – sdílí ji 2284143, 2273022 i 2294834; poměr stran 1,277 neodpovídá ani 444/395 ani 395/362).
// Fotografie se proto ZAMĚŘUJE v pixelech a převádí na rozměry kufru NEUNIFORMNĚ: celá šířka fotografie (px 0..1199) = délka L, celá výška (py 0..939) = výška H
// (rozměry L × H z hilti.cz). Absolutní míry prvků (logo, západky, držadlo) se tím roztahují s kufrem – viz zdroje/<číslo>_poznamky.md.
// Konstrukce: dutá skořepina víka a korpusu = smyčka obrysu v rovině YZ podél osy X (obrys z fotografie, s výřezem pro držadlo), čelní reliéf = desky na plochém čele.
import { Part, Group } from '../kufriky_cloud/jadro/mesh.js';
import { earcut2 } from './earcut2.mjs';
export { Part, Group };

export const PXC = 599.5, PXW = 1199, PYH = 939;   // střed a rozsah fotografie v px (0..1199, 0..939)

// ---------- obrys z fotografie (px; levý řetězec od levého dolního rohu nahoru k výřezu držadla) ----------
// Zdroj: řádkový sken masky siluety c01 (extrémy po řádcích py 0..939), výřez držadla = vnější okraj černého rámu (px 393..806, spodek py 143).
// Horní hrana: py 22 (korpus), "pedestal" nad držadlem py 3..16 (px 294..393).
const LCHAIN = [[25, 939], [24.1, 930], [21, 900], [7, 868], [5.5, 840], [5, 630], [2, 600], [0, 586], [0, 332], [3, 300], [4, 270], [4.5, 150], [5.5, 120], [6.5, 90],
  [7, 66], [8, 60], [10, 54], [14, 48], [32, 42], [56, 36], [78, 30], [102, 24], [125, 22], [294, 22], [296, 16], [350, 9], [393, 3], [393, 66], [466, 143]];

// ---------- 2D pomocné (polygon = [[y, z']...]) ----------
const area2 = P => { let a = 0; for (let i = 0; i < P.length; i++) { const p = P[i], q = P[(i + 1) % P.length]; a += p[0] * q[1] - q[0] * p[1]; } return a; };
export const ccw = P => area2(P) < 0 ? P.slice().reverse() : P;
export function offsetPoly(P, e) {        // dovnitř o e (polygon CCW), mitra omezená
  const n = P.length, out = [];
  for (let i = 0; i < n; i++) {
    const a = P[(i + n - 1) % n], b = P[i], c = P[(i + 1) % n];
    let d1 = [b[0] - a[0], b[1] - a[1]], d2 = [c[0] - b[0], c[1] - b[1]];
    const l1 = Math.hypot(...d1) || 1, l2 = Math.hypot(...d2) || 1;
    const n1 = [-d1[1] / l1, d1[0] / l1], n2 = [-d2[1] / l2, d2[0] / l2];
    const k = 1 / Math.max(1 + n1[0] * n2[0] + n1[1] * n2[1], 0.25);
    out.push([b[0] + e * (n1[0] + n2[0]) * k, b[1] + e * (n1[1] + n2[1]) * k]);
  }
  return out;
}
export function scanY(P, z) {              // průsečíky vodorovné přímky z' = z s polygonem, seřazené podle y
  const ys = [];
  for (let i = 0; i < P.length; i++) {
    const a = P[i], b = P[(i + 1) % P.length];
    if ((a[1] <= z && b[1] > z) || (b[1] <= z && a[1] > z)) ys.push(a[0] + (z - a[1]) / (b[1] - a[1]) * (b[0] - a[0]));
  }
  return ys.sort((p, q) => p - q);
}
const pairs = ys => { const o = []; for (let i = 0; i + 1 < ys.length; i += 2) o.push([ys[i], ys[i + 1]]); return o; };
export function selfIntersects(P) {
  const n = P.length; const X = (a, b, c, d) => { const o = (p, q, r) => (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]); return o(a, b, c) * o(a, b, d) < -1e-9 && o(c, d, a) * o(c, d, b) < -1e-9; };
  for (let i = 0; i < n; i++) for (let j = i + 2; j < n; j++) { if (i === 0 && j === n - 1) continue; if (X(P[i], P[(i + 1) % n], P[j], P[(j + 1) % n])) return [i, j]; }
  return null;
}
const lerpTab = (tab, v) => {            // po částech lineární funkce; tab = [[x, f]...] seřazené podle x vzestupně; mimo rozsah konstantní
  if (v <= tab[0][0]) return tab[0][1]; const L = tab[tab.length - 1]; if (v >= L[0]) return L[1];
  for (let i = 0; i < tab.length - 1; i++) { const a = tab[i], b = tab[i + 1]; if (v >= a[0] && v <= b[0]) return b[0] === a[0] ? b[1] : a[1] + (b[1] - a[1]) * (v - a[0]) / (b[0] - a[0]); }
};

// ---------- parametrizace pro konkrétní kufr ----------
// P = { sku, L, H, D }  (mm; D = hloubka, L = délka, H = výška v nesené poloze)
export function mk(P) {
  const { L, H, D } = P;
  const sy = L / PXW, sz = H / PYH;
  const pY = px => (px - PXC) * sy;            // px (vodorovně) → Y
  const pZ = py => (PYH - py) * sz;            // py (svisle) → z' od spodní plochy
  const zc = z => z - H / 2;
  const K = { P, L, H, D, sy, sz, pY, pZ, zc };
  // --- hloubkové míry (odhady, ve fotografii nejsou měřitelné) ---
  K.LD = Math.round(D * 0.34 * 2) / 2;          // hloubka víka (odhad 34 % z D; neověřeno)
  K.xs = D / 2 - K.LD;                          // dělicí rovina víko/korpus
  K.gap = 0.3;                                  // poloviční spára
  K.xl = K.xs + K.gap; K.xb = K.xs - K.gap;
  K.pad = 2.5;                                  // výška vyvýšených polštářů nad čelní plochou
  K.F0 = D / 2 - K.pad;                         // čelní plocha (horní a spodní pole)
  K.recess = 8; K.xC = K.F0 - K.recess;         // ploché dno čela pod reliéfem (viditelné jen v dolní prohlubni)
  K.cfx = 8; K.dC = 15;                         // zkosení čelní hrany: hloubka v X, šířka (odsazení) v YZ
  K.w = 3;                                      // tloušťka stěny
  K.rB = 8;                                     // zaoblení zadní hrany korpusu
  K.band = 4;                                   // zapuštění středního pásu s logem
  K.lip = 7;                                    // spodní zkosení čela (hloubka)
  // --- obrys ---
  const toMM = ([px, py]) => [pY(px), pZ(py)];
  const Lc = LCHAIN.map(toMM);
  const Rc = LCHAIN.map(([px, py]) => toMM([PXW - px, py]));
  K.O = Rc.concat(Lc.slice().reverse());        // CCW při pohledu z +X (y doprava, z' nahoru)
  const z22 = pZ(22);
  // vyhlazený obrys pro výpočet odsazení (bez pedestalu nad držadlem a s horním rohem zjednodušeným na zkosení – odsazení malých poloměrů by se jinak protnulo)
  const LS = LCHAIN.map(([px, py], j) => { if (j >= 15 && j <= 20) { const a = LCHAIN[14], b = LCHAIN[21]; return [px, a[1] + (px - a[0]) / (b[0] - a[0]) * (b[1] - a[1])]; } return [px, Math.max(py, 22)]; });
  K.S = LS.map(([px, py]) => toMM([PXW - px, py])).concat(LS.map(toMM).reverse());
  K.z22 = z22;
  K.I = offsetPoly(K.S, K.dC);                  // hranice plochého čela
  K.W = offsetPoly(K.S, K.w);                   // vnitřní stěna dutiny
  K.ringAt = d => offsetPoly(K.S, d).map((q, i) => { const g = Math.max(0, 1 - d / 6); return [q[0] + (K.O[i][0] - K.S[i][0]) * g, q[1] + (K.O[i][1] - K.S[i][1]) * g]; });
  for (const [nm, poly] of [['O', K.O], ['I', K.I], ['W', K.W]]) { const x = selfIntersects(poly); if (x) throw new Error(`obrys ${nm} se protíná: ${x}`); }

  // --- čelní plocha: výška čela x v závislosti na z' (od nejhlubšího po vyvýšené) ---
  const zTI = Math.max(...K.I.map(q => q[1]));  // horní hrana ploché části čela
  K.zTI = zTI;
  // ploché čelo – reliéfní tabulka (py = řádek fotografie): zkosení při horní hraně → plocha → pás s logem (zapuštěný) → plocha → dolní zkosení
  K.frontSurface = z => lerpTab([[0, K.F0], [pZ(128), K.F0], [K.zTI, K.xC], [K.z22, K.xC - K.cfx]], z);
  K.panelFront = z => lerpTab([
    [0, K.F0 - K.lip], [pZ(900), K.F0 - K.lip], [pZ(860), K.F0], [pZ(600), K.F0], [pZ(568), K.F0 - K.band], [pZ(345), K.F0 - K.band], [pZ(315), K.F0],
    [pZ(128), K.F0], [K.zTI, K.xC],
  ].sort((a, b) => a[0] - b[0]), z);
  // dolní prohlubeň (lichoběžník ve spodní hraně, py 800..939; px ±190 nahoře, ±272 od py 865) – zde čelní deska chybí
  K.biteHalf = z => Math.abs(pY(PXC + lerpTab([[pZ(939), 285], [pZ(865), 272], [pZ(800), 190]], z)));
  K.biteTop = pZ(800);
  return K;
}

// ---------- sítě ----------
const mkId = (part, K, x, y, zp) => part.addV(x, y, K.zc(zp));
// smyčka prstenců [[x,y,z']...]; normála = tečna × směr postupu (CCW při pohledu z +X a postup do +X = ven)
export function loft(part, K, rings) {
  const ids = rings.map(r => r.map(p => mkId(part, K, p[0], p[1], p[2])));
  const n = rings[0].length;
  for (let k = 0; k < rings.length - 1; k++) for (let i = 0; i < n; i++) { const j = (i + 1) % n; part.addQ(ids[k][i], ids[k][j], ids[k + 1][j], ids[k + 1][i]); }
}
// víčko z polygonu v rovině YZ; pts3 = [[x,y,z']...] (x může být proměnné), plusX = normála do +X
export function cap(part, K, pts3, plusX, holes3 = []) {
  const flat = pts3.map(p => [p[1], p[2]]), hf = holes3.map(h => h.map(p => [p[1], p[2]]));
  const { pts, tris } = earcut2(flat, hf);
  const all = pts3.concat(...holes3);
  const find = q => { let best = 0, bd = Infinity; for (let i = 0; i < all.length; i++) { const d = Math.hypot(all[i][1] - q[0], all[i][2] - q[1]); if (d < bd) { bd = d; best = i; } } return all[best]; };
  const ids = pts.map(q => { const o = find(q); return mkId(part, K, o[0], q[0], q[1]); });
  for (const [a, b, c] of tris) { if (plusX) part.addT(ids[a], ids[b], ids[c]); else part.addT(ids[a], ids[c], ids[b]); }
}
const at = (poly, x) => poly.map(q => [x, q[0], q[1]]);

// dutá skořepina (víko: otevřená do -X; korpus: otevřená do +X). Vrací Part.
export function vickoSkorapka(K, mat = 'cervena') {
  const p = new Part('vicko_plast', mat); p.crease = 22;
  const { xl, xC, cfx, w } = K;
  const xCav = xC - cfx - 1;
  const r0 = at(K.O, xl), r1 = at(K.ringAt(0), xC - cfx), r2 = at(K.I, xC);
  loft(p, K, [r0, r1, r2]); cap(p, K, r2, true);
  const W = at(K.W, xl), W2 = at(K.W, xCav);
  loft(p, K, [W2, W]); cap(p, K, W2, false);                    // vnitřní stěna (postup do -X → normála dovnitř dutiny)
  cap(p, K, r0, false, [W]);                                     // okraj skořepiny (rovina dělení), normála k korpusu
  return p;
}
export function korpusSkorapka(K, mat = 'cervena') {
  const p = new Part('korpus_vana', mat); p.crease = 22;
  const { xb, D, rB, w } = K;
  const rings = [];
  const N = 4, xc = -D / 2 + rB;
  for (let k = 0; k <= N; k++) { const phi = (Math.PI / 2) * (1 - k / N), d = rB * (1 - Math.cos(phi)); rings.push(at(K.ringAt(d), xc - rB * Math.sin(phi))); }
  rings.push(at(K.O, xb));
  loft(p, K, rings); cap(p, K, rings[0], false);
  const xFl = -D / 2 + w;
  const W = at(K.W, xb), W2 = at(K.W, xFl);
  loft(p, K, [W, W2]); cap(p, K, W2, true);
  cap(p, K, rings[rings.length - 1], true, [W]);
  return p;
}

// hranol z polygonu v YZ s proměnnou zadní/přední plochou: xb(y,z'), xf(y,z'); polygon se předtím zjemní podle bodů zlomu z'
export function subdivZ(poly, zs) {
  const out = [];
  for (let i = 0; i < poly.length; i++) {
    const a = poly[i], b = poly[(i + 1) % poly.length]; out.push(a);
    const hits = zs.filter(z => (a[1] < z - 1e-9 && b[1] > z + 1e-9) || (b[1] < z - 1e-9 && a[1] > z + 1e-9)).sort((s, t) => a[1] < b[1] ? s - t : t - s);
    for (const z of hits) { const t = (z - a[1]) / (b[1] - a[1]); out.push([a[0] + t * (b[0] - a[0]), z]); }
  }
  return out;
}
export function deska(part, K, poly, xb, xf, zs = []) {
  const P = subdivZ(ccw(poly), zs);
  const fb = typeof xb === 'function' ? xb : () => xb, ff = typeof xf === 'function' ? xf : () => xf;
  const back = P.map(q => [fb(q[0], q[1]), q[0], q[1]]), front = P.map(q => [ff(q[0], q[1]), q[0], q[1]]);
  loft(part, K, [back, front]); cap(part, K, front, true); cap(part, K, back, false);
  return part;
}
// komolý jehlan (polštář): základna obdélník (y0,y1,z0,z1) v x = xA, horní plocha zmenšená o (iy, iz) v x = xB
export function jehlan(part, K, y0, y1, z0, z1, xA, xB, iy, iz) {
  const R = (a, b, c, d) => [[a, c], [b, c], [b, d], [a, d]];
  const A = R(y0, y1, z0, z1).map(q => [xA, q[0], q[1]]), B = R(y0 + iy, y1 - iy, z0 + iz, z1 - iz).map(q => [xB, q[0], q[1]]);
  loft(part, K, [A, B]); cap(part, K, B, true); cap(part, K, A, false);
  return part;
}

// pásová deska čela: pro vzorky z' spočte intervaly y (z polygonu I minus dolní prohlubeň), výška čela front(z'); stěny na koncích a na změnách počtu intervalů
export function celniDeska(part, K, { zA, zB, front, xb, bite = false, extra = [], eps = 1e-3 }) {
  const ints = z => {
    let iv = pairs(scanY(K.I, z));
    if (bite && z < K.biteTop) { const b = K.biteHalf(z); const o = []; for (const [a, c] of iv) { if (c <= -b || a >= b) o.push([a, c]); else { if (a < -b) o.push([a, -b]); if (c > b) o.push([b, c]); } } iv = o; }
    return iv;
  };
  const brk = new Set([zA, zB, ...extra.filter(z => z > zA && z < zB), ...K.I.map(q => q[1]).filter(z => z > zA && z < zB)]);
  const bl = [...brk].sort((a, b) => a - b), zs = [];
  bl.forEach((b, i) => { if (i === 0) zs.push(b + eps); else if (i === bl.length - 1) zs.push(b - eps); else { zs.push(b - eps, b + eps); } });
  const V = (x, y, z) => mkId(part, K, x, y, z);
  const quad = (pts, hint) => {                // čtyřúhelník v zadaném pořadí; převrátí se, když normála míří proti hintu
    const [a, b, c] = pts; const u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], v = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
    const nx = u[1] * v[2] - u[2] * v[1], ny = u[2] * v[0] - u[0] * v[2], nz = u[0] * v[1] - u[1] * v[0];
    const d = nx * hint[0] + ny * hint[1] + nz * hint[2];
    const ids = pts.map(q => V(q[0], q[1], q[2]));
    if (d >= 0) part.addQ(ids[0], ids[1], ids[2], ids[3]); else part.addQ(ids[0], ids[3], ids[2], ids[1]);
  };
  const sub = (A, B) => { const o = []; for (const [a, c] of A) { let segs = [[a, c]]; for (const [p, q] of B) { const nx = []; for (const [s, t] of segs) { if (q <= s || p >= t) nx.push([s, t]); else { if (p > s) nx.push([s, p]); if (q < t) nx.push([q, t]); } } segs = nx; } o.push(...segs); } return o.filter(([s, t]) => t - s > 1e-6); };
  const wallZ = (iv, z, dir) => { for (const [a, c] of iv) quad([[xb, a, z], [front(z), a, z], [front(z), c, z], [xb, c, z]], [0, 0, dir]); };
  for (let k = 0; k < zs.length - 1; k++) {
    const z0 = zs[k], z1 = zs[k + 1], I0 = ints(z0), I1 = ints(z1);
    if (k === 0) wallZ(I0, z0, -1);
    if (k === zs.length - 2) wallZ(I1, z1, +1);
    if (I0.length !== I1.length) { wallZ(sub(I0, I1), z0, +1); wallZ(sub(I1, I0), z1, -1); continue; }
    for (let m = 0; m < I0.length; m++) {
      const [a0, b0] = I0[m], [a1, b1] = I1[m], f0 = front(z0), f1 = front(z1);
      quad([[f0, a0, z0], [f0, b0, z0], [f1, b1, z1], [f1, a1, z1]], [1, 0, 0]);      // čelo
      quad([[xb, a0, z0], [xb, b0, z0], [xb, b1, z1], [xb, a1, z1]], [-1, 0, 0]);      // zadek
      quad([[xb, a0, z0], [f0, a0, z0], [f1, a1, z1], [xb, a1, z1]], [0, -1, 0]);      // levá stěna
      quad([[xb, b0, z0], [f0, b0, z0], [f1, b1, z1], [xb, b1, z1]], [0, 1, 0]);       // pravá stěna
    }
  }
  return part;
}
