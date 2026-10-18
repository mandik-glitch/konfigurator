// Pomocné funkce a rozměry modelu stroje (čistič s ohřevem vody). Jednotky mm.
// Souřadnice modelu: X = šířka, Y = délka (ČELO s rukojetí = +Y, přední – vyšší – konec krytu = −Y), Z = výška nahoru; počátek = střed obálky 650 × 650 × 780.
// V kódu se výšky zadávají jako z' = výška nad zemí (0 = spodek kol); funkce zc() je převede na Z modelu (z' − 390).
// Vlastní generátor: jádro z kufriky_cloud/jadro (mesh.js, glb.js) se jen importuje, neupravuje.
import { Part, Group, loftRings, earClip, roundedBox, prism, cylinder, tube, lathe, box, rrRing } from '../../kufriky_cloud/jadro/mesh.js';
import { MATERIALY } from '../../kufriky_cloud/jadro/glb.js';
import { earcut2 } from '../../kufriky_cloud/earcut_cloud.mjs';
import fs from 'node:fs';
export { Part, Group, loftRings, roundedBox, prism, cylinder, tube, lathe, box, rrRing, earcut2, MATERIALY };

// ---------- vlastní materiály (jádro se neupravuje – doplňují se do exportovaného slovníku) ----------
MATERIALY.nerez = { color: [0.30, 0.305, 0.315], metallic: 0.72, roughness: 0.55 };          // kartáčovaný, zaprášený nerez (matný oděr)
MATERIALY.nerez_svetly = { color: [0.40, 0.40, 0.40], metallic: 0.6, roughness: 0.5 };
MATERIALY.ocel_tmava = { color: [0.15, 0.145, 0.14], metallic: 0.5, roughness: 0.62 };       // disk kola (zašpiněný)     // světlejší plech (děrovaný panel)
MATERIALY.mosaz = { color: [0.55, 0.36, 0.10], metallic: 0.9, roughness: 0.4 };
MATERIALY.guma = { color: [0.012, 0.012, 0.014], metallic: 0.0, roughness: 0.9 };         // pryž kol a lemů
MATERIALY.plocha_tmava = { color: [0.012, 0.016, 0.03], metallic: 0.0, roughness: 0.6 };    // neutrální tmavá plošková nálepka (bez textu)
MATERIALY.plocha_modra = { color: [0.02, 0.18, 0.55], metallic: 0.0, roughness: 0.45 };    // neutrální modrá plošky
MATERIALY.plocha_bila = { color: [0.68, 0.68, 0.66], metallic: 0.0, roughness: 0.5 };
MATERIALY.plocha_zluta = { color: [0.85, 0.62, 0.0], metallic: 0.0, roughness: 0.5 };

