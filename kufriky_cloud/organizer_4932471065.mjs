// Milwaukee PACKOUT Compact Slim Organiser, SKU 4932471065 – vlastní parametrický generátor (cloud).
// Tvar podle fotografií výrobce (viz zdroje/4932471065_poznamky.md). Jednotky mm. X = šířka (249), Y = délka (411, čelo +Y),
// Z = výška (64, nahoru). Počátek = střed obálky. Interně se počítá ve výškách zb = 0 (dno) .. 64 (vrch víka), posun o ZB.
import { Group, Part, box, cylinder, tube, loftRings } from './jadro/mesh.js';
import { writeGLB, MATERIALY } from './jadro/glb.js';
import { clipPolyY, extrude, loftPoly, roundPoly, offsetPoly, rectPoly, circlePoly, movePoly, rotPoly, boxR, ccw, cw, merge, mirrorPolyX, rrect, profileSolid, seg2, cylX, pointInPoly } from './pomocne.mjs';

export const SKU = '4932471065';
export const OBALKA = { x: 249, y: 411, z: 64 };
export const CELO = 'Y';

// vlastní (nové) materiály – jen přidání klíčů, stávající se nemění
MATERIALY.cira_hex ??= { color: [0.75, 0.78, 0.82], metallic: 0.0, roughness: 0.2, alpha: 0.5 };
MATERIALY.cira_viko ??= { color: [0.66, 0.72, 0.76], metallic: 0.0, roughness: 0.12, alpha: 0.38 };

const ZB = -32;
const Zc = v => v + ZB;
const D2R = Math.PI / 180;

// ======================= PARAMETRY =======================
const P = {
  // výškové úrovně (zb od spodku)
  zFoot: 0, zPlate: 3.0, zWallBot: 8, zFloor: 8, zRimStep: 23.5, zSeam: 28, zLidTop: 64,
  zHandleTop: 26, zCap: 51, zBumpTop: 56,
  // základna
  bodyHW: 115.5, rimHW: 113, bodyY0: -196, bodyY1: 150,
  cavHW: 103, cavY0: -177, cavY1: 128,
  // víko
  lidHW: 117.8, lidYb: -190,
  lidWall: 2.2, plateT: 3, lidFillet: 8,
  pocketDepth: 11, pocketInset: 10,
  // nádoby
  contZ0: 8, contH: 44,
  // závěs
  hingeY: -196.5, hingeZ: 30.5, hingeR: 7.2,
  // spony: střed (pravá), směr tečny
  latchC: [102, 160],
};

// ======================= PŮDORYSY =======================
const baseBodyOutline = () => roundPoly([[-P.bodyHW, P.bodyY0], [P.bodyHW, P.bodyY0], [P.bodyHW, 140], [106.8, P.bodyY1], [-106.8, P.bodyY1], [-P.bodyHW, 140]], [22, 22, 0, 0, 0, 0], 8);
const handleOutline = () => [[108.5, 147], [81.5, 177.3], [56.7, 205.5], [-56.7, 205.5], [-81.5, 177.3], [-108.5, 147]];
const windowPoly = () => roundPoly([[-54.5, 184.5], [-54.5, 171], [-33, 151], [33, 151], [54.5, 171], [54.5, 184.5]], [6.5, 3, 3, 3, 3, 6.5], 5);
const LIDFRONT = process.env.LIDFRONT || 'B';
const lidOutline = () => LIDFRONT === 'A'
  ? roundPoly([[-P.lidHW, P.lidYb], [P.lidHW, P.lidYb], [P.lidHW, 138], [86, 176], [40, 155], [-40, 155], [-86, 176], [-P.lidHW, 138]], [25, 25, 3, 3, 2, 2, 3, 3], 8)
  : roundPoly([[-P.lidHW, P.lidYb], [P.lidHW, P.lidYb], [P.lidHW, 140], [123, 150], [121, 164], [108, 178], [92, 180], [52, 155.5], [-52, 155.5], [-92, 180], [-108, 178], [-121, 164], [-123, 150], [-P.lidHW, 140]], [25, 25, 3, 5, 6, 8, 4, 2, 2, 4, 8, 6, 5, 3], 6);
