// Sestavení boxu se zásuvkami podle konfigurace čel (shora dolů): [{z0, z1}, …]. Společné pro 4932472129 / 4932472130 / 4932493189 / 4932493190.
import { Group, G } from './p4932472129_zaklad.mjs';
import { vicko } from './p4932472129_vicko.mjs';
import { telo, madla } from './p4932472129_telo.mjs';
import { zasuvka, kolejnice, overZasuvky } from './p4932472129_zasuvky.mjs';
import { trmen } from './p4932472129_trmen.mjs';

// čela rovnoměrně: n stejných čel s mezerou G.MEZERA v pásmu ZASUVKY_Z0 … ZASUVKY_Z1
export function stejnaCela(n) {
  const h = (G.ZASUVKY_Z1 - G.ZASUVKY_Z0 - (n - 1) * G.MEZERA) / n, out = [];
  for (let i = 0; i < n; i++) { const z1 = G.ZASUVKY_Z1 - i * (h + G.MEZERA); out.push({ z1, z0: z1 - h }); }
  return out;
}

export function sestav(faces, { jmeno = 'box_se_zasuvkami', stredCerveny = false } = {}) {
  const root = new Group(jmeno);
  root.addGroup(telo(faces, { stredCerveny }));
  root.addGroup(vicko());
  root.addGroup(madla());
  faces.forEach((f, i) => { const z = zasuvka(i, f); root.addGroup(z); for (const k of kolejnice(i, f)) root.addGroup(k); });
  root.addGroup(trmen());
  return root;
}
export { overZasuvky };