// ---------- rozměry (z' od země) – původ každého čísla viz zdroje/cistic_poznamky.md ----------
export const ZC = 390;
export const zc = z => z - ZC;
// ---- Y-souřadnice ----
// Hodnoty „A“ (…_A) jsou odhad z fotografií (svazkové vyrovnání, nezávisle na zadané obálce; v Y vychází ≈ 585–610 mm, nejistota ≈ ±6 %).
// Obálka 650 mm v Y je dána zadáním (Robert: „vše vnější rozměr“) → polohy v Y se roztahují od přední roviny (−325, čelo pneumatik)
// koeficientem SY tak, aby nejzazší bod (konec přípojek na zadní stěně) ležel v +325. Kola (poloměry, tloušťky) se neroztahují.
export const A_FRONT = -323.1, FIT_LEN = 26;
// Rozměry „A“ (z fotografií); lze přepsat JSON souborem v CISTIC_DIMS (nástroj nastroje/doladeni_rozmeru.mjs)
export const DA = {
  hw: 228, Yf: -298, ys: 52, yb: 193, Hb: 612, zb: 168, zft: 595, yft: -171, yRear: 215, zfb: 188, slope: 0.142,
  tw: 86, R: 135.5, hwBox: 218, yBox0: 190, yBox: 235, zBoxT: 612, xp: 231, yp: 231, Yh: 223, zh: 655, xc: 173, yc: 206, Rc: 54,
  holeX: 25, holeY: -225, holeHX: 62.5, holeHY: 27.5,
};
if (process.env.CISTIC_DIMS) Object.assign(DA, JSON.parse(fs.readFileSync(process.env.CISTIC_DIMS, 'utf8')));
export const SY = process.env.CISTIC_SY ? +process.env.CISTIC_SY : (650 - FIT_LEN) / (DA.yBox - A_FRONT);
export const Y = y => -325 + (y - A_FRONT) * SY;
export const K = {
  Ht: 780,                  // temeno krytu (zadání)
  hw: DA.hw,                // polovina šířky krytu (rovina bočních stěn)
  Yf: Y(DA.Yf),             // čelní (přední, vyšší) stěna krytu (za čelem pneumatik)
  ys: Y(DA.ys), yb: Y(DA.yb),    // začátek a konec šikmého přechodu (y)
  Hb: DA.Hb,                // výška dolní hrany šikmého přechodu (nad boxem)
  zb: DA.zb,                // spodní okraj krytu
  // boční rám (černé úhelníky) + děrovaný panel
  zft: DA.zft, yft: Y(DA.yft), slope: DA.slope * SY, zfb: DA.zfb, wBar: 30, yRear: Y(DA.yRear),
  // kola (poloha v Y je pevná: čelo pneumatik = čelo obálky)
  xw: 325 - DA.tw / 2, tw: DA.tw, R: DA.R, yw: -325 + DA.R,
  // zadní stěna / sloupky / rukojeť
  hwBox: DA.hwBox, yBox0: Y(DA.yBox0), yBox: Y(DA.yBox), zBox0: 125, zBoxT: DA.zBoxT,
  xp: DA.xp, yp: Y(DA.yp), rp: 15.5, Yh: Y(DA.Yh), zh: DA.zh, ramH: 22,
  // otočná kolečka
  xc: DA.xc, yc: Y(DA.yc), Rc: DA.Rc,
};

// ---------- 2D pomůcky ----------
export function signedArea(P) { let a = 0; for (let i = 0; i < P.length; i++) { const p = P[i], q = P[(i + 1) % P.length]; a += p[0] * q[1] - q[0] * p[1]; } return a / 2; }

