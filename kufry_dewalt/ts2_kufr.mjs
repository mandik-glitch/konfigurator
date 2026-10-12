// Sdílený modul rodiny DeWalt ToughSystem 2.0 (DS300 / DS400): jedna parametrická skořepina, výška H = parametr.
// Souřadnice: X = hloubka 371 (čelo s logem a západkami do +X), Y = délka 554, Z = výška; počátek = střed obálky 554 × 371 × H.
import { Group, nastavVysku } from './ts2_zaklad.mjs';
import { par } from './ts2_par.mjs';
import { korpus } from './ts2_korpus.mjs';
import { vicko, madlo } from './ts2_vicko.mjs';

export function postav(H, nazev) {
  nastavVysku(H);
  const p = par(H);
  const root = new Group(nazev);
  root.addGroup(korpus(p));
  root.addGroup(vicko(p));
  root.addGroup(madlo(p));
  return root;
}
