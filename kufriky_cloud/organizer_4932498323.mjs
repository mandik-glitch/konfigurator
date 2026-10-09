// Milwaukee PACKOUT Tilt Bin Organiser, SKU 4932498323 – vlastní parametrický generátor (cloud).
// Souřadnice (mm, katalogová konvence GLB): X = šířka 386 (strana s madlem = +X), Y = délka 500, Z = výška 170.
// Počátek = střed obálky. Plocha s výklopnými boxy míří do +Z. Stojící poloha výrobku = madlo nahoře (+X nahoře).
// Tvar je odvozen z fotografií c01…c15 (viz zdroje/4932498323_poznamky.md); nic z cizích modelů.
import { Part, Group, box, roundedBox, prism, tube, cylinder, earClip } from './jadro/mesh.js';
import { MATERIALY } from './jadro/glb.js';

export const SKU = '4932498323';
export const OBALKA = { x: 386, y: 500, z: 170 };
export const CELO = 'X';

// vlastní materiály navíc (do sdílené tabulky se jen přidávají / upravují za běhu, soubory jádra se needitují)
MATERIALY.cerna = { color: [0.012, 0.012, 0.014], metallic: 0.0, roughness: 0.6 };
MATERIALY.cerna_mat = { color: [0.007, 0.007, 0.008], metallic: 0.0, roughness: 0.85 };
MATERIALY.cerna_dira = { color: [0.002, 0.002, 0.003], metallic: 0.0, roughness: 0.95 };

// ---------------------------------------------------------------------------------------------
// Parametry (mm). Zdroj měření: viz poznámky; „odhad“ = neměřeno přímo.
export const P = {
  XT: 193, XB: -193,               // horní (madlo) / spodní konec obálky (nožičky)
  XBODY_B: -178.2,                 // spodní hrana korpusu (nožičky pod ní)
  ZF: 85, ZBODY_B: -68, ZLEG: -85, // čelní rovina (rám), zadní plocha korpusu, konec patek u madla
  ZBP: -58,                        // vnitřní líc zadní desky (odhad)
  REAR_CH: 7, BUMP_REC: 2.5,       // zkosení zadní hrany; zapuštění středu nárazníkových sloupků (c04)
  YIN: 202,                        // vnitřní polovina okna s boxy
  X_OPEN_T: 161.5, PITCH: 108.1,   // horní hrana okna, rozteč řad
  ZROD: 77, RROD: 2.7,             // osa tyčí (otočné osy boxů), poloměr tyče
  ZFB: 72,                         // čelní rovina boxů (spodní tělo)
  BOX_D: 102,                      // hloubka boxu (odhad ze siluety c08, c11)
  BOX_HF: 94.2, BOX_HOOD: 16, BOX_RISE: 6, BOX_T: 1.7, BOX_FOOT: 9,
  W_SMALL: 88.5, W_GAP: 5.5, W_BIG: 182.5,
  ROD_BELOW_LIP: 80.2,
  HINGE: [176, 0, 21],             // osa čepu madla (rovnoběžná s Y)
};
const XTOP = [0, 1, 2].map(i => P.X_OPEN_T - P.PITCH * i);          // horní hrana boxů řady i
const XROD = XTOP.map(x => x - P.ROD_BELOW_LIP);                     // osa tyče řady i
const XBOT = XTOP.map(x => x - P.BOX_HF);                            // dno boxů řady i

// ---------------------------------------------------------------------------------------------
// pomocné funkce
function extrudeXZ(mat, name, polyXZ, y0, y1) {          // polygon [X,Z] vytažený podél Y
  const p = prism(mat, name, polyXZ, y0, y1);
  p.mapV((x, y, z) => [x, z, y]); p.flip(); return p;
}
function extrudeYZ(mat, name, polyYZ, x0, x1) {          // polygon [Y,Z] vytažený podél X
  const p = prism(mat, name, polyYZ, x0, x1);
  p.mapV((x, y, z) => [z, x, y]); return p;
}
const extrudeXY = (mat, name, polyXY, z0, z1) => prism(mat, name, polyXY, z0, z1);   // polygon [X,Y] podél Z