// zaoblený polygon: corners = [{p:[u,v], r, seg, tag}] (tag = štítek přímé hrany ZA rohem); vrací {pts, tags} (tags[i] = štítek hrany pts[i]→pts[i+1])
export function roundPoly(corners, defSeg = 6) {
  const n = corners.length, pts = [], tags = [];
  for (let k = 0; k < n; k++) {
    const c = corners[k], a = corners[(k + n - 1) % n].p, b = corners[(k + 1) % n].p, p = c.p, r = c.r || 0, seg = c.seg || defSeg;
    if (r <= 1e-6) { pts.push([p[0], p[1]]); tags.push(c.tag || ''); continue; }
    const v1 = [a[0] - p[0], a[1] - p[1]], v2 = [b[0] - p[0], b[1] - p[1]];
    const l1 = Math.hypot(...v1), l2 = Math.hypot(...v2); v1[0] /= l1; v1[1] /= l1; v2[0] /= l2; v2[1] /= l2;
    const cosA = Math.max(-1, Math.min(1, v1[0] * v2[0] + v1[1] * v2[1])), ang = Math.acos(cosA);   // úhel mezi hranami
    let t = r / Math.tan(ang / 2); t = Math.min(t, l1 * 0.49, l2 * 0.49); const rr = t * Math.tan(ang / 2);
    const s = [p[0] + v1[0] * t, p[1] + v1[1] * t], e = [p[0] + v2[0] * t, p[1] + v2[1] * t];
    const bis = [v1[0] + v2[0], v1[1] + v2[1]], bl = Math.hypot(...bis); bis[0] /= bl; bis[1] /= bl;
    const cc = [p[0] + bis[0] * rr / Math.sin(ang / 2), p[1] + bis[1] * rr / Math.sin(ang / 2)];
    let a0 = Math.atan2(s[1] - cc[1], s[0] - cc[0]), a1 = Math.atan2(e[1] - cc[1], e[0] - cc[0]);
    let da = a1 - a0; while (da > Math.PI) da -= 2 * Math.PI; while (da < -Math.PI) da += 2 * Math.PI;
    for (let i = 0; i <= seg; i++) { const q = a0 + da * i / seg; pts.push([cc[0] + rr * Math.cos(q), cc[1] + rr * Math.sin(q)]); tags.push(i < seg ? 'arc' : (c.tag || '')); }
  }
  return { pts, tags };
}
// odsazení konvexního CCW polygonu dovnitř o d (miter)
export function insetPoly(P, d) {
  const n = P.length, out = [];
  for (let i = 0; i < n; i++) {
    const a = P[(i + n - 1) % n], b = P[i], c = P[(i + 1) % n];
    const e1 = [b[0] - a[0], b[1] - a[1]], e2 = [c[0] - b[0], c[1] - b[1]];
    const l1 = Math.hypot(...e1) || 1, l2 = Math.hypot(...e2) || 1;
    const n1 = [-e1[1] / l1, e1[0] / l1], n2 = [-e2[1] / l2, e2[0] / l2];      // vnitřní normály (CCW)
    const m = [n1[0] + n2[0], n1[1] + n2[1]], ml = Math.hypot(...m) || 1, cosH = Math.max(0.35, (n1[0] * n2[0] + n1[1] * n2[1] + 1) / 2) ** 0.5;
    out.push([b[0] + m[0] / ml * d / cosH, b[1] + m[1] / ml * d / cosH]);
  }
  return out;
}

