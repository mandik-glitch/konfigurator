// Pomocné funkce pro organizer_4932471064.mjs (vlastní kód; jadro/ se needituje, co v něm chybí, je tady):
// triangulace polygonu s dírami (earcut), zaoblení/zkosení rohů polygonu, spojení dvou smyček stejné délky (stěny),
// ploché desky s otvory, prostorové ukotvení (sklon/zaoblení hran) apod.
// Konvence: polygony jsou pole [x,y] (x = X, y = Y modelu), kladná orientace = proti směru hodinových ručiček při pohledu shora (+Z).
import { Part } from './jadro/mesh.js';

export const area2 = (P) => { let s = 0; for (let i = 0; i < P.length; i++) { const a = P[i], b = P[(i + 1) % P.length]; s += a[0] * b[1] - b[0] * a[1]; } return s; };
export const ccw = (P) => (area2(P) < 0 ? P.slice().reverse() : P.slice());
export const cw = (P) => (area2(P) > 0 ? P.slice().reverse() : P.slice());

// ---------- earcut: polygon s dírami -> trojúhelníky ----------
// outer: pole [x,y]; holes: pole polí. Vrací { pts, tris } (pts = sloučený kruh bodů s mosty, tris = trojice indexů do pts).
export function earcut(outer, holes = []) {
  const dd = (P) => { const o = []; for (const q of P) { const l = o[o.length - 1]; if (!l || Math.hypot(q[0] - l[0], q[1] - l[1]) > 1e-6) o.push(q); } while (o.length > 1 && Math.hypot(o[0][0] - o[o.length - 1][0], o[0][1] - o[o.length - 1][1]) < 1e-6) o.pop(); return o; };
  outer = dd(outer); holes = holes.map(dd);
  let ring = ccw(outer).map(p => ({ x: p[0], y: p[1] }));
  const H = holes.map(h => cw(h).map(p => ({ x: p[0], y: p[1] })));
  const segX = (a, b, c, d) => {                         // vlastní průsečík úseček ab a cd (bez dotyku koncových bodů)
    const o = (p, q, r) => (q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x);
    const d1 = o(a, b, c), d2 = o(a, b, d), d3 = o(c, d, a), d4 = o(c, d, b);
    return ((d1 > 1e-9 && d2 < -1e-9) || (d1 < -1e-9 && d2 > 1e-9)) && ((d3 > 1e-9 && d4 < -1e-9) || (d3 < -1e-9 && d4 > 1e-9));
  };
  H.sort((p, q) => Math.min(...p.map(v => v.x)) - Math.min(...q.map(v => v.x)));
  for (const hole of H) {
    // most: z bodu díry (nejlevější) k nejbližšímu viditelnému bodu kruhu
    let mi = 0; for (let i = 1; i < hole.length; i++) if (hole[i].x < hole[mi].x) mi = i;
    const M = hole[mi];
    const cand = ring.map((p, i) => ({ i, d: (p.x - M.x) ** 2 + (p.y - M.y) ** 2 })).sort((a, b) => a.d - b.d);
    let bi = -1;
    for (const c of cand) {
      const P = ring[c.i]; let ok = true;
      for (let k = 0; k < ring.length && ok; k++) { const a = ring[k], b = ring[(k + 1) % ring.length]; if (a === P || b === P) continue; if (segX(M, P, a, b)) ok = false; }
      for (const h2 of H) { if (!ok) break; for (let k = 0; k < h2.length && ok; k++) { const a = h2[k], b = h2[(k + 1) % h2.length]; if (a === M || b === M) continue; if (segX(M, P, a, b)) ok = false; } }
      if (ok) { bi = c.i; break; }
    }
    if (bi < 0) throw new Error('earcut: most k díře nenalezen');
    const hr = []; for (let k = 0; k <= hole.length; k++) hr.push({ ...hole[(mi + k) % hole.length] });
    ring = [...ring.slice(0, bi + 1), ...hr, { ...ring[bi] }, ...ring.slice(bi + 1)];
  }
  const pts = ring.map(p => [p.x, p.y]);
  const n = ring.length, idx = [...Array(n).keys()], tris = [];
  const ar = (a, b, c) => (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
  const same = (a, b) => Math.abs(a.x - b.x) < 1e-9 && Math.abs(a.y - b.y) < 1e-9;
  const inTri = (a, b, c, p) => ar(a, b, p) >= -1e-12 && ar(b, c, p) >= -1e-12 && ar(c, a, p) >= -1e-12;
  let guard = 0;
  while (idx.length > 3 && guard++ < 200000) {
    let cut = false;
    for (let t = 0; t < idx.length; t++) {
      const ia = idx[(t + idx.length - 1) % idx.length], ib = idx[t], ic = idx[(t + 1) % idx.length];
      const a = ring[ia], b = ring[ib], c = ring[ic];
      if (ar(a, b, c) <= 1e-10) continue;                              // reflexní nebo degenerovaný
      let ok = true;
      for (const j of idx) {
        if (j === ia || j === ib || j === ic) continue;
        const p = ring[j];
        if (same(p, a) || same(p, b) || same(p, c)) continue;
        if (inTri(a, b, c, p)) { ok = false; break; }
      }
      if (!ok) continue;
      tris.push([ia, ib, ic]); idx.splice(t, 1); cut = true; break;
    }
    if (!cut) { // nouzově: odstranit degenerovaný vrchol
      let removed = false;
      for (let t = 0; t < idx.length; t++) { const ia = idx[(t + idx.length - 1) % idx.length], ib = idx[t], ic = idx[(t + 1) % idx.length]; if (Math.abs(ar(ring[ia], ring[ib], ring[ic])) <= 1e-10) { idx.splice(t, 1); removed = true; break; } }
      if (!removed) { tris.push([idx[0], idx[1], idx[2]]); idx.splice(1, 1); }
    }
  }
  if (idx.length === 3) tris.push([idx[0], idx[1], idx[2]]);
  return { pts, tris };
}

// ploché plochy: polygon s otvory na výšce z; up=true normála +Z
import { earcut2 } from './earcut_cloud.mjs';
export function flatFace(part, outer, holes, z, up = true) {
  const dd = (P) => { const o = []; for (const q of P) { const l = o[o.length - 1]; if (!l || Math.hypot(q[0] - l[0], q[1] - l[1]) > 1e-6) o.push(q); } while (o.length > 1 && Math.hypot(o[0][0] - o[o.length - 1][0], o[0][1] - o[o.length - 1][1]) < 1e-6) o.pop(); return o; };
  const { pts, tris } = earcut2(ccw(dd(outer)), holes.map(h => cw(dd(h))));
  const base = pts.map(p => part.addV(p[0], p[1], z));
  for (const [a, b, c] of tris) {
    const A = pts[a], B = pts[b], C = pts[c]; if (Math.abs((B[0] - A[0]) * (C[1] - A[1]) - (B[1] - A[1]) * (C[0] - A[0])) < 1e-7) continue;   // žádné nulové plošky
    if (up) part.addT(base[a], base[b], base[c]); else part.addT(base[a], base[c], base[b]);
  }
  return part;
}

// spojí dvě smyčky stejné délky (A na z0, B na z1; obě CCW podle XY) bočními čtyřúhelníky; out=true normály ven (od středu smyčky)
export function wall(part, A, B, out = true) {
  const n = A.length;
  const a = A.map(p => part.addV(p[0], p[1], p[2])), b = B.map(p => part.addV(p[0], p[1], p[2]));
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    if (out) part.addQ(a[i], a[j], b[j], b[i]); else part.addQ(a[i], b[i], b[j], a[j]);
  }
  return part;
}
export const at = (P, z) => P.map(p => [p[0], p[1], z]);

