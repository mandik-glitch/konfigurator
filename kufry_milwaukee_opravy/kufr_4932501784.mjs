// Milwaukee PACKOUT XL Box, nová revize 4932501784 (katalog 394 × 554 × 422): společný základ s 4932478162 + zdvižitelné U-madlo (pohyblivý uzel).
// Souřadnice: X = hloubka 394 (čelo +X), Y = šířka 554, Z = výška 422; počátek = střed obálky. Výchozí poloha = madlo sklopené (v obálce).
import { Group } from './p4932478162_zaklad.mjs';
import { zakladXL } from './p4932478162_sestav.mjs';
import { madlo } from './p4932501784_madlo.mjs';

export const SKU = '4932501784';
export const OBALKA = { x: 394, y: 554, z: 422 };
export const CELO = 'X';
export const NAZEV = 'Milwaukee PACKOUT XL Box, revize s U-madlem (4932501784)';

export function build() {
  const root = new Group(SKU);
  zakladXL(root, { stitek: true });
  root.addGroup(madlo());
  return root;
}