// ---------- extruze polygonu (u,v) podél třetí osy se zaoblenými hranami ----------
// mapF(u,v,w) → [x,y,z]; polygon CCW v (u,v); w0..w1; re = zaoblení hran; holes = [{tag, polys:[[ [s,t]... ]]}] díry v rovné hraně se štítkem tag
// (s = souřadnice po w od w0+re .. w1−re, t = vzdálenost podél hrany od jejího začátku); výška díry v rovině hrany: souřadnice (w, t).
export function extrudeRound(mat, name, poly, w0, w1, { re = 0, seg = 3, mapF = (u, v, w) => [w, u, v], tags = null, holes = [], crease = 40 } = {}) {
  const p = new Part(name, mat); p.crease = crease;
  let P = poly; let T = tags || poly.map(() => '');
  if (signedArea(P) < 0) throw new Error('extrudeRound: polygon musí být CCW');
  const n = P.length;
  const mo = mapF(0, 0, 0), mu = mapF(1, 0, 0), mv = mapF(0, 1, 0), mw = mapF(0, 0, 1);
  const dU = [mu[0] - mo[0], mu[1] - mo[1], mu[2] - mo[2]], dV = [mv[0] - mo[0], mv[1] - mo[1], mv[2] - mo[2]], dW = [mw[0] - mo[0], mw[1] - mo[1], mw[2] - mo[2]];
  const posDet = ((dU[1] * dV[2] - dU[2] * dV[1]) * dW[0] + (dU[2] * dV[0] - dU[0] * dV[2]) * dW[1] + (dU[0] * dV[1] - dU[1] * dV[0]) * dW[2]) > 0;
  const rings = [];                                                                // [{w, pts}]
  if (re > 1e-6) {
    for (let j = 0; j <= seg; j++) { const th = Math.PI / 2 * j / seg; rings.push({ w: w0 + re * (1 - Math.cos(th)), pts: insetPoly(P, re * (1 - Math.sin(th))) }); }
    for (let j = seg; j >= 0; j--) { const th = Math.PI / 2 * j / seg; rings.push({ w: w1 - re * (1 - Math.cos(th)), pts: insetPoly(P, re * (1 - Math.sin(th))) }); }
  } else { rings.push({ w: w0, pts: P }, { w: w1, pts: P }); }
  const V = rings.map(R => R.pts.map(q => p.addV(...mapF(q[0], q[1], R.w))));
  const mid = re > 1e-6 ? seg : 0;                                                  // index prstence těsně před střední (rovnou) částí
  for (let k = 0; k < rings.length - 1; k++) {
    for (let i = 0; i < n; i++) {
      const j = (i + 1) % n;
      if (k === mid && holes.some(h => h.tag === T[i])) continue;                   // rovnou plochu s dírami řeší zvlášť
      if (posDet) p.addQ(V[k][i], V[k][j], V[k + 1][j], V[k + 1][i]); else p.addQ(V[k][i], V[k + 1][i], V[k + 1][j], V[k][j]);
    }
  }
  // rovné plochy s dírami
  for (const h of holes) {
    for (let i = 0; i < n; i++) if (T[i] === h.tag) {
      const j = (i + 1) % n, A = P[i], B = P[j], L = Math.hypot(B[0] - A[0], B[1] - A[1]), e = [(B[0] - A[0]) / L, (B[1] - A[1]) / L];
      const wa = rings[mid].w, wb = rings[mid + 1].w;
      const to3 = (s, t) => mapF(A[0] + e[0] * t, A[1] + e[1] * t, s);
      const outer = [[wa, 0], [wb, 0], [wb, L], [wa, L]];
      const { pts, tris } = earcut2(outer, h.polys);
      const ids = pts.map(q => p.addV(...to3(q[0], q[1])));
      // orientace: normála = (B−A)×w-směr … ověříme z prvního trojúhelníku proti očekávané vnější normále
      const nOut3 = (() => { const a0 = mapF(A[0], A[1], wa), b0 = mapF(B[0], B[1], wa), a1 = mapF(A[0], A[1], wb); const u1 = [b0[0] - a0[0], b0[1] - a0[1], b0[2] - a0[2]], u2 = [a1[0] - a0[0], a1[1] - a0[1], a1[2] - a0[2]]; return [u1[1] * u2[2] - u1[2] * u2[1], u1[2] * u2[0] - u1[0] * u2[2], u1[0] * u2[1] - u1[1] * u2[0]]; })();
      // vnější normála hrany v (u,v): (e_v, −e_u)
      const nv = [e[1], -e[0]]; const o0 = mapF(0, 0, 0), ou = mapF(nv[0], nv[1], 0); const exp = [ou[0] - o0[0], ou[1] - o0[1], ou[2] - o0[2]];
      const flip = (nOut3[0] * exp[0] + nOut3[1] * exp[1] + nOut3[2] * exp[2]) < 0;
      for (const [a, b, c] of tris) { // earcut dává CCW v (s,t); porovnání s požadovanou normálou
        const A3 = p.pos.slice(3 * ids[a], 3 * ids[a] + 3), B3 = p.pos.slice(3 * ids[b], 3 * ids[b] + 3), C3 = p.pos.slice(3 * ids[c], 3 * ids[c] + 3);
        const u1 = [B3[0] - A3[0], B3[1] - A3[1], B3[2] - A3[2]], u2 = [C3[0] - A3[0], C3[1] - A3[1], C3[2] - A3[2]];
        const nn = [u1[1] * u2[2] - u1[2] * u2[1], u1[2] * u2[0] - u1[0] * u2[2], u1[0] * u2[1] - u1[1] * u2[0]];
        if (nn[0] * exp[0] + nn[1] * exp[1] + nn[2] * exp[2] >= 0) p.addT(ids[a], ids[b], ids[c]); else p.addT(ids[a], ids[c], ids[b]);
      }
      void flip;
    }
  }
  // víčka (ear-clipping; polygon může být nekonvexní)
  const cap = (R, sgn) => {
    const ids = R.pts.map(q => p.addV(...mapF(q[0], q[1], R.w)));
    for (const [a, b, c] of earClip(R.pts)) { if ((sgn > 0) === posDet) p.addT(ids[a], ids[b], ids[c]); else p.addT(ids[a], ids[c], ids[b]); }
  };
  cap(rings[0], -1); cap(rings[rings.length - 1], +1);
  return p;
}

