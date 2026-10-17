// Milwaukee PACKOUT Otevřená přepravka 4932471724 – OPRAVENÁ verze (vlastní generátor). X = šířka 389, Y = délka 475, Z = výška 251; počátek = střed obálky; čelo (+X) se sedlem spojky.
// Moduly: p4932471724_telo.mjs, p4932471724_celo.mjs; stavební funkce p4932471723_zaklad.mjs.
import { Group } from './p4932471723_zaklad.mjs';
import { telo } from './p4932471724_telo.mjs';
import { celo } from './p4932471724_celo.mjs';
export const SKU = '4932471724';
export const OBALKA = { x: 389, y: 475, z: 251 };
export const CELO = 'X';
export const NAZEV = 'Milwaukee PACKOUT Otevřená přepravka (4932471724)';
export function build() {
  const root = new Group(SKU);
  root.addGroup(telo());
  root.addGroup(celo());
  return root;
}
