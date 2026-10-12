// Korpus (spodní díl) kufru Hilti řady SF – ZAVŘENÁ verze, vnější pohled; vnitřek = hladká prázdná dutina (stěna 3 mm), bez vložky.
// Obsah: hladká vana s obrysem z fotografie L137214 (včetně "pedestalu" a výřezu držadla), spodní polovina černého držadla (rám s oknem), dvě černé západky.
// Co se na fotografii nedá změřit (hloubka dělení víko/korpus, zadní strana, spodek, pant, nožky) je v zdroje/<číslo>_poznamky.md vedeno jako odhad/neověřeno.
import { Group, Part, korpusSkorapka, deska } from './p2284143_zaklad.mjs';

// černý rám držadla v px (vnější okraj = okraj výřezu v obrysu; okno = průhledný lichoběžník podle fotografie)
export const RAM_HORNI = [[393, 0], [806, 0], [806, 66], [393, 66]];
export const RAM_SPODNI = [[393, 66], [442.5, 66], [508.5, 123], [690.5, 123], [756.5, 66], [806, 66], [733, 143], [466, 143]];
export const ZAPADKA_L = [[157, 27], [170, 15], [280, 15], [292, 27], [292, 79], [157, 79]];
export const px2mm = (K, poly) => poly.map(([px, py]) => [K.pY(px), K.pZ(py)]);

export function ramDrzadla(K, name, xb, xf) {
  const p = new Part(name, 'cerna'); p.crease = 30;
  for (const poly of [RAM_HORNI, RAM_SPODNI]) deska(p, K, px2mm(K, poly), xb, (y, z) => xf(z), [K.z22, K.zTI, K.pZ(128)]);
  return p;
}
export function zapadky(K) {
  const out = [];
  for (const s of [-1, 1]) {
    const poly = px2mm(K, ZAPADKA_L).map(([y, z]) => [s < 0 ? y : -y, z]);
    const p = new Part(s < 0 ? 'zapadka_levá' : 'zapadka_pravá', 'cerna'); p.crease = 30;
    deska(p, K, poly, K.xs - 3, (y, z) => K.frontSurface(z) + 3, [K.z22, K.zTI, K.pZ(128)]);
    out.push(p);
  }
  return out;
}
export function korpus(K) {
  const g = new Group('korpus');
  g.add(korpusSkorapka(K));
  g.add(ramDrzadla(K, 'drzadlo_korpus', -K.D / 2 + 12, z => K.xb));   // spodní půlka držadla (vyplní výřez v korpusu)
  for (const z of zapadky(K)) g.add(z);
  return g;
}