// těleso z proměnného polygonu: polyAt(z) vrací pole [X,Y] se STEJNÝM počtem bodů pro každé z ∈ zs (rostoucí), víka přes ear-clipping
function loftPrism(mat, name, zs, polyAt) {
  const p = new Part(name, mat);
  const rings = zs.map(z => polyAt(z));
  const n = rings[0].length;
  let area = 0; for (let i = 0; i < n; i++) { const a = rings[0][i], b = rings[0][(i + 1) % n]; area += a[0] * b[1] - b[0] * a[1]; }
  const ccw = area > 0;
  const ids = rings.map((r, k) => r.map(q => p.addV(q[0], q[1], zs[k])));
  for (let k = 0; k + 1 < zs.length; k++) for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    if (ccw) p.addQ(ids[k][i], ids[k][j], ids[k + 1][j], ids[k + 1][i]); else p.addQ(ids[k][j], ids[k][i], ids[k + 1][i], ids[k + 1][j]);
  }
  const cap = (k, up) => {
    const R = ccw ? rings[k] : rings[k].slice().reverse();
    const idx = ccw ? ids[k] : ids[k].slice().reverse();
    const cv = R.map(q => p.addV(q[0], q[1], zs[k]));
    for (const [a, b, c] of earClip(R)) { if (up) p.addT(cv[a], cv[b], cv[c]); else p.addT(cv[a], cv[c], cv[b]); }
  };
  cap(0, false); cap(zs.length - 1, true);
  p.crease = 25;
  return p;
}
// vnitřní odsazení polygonu (miter), d>0 = dovnitř
function insetPoly(poly, d) {
  const n = poly.length; let area = 0;
  for (let i = 0; i < n; i++) { const a = poly[i], b = poly[(i + 1) % n]; area += a[0] * b[1] - b[0] * a[1]; }
  const sgn = area > 0 ? 1 : -1;
  const out = [];
  for (let i = 0; i < n; i++) {
    const a = poly[(i + n - 1) % n], b = poly[i], c = poly[(i + 1) % n];
    const e1 = [b[0] - a[0], b[1] - a[1]], e2 = [c[0] - b[0], c[1] - b[1]];
    const l1 = Math.hypot(...e1) || 1, l2 = Math.hypot(...e2) || 1;
    const n1 = [-sgn * e1[1] / l1, sgn * e1[0] / l1], n2 = [-sgn * e2[1] / l2, sgn * e2[0] / l2];   // dovnitř
    let bx = n1[0] + n2[0], by = n1[1] + n2[1]; const bl = Math.hypot(bx, by);
    if (bl < 1e-6) { out.push([b[0] + n1[0] * d, b[1] + n1[1] * d]); continue; }
    bx /= bl; by /= bl; const k = 1 / Math.max(bx * n1[0] + by * n1[1], 0.35);
    out.push([b[0] + bx * d * k, b[1] + by * d * k]);
  }
  return out;
}

// deska s pravoúhlými kapsami. axis 'x': kapsy [ya,yb,za,zb] hluboké `depth` od líce x1; axis 'z': kapsy [xa,xb,ya,yb] od líce z1
function pocketSlab(mat, name, axis, [x0, x1, y0, y1, z0, z1], holes, depth) {
  const out = new Part(name, mat);
  const [u0, u1, v0, v1] = axis === 'x' ? [y0, y1, z0, z1] : [x0, x1, y0, y1];
  const us = new Set([u0, u1]), vs = new Set([v0, v1]);
  for (const h of holes) { us.add(h[0]); us.add(h[1]); vs.add(h[2]); vs.add(h[3]); }
  const U = [...us].sort((a, b) => a - b), V = [...vs].sort((a, b) => a - b);
  for (let i = 0; i + 1 < U.length; i++) for (let j = 0; j + 1 < V.length; j++) {
    const cu = (U[i] + U[i + 1]) / 2, cv = (V[j] + V[j + 1]) / 2;
    const inH = holes.some(h => cu > h[0] && cu < h[1] && cv > h[2] && cv < h[3]);
    if (axis === 'x') out.append(box(mat, name, x0, inH ? x1 - depth : x1, U[i], U[i + 1], V[j], V[j + 1]));
    else out.append(box(mat, name, U[i], U[i + 1], V[j], V[j + 1], z0, inH ? z1 - depth : z1));
  }
  return out;
}

