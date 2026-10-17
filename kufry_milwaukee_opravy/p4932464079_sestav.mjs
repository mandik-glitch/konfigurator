// Sestavení boxu PACKOUT (velký / nižší) z modulů – parametr V (výška a polohy hardwaru) určuje variantu.
import { Group, nastavVysku, shiftY } from './p4932464079_zaklad.mjs';
import { vana } from './p4932464079_korpus.mjs';
import { rohy } from './p4932464079_rohy.mjs';
import { vicko } from './p4932464079_vicko.mjs';
import { rukojet, zapadka, celoDetaily } from './p4932464079_celo.mjs';
import { horniDrzadlo } from './p4932464079_drzadlo.mjs';

export function sestavBox(V0, opt = {}) {
  const V = Object.assign({}, V0, JSON.parse(process.env.KUF_OVR || '{}'));   // ladění parametrů (jen pro nástroje)
  nastavVysku(V.H);
  const root = new Group(V.sku);
  const k = vana(V);
  for (const p of celoDetaily(V)) k.add(p.move(0, V.yFront || 0, 0));
  root.addGroup(k);
  if (V.rohy !== false) root.addGroup(rohy(V));
  const vk = vicko(V);
  if (V.horniDrzadlo) vk.addGroup(horniDrzadlo(V, !!opt.drzadloNahore));
  if (V.doplnky) for (const f of V.doplnky) f(V, root, vk, k);
  root.addGroup(vk);
  root.addGroup(shiftY(rukojet(V), V.yFront || 0));
  root.addGroup(shiftY(zapadka(V, -1), V.yFront || 0)); root.addGroup(shiftY(zapadka(V, 1), V.yFront || 0));
  return root;
}
