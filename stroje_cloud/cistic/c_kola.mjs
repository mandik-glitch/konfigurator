// Kola: dvě velká kola vpředu (pryžový pneu s chevronovým běhounem, plechový disk, náboj) a dvě otočná kolečka vzadu.
// Pohyblivé díly jsou uzly s pivotem a extras.osa: kolo (osa X přes střed), kolečko (otočný čep, osa Z) + jeho kolo (osa X).
import { Part, Group, roundedBox, box, cylinder, cylX, latheOpen, lathe, K } from './c_zaklad.mjs';

// pneumatika: profil (r, h) kolem osy Z (po transformaci osa X), h > 0 = vnější strana kola
function pneu(R, tw) {
  const h = tw / 2, rb = R - 46, Rt = R - 3.2;            // těleso pneu končí 3,2 mm pod vrcholky lišt běhounu
  const prof = [[rb, -h + 3], [Rt - 18, -h], [Rt - 6, -h * 0.8], [Rt - 1.5, -h * 0.5], [Rt, -h * 0.25], [Rt, h * 0.25], [Rt - 1.5, h * 0.5], [Rt - 6, h * 0.8], [Rt - 18, h], [rb, h - 3]];
  return lathe('guma', 'pneu', prof, 36);
}
// chevronový běhoun: dvě řady šikmých lišt (V), n lišt po obvodu
function behoun(R, tw, n) {
  const p = new Part('behoun', 'guma'); p.crease = 50;
  const h = tw / 2;
  for (let k = 0; k < n; k++) {
    for (const s of [-1, 1]) {
      const l = roundedBox('guma', 'l', { x0: R - 3.8, x1: R - 0.4, y0: -6.5, y1: 6.5, z0: s * (h * 0.52) - h * 0.48, z1: s * (h * 0.52) + h * 0.48, rc: 2.5, re: 1.5, seg: 1, fs: 1 });
      l.rot('x', s * 32, [R - 2, 0, s * h * 0.52]).rot('z', (k + (s > 0 ? 0.5 : 0)) * 360 / n);
      p.append(l);
    }
  }
  return p;
}
// disk kola: plechový talíř s velkým středovým otvorem (vidět tmavý náboj)
function disk(Rr, tw) {
  const h = tw / 2;
  const prof = [[Rr, -h + 3], [Rr, h - 3], [Rr - 4, h - 0.6], [66, h - 3], [52, h - 10], [30, h - 12], [26, h - 8]];
  return latheOpen('ocel_tmava', 'disk', prof, 36);
}

export function kolo(sg) {
  const { R, tw, xw, yw } = K;
  const g = new Group(sg > 0 ? 'kolo_E' : 'kolo_W', { pivot: [sg * xw, yw, R], extras: { osa: [1, 0, 0] } });
  const parts = [pneu(R, tw), behoun(R, tw, 13), disk(R - 46 + 2, tw), cylinder('cerna', 'naboj', 25, -tw / 2 - 2, tw / 2 - 5, 20), cylinder('cerna_mat', 'naboj_dutina', 20, tw / 2 - 8, tw / 2 - 3, 18)];
  for (const p of parts) {
    p.rot('y', 90);                                         // osa Z → osa X (vnější strana h>0 → +X)
    if (sg < 0) p.mirror('x', 0);
    p.move(sg * xw, yw, R); g.add(p);
  }
  return g;
}

export function kolecko(sg) {
  const { xc, yc, Rc } = K;
  const stem = [sg * xc, yc + 20, 114];
  const root = new Group(sg > 0 ? 'kolecko_E' : 'kolecko_W', { pivot: stem, extras: { osa: [0, 0, 1] } });
  const x0 = sg * xc;
  root.add(box('cerna', 'kolecko_deska', x0 - 30, x0 + 30, yc - 12, yc + 52, 112, 116));
  root.add(cylinder('ocel', 'kolecko_cep', 9, 102, 112, 14, [x0, yc + 20]));
  // vidlice: dvě desky po stranách kola + příčka
  for (const s of [-1, 1]) root.add(box('cerna', 'vidlice', x0 + s * 20 - 2, x0 + s * 20 + 2, yc - 14, yc + 24, 56, 104));
  root.add(box('cerna', 'vidlice_pricka', x0 - 22, x0 + 22, yc + 14, yc + 24, 96, 104));
  const w = new Group(root.name + '_kolo', { pivot: [x0, yc, Rc], extras: { osa: [1, 0, 0] } });
  const t = lathe('guma', 'kolecko_pneu', [[Rc - 18, -13], [Rc - 4, -14], [Rc - 1, -9], [Rc, -4], [Rc, 4], [Rc - 1, 9], [Rc - 4, 14], [Rc - 18, 13]], 24).rot('y', 90).move(x0, yc, Rc);
  const d = cylinder('nerez_svetly', 'kolecko_disk', Rc - 14, -15, 15, 20).rot('y', 90).move(x0, yc, Rc);
  const ax = cylX('ocel', 'kolecko_osa', 4.5, x0 - 24, x0 + 24, yc, Rc, 10);
  w.add(t, d, ax);
  root.addGroup(w);
  return root;
}