// obrys půdorysu (X,Y) – polovina Y>0 shora dolů. Z c01 (obrys), viz poznámky.
function outlineHalf() {
  const pts = [];
  const cx = 169, cy = 226, r = 24;                       // horní roh: zaoblení r=24
  for (let k = 0; k <= 6; k++) { const f = (k / 6) * Math.PI / 2; pts.push([cx + r * Math.cos(f), cy + r * Math.sin(f)]); }
  pts.push([146.5, 250], [139, 238.6]);                   // zkosení za horním nárazníkem
  pts.push([-122.3, 238.6], [-126, 241.5], [-130, 245.5], [-134, 248.5], [-136.6, 250]);   // náběh spodního nárazníku
  pts.push([-163, 250], [-167.7, 246.7], [-172.4, 242.9], [-177.2, 237.2], [-178.2, 233]);
  return pts;
}
function outlineFull() {
  const h = outlineHalf();
  const neg = h.slice().reverse().map(p => [p[0], -p[1]]);
  return [...h, ...neg];
}

// ---------------------------------------------------------------------------------------------
// KORPUS (černý PP)
function buildKorpus(g) {
  const { ZF, ZBODY_B, ZBP, YIN, XBODY_B } = P;
  // zadní deska: celý obrys, spodní hrana zkosená (c04: zúžení u Z -62…-68)
  const out = outlineFull();
  g.add(loftPrism('cerna', 'korpus_zadni_deska', [ZBODY_B, ZBODY_B + P.REAR_CH, ZBP], z => insetPoly(out, z < ZBODY_B + 0.01 ? P.REAR_CH : 0)));
  // levý/pravý pás rámu s nárazníky; nárazníky mají koncové hlavice (Z>58, Z<-39) a o 2,5 mm zapuštěný střed (c04)
  const rec = z => (z > 58 || z < -39) ? 0 : P.BUMP_REC;
  for (const s of [1, -1]) {
    const h = outlineHalf();
    const polyAt = z => {
      const r = rec(z);
      const hh = h.map(p => [p[0], s * (p[1] - r * Math.min(Math.max((p[1] - 238.6) / 11.4, 0), 1))]);
      return [[161.5, s * 219], [193, s * 219], ...hh, [XBODY_B, s * YIN], [161.5, s * YIN]];
    };
    const zs = [ZBP, -39 - 0.01, -39 + P.BUMP_REC, 58 - P.BUMP_REC, 58 + 0.01, ZF];
    g.add(loftPrism('cerna', 'korpus_bok_' + (s > 0 ? 'p' : 'm'), [ZBP, -39, -39 + P.BUMP_REC, 58 - P.BUMP_REC, 58, ZF], z => {
      const r = z <= -39 || z >= 58 ? 0 : (z < -39 + P.BUMP_REC ? P.BUMP_REC * (z + 39) / P.BUMP_REC : (z > 58 - P.BUMP_REC ? P.BUMP_REC * (58 - z) / P.BUMP_REC : P.BUMP_REC));
      const hh = h.map(p => [p[0], s * (p[1] - r * Math.min(Math.max((p[1] - 238.6) / 11.4, 0), 1))]);
      return [[161.5, s * 219], [193, s * 219], ...hh, [XBODY_B, s * YIN], [161.5, s * YIN]];
    }));
  }
  g.add(box('cerna', 'korpus_dolni_pas', XBODY_B, -162.8, -YIN, YIN, ZBP, ZF));
  // nožičky (u čelní strany; zadní strana neověřena)
  for (const s of [1, -1]) {
    g.add(extrudeXY('cerna', 'nozicka_' + (s > 0 ? 'p' : 'm'), [[XBODY_B, s * 177], [XBODY_B, s * 212], [-193, s * 203], [-193, s * 180.4]], 45, ZF));
  }
}