const octa = (x0, x1, y0, y1, c, r = 1.5) => roundPoly([[x0 + c, y0], [x1 - c, y0], [x1, y0 + c], [x1, y1 - c], [x1 - c, y1], [x0 + c, y1], [x0, y1 - c], [x0, y0 + c]], r, 3);

// ======================= ZÁKLADNA =======================
function buildBase() {
  const g = new Group('zaklad');
  const outB = baseBodyOutline(), outH = handleOutline(), win = windowPoly();
  const cav = roundPoly(rectPoly(-P.cavHW, P.cavHW, P.cavY0, P.cavY1), 9, 6);
  g.add(extrude('cerna', 'dno', offsetPoly(outB, 6.5), [], Zc(P.zPlate), Zc(P.zFloor)));
  g.add(extrude('cerna', 'stena', outB, [cav], Zc(P.zWallBot), Zc(P.zRimStep)));
  const rimOut = roundPoly([[-P.rimHW, P.bodyY0 + 1.5], [P.rimHW, P.bodyY0 + 1.5], [P.rimHW, 139], [105, P.bodyY1], [-105, P.bodyY1], [-P.rimHW, 139]], [21, 21, 0, 0, 0, 0], 8);
  g.add(extrude('cerna', 'okraj', rimOut, [cav], Zc(P.zRimStep), Zc(P.zSeam)));
  g.add(extrude('cerna', 'rukojet', outH, [win], Zc(P.zWallBot), Zc(P.zHandleTop)));
  // žebra úchopu na horní hraně příčky rukojeti
  for (let i = -5; i <= 5; i++) g.add(boxR('cerna_mat', 'zebro_' + i, i * 7.8, 194, 3.8, 12, Zc(P.zHandleTop), Zc(P.zHandleTop + 0.9), { r: 1.4, crease: 5 }));
  // zámek víka (černý jazýček na čelní stěně dutiny)
  g.add(profileSolid('cerna', 'jazyk_zamku', rrect(0, 135.8, 47, 12.5, 3.5), [[Zc(P.zSeam), 0], [Zc(P.zSeam + 3), 0], [Zc(P.zSeam + 4.2), 1.4]]));
  // červené tlačítko (vysouvací) – těleso při dně + palcová část v okně
  g.add(boxR('cervena', 'tlacitko_dno', 0, 136.5, 45.6, 27.6, Zc(P.zPlate), Zc(P.zFloor + 1), { r: 4 }));
  g.add(profileSolid('cervena', 'tlacitko_palec', rrect(0, 154.5, 28, 11, 3), [[Zc(14), 0], [Zc(22), 0], [Zc(26), 1.5], [Zc(26.8), 3]]));
  // zadní rohové nárazníky + závěs
  for (const s of [1, -1]) g.add(bumper(s));
  g.add(...hingeBase());
  g.add(...latchBase());
  g.add(...feet());
  g.add(...wallRibs());
  return g;
}

function bumper(s) {
  // půdorys pravého nárazníku (s=1), zrcadlí se pro s=-1; vršek šikmo (vnější zadní roh nižší)
  const arc = (cx, cy, r, a0, a1, n) => Array.from({ length: n + 1 }, (_, i) => { const a = (a0 + (a1 - a0) * i / n) * D2R; return [cx + r * Math.cos(a), cy + r * Math.sin(a)]; });
  let poly = [[84.5, -205.3], [95, -205.3], ...arc(95, -176, 29.0, -90, 0, 10).slice(1), [124.3, -163], [119.4, -157.5], ...arc(93, -165, 25.8, 0, -90, 10), [84.5, -190.8]];
  if (s < 0) poly = mirrorPolyX(poly);
  const p = extrude('cerna', s > 0 ? 'naraznik_P' : 'naraznik_L', poly, [], Zc(5), Zc(P.zBumpTop), { crease: 30 });
  // zkosení vrchu: výška klesá s odstupem od středu rohu (95,-165)
  p.mapV((x, y, z) => { if (z < Zc(P.zBumpTop) - 1e-6) return [x, y, z]; const d = Math.hypot(Math.abs(x) - 95, y + 165); return [x, y, z - Math.min(9, Math.max(0, (d - 14) * 0.45))]; });
  return p;
}

