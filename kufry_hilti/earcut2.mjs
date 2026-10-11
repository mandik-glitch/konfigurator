// Triangulace polygonu s dírami (ear clipping s mosty k dírám) – vlastní implementace podle postupu "earcut" (bez z-křivky; pro stovky bodů stačí).
// earcut2(outer, holes) → { pts: [[x,y]...], tris: [[i,j,k]...] }  (indexy do pts; trojúhelníky CCW)
class Node { constructor(i, x, y) { this.i = i; this.x = x; this.y = y; this.prev = null; this.next = null; this.steiner = false; } }
const area = (p, q, r) => (q.y - p.y) * (r.x - q.x) - (q.x - p.x) * (r.y - q.y);
const equals = (a, b) => Math.abs(a.x - b.x) < 1e-9 && Math.abs(a.y - b.y) < 1e-9;
function linked(pts, start, end, clockwise) {
  let last = null;
  let s = 0; for (let i = start, j = end - 1; i < end; j = i, i++) s += (pts[j][0] - pts[i][0]) * (pts[i][1] + pts[j][1]);
  if (clockwise === (s > 0)) { for (let i = start; i < end; i++) last = insertNode(i, pts[i][0], pts[i][1], last); }
  else { for (let i = end - 1; i >= start; i--) last = insertNode(i, pts[i][0], pts[i][1], last); }
  if (last && equals(last, last.next)) { removeNode(last); last = last.next; }
  return last;
}
function insertNode(i, x, y, last) { const p = new Node(i, x, y); if (!last) { p.prev = p; p.next = p; } else { p.next = last.next; p.prev = last; last.next.prev = p; last.next = p; } return p; }
function removeNode(p) { p.next.prev = p.prev; p.prev.next = p.next; }
function filterPoints(start, end) {
  if (!start) return start; if (!end) end = start;
  let p = start, again;
  do {
    again = false;
    if (!p.steiner && (equals(p, p.next) || area(p.prev, p, p.next) === 0)) { removeNode(p); p = end = p.prev; if (p === p.next) break; again = true; } else p = p.next;
  } while (again || p !== end);
  return end;
}
function pointInTriangle(ax, ay, bx, by, cx, cy, px, py) { return (cx - px) * (ay - py) >= (ax - px) * (cy - py) && (ax - px) * (by - py) >= (bx - px) * (ay - py) && (bx - px) * (cy - py) >= (cx - px) * (by - py); }
function isEar(ear) {
  const a = ear.prev, b = ear, c = ear.next;
  if (area(a, b, c) >= 0) return false;
  let p = ear.next.next;
  while (p !== ear.prev) {
    if (pointInTriangle(a.x, a.y, b.x, b.y, c.x, c.y, p.x, p.y) && area(p.prev, p, p.next) >= 0) return false;
    p = p.next;
  }
  return true;
}
function earcutLinked(ear, out, pass) {
  if (!ear) return;
  let stop = ear, prev, next;
  while (ear.prev !== ear.next) {
    prev = ear.prev; next = ear.next;
    if (isEar(ear)) { out.push([prev.i, ear.i, next.i]); removeNode(ear); ear = next.next; stop = next.next; continue; }
    ear = next;
    if (ear === stop) {
      if (!pass) earcutLinked(filterPoints(ear), out, 1);
      else if (pass === 1) { ear = cureLocal(filterPoints(ear), out); earcutLinked(ear, out, 2); }
      else if (pass === 2) splitEarcut(ear, out);
      break;
    }
  }
}
const sameP = (a, b) => a.x === b.x && a.y === b.y;
function cureLocal(start, out) {
  let p = start;
  do {
    const a = p.prev, b = p.next.next;
    if (!sameP(a, b) && intersects(a, p, p.next, b) && locallyInside(a, b) && locallyInside(b, a)) {
      out.push([a.i, p.i, b.i]); removeNode(p); removeNode(p.next); p = start = b;
    }
    p = p.next;
  } while (p !== start);
  return filterPoints(p);
}
function splitEarcut(start, out) {
  let a = start;
  do {
    let b = a.next.next;
    while (b !== a.prev) {
      if (a.i !== b.i && isValidDiagonal(a, b)) {
        let c = splitPolygon(a, b);
        a = filterPoints(a, a.next); c = filterPoints(c, c.next);
        earcutLinked(a, out, 0); earcutLinked(c, out, 0); return;
      }
      b = b.next;
    }
    a = a.next;
  } while (a !== start);
}
function eliminateHoles(pts, holeIdx, outer) {
  const queue = [];
  for (let i = 0; i < holeIdx.length; i++) {
    const start = holeIdx[i], end = i < holeIdx.length - 1 ? holeIdx[i + 1] : pts.length;
    const list = linked(pts, start, end, false); if (list === list.next) list.steiner = true;
    queue.push(getLeftmost(list));
  }
  queue.sort((a, b) => a.x - b.x);
  for (const h of queue) outer = eliminateHole(h, outer);
  return outer;
}
function eliminateHole(hole, outer) {
  const bridge = findHoleBridge(hole, outer); if (!bridge) return outer;
  const bridgeReverse = splitPolygon(bridge, hole);
  filterPoints(bridgeReverse, bridgeReverse.next);
  return filterPoints(bridge, bridge.next);
}
function findHoleBridge(hole, outer) {
  let p = outer, qx = -Infinity, m; const hx = hole.x, hy = hole.y;
  do {
    if (hy <= p.y && hy >= p.next.y && p.next.y !== p.y) {
      const x = p.x + (hy - p.y) * (p.next.x - p.x) / (p.next.y - p.y);
      if (x <= hx && x > qx) { qx = x; m = p.x < p.next.x ? p : p.next; if (x === hx) return m; }
    }
    p = p.next;
  } while (p !== outer);
  if (!m) return null;
  const stop = m, mx = m.x, my = m.y; let tanMin = Infinity;
  p = m;
  do {
    if (hx >= p.x && p.x >= mx && hx !== p.x && pointInTriangle(hy < my ? hx : qx, hy, mx, my, hy < my ? qx : hx, hy, p.x, p.y)) {
      const tan = Math.abs(hy - p.y) / (hx - p.x);
      if (locallyInside(p, hole) && (tan < tanMin || (tan === tanMin && (p.x > m.x || (p.x === m.x && sectorContainsSector(m, p)))))) { m = p; tanMin = tan; }
    }
    p = p.next;
  } while (p !== stop);
  return m;
}
function sectorContainsSector(m, p) { return area(m.prev, m, p.prev) < 0 && area(p.next, m, m.next) < 0; }
function getLeftmost(start) { let p = start, l = start; do { if (p.x < l.x || (p.x === l.x && p.y < l.y)) l = p; p = p.next; } while (p !== start); return l; }
function isValidDiagonal(a, b) {
  return a.next.i !== b.i && a.prev.i !== b.i && !intersectsPolygon(a, b) &&
    ((locallyInside(a, b) && locallyInside(b, a) && middleInside(a, b) && (area(a.prev, a, b.prev) || area(a, b.prev, b))) || (sameP(a, b) && area(a.prev, a, a.next) > 0 && area(b.prev, b, b.next) > 0));
}
const sign = n => (n > 0 ? 1 : n < 0 ? -1 : 0);
const onSegment = (p, q, r) => q.x <= Math.max(p.x, r.x) && q.x >= Math.min(p.x, r.x) && q.y <= Math.max(p.y, r.y) && q.y >= Math.min(p.y, r.y);
function intersects(p1, q1, p2, q2) {
  const o1 = sign(area(p1, q1, p2)), o2 = sign(area(p1, q1, q2)), o3 = sign(area(p2, q2, p1)), o4 = sign(area(p2, q2, q1));
  if (o1 !== o2 && o3 !== o4) return true;
  if (o1 === 0 && onSegment(p1, p2, q1)) return true; if (o2 === 0 && onSegment(p1, q2, q1)) return true;
  if (o3 === 0 && onSegment(p2, p1, q2)) return true; if (o4 === 0 && onSegment(p2, q1, q2)) return true;
  return false;
}
function intersectsPolygon(a, b) {
  let p = a;
  do { if (p.i !== a.i && p.next.i !== a.i && p.i !== b.i && p.next.i !== b.i && intersects(p, p.next, a, b)) return true; p = p.next; } while (p !== a);
  return false;
}
const locallyInside = (a, b) => (area(a.prev, a, a.next) < 0 ? area(a, b, a.next) >= 0 && area(a, a.prev, b) >= 0 : area(a, b, a.prev) < 0 || area(a, a.next, b) < 0);
function middleInside(a, b) {
  let p = a, inside = false; const px = (a.x + b.x) / 2, py = (a.y + b.y) / 2;
  do { if (((p.y > py) !== (p.next.y > py)) && p.next.y !== p.y && (px < (p.next.x - p.x) * (py - p.y) / (p.next.y - p.y) + p.x)) inside = !inside; p = p.next; } while (p !== a);
  return inside;
}
function splitPolygon(a, b) {
  const a2 = new Node(a.i, a.x, a.y), b2 = new Node(b.i, b.x, b.y), an = a.next, bp = b.prev;
  a.next = b; b.prev = a; a2.next = an; an.prev = a2; b2.next = a2; a2.prev = b2; bp.next = b2; b2.prev = bp;
  return b2;
}
export function earcut2(outer, holes = []) {
  const pts = outer.map(p => [p[0], p[1]]); const holeIdx = [];
  for (const h of holes) { holeIdx.push(pts.length); for (const p of h) pts.push([p[0], p[1]]); }
  const out = [];
  let node = linked(pts, 0, outer.length, true);   // vnější: dle konvence earcut (clockwise=true značí, že se projde tak, aby byl výsledek CW ve vnitřní orientaci)
  if (!node || node.next === node.prev) return { pts, tris: out };
  if (holeIdx.length) node = eliminateHoles(pts, holeIdx, node);
  earcutLinked(node, out, 0);
  // normalizace orientace na CCW (earcut vrací trojúhelníky v opačném smyslu vůči (x,y) s osou y dolů – sjednotíme)
  const res = out.map(([a, b, c]) => { const p = pts[a], q = pts[b], r = pts[c]; const ar = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]); return ar < 0 ? [a, c, b] : [a, b, c]; });
  return { pts, tris: res };
}