// ---------------------------------------------------------------------------------------------
// STĚNA U MADLA (strana +X): zapuštěné panely, pás s kapsami, střední modul s kapsou pro madlo
function buildMadloStrana(g) {
  const { ZBP } = P;
  const XI = 161.5;
  // boční panely X∈[161.5,185], Y∈±[118,219], profil v (Y,Z): nahoře skos na Z=73 (|Y|<161)
  for (const s of [1, -1]) {
    const poly = s > 0
      ? [[118, ZBP], [219, ZBP], [219, 85], [174, 85], [161, 73], [118, 73]]
      : [[-118, ZBP], [-118, 73], [-161, 73], [-174, 85], [-219, 85], [-219, ZBP]];
    g.add(extrudeYZ('cerna', 'stena_panel_' + (s > 0 ? 'p' : 'm'), poly, XI, 185));
    // horní lem (pás Z∈[60,85]) na X∈[185,193] s kapsami (větrací otvory) – Y∈±[165,212]
    const rim = s > 0
      ? [[118, 60], [219, 60], [219, 85], [174, 85], [161, 73], [118, 73]]
      : [[-118, 60], [-118, 73], [-161, 73], [-174, 85], [-219, 85], [-219, 60]];
    g.add(extrudeYZ('cerna', 'stena_lem_' + (s > 0 ? 'p' : 'm'), rim, 185, 193));
  }
  // střední modul: sloupky Y∈±[89.7,118], plná výška Z -85…85
  for (const s of [1, -1]) {
    const y0 = s > 0 ? 89.7 : -118, y1 = s > 0 ? 118 : -89.7;
    g.add(box('cerna', 'stena_sloupek_' + (s > 0 ? 'p' : 'm'), XI, 193, y0, y1, P.ZLEG, 85));
  }
  // zadní stěna kapsy madla (X 161.5…169), žebra, strop a dno kapsy
  g.add(box('cerna', 'kapsa_zad', XI, 169, -89.7, 89.7, ZBP, 73));
  for (let i = -3; i <= 3; i++) g.add(box('cerna_dira', 'kapsa_zebro_' + i, 169, 172.5, i * 9.5 - 1.6, i * 9.5 + 1.6, -40, 20));
  g.add(box('cerna', 'kapsa_strop', XI, 193, -89.7, 89.7, 66, 73));
  g.add(box('cerna', 'kapsa_dno', XI, 185, -89.7, 89.7, -68, -48));
  // rošt na horní hraně modulu (zvýšený blok s drážkami), Y∈[-61,62]
  const slots = [];
  for (const [ya, yb] of [[49.5, 61.3], [35, 47], [23.4, 32], [14, 22.6], [4.5, 13], [-4.5, 3.8], [-13.5, -5], [-22.5, -14], [-31, -23]]) slots.push([165, 188, ya, yb]);
  g.add(pocketSlab('cerna', 'rost_horni', 'z', [161.5, 193, -61, 62, 73, 83], slots, 9));
  // otvor se šroubem (c01: Y≈-49, X≈181, Ø15)
  g.add(cylinder('cerna_dira', 'sroub_otvor', 7.5, 73, 73.6, 20, [181, -49]));
  // štítek PACKOUT (červený) na čelní ploše pásu: Y∈[-155,-66], X∈[165.4,187]
  g.add(box('cervena', 'stitek_celo', 165.4, 187, -155, -66, 73, 74.4));
  // štítek PACKOUT na ploše s madlem: Y±66.5, Z 24.5…66
  g.add(extrudeYZ('cervena', 'stitek_madlo', [[-66.5, 66], [66.5, 66], [66.5, 38], [60, 33], [40, 24.5], [-40, 24.5], [-60, 33], [-66.5, 38]], 188, 193));
}

