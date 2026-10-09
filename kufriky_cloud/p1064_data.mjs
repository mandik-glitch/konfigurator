// Společná data modelu 4932471064 (Slim Organiser): plánové rozměry měřené z přímého pohledu shora c04 (přepočet 2,114 px/mm podle
// délky 500 mm), výšky z' (od nejnižšího bodu) z rektifikací šikmých pohledů. Souřadnice: plán (xp, Y): xp = vzdálenost od zadního okraje nárazníků
// (0 … 380), Y podél délky (+Y = strana s logem PACKOUT při pohledu zpředu zprava); model X = xp - XO, Z = z' - 32.
import { rrPoly } from './p1064_zaklad.mjs';

export const XO = 207;                       // posun plán → model (bude upřesněn podle obálky)
export const X = xp => xp - XO;

export const H = {
  zBot: 4.5,        // spodní plocha vany (nárazníky/držadlo/západky sahají až na 0) – neověřeno (bez fotografie spodku)
  zSeam: 38,        // švík víko–vana
  zTop: 64,         // horní plocha víka
  zFloor: 8,        // podlaha vany (nádoby stojí na ní)
  zBin: 52,         // horní okraj nádob
  zBumper: 56,      // vrch nárazníku (c07: horní plocha nárazníku v polovině výšky víka)
};

// Plán víka (xp, Y)
export const LID = { xp0: 14, xp1: 372, y: 240, rc: 26 };
export const BASE = { xp0: 6, xp1: 362, y: 243.5, rc: 16 };       // čelní stěna vany je zapuštěna pod přesahem víka (c07 vs c10: viditelná černá část čela)
export const CAV = { xp0: 27, xp1: 332, y: 229, rc: 7 };                   // otvor vany (vnitřní prostor 305 × 457)

// Řady kapes v xp: [rear, front] obrysu; sloupce v Y (+Y strana; −Y zrcadlově)
export const ROWS = { F: [239, 322], M: [134.6, 221.7], B: [34.6, 119.2] };
export const COLS = { small: [[133.7, 219.7], [32.5, 118.5]], big: [29, 217] };
export const STRIP = { y: 21.5, xp0: 44.5, xp1: 312.7 };

// seznam nádob/kapes: obrys obdélníku (xp0,xp1,y0,y1) pro obě poloviny
export function seznam() {
  const out = [];
  for (const s of [1, -1]) {
    const yy = ([a, b]) => (s > 0 ? [a, b] : [-b, -a]);
    for (const r of ['F', 'B']) for (const c of COLS.small) { const [y0, y1] = yy(c); out.push({ xp0: ROWS[r][0], xp1: ROWS[r][1], y0, y1, velka: false, r, s }); }
    const [y0, y1] = yy(COLS.big); out.push({ xp0: ROWS.M[0], xp1: ROWS.M[1], y0, y1, velka: true, r: 'M', s });
  }
  return out;
}