function hingeBase() {
  const out = [];
  const zc = Zc(P.hingeZ), y = P.hingeY, r = P.hingeR;
  for (const xc of [-48, 0, 48]) {
    const x0 = xc - 11.1, x1 = xc + 11.1;
    out.push(cylX('cerna', 'zavesni_cep_' + xc, y, zc, r, x0, x1, 18));
    out.push(box('cerna', 'zavesni_noha_' + xc, x0, x1, y, P.bodyY0 + 3, zc - r, zc + r - 0.5));
    out.push(box('cerna', 'zavesni_zaklad_' + xc, x0, x1, y - 1, P.bodyY0 + 3, Zc(P.zRimStep) , zc - r + 0.1));
  }
  out.push(cylX('ocel', 'zavesni_cep_osa', y, zc, 1.6, -108, 108, 10));
  return out;
}

// pozice a směry spon (s=+1 pravá, -1 levá)
function latchFrame(s) {
  const t = s > 0 ? [-0.673, 0.739] : [0.673, 0.739];
  const n = s > 0 ? [0.739, 0.673] : [-0.739, 0.673];
  const rot = Math.atan2(t[1], t[0]) / D2R;
  return { t, n, rot, c: [s * P.latchC[0], P.latchC[1]] };
}
function latchBase() {
  const out = [];
  for (const s of [1, -1]) {
    const f = latchFrame(s);
    const at = (dt, dn) => [f.c[0] + f.t[0] * dt + f.n[0] * dn, f.c[1] + f.t[1] * dt + f.n[1] * dn];
    const L = s > 0 ? 'P' : 'L';
    const b = at(-1, -2);
    out.push(extrude('cerna', 'sponaz_podstavec_' + L, rrect(b[0], b[1], 30, 20, 3, f.rot), [], Zc(P.zPlate), Zc(P.zSeam - 2)));
    const a = at(0, 4);   // červená páka
    out.push(profileSolid('cervena', 'paka_' + L, rrect(a[0], a[1], 31, 14.5, 3.5, f.rot), [[Zc(3.5), 2], [Zc(8), 0], [Zc(22.5), 0], [Zc(25), 1.6], [Zc(26), 3.2]]));
    const c = at(0.5, 4.5); // černý pásek pod čepičkou
    out.push(profileSolid('cerna_mat', 'pasek_' + L, rrect(c[0], c[1], 28, 12.5, 3.5, f.rot), [[Zc(26), 0], [Zc(33), 0]]));
  }
  return out;
}
function latchLid() {
  const out = [];
  for (const s of [1, -1]) {
    const f = latchFrame(s);
    const at = (dt, dn) => [f.c[0] + f.t[0] * dt + f.n[0] * dn, f.c[1] + f.t[1] * dt + f.n[1] * dn];
    const L = s > 0 ? 'P' : 'L';
    const c = at(1.5, 5.0);
    out.push(profileSolid('cira_viko', 'cepicka_' + L, rrect(c[0], c[1], 31, 13, 5, f.rot), [[Zc(33), 0], [Zc(46), 0], [Zc(49), 1.4], [Zc(51), 3.5]], { capStart: 'down' }));
  }
  return out;
}
function latchBails() {
  const bails = [];
  for (const s of [1, -1]) {
    const f = latchFrame(s);
    const at = (dt, dn, z) => { const p = [f.c[0] + f.t[0] * dt + f.n[0] * dn, f.c[1] + f.t[1] * dt + f.n[1] * dn]; return [p[0], p[1], Zc(z)]; };
    const piv = at(0, 7, 7);
    const axis = s > 0 ? [f.t[0], f.t[1], 0] : [-f.t[0], -f.t[1], 0];
    const g = new Group(s > 0 ? 'sponaP' : 'sponaL', { pivot: piv, extras: { osa: axis } });
    // uzavřená drátěná smyčka: příčka uvnitř páky (dn=7), nohy po vnější straně čepičky (dn=12.6), vršek přes čepičku
    const path = [at(-17.5, 7, 7), at(-17.5, 12.6, 9), at(-17.5, 12.6, 46), at(-13, 12.6, 52.8), at(13, 12.6, 52.8), at(17.5, 12.6, 46), at(17.5, 12.6, 9), at(17.5, 7, 7), at(-17.5, 7, 7)];
    g.add(tube('ocel', 'draty_' + (s > 0 ? 'P' : 'L'), path, 1.25, 8));
    bails.push(g);
  }
  return bails;
}

