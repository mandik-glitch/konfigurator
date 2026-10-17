// Milwaukee PACKOUT Pojízdný box se zásuvkou 4932498651 (katalog L×Š×V 610 × 480 × 550): vlastní generátor podle fotografií výrobce.
// Souřadnice: X = hloubka 480 (čelo se zásuvkou +X), Y = šířka 610 (tělo ≈ 514 + kola do ±305), Z = výška 550 (spodek kol – vrch víka); počátek = střed obálky.
// Výchozí poloha = ZAVŘENÁ: zásuvka zasunutá, teleskopické madlo zasunuté (katalogová obálka 610 × 480 × 550 platí pro ni, ne pro vysunuté madlo ≈ +600 mm).
import { Group } from './p4932478162_zaklad.mjs';
import { skrin, viko, rohy, rukojetBok } from './p4932498651_telo.mjs';
import { zasuvka } from './p4932498651_zasuvka.mjs';
import { kola } from './p4932498651_kola.mjs';
import { madlo } from './p4932498651_madlo.mjs';

export const SKU = '4932498651';
export const OBALKA = { x: 480, y: 610, z: 550 };
export const CELO = 'X';
export const NAZEV = 'Milwaukee PACKOUT Pojízdný box se zásuvkou (4932498651)';

export function build() {
  const root = new Group(SKU);
  const { g: telo, POC } = skrin(); root.addGroup(telo);
  root.addGroup(viko()); root.addGroup(rohy());
  root.addGroup(rukojetBok(1, POC)); root.addGroup(rukojetBok(-1, POC));
  root.addGroup(zasuvka()); root.addGroup(kola()); root.addGroup(madlo());
  return root;
}