// ---------- deska s dírami (plech): outer + holes v rovině (u,v), tloušťka w0..w1; mapF jako výše ----------
export function plate(mat, name, outer, holes, w0, w1, mapF = (u, v, w) => [w, u, v], { crease = 30 } = {}) {
  const p = new Part(name, mat); p.crease = crease;
  const { pts, tris } = earcut2(outer, holes);
  const side = (w, up) => { const ids = pts.map(q => p.addV(...mapF(q[0], q[1], w))); for (const [a, b, c] of tris) { if (up) p.addT(ids[a], ids[b], ids[c]); else p.addT(ids[a], ids[c], ids[b]); } };
  // earcut: trojúhelníky CCW v (u,v); „nahoru“ = +w pokud mapF zachovává orientaci; kontrola níže
  const o = mapF(0, 0, 0), eu = mapF(1, 0, 0), ev = mapF(0, 1, 0), ew = mapF(0, 0, 1);
  const U = [eu[0] - o[0], eu[1] - o[1], eu[2] - o[2]], Vv = [ev[0] - o[0], ev[1] - o[1], ev[2] - o[2]], W = [ew[0] - o[0], ew[1] - o[1], ew[2] - o[2]];
  const det = (U[1] * Vv[2] - U[2] * Vv[1]) * W[0] + (U[2] * Vv[0] - U[0] * Vv[2]) * W[1] + (U[0] * Vv[1] - U[1] * Vv[0]) * W[2];
  const pos = det > 0;
  side(w1, pos); side(w0, !pos);
  const wall = (ring, inward) => {                       // ring = uzavřená smyčka bodů (u,v)
    const n = ring.length; let ar = signedArea(ring);
    for (let i = 0; i < n; i++) {
      const a = ring[i], b = ring[(i + 1) % n];
      const A0 = p.addV(...mapF(a[0], a[1], w0)), B0 = p.addV(...mapF(b[0], b[1], w0)), B1 = p.addV(...mapF(b[0], b[1], w1)), A1 = p.addV(...mapF(a[0], a[1], w1));
      // vnější okraj CCW: vnější normála vpravo od směru; otvory (CW v earcut výstupu) – normála do otvoru
      const flipw = (ar > 0) !== pos;
      if (!inward ? !flipw : flipw) p.addQ(A0, B0, B1, A1); else p.addQ(A0, A1, B1, B0);
    }
  };
  wall(outer, false); for (const h of holes) wall(h, true);
  return p;
}

// zaoblený obdélník / drážka (stadion) v (u,v) jako smyčka bodů CCW
export function slotRing(cu, cv, len, wid, angDeg, seg = 5) {
  const r = wid / 2, h = Math.max(len / 2 - r, 0), pts = [], a = angDeg * Math.PI / 180, ca = Math.cos(a), sa = Math.sin(a);
  const P = (x, y) => [cu + x * ca - y * sa, cv + x * sa + y * ca];
  for (let i = 0; i <= seg; i++) { const t = -Math.PI / 2 + Math.PI * i / seg; pts.push(P(h + r * Math.cos(t), r * Math.sin(t))); }
  for (let i = 0; i <= seg; i++) { const t = Math.PI / 2 + Math.PI * i / seg; pts.push(P(-h + r * Math.cos(t), r * Math.sin(t))); }
  return pts;
}
export function rrect(cu, cv, hu, hv, r, seg = 5) { return rrRing(cu, cv, hu, hv, r, seg); }