// svislá žebra (rysky) na spodní vnější stěně základny po obou delších stranách
function wallRibs() {
  const out = [];
  for (const sx of [1, -1]) for (let y = -150; y <= 135; y += 10.4) {
    out.push(box('cerna', 'zebro_steny', sx > 0 ? P.bodyHW - 0.2 : -P.bodyHW - 0.6, sx > 0 ? P.bodyHW + 0.6 : -P.bodyHW + 0.2, y - 0.7, y + 0.7, Zc(P.zWallBot + 3), Zc(P.zRimStep - 1.5)));
  }
  return out;
}
function feet() {
  const out = [];
  const ys = [54.5, -45.5, -145.5], xs = [-48.5, 48.5];
  for (const y of ys) for (const x of xs) {
    const slots = [];
    for (let i = 0; i < 8; i++) slots.push(rrect(x + (i - 3.5) * 7.4, y, 4.2, 17.5, 1.6, 0, 2));
    out.push(extrude('cerna', 'patka', rrect(x, y, 66, 36, 4, 0, 3), slots, Zc(P.zFoot), Zc(P.zPlate + 0.2)));
  }
  return out;
}

// ======================= VÍKO =======================
// sklon čelní plochy víka: výška horní plochy zl(y): 64 do y=140, pak 45° dolů na 47 při y>=157
const zlTop = y => y <= 140 ? P.zLidTop : Math.max(P.zCap, P.zLidTop - (y - 140));
function buildLid() {
  const g = new Group('vicko', { pivot: [0, P.hingeY, Zc(P.hingeZ)], extras: { osa: [1, 0, 0] } });
  const out = lidOutline();
  const z0 = Zc(P.zSeam), z1 = Zc(P.zLidTop), R = P.lidFillet;
  const arc = [];
  for (let k = 0; k <= 5; k++) { const a = Math.PI / 2 * k / 5; arc.push([z1 - R + R * Math.sin(a), R - R * Math.cos(a)]); }
  const prof = [[z0, 0.4], [z0 + 12, 0], ...arc, [z1, R + 1], [z1 - P.plateT, R + 1], [z1 - P.plateT, P.lidWall], [z0, P.lidWall]];
  const rings = prof.map(([z, d]) => ccw(offsetPoly(out, d)).map(q => [q[0], q[1], z]));
  const shell = new Part('vicko_plast', 'cira_viko');
  loftRings(shell, rings, { closed: true });
  // čelní sklon: horní část prstenců (zaoblení + deska) se posune dolů, stěna se ořízne
  const bend = (part) => part.mapV((x, y, z) => {
    const sh = Math.max(0, P.zLidTop - zlTop(y));
    if (sh <= 0) return [x, y, z];
    return z >= z1 - R - 1e-6 ? [x, y, z - sh] : [x, y, Math.min(z, z1 - R - sh)];
  });
  bend(shell); g.add(shell);
  // horní deska: část A (rovná, s prolisy) a část B (čelní sklon)
  const pockets = pocketOutlines();
  const plateOut = offsetPoly(out, R + 1);
  g.add(extrude('cira_viko', 'vicko_deska', clipPolyY(plateOut, 140, true), [...pockets.map(p => p.top), labelRecess()], z1 - P.plateT, z1));
  const plateB = extrude('cira_viko', 'vicko_celo', clipPolyY(plateOut, 140, false), [], z1 - P.plateT, z1);
  bend(plateB); g.add(plateB);
  const zf = z1 - P.pocketDepth;
  for (const pk of pockets) {
    const w = loftPoly('cira_viko', 'prolis_' + pk.name, [{ poly: pk.top, z: z1 }, { poly: pk.bot, z: zf }], { capStart: null, capEnd: null });
    w.flip(); g.add(w);
    g.add(extrude('cira_viko', 'prolis_dno_' + pk.name, pk.bot, [], zf - 2.2, zf));
    const skip = pk.name === 'L' ? (p) => p[0] > -64 && p[0] < 64 && p[1] > -64 && p[1] < 7 : null;
    g.add(hexPattern('hex_' + pk.name, pk.bot, zf, 6.9, 0.9, skip));
  }
  { const lr = labelRecess(); const w = loftPoly('cira_viko', 'stitek_stena', [{ poly: lr, z: z1 }, { poly: offsetPoly(lr, 2), z: z1 - 2.5 }], { capStart: null, capEnd: null }); w.flip(); g.add(w); g.add(extrude('cira_viko', 'stitek_dno', offsetPoly(lr, 2), [], z1 - 4.5, z1 - 2.5)); }
  g.add(...skirtTiles());
  g.add(...latchLid());
  g.add(...hingeLid());
  g.add(eyelet());
  return g;
}
const labelRecess = () => roundPoly(rectPoly(-28.5, 28.5, 128.7, 142.6), 3, 3);
function pocketOutlines() {
  const defs = [
    ['FL', -99.8, -4.8, 28.5, 124], ['FR', 4.8, 99.8, 28.5, 124],
    ['L', -99.8, 99.8, -76, 15],
    ['BL', -99.8, -4.8, -178, -90], ['BR', 4.8, 99.8, -178, -90],
  ];
  return defs.map(([name, x0, x1, y0, y1]) => ({ name, top: octa(x0, x1, y0, y1, 8, 2.5), bot: octa(x0 + P.pocketInset, x1 - P.pocketInset, y0 + P.pocketInset, y1 - P.pocketInset, 4, 1.5) }));
}
function skirtTiles() {
  const out = [];
  const z0 = Zc(P.zSeam + 1.5), z1 = Zc(P.zLidTop - 4.5);
  for (const s of [1, -1]) for (let j = -8; j <= 6; j++) {
    const yc = 16 + 19.35 * j + 9.7;
    if (yc > 126 || yc < -150) continue;
    out.push(box('cira_viko', 'zebro_viko_' + (s > 0 ? 'P' : 'L') + j, s > 0 ? P.lidHW - 0.2 : -P.lidHW - 1.1, s > 0 ? P.lidHW + 1.1 : -P.lidHW + 0.2, yc - 8.2, yc + 8.2, z0, z1));
  }
  return out;
}
function hingeLid() {
  const out = [];
  const zc = Zc(P.hingeZ), y = P.hingeY, r = P.hingeR;
  for (const xc of [-72, -24, 24, 72]) {
    const x0 = xc - 11.6, x1 = xc + 11.6;
    out.push(cylX('cira_viko', 'viko_cep_' + xc, y, zc, r, x0, x1, 18));
    out.push(box('cira_viko', 'viko_noha_' + xc, x0, x1, y, P.lidYb + 1, zc - r, zc + r));
  }
  return out;
}
function eyelet() {
  const poly = roundPoly([[37.5, 151], [53, 151], [53, 166.5], [37.5, 166.5]], [1, 1, 6.5, 6.5], 4);
  const hole = circlePoly(43.3, 160.5, 3.6, 16);
  return extrude('cira_viko', 'ouško', poly, [hole], Zc(41), Zc(P.zCap + 0.5));
}

