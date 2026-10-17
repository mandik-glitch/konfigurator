// Milwaukee PACKOUT Kompaktní box na nářadí 4932471723 – OPRAVENÁ verze (vlastní generátor, ne úprava Johnova modelu).
// X = šířka 249, Y = délka 411 (čelo se sponou do +Y), Z = výška 330; počátek = střed obálky. Obálka = katalog (kufriky_john/kufriky.csv), držadlo ve výchozí zavřené poloze.
// Moduly: p4932471723_telo.mjs, _vicko.mjs, _spona.mjs, _drzadlo.mjs; stavební funkce p4932471723_zaklad.mjs.
import { Group } from './p4932471723_zaklad.mjs';
import { telo } from './p4932471723_telo.mjs';
import { vicko } from './p4932471723_vicko.mjs';
import { spona } from './p4932471723_spona.mjs';
import { drzadlo } from './p4932471723_drzadlo.mjs';
export const SKU = '4932471723';
export const OBALKA = { x: 249, y: 411, z: 330 };
export const CELO = 'Y';
export const NAZEV = 'Milwaukee PACKOUT Kompaktní box na nářadí (4932471723)';
export const VARIANTY = [{ pripona: '_drzadlo_nahore', volby: { nahore: true } }];   // jen pro srovnání s fotkou (držadlo vztyčené)
export function build(volby = {}) {
  const root = new Group(SKU);
  root.addGroup(telo());
  root.addGroup(vicko());
  root.addGroup(spona());
  root.addGroup(drzadlo(!!volby.nahore));
  return root;
}