// polygon s upravenými rohy: kazdy vrchol má poloměr r (>0 zaoblení s n segmenty, <0 zkosení o |r|, 0 ostrý)
export function cornerPoly(P, radii, seg = 4) {
  const n = P.length, out = [];
  const sub = (a, b) => [a[0] - b[0], a[1] - b[1]]; const len = v => Math.hypot(v[0], v[1]);
  for (let i = 0; i < n; i++) {
    const V = P[i], A = P[(i + n - 1) % n], B = P[(i + 1) % n];
    const r = Array.isArray(radii) ? radii[i] : radii;
    if (!r) { out.push(V.slice()); continue; }
    const da = sub(A, V), db = sub(B, V), la = len(da), lb = len(db);
    const ua = [da[0] / la, da[1] / la], ub = [db[0] / lb, db[1] / lb];
    if (r < 0) { const c = Math.min(-r, la * 0.5, lb * 0.5); out.push([V[0] + ua[0] * c, V[1] + ua[1] * c], [V[0] + ub[0] * c, V[1] + ub[1] * c]); continue; }
    const cosT = Math.max(-1, Math.min(1, ua[0] * ub[0] + ua[1] * ub[1])); const th = Math.acos(cosT);   // vnitřní úhel
    if (th < 1e-3 || Math.abs(Math.PI - th) < 1e-3) { out.push(V.slice()); continue; }
    let t = r / Math.tan(th / 2); const tmax = Math.min(la, lb) * 0.5; let rr = r; if (t > tmax) { rr = r * tmax / t; t = tmax; }
    const T1 = [V[0] + ua[0] * t, V[1] + ua[1] * t], T2 = [V[0] + ub[0] * t, V[1] + ub[1] * t];
    const bis = [ua[0] + ub[0], ua[1] + ub[1]]; const lbis = len(bis); const dc = rr / Math.sin(th / 2);
    const C = [V[0] + bis[0] / lbis * dc, V[1] + bis[1] / lbis * dc];
    let a1 = Math.atan2(T1[1] - C[1], T1[0] - C[0]), a2 = Math.atan2(T2[1] - C[1], T2[0] - C[0]);
    let da2 = a2 - a1; while (da2 > Math.PI) da2 -= 2 * Math.PI; while (da2 < -Math.PI) da2 += 2 * Math.PI;
    for (let k = 0; k <= seg; k++) { const a = a1 + da2 * k / seg; out.push([C[0] + rr * Math.cos(a), C[1] + rr * Math.sin(a)]); }
  }
  return out;
}