// ---------- trubka po cestě se zaoblenými zlomy ----------
export function filletPath(pts, R, seg = 6) {
  const out = [pts[0].slice()];
  for (let i = 1; i < pts.length - 1; i++) {
    const a = pts[i - 1], b = pts[i], c = pts[i + 1], r = Array.isArray(R) ? R[i] : R;
    const v1 = [a[0] - b[0], a[1] - b[1], a[2] - b[2]], v2 = [c[0] - b[0], c[1] - b[1], c[2] - b[2]];
    const l1 = Math.hypot(...v1), l2 = Math.hypot(...v2); for (let k = 0; k < 3; k++) { v1[k] /= l1; v2[k] /= l2; }
    const cosA = v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2], ang = Math.acos(Math.max(-1, Math.min(1, cosA)));
    if (ang > Math.PI - 1e-3 || r <= 0) { out.push(b.slice()); continue; }
    let t = r / Math.tan(ang / 2); t = Math.min(t, l1 * 0.48, l2 * 0.48);
    const s = [b[0] + v1[0] * t, b[1] + v1[1] * t, b[2] + v1[2] * t], e = [b[0] + v2[0] * t, b[1] + v2[1] * t, b[2] + v2[2] * t];
    for (let k = 0; k <= seg; k++) {                      // kvadratická Bézierova křivka s,b,e
      const u = k / seg, w0 = (1 - u) * (1 - u), w1 = 2 * u * (1 - u), w2 = u * u;
      out.push([w0 * s[0] + w1 * b[0] + w2 * e[0], w0 * s[1] + w1 * b[1] + w2 * e[1], w0 * s[2] + w1 * b[2] + w2 * e[2]]);
    }
  }
  out.push(pts[pts.length - 1].slice());
  return out;
}

// válec s osou podél X / Y (střed ve (cy,cz) / (cx,cz)); cylinder() má osu Z
export function cylX(mat, name, r, x0, x1, cy, cz, n = 20) { return cylinder(mat, name, r, x0, x1, n, [0, 0]).mapV((u, v, w) => [w, u + cy, v + cz]); }
export function cylY(mat, name, r, y0, y1, cx, cz, n = 20) { return cylinder(mat, name, r, y0, y1, n, [0, 0]).mapV((u, v, w) => [u + cx, w, v + cz]).flip(); }

// rotační těleso bez víček (jen plášť) kolem osy Z: prof = [[r,z]...]; capStart/capEnd = 'down'|'up'|null
export function latheOpen(mat, name, prof, n = 28, { capStart = null, capEnd = null, center = [0, 0, 0] } = {}) {
  const p = new Part(name, mat);
  const rings = prof.map(([r, z]) => { const R = []; for (let i = 0; i < n; i++) { const a = 2 * Math.PI * i / n; R.push([center[0] + r * Math.cos(a), center[1] + r * Math.sin(a), center[2] + z]); } return R; });
  loftRings(p, rings, { capStart, capEnd });
  return p;
}

// posunout celý strom (skupiny + díly) – převod z' → Z modelu
export function shiftTree(g, dx, dy, dz) {
  for (const p of g.allParts()) p.move(dx, dy, dz);
  const walk = n => { n.pivot = [n.pivot[0] + dx, n.pivot[1] + dy, n.pivot[2] + dz]; if (n.extras && n.extras.osa === undefined) { /* osa je směr, neposouvá se */ } n.children.forEach(walk); };
  walk(g);
}
// zrcadlení stromu kolem roviny x = 0 (pro druhou stranu)
export function mirrorParts(parts, axis = 'x') { return parts.map(p => p.clone().mirror(axis, 0)); }