// ======================= NÁDOBY =======================
function container(name, cx, cy, w, d, z0, h, opt) {
  const out = [];
  const p = new Part(name, 'cervena');
  const P0 = octa(cx - w / 2, cx + w / 2, cy - d / 2, cy + d / 2, 7.5, 2.6);
  const z1 = z0 + h;
  const prof = [[z0, 3.4], [z1 - 4.5, 1.2], [z1 - 3.0, 0], [z1, 0], [z1, 1.9], [z1 - 3, 2.3], [z0 + 2.0, 4.8], [z0 + 2.0, 6.0]];
  const rings = prof.map(([z, dd]) => ccw(offsetPoly(P0, dd)).map(q => [q[0], q[1], z]));
  loftRings(p, rings, { capStart: 'down', capEnd: 'up' });
  out.push(p);
  const inX0 = cx - w / 2 + 4.6, inX1 = cx + w / 2 - 4.6, inY0 = cy - d / 2 + 4.6, inY1 = cy + d / 2 - 4.6;
  if (opt.kind === 'mala') {
    const yd = cy + opt.dOff;                                  // dělicí stěna rovnoběžná s X
    const hz = z0 + 2 + (h - 2) * 0.56;
    out.push(box('cervena', name + '_delic', inX0 + 0.5, inX1 - 0.5, yd - 0.85, yd + 0.85, z0 + 2, hz));
    out.push(box('cervena', name + '_delic_lem', inX0 + 0.5, inX1 - 0.5, yd - 1.7, yd + 1.7, hz - 0.5, hz));
    out.push(box('cervena', name + '_delic_ucho_L', inX0 - 0.8, inX0 + 3.2, yd - 2.3, yd + 2.3, z0 + 2, hz + 2));
    out.push(box('cervena', name + '_delic_ucho_P', inX1 - 3.2, inX1 + 0.8, yd - 2.3, yd + 2.3, z0 + 2, hz + 2));
    out.push(box('cervena', name + '_zebro', cx - 3.2, cx + 3.2, inY0 - 0.6, inY0 + 1.6, z1 - 15, z1 - 1.2));    // zámek v zadní stěně
  } else {
    const hz = z0 + 2 + (h - 2) * 0.88;
    for (const xd of [-33.7, 33.7]) {
      out.push(box('cervena', name + '_delic', xd - 1.3, xd + 1.3, inY0 + 0.5, inY1 - 0.5, z0 + 2, hz));
      out.push(box('cervena', name + '_delic_ucho', xd - 2.4, xd + 2.4, inY0 - 0.8, inY0 + 3.4, z0 + 2, hz + 1.5));
      out.push(box('cervena', name + '_delic_ucho2', xd - 2.4, xd + 2.4, inY1 - 3.4, inY1 + 0.8, z0 + 2, hz + 1.5));
    }
  }
  return out;
}
function buildContainers() {
  const parts = [];
  const rowY = [77.25, -24.5, -126.25];
  const z0 = Zc(P.contZ0), h = P.contH, s = 100.8;
  parts.push(...container('nadoba_FL', -50.9, rowY[0], s, s, z0, h, { kind: 'mala', dOff: -2.5 }));
  parts.push(...container('nadoba_FR', 50.9, rowY[0], s, s, z0, h, { kind: 'mala', dOff: -2.5 }));
  parts.push(...container('nadoba_velka', 0, rowY[1], 202.4, s, z0, h, { kind: 'velka' }));
  parts.push(...container('nadoba_BL', -50.9, rowY[2], s, s, z0, h, { kind: 'mala', dOff: -2.5 }));
  parts.push(...container('nadoba_BR', 50.9, rowY[2], s, s, z0, h, { kind: 'mala', dOff: -2.5 }));
  return parts;
}

