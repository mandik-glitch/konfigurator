// Pojízdný čistič s ohřevem vody (nerezový plechový kryt, černý rám, kola) – vlastní parametrický generátor podle 4 fotografií.
// Souřadnice: X = šířka, Y = délka, Z = výška (nahoru); počátek ve středu obálky 650 × 650 × 780 mm. ČELO = strana s rukojetí = +Y;
// přední (vyšší) konec krytu s větracími drážkami a velkými koly = −Y. Pohyblivé uzly: kolo_E/W (osa X), kolecko_E/W (osa Z) + jejich kolo (osa X).
import { Group, shiftTree } from './c_zaklad.mjs';
import { kryt } from './c_kryt.mjs';
import { ramBoky, spodniRam } from './c_ram.mjs';
import { zadni } from './c_zadni.mjs';
import { kolo, kolecko } from './c_kola.mjs';

export const SKU = 'cistic';
export const OBALKA = { x: 650, y: 650, z: 780 };
export const CELO = '+Y';
export const NAZEV = 'Pojízdný čistič s ohřevem vody';

export function build() {
  const root = new Group('stroj_cistic');
  root.addGroup(kryt()); root.addGroup(ramBoky()); root.addGroup(spodniRam()); root.addGroup(zadni());
  for (const s of [1, -1]) { root.addGroup(kolo(s)); root.addGroup(kolecko(s)); }
  shiftTree(root, 0, 0, -390);
  return root;
}