// obdélník [x0,x1]×[y0,y1] jako polygon CCW (se zkosením/zaoblením rohů radii: [x0y0, x1y0, x1y1, x0y1])
export function rectPoly(x0, x1, y0, y1, radii = 0, seg = 4) {
  const P = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
  return radii === 0 ? P : cornerPoly(P, radii, seg);
}

// vyplněný hranol z polygonu s dírami (horní a dolní podstava + boční stěny okraje i děr)
export function prismHoles(mat, name, outer, holes, z0, z1) {
  const p = new Part(name, mat);
  flatFace(p, outer, holes, z1, true); flatFace(p, outer, holes, z0, false);
  const o = ccw(outer); wall(p, at(o, z0), at(o, z1), true);
  for (const h of holes) { const hh = cw(h); wall(p, at(hh, z0), at(hh, z1), true); }
  p.crease = 25;
  return p;
}

// zrcadlení bodů polygonu (X nebo Y), vrací CCW
export const mirrorPolyY = (P) => ccw(P.map(p => [p[0], -p[1]]));
export const mirrorPolyX = (P) => ccw(P.map(p => [-p[0], p[1]]));

// odstraní zdegenerované (nulová plocha) trojúhelníky z dílu
export function cistiDil(part, eps = 2e-3) {
  const P = part.pos, I = part.idx, out = [];
  for (let t = 0; t < I.length; t += 3) {
    const a = I[t], b = I[t + 1], c = I[t + 2];
    const ux = P[3 * b] - P[3 * a], uy = P[3 * b + 1] - P[3 * a + 1], uz = P[3 * b + 2] - P[3 * a + 2];
    const vx = P[3 * c] - P[3 * a], vy = P[3 * c + 1] - P[3 * a + 1], vz = P[3 * c + 2] - P[3 * a + 2];
    if (Math.hypot(uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx) < eps) continue;
    out.push(a, b, c);
  }
  const n = I.length / 3 - out.length / 3; part.idx = out; return n;
}