// šestiúhelníkový vzor (ploché šestiúhelníky, R = 6.9 mm) na dnu prolisu: tenké žebírko šířky 0.9 a výšky 0.5
function hexPattern(name, poly, zTop, R = 6.9, w = 0.9, skip = null) {
  const inner = offsetPoly(poly, 1.6);
  const part = new Part(name, 'cira_hex');
  const seen = new Set();
  const key = (p) => Math.round(p[0] * 20) + ',' + Math.round(p[1] * 20);
  const hx = 1.5 * R, hy = Math.sqrt(3) * R;
  for (let i = -30; i <= 30; i++) for (let j = -30; j <= 30; j++) {
    const cx = i * hx, cy = j * hy + (Math.abs(i) % 2 ? hy / 2 : 0);
    if (cx < -110 || cx > 110 || cy < -190 || cy > 130) continue;
    const V = Array.from({ length: 6 }, (_, k) => { const a = k * Math.PI / 3; return [cx + R * Math.cos(a), cy + R * Math.sin(a)]; });
    for (let k = 0; k < 6; k++) {
      const A = V[k], B = V[(k + 1) % 6]; const ek = [key(A), key(B)].sort().join('|');
      if (seen.has(ek)) continue; seen.add(ek);
      if (!pointInPoly(A, inner) || !pointInPoly(B, inner)) continue;
      if (skip && (skip(A) || skip(B))) continue;
      part.append(seg2('cira_hex', 'h', A, B, w, zTop, zTop + 0.5));
    }
  }
  return part;
}

export function build() {
  const root = new Group('organizer');
  const base = buildBase(); root.addGroup(base);
  for (const c of buildContainers()) base.add(c);
  root.addGroup(buildLid());
  for (const b of latchBails()) root.addGroup(b);
  return root;
}

if (process.argv[1] && process.argv[1].endsWith('organizer_4932471065.mjs')) {
  const r = writeGLB(build(), new URL('./modely/' + SKU + '.glb', import.meta.url).pathname, { sku: SKU });
  console.log(r);
}
