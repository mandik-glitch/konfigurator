// Čelní sestava (+Y): dvě spony na úhlopříčných rozích (červená páka, černý pásek, drátěný třmen jako samostatný otočný uzel).
// Čepičky (čirá část) jsou součástí víka (p1065_vicko.mjs). Tvar páky/čepičky/třmenu: rektifikace c07 na rovinu spony
// (nástroj rekt_plane.py ve scratchpadu): páka 38 mm široká, z' 0,5..25, pásek 25..31, čepička 29..51, třmen o šířce ~41 mm.
import { Group, Part, loftSolid, ccw, tube, bx, zc } from './p1065_zaklad.mjs';
import { extrude, rrect, offsetPoly } from './pomocne.mjs';

// rám spony (s = +1 pravá, −1 levá): tečna t podél úhlopříčné hrany rohu, normála n ven; C0 = střed spony na hraně
export function latchFrame(s) {
  const t = [-0.669, 0.744], n = [0.744, 0.669];
  const C0 = [99.2, 157.5];
  const sx = s;
  return {
    t: [sx * t[0], t[1]], n: [sx * n[0], n[1]], c: [sx * C0[0], C0[1]],
    rot: Math.atan2(t[1], sx * t[0]) * 180 / Math.PI,
    at(dt, dn) { return [this.c[0] + this.t[0] * dt + this.n[0] * dn, this.c[1] + this.t[1] * dt + this.n[1] * dn]; },
  };
}
const rr = (f, dt, dn, L, T, r, k = 0) => { const p = f.at(dt, dn); return rrect(p[0], p[1], L - 2 * k, T - 2 * k, Math.max(r - k, 0.4), f.rot, 3); };

function paka(g, s) {
  const f = latchFrame(s), L = s > 0 ? 'P' : 'L';
  // černý podstavec spony (zapuštěný do rohu těla – drží páku)
  g.add(extrude('cerna_mat', 'spona_podstavec_' + L, rr(f, 0, 2, 40, 12, 3), [], zc(6), zc(26.5)));
  // červená páka: z' 0,5 .. 25; spodní část šikmo zkosená, horní plocha se sklonem k čelu
  const lay = (k, z) => ({ poly: ccw(rr(f, 0, 7.25 + 0.0, 38, 14.5, 4, k)), z });
  g.add(loftSolid('cervena', 'spona_paka_' + L, [lay(2.4, 0.5), lay(0.8, 2.5), lay(0, 5), lay(0, 21.5), lay(1.2, 24.2), lay(2.8, 25.2)], { crease: 40 }));
  // černý pásek (pružná vložka mezi pákou a čepičkou)
  g.add(loftSolid('cerna_mat', 'spona_pasek_' + L, [{ poly: ccw(rr(f, 0, 7, 35, 12.5, 3.5)), z: 24.8 }, { poly: ccw(rr(f, 0, 7, 35, 12.5, 3.5)), z: 30.3 }], { crease: 40 }));
  // tři žebra na čelní ploše páky
  for (let k = 0; k < 3; k++) {
    const p = f.at(0, 14.3);
    g.add(extrude('cervena', 'spona_zebro_' + L, rrect(p[0], p[1], 24, 0.9, 0.4, f.rot, 2), [], zc(4 + k * 3.2), zc(5.4 + k * 3.2)));
  }
}

// třmen: jedna uzavřená drátěná smyčka (příčka v páce, nohy po vnější straně čepičky, vršek přes čepičku); otáčí se kolem příčky
function trmen(s) {
  const f = latchFrame(s);
  const P3 = (dt, dn, z) => { const p = f.at(dt, dn); return [p[0], p[1], zc(z)]; };
  const piv = P3(0, 7, 6);
  const axis = s > 0 ? [f.t[0], f.t[1], 0] : [-f.t[0], -f.t[1], 0];   // kladný úhel: třmen se vyklápí ven a dolů
  const g = new Group(s > 0 ? 'trmen_P' : 'trmen_L', { pivot: piv, extras: { osa: axis, max_uhel: 170 } });
  const w = 19.6, dn = 14.4;
  const path = [P3(-w, 7, 6), P3(-w, dn, 8.5), P3(-w, dn, 44), P3(-w + 3.5, dn, 50.6), P3(w - 3.5, dn, 50.6), P3(w, dn, 44), P3(w, dn, 8.5), P3(w, 7, 6), P3(-w, 7, 6)];
  g.add(tube('ocel', 'spona_trmen_' + (s > 0 ? 'P' : 'L'), path, 1.25, 8));
  return g;
}

// zámkový jazýček + tlačítko jsou v korpusu; zde jen spony
export function celo() {
  const g = new Group('celo');
  for (const s of [1, -1]) { paka(g, s); g.addGroup(trmen(s)); }
  return g;
}
