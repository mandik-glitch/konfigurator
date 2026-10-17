// Milwaukee PACKOUT Skříň s předními dvířky 4932480623 – OPRAVENÁ verze (vlastní generátor). X = hloubka 381 (čelo s dvířky do +X), Y = šířka 508, Z = výška 381; počátek = střed obálky.
// Dvířka = pohyblivý uzel `dvirka` (extras.osa = [0,-1,0], pivot na horní hraně); pose: dvirka=90 → odklopená nahoru do vodorovné polohy.
import { Group } from './p4932471723_zaklad.mjs';
import { telo } from './p4932480623_telo.mjs';
import { vicko } from './p4932480623_vicko.mjs';
import { dvirka } from './p4932480623_dvirka.mjs';
export const SKU = '4932480623';
export const OBALKA = { x: 381, y: 508, z: 381 };
export const CELO = 'X';
export const NAZEV = 'Milwaukee PACKOUT Skříň s předními dvířky (4932480623)';
export function build() {
  const root = new Group(SKU);
  root.addGroup(telo());
  root.addGroup(vicko());
  root.addGroup(dvirka());
  return root;
}