// ---------------------------------------------------------------------------------------------
// BUŇKY: přepážky, střední sloupek, tyče
function buildBunky(g) {
  const { ZBP, YIN, ZROD, RROD } = P;
  for (let i = 0; i < 3; i++) {
    const xb = XBOT[i];
    g.add(box('cerna_mat', 'prepazka_' + (i + 1), xb - 13.9, xb, -YIN, YIN, ZBP, 72));
  }
  // střední sloupek
  g.add(box('cerna_mat', 'sloupek_stred', -162.8, P.X_OPEN_T, -15.8, 15.8, ZBP, 82));
  for (let i = 0; i < 3; i++) g.add(box('cerna_mat', 'sloupek_objimka_' + (i + 1), XROD[i] - 6, XROD[i] + 6, -17.6, 17.6, 70, 82));
  // západka sloupku (červené T)
  g.add(roundedBox('cervena', 'sloupek_zapadka_pricka', { x0: 42.3, x1: 54.2, y0: -10.5, y1: 9.5, z0: 80, z1: 84.5, rc: 1.5, re: 0.8 }));
  g.add(roundedBox('cervena', 'sloupek_zapadka_noha', { x0: 28, x1: 42.3, y0: -5.5, y1: 5, z0: 80, z1: 84.5, rc: 1.5, re: 0.8 }));
  // tyče
  for (let i = 0; i < 3; i++) g.add(tube('ocel', 'tyc_' + (i + 1), [[XROD[i], -YIN - 6, ZROD], [XROD[i], YIN + 6, ZROD]], RROD, 14));
}

// ---------------------------------------------------------------------------------------------
// BOX (čirý PC) + případný dělič
export function buildBox(idx, row, yc, W, big) {
  const { ZFB: Zf, ZROD, BOX_D, BOX_HOOD, BOX_RISE, BOX_T: t } = P;
  const xr = XROD[row], Xbot = XBOT[row], Xf = XTOP[row], Xr = Xf + BOX_RISE, Xh = Xf - BOX_HOOD;
  const Zb = Zf - BOX_D, Zp = Zf - 3, Zh = Zf + 2.2;
  const y0 = yc - W / 2, y1 = yc + W / 2;
  const g = new Group('box_' + idx, { pivot: [xr, yc, ZROD], extras: { osa: [0, -1, 0], rada: row + 1, velky: !!big, popis: 'osa otáčení = tyč (rovnoběžná s Y); kladný úhel = sklopení dopředu (+Z)' } });
  const Xfl = Xbot + P.BOX_FOOT;                          // spodní líc dna (pilířky bočnic sahají níž, až na Xbot)
  const side = [[Xfl + 2, Zb], [Xfl, Zb + 2], [Xfl, Zf - 16], [Xbot + 1, Zf - 8], [Xbot + 3, Zf - 1], [Xbot + 8, Zf], [Xh, Zf], [Xh, Zh], [Xf, Zh], [Xr, Zb]];
  g.add(extrudeXZ('cira', 'stena_l', side, y0, y0 + t));
  g.add(extrudeXZ('cira', 'stena_p', side, y1 - t, y1));
  g.add(box('cira', 'dno', Xfl, Xfl + t, y0 + t, y1 - t, Zb + 1, Zp));
  g.add(box('cira', 'zadni_stena', Xfl, Xr, y0 + t, y1 - t, Zb, Zb + t));
  g.add(box('cira', 'celni_panel', Xfl, Xh, y0 + t, y1 - t, Zp - t, Zp));
  g.add(box('cira', 'kapa_police', Xh - t, Xh, y0 + t, y1 - t, Zp - t, Zh));
  // čelní pás (kápě) s výřezem pro prst (u velkého boxu dvě poloviny, mezi nimi štěrbina pro dělič)
  const nw = 9, nd = 5;
  const band = (ya, yb, c) => {
    const q = [[Xh, ya], [Xf, ya]];
    q.push([Xf, c - nw], [Xf - nd, c - nw + 4], [Xf - nd, c + nw - 4], [Xf, c + nw]);
    q.push([Xf, yb], [Xh, yb]); return q;
  };
  if (big) {
    g.add(prism('cira', 'celni_pas_a', band(y0 + t, yc - 1.5, yc - W / 4), Zh - t, Zh));
    g.add(prism('cira', 'celni_pas_b', band(yc + 1.5, y1 - t, yc + W / 4), Zh - t, Zh));
  } else g.add(prism('cira', 'celni_pas', band(y0 + t, y1 - t, yc), Zh - t, Zh));
  // oka okolo tyče (hák) + krček
  for (const [ya, yb] of [[y0 - 0.5, y0 + t + 1.2], [y1 - t - 1.2, y1 + 0.5]]) g.add(tube('cira', 'hak', [[xr, ya, ZROD], [xr, yb, ZROD]], 5.2, 14));
  const neck = [[xr - 5, ZROD], [xr + 1, ZROD], [xr + 1, Zf - 3], [Xbot + 5, Zf - 3]];
  g.add(extrudeXZ('cira', 'krcek_l', neck, y0, y0 + t));
  g.add(extrudeXZ('cira', 'krcek_p', neck, y1 - t, y1));
  if (big) {
    const dv = [[Xfl + t + 0.3, Zb + t + 0.2], [Xfl + t + 0.3, Zp - t - 0.2], [Xh - 0.5, Zp - t - 0.2], [Xh - 0.5, Zh + 1.8], [Xf + 1, Zh + 1.8], [Xr + 1, Zb + t + 0.2]];
    g.add(extrudeXZ('cerna', 'delic', dv, yc - 1.1, yc + 1.1));
  }
  return g;
}

