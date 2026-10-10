// Válečková dráha Rollers.PL-601F_WS: tělo z pozinkovaného plechu (U-profil s ohnutými háčky a 2 prolisy ve dně), plastové válečky Ø16 × 46, rozteč 18,5 mm.
// Kóty z výkresu výrobce (uživatel, 2026-10-10): šířka 60, výška těla 23, osa válečku ve výšce 19, válec vyčnívá 8 mm nad stěnu (celkem 27), délka válečku 46, Ø16, rozteč 18.5P.
// Souřadnice: X = šířka (60), Y = délka (podél dráhy, vystředěná), Z = výška (spodek těla = 0).
// node generuj.mjs [--delka 1000] [--vystup soubor.glb]
import { Group, Part, prism, lathe, cylinder } from '../../kufriky_cloud/jadro/mesh.js';
import { writeGLB, readGLB } from '../../kufriky_cloud/jadro/glb.js';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
export const P = { sirka: 60, vyskaTela: 23, osaZ: 19, valecR: 8, valecDelka: 46, rozteca: 18.5, t: 1.0 };   // t = tloušťka plechu (odhad, na výkrese není)

// střednice plechu v rovině (x, z) – jedna otevřená lomená čára zleva doprava
function strednice() {
  const h = P.t / 2, w = P.sirka / 2 - h - 0.17;                  // vnější šířka = 60
  const L = [[-22.2, 21.0], [-22.2, 22.5], [-26.0, 22.5], [-27.2, 8], [-w, h]];     // háček (zahnutý dovnitř) → stěna (mírně šikmá) → roh dna
  const dno = [[-15, h], [-13.2, 3.2], [-9.2, 3.2], [-7.4, h], [7.4, h], [9.2, 3.2], [13.2, 3.2], [15, h]];                // dno se dvěma prolisy
  const R = [[w, h], [27.2, 8], [26.0, 22.5], [22.2, 22.5], [22.2, 21.0]].map(p => p);
  return [...L, ...dno, ...R];
}
// plech = střednice ± t/2 (miter), vrací polygon (uzavřený obrys) pro prism()
function obrysPlechu(pts, t) {
  const n = pts.length, left = [], right = [];
  const nor = (a, b) => { const dx = b[0] - a[0], dz = b[1] - a[1], l = Math.hypot(dx, dz); return [-dz / l, dx / l]; };
  for (let i = 0; i < n; i++) {
    const n1 = i > 0 ? nor(pts[i - 1], pts[i]) : nor(pts[0], pts[1]), n2 = i < n - 1 ? nor(pts[i], pts[i + 1]) : nor(pts[n - 2], pts[n - 1]);
    let mx = n1[0] + n2[0], mz = n1[1] + n2[1]; const ml = Math.hypot(mx, mz); mx /= ml; mz /= ml;
    const k = (t / 2) / Math.max(0.35, mx * n1[0] + mz * n1[1]);              // miter (omezeno)
    left.push([pts[i][0] + mx * k, pts[i][1] + mz * k]); right.push([pts[i][0] - mx * k, pts[i][1] - mz * k]);
  }
  return [...left, ...right.reverse()];
}
export function build(delka = 4000) {
  const root = new Group('PL-601F_WS', { extras: {} });
  const telo = new Group('telo');
  const poly = obrysPlechu(strednice(), P.t);
  const body = prism('pozink', 'telo_pozink', poly, -delka / 2, delka / 2);      // polygon (x, z) vytlačený podél Z, pak otočit osu do Y
  body.rot('x', 90); body.crease = 40; telo.add(body);
  root.addGroup(telo);
  const valecky = new Group('valecky');
  const N = Math.floor(delka / P.rozteca), y0 = -(N - 1) * P.rozteca / 2;
  const R = P.valecR, Lh = P.valecDelka / 2;
  const prof = [[0, -Lh], [R - 1.2, -Lh], [R, -Lh + 1.2], [R, -2.5], [R - 0.35, -2], [R - 0.35, 2], [R, 2.5], [R, Lh - 1.2], [R - 1.2, Lh], [0, Lh]];      // chamfery na koncích + mělká drážka uprostřed
  for (let i = 0; i < N; i++) {
    const v = lathe('plast_bily', 'valecek_' + (i + 1), prof, 28); v.rot('y', 90).move(0, y0 + i * P.rozteca, P.osaZ); valecky.add(v);
    const osa = cylinder('pozink', 'osa_' + (i + 1), 1.6, -Lh - 1.4, Lh + 1.4, 12); osa.rot('y', 90).move(0, y0 + i * P.rozteca, P.osaZ); valecky.add(osa);
  }
  root.addGroup(valecky);
  root.__N = N;
  return root;
}
if (process.argv[1] && process.argv[1].endsWith('generuj.mjs')) {
  const delka = +opt('delka', 4000), out = opt('vystup', path.join(HERE, 'PL-601F_WS_' + delka + '.glb'));
  const g = build(delka);
  const r = writeGLB(g, out, { nazev: 'Válečková dráha PL-601F_WS (délka ' + delka + ' mm)', kod: 'Rollers.PL-601F_WS', jednotky: 'mm', osy: 'X=sirka, Y=delka (vystredena), Z=vyska (spodek tela 0)', material: 'telo pozinkovany plech, valecky plast', zdroj: 'vyrobni vykres uzivatele (kóty), tloustka plechu 1.0 mm odhad', cena_prodejni_bez_dph_CZK_za_kus: 1290, cena_poznamka: 'prodejni cena za 1 ks (draha delky ' + delka + ' mm) bez DPH, zadal uzivatel 2026-10-10', start: { target: [0, -delka / 2 + 120, 12], dist: 330, az: 35, el: 28 } });
  const gl = readGLB(out); const b = [1e9, 1e9, 1e9, -1e9, -1e9, -1e9]; let telo = null; const rol = [];
  for (const p of gl.parts) { const q = [1e9, 1e9, 1e9, -1e9, -1e9, -1e9]; for (let i = 0; i < p.pos.length; i += 3) for (let k = 0; k < 3; k++) { q[k] = Math.min(q[k], p.pos[i + k]); q[k + 3] = Math.max(q[k + 3], p.pos[i + k]); } for (let k = 0; k < 3; k++) { b[k] = Math.min(b[k], q[k]); b[k + 3] = Math.max(b[k + 3], q[k + 3]); } if (p.name === 'telo_pozink') telo = q; if (/^valecek_/.test(p.name)) rol.push(q); }
  const f = v => v.toFixed(2);
  console.log(`GLB ${out}: ${r.parts} dílů, ${r.triangles} trojúhelníků, ${(r.bytes / 1e6).toFixed(2)} MB`);
  console.log('KÓTA | výkres | naměřeno');
  console.log(`šířka těla | 60 | ${f(telo[3] - telo[0])}`);
  console.log(`výška těla (s háčky) | 23 | ${f(telo[5] - telo[2])}`);
  console.log(`celková výška (válec) | 27 | ${f(b[5] - b[2])}`);
  console.log(`výčnělek válečku nad stěnu (osa 19) | 8 | ${f(rol[0][5] - P.osaZ)}`);
  console.log(`Ø válečku | 16 | ${f(rol[0][5] - rol[0][2])}`);
  console.log(`délka válečku | 46 | ${f(rol[0][3] - rol[0][0])}`);
  console.log(`rozteč válečků | 18.5 | ${f(((rol[1][1] + rol[1][4]) - (rol[0][1] + rol[0][4])) / 2)}`);
  console.log(`počet válečků | – | ${g.__N}; délka dráhy ${delka} mm`);
}
