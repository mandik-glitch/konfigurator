// Logo „Makita“ jako tenké bílé plošky na vyhloubené ploše víka (jednoduché šikmé tahové písmo; tvar písmen zjednodušen).
import { Part, prism, zc } from './makpac_zaklad.mjs';

// glyfy v jednotkách výšky 1: tahy [[u0,v0],[u1,v1],...] polylinie; aw = šířka tahu; adv = posun na další znak
const G = {
  M: { adv: 1.25, s: [[[0, 0], [0.04, 1], [0.62, 0.3], [1.1, 1], [1.12, 0]]] },
  a: { adv: 0.85, s: [(() => { const o = []; for (let i = 0; i <= 14; i++) { const a = 2 * Math.PI * i / 14; o.push([0.34 + 0.27 * Math.cos(a), 0.3 + 0.27 * Math.sin(a)]); } return o; })(), [[0.64, 0], [0.64, 0.6]]] },
  k: { adv: 0.78, s: [[[0, 0], [0.04, 1]], [[0.55, 0.62], [0.06, 0.28]], [[0.2, 0.42], [0.62, 0]]] },
  i: { adv: 0.42, s: [[[0, 0], [0, 0.6]], [[0, 0.82], [0, 0.98]]] },
  t: { adv: 0.62, s: [[[0.12, 0], [0.12, 0.88]], [[-0.08, 0.6], [0.4, 0.6]]] },
};
export const LOGO_P = { xc: 97, w: 190, h: 33, z: 0 };

export function logo(V, { xc = LOGO_P.xc, w = LOGO_P.w, h = LOGO_P.h } = {}) {
  const txt = 'Makita', shear = 0.28, sw = 0.19;
  let tot = 0; for (const ch of txt) tot += G[ch].adv + 0.1; tot -= 0.1; tot += shear;
  const sc = w / tot, p = new Part('logo_makita', 'bila');
  let u0 = -w / 2;
  for (const ch of txt) {
    for (const st of G[ch].s) {
      for (let i = 0; i + 1 < st.length; i++) {
        const a = st[i], b = st[i + 1];
        const dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy) || 1, nx = -dy / l * sw / 2, ny = dx / l * sw / 2;
        const pts = [[a[0] + nx, a[1] + ny], [b[0] + nx, b[1] + ny], [b[0] - nx, b[1] - ny], [a[0] - nx, a[1] - ny]];
        // (u,v) → model: x = xc + h/2 − v·h, y = u0 + (u + shear·v)·sc
        const poly = pts.map(([u, v]) => [xc + h / 2 - v * h, u0 + (u + shear * v) * sc]);
        const q = prism('bila', 'q', poly, zc(V - 0.9), zc(V - 0.5)); p.append(q);
      }
    }
    u0 += (G[ch].adv + 0.1) * sc;
  }
  p.crease = 25;
  return [p];
}