// ---------------------------------------------------------------------------------------------
// MADLO (červený rám + guma), výchozí poloha sklopená v kapse; rukojet=90 → vyklopená nahoru (+X)
function buildMadlo() {
  const [hx, hy, hz] = P.HINGE;
  const g = new Group('rukojet', { pivot: [hx, hy, hz], extras: { osa: [0, -1, 0], popis: 'výchozí = sklopeno v kapse na čele s madlem; --pose rukojet=90 = vyklopeno nahoru (+X, c01)' } });
  const z0 = hz - 7, z1 = hz + 7;
  const outline = [[176, -90], [236.5, -90], [240.5, -86], [240.5, 86], [236.5, 90], [176, 90], [176, 58], [198, 58], [205, 64], [214, 64], [214, -64], [205, -64], [198, -58], [176, -58]];
  const parts = [];
  parts.push(extrudeXY('cervena', 'madlo_ram', outline, z0, z1));
  for (const s of [1, -1]) parts.push(tube('cervena', 'madlo_cep_' + (s > 0 ? 'p' : 'm'), [[hx, s * 58, hz], [hx, s * 90, hz]], 7, 16));
  parts.push(roundedBox('cerna_mat', 'madlo_guma', { x0: 211, x1: 229, y0: -52, y1: 52, z0: z1, z1: z1 + 5, rc: 3, re: 1.5 }));
  for (const p of parts) { p.rot('y', 90, [hx, hy, hz]); g.add(p); }
  return g;
}

// ZÁPADKA (červený hák pod madlem) a červené pásky na bocích
function buildZapadka(g) {
  g.add(roundedBox('cervena', 'zapadka_telo', { x0: 176, x1: 190, y0: -17, y1: 17, z0: -80, z1: -45, rc: 4, re: 3 }));
  g.add(roundedBox('cervena', 'zapadka_prirub', { x0: 172, x1: 191, y0: -22.5, y1: 22.5, z0: -80, z1: -71, rc: 3, re: 1.5 }));
  for (const s of [1, -1]) g.add(box('cervena', 'bok_pasek_' + (s > 0 ? 'p' : 'm'), -51, 71, s > 0 ? 238.6 : -239.6, s > 0 ? 239.6 : -238.6, 9, 21));
}

// ---------------------------------------------------------------------------------------------
export function build() {
  const root = new Group('organizer');
  const telo = root.addGroup(new Group('telo'));
  buildKorpus(telo);
  buildMadloStrana(telo);
  buildBunky(telo);
  buildZapadka(telo);
  // boxy: číslování jako na c01 (shora = od madla, zleva doprava = od +Y k -Y)
  const ws = P.W_SMALL, gap = P.W_GAP;
  const cB = 18.6 + ws / 2, cA = cB + ws + gap;                 // středy malých boxů poloviny +Y (zrcadlově -Y)
  const cBig = 18.6 + P.W_BIG / 2;
  let n = 0;
  for (const c of [cA, cB, -cB, -cA]) root.addGroup(buildBox(++n, 0, c, ws, false));
  for (const c of [cBig, -cBig]) root.addGroup(buildBox(++n, 1, c, P.W_BIG, true));
  for (const c of [cA, cB, -cB, -cA]) root.addGroup(buildBox(++n, 2, c, ws, false));
  root.addGroup(buildMadlo());
  return root;
}
