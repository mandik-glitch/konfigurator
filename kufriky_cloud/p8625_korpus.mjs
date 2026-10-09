// Korpus hlubokého organizéru 4932478625: černá vana s lemem na švíku víka, rohové nárazníky, hřbet s pantem, patky spodku.
// Konstrukce převzata z modelu 4932464082 (p4082_korpus.mjs), rozměry a výšky podle fotografií c13/c01/c04/c02/c03 tohoto SKU.
// Co fotografie neukazují (spodek, zadní strana, levý konec) je převzato z konstrukce standardního typu a v poznámkách označeno NEOVĚŘENO.
import { Group, Part, rrPoly, roundPoly, ccw, loftSolid, ext, slab, rrShell, tray, ringSolid, bx, zc, cylinder, ZC } from './p8625_zaklad.mjs';

export const K = {
  zBot: 26.5, zBotC: 30.5,        // spodní hrana stěn (boky) a uprostřed pod držadlem (c13, silueta)
  zRim: 157.5, yT: 247,         // horní okraj vany = švík víka; poloviční šířka vany
  xF: 183.5, xR: -172,            // čelní a zadní rovina vany
  cav: { x0: -162.2, x1: 151.3, y: 235.2, floor: 30 },        // dutina vany (viz měření na c03) a horní plocha dna
  yP: 253.5, xP: 193,             // vnější obálka nárazníků
};

// ---------- nárazníky (rohové sloupky) ----------
// čelní: patka (26,5–46) + sloupek (46–150) + čepice (150–176) se zaobleným temenem; zadní podobně (neověřeno, c13 ukazuje jen horní část)
function narazniky(g) {
  const items = [];
  items.push(slab('cerna_mat', 'naraznik_patka', { x0: 152, x1: K.xP, y0: 216, y1: K.yP, z0: K.zBot, z1: 46, rs: [12, 4, 4, 3], seg: 4, reT: 1.5, reB: 3.5, fs: 3 }));
  items.push(slab('cerna_mat', 'naraznik_sloupek', { x0: 153, x1: 191.6, y0: 219, y1: 251.8, z0: 45, z1: 150, rs: [11, 3, 3, 3], seg: 4, reT: 0.5, reB: 0.5, fs: 1 }));
  items.push(slab('cerna_mat', 'naraznik_cepice', { x0: 152.5, x1: K.xP, y0: 214, y1: K.yP, z0: 148.5, z1: 176.2, rs: [15, 5, 5, 4], seg: 4, reT: 8, reB: 1.5, fs: 5, kT: 1.7 }));
  // zadní nárazník: nižší zešikmené temeno (c13: zadní pravý sloupek), plná výška
  items.push(slab('cerna_mat', 'naraznik_patka_z', { x0: -K.xP, x1: -163, y0: 216, y1: K.yP, z0: K.zBot, z1: 46, rs: [3, 12, 3, 4], seg: 4, reT: 1.5, reB: 3.5, fs: 3 }));
  items.push(slab('cerna_mat', 'naraznik_sloupek_z', { x0: -191.6, x1: -163.5, y0: 219, y1: 251.8, z0: 45, z1: 148, rs: [3, 11, 3, 3], seg: 4, reT: 0.5, reB: 0.5, fs: 1 }));
  items.push(slab('cerna_mat', 'naraznik_cepice_z', { x0: -K.xP, x1: -163, y0: 214, y1: K.yP, z0: 146.5, z1: 174, rs: [5, 15, 4, 5], seg: 4, reT: 8, reB: 1.5, fs: 5, kT: 1.7 }));
  for (const it of items) { g.add(it); const m = it.clone(it.name + '_m'); m.mirror('y', 0); g.add(m); }
}

// rámeček z pásků (okno) kolem obdélníku na ploše s normálou X nebo Y
function ramecek(L, name, { n, p, a0, a1, z0, z1, w = 1.4, h = 0.6 }) {
  const lo = p - 0.3, hi = p + h;
  const mk = (u0, u1, zz0, zz1) => n === 'x' ? bx('cerna', name, lo, hi, u0, u1, zz0, zz1) : bx('cerna', name, u0, u1, lo, hi, zz0, zz1);
  L.push(mk(a0, a1, z0, z0 + w), mk(a0, a1, z1 - w, z1), mk(a0, a0 + w, z0 + w, z1 - w), mk(a1 - w, a1, z0 + w, z1 - w));
}
function okna(g) {
  const L = [];
  // čelo čelního nárazníku (y>0): horní okna na čepici, dolní okna v patce, panel uprostřed
  ramecek(L, 'okno_cF_h', { n: 'x', p: 192.6, a0: 224, a1: 237.5, z0: 152, z1: 163 });
  ramecek(L, 'okno_cF_d', { n: 'x', p: 192.4, a0: 227, a1: 238, z0: 29, z1: 40 });
  ramecek(L, 'panel_cF', { n: 'x', p: 191.2, a0: 225.5, a1: 245.5, z0: 52, z1: 142, w: 1.0, h: 0.5 });
  // koncová (boční) plocha: okna a panel
  ramecek(L, 'okno_kF_h', { n: 'y', p: 252.2, a0: 164, a1: 176, z0: 152, z1: 163 });
  ramecek(L, 'okno_kF_d', { n: 'y', p: 252.2, a0: 165, a1: 176, z0: 29, z1: 40 });
  ramecek(L, 'panel_kF', { n: 'y', p: 251.0, a0: 158, a1: 186, z0: 52, z1: 142, w: 1.0, h: 0.5 });
  for (const it of L) { g.add(it); const m = it.clone(it.name + '_m'); m.mirror('y', 0); g.add(m); }
}

// ---------- vana ----------
function vana(g) {
  const C = K.cav;
  // tenkostěnná vana (dno, stěny 4 mm), čelní stěnu tvoří reliéf čela (p8625_celo.mjs)
  g.add(tray('cerna_mat', 'vana', { x0: K.xR, x1: C.x1 + 6, y0: -K.yT, y1: K.yT, z0: K.zBot, z1: K.zRim - 0.6, rs: [3, 12, 12, 3], seg: 4, wall: 4, floor: C.floor - K.zBot, re: 3, fs: 3 }));
  // silné boční a zadní stěny kolem dutiny (dutina 313 × 470 u okraje, c03/c04)
  for (const sy of [-1, 1]) g.add(bx('cerna_mat', 'stena_boční', K.xR + 3, C.x1 + 4, sy > 0 ? C.y : -K.yT + 3.5, sy > 0 ? K.yT - 3.5 : -C.y, C.floor - 2, K.zRim - 6));
  g.add(bx('cerna_mat', 'stena_zadni', K.xR + 3, C.x0, -K.yT + 3.5, K.yT - 3.5, C.floor - 2, K.zRim - 6));
  // zesílení dna uprostřed (|y| < 98) – spodní hrana o 4 mm výš
  // (dno vany je z K.zBot; deska pod držadlem je vynechána reliéfem čela)
  // horní lem (rám) na švíku víka: vnější obrys vany, otvor = dutina
  g.add(ringSolid('cerna_mat', 'vana_ram', rrPoly(K.xR, K.xF, -K.yT, K.yT, [3, 12, 12, 3], 4), rrPoly(C.x0, C.x1, -C.y, C.y, [6.5, 6.5, 6.5, 6.5], 4), K.zRim - 6, K.zRim, { outerWall: true }));
  // svislá žebra (pilastry) na koncové stěně u zadní strany (c13: pravý konec)
  for (const s of [-1, 1]) for (const x of [-150, -125, 40, 90]) g.add(bx('cerna_mat', 'pilastr', x - 5, x + 5, s > 0 ? K.yT : -K.yT - 1.2, s > 0 ? K.yT + 1.2 : -K.yT, 60, 150));
  // pásek vodorovných drážek pod okrajem (větrací štěrbiny pod víkem, c13)
  for (const s of [-1, 1]) for (let k = 0; k < 14; k++) { const x = 100 - k * 12; g.add(bx('cerna_mat', 'zebro_pasu', x - 0.6, x + 0.6, s > 0 ? K.yT : -K.yT - 0.9, s > 0 ? K.yT + 0.9 : -K.yT, 138, 149)); }
}

// ---------- hřbet: černá oka pantu a ocelový čep (poloha jako u standardního typu, c04: čiré články středy |y| = 54,4; 104,6; 154,4; 203,8) ----------
export const PIVOT = [-178.5, 0, 161];
function hrbet(g) {
  const lug = (y0, y1) => g.add(slab('cerna_mat', 'pant_oko', { x0: -187, x1: -167, y0, y1, z0: 152, z1: 168.5, rs: 2.5, seg: 2, reT: 2, reB: 0.8, fs: 2 }));
  lug(-40, 40);
  for (const yc of [79.4, 129.5, 179.1]) for (const s of [-1, 1]) lug(s * yc - 11.2, s * yc + 11.2);
  g.add(cylinder('ocel', 'pant_cep', 1.6, 0, 480, 12, [0, 0]).rot('x', 90).move(PIVOT[0], 240, zc(PIVOT[2])));
}

// ---------- patky spodku (NEOVĚŘENO: převzato ze standardního typu; fotografie spodku tohoto SKU nemáme) ----------
const PADS = [
  { x0: 57, x1: 98.5, ys: [[41.7, 116.7], [140, 223]] },
  { x0: -49, x1: -8, ys: [[52, 105], [151, 222]] },
  { x0: -150, x1: -112, ys: [[33, 120], [142, 225]] },
];
function patky(g) {
  for (const row of PADS) for (const [a, b] of row.ys) for (const s of [-1, 1]) {
    const y0 = s > 0 ? a : -b, y1 = s > 0 ? b : -a;
    const lay = (dx, dy, z) => ({ poly: ccw(rrPoly(row.x0 + dx, row.x1 - dx, y0 + dy, y1 - dy, 4, 3)), z });
    g.add(loftSolid('cerna_mat', 'patka', [lay(4.6, 1.9, 0), lay(3.6, 1.4, 1.5), lay(0.6, 0.3, K.zBot - 6), lay(0, 0, K.zBot + 1)], { crease: 40 }));
  }
}

export function korpus() {
  const g = new Group('korpus');
  vana(g); narazniky(g); okna(g); hrbet(g); patky(g);
  return g;
}
