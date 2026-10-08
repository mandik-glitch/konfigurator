// Cilena oprava #379 (Doblo K-075 B, hbv=5) - NA ROZDIL od verze A,
// box-fitting (col0/col1) se u hbv=5 NEMENI: col0 stack je omezeny
// "police" podelnikem (podelnik-celni-spodni, Y~976.5-1006.5), ne
// yHornihoHor - overeno vypoctem, ze box p5 by kolidoval s policovym
// podelnikem uz driv, nez by narazil na (byt buggy) strop. Jedina zmena:
// sloucit podelnik-*-horni-0/-1 (split, Y=1175 buggy) do 1 kusu (Y=1205,
// presne vzor overeny na verzi A/C).
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");

const d = JSON.parse(fs.readFileSync(
  "/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/asm379_current.json", "utf8"));

const REMOVE = new Set(["podelnik-celni-horni-0", "podelnik-celni-horni-1",
  "podelnik-zadni-horni-0", "podelnik-zadni-horni-1"]);
const kept = d.parts.filter(p => !REMOVE.has(p.role));
const Q_PODELNY = [-0.7071067811865475, 0, 0, 0.7071067811865476];
const nove = [
  { part_id: "Object_7", position: [-387.49999237060547, 1205, -692.5025410652161], quaternion: Q_PODELNY, scale: [1, 1.286, 1], role: "podelnik-celni-horni" },
  { part_id: "Object_7", position: [-636.4999923706055, 1205, -692.5025410652161], quaternion: Q_PODELNY, scale: [1, 1.286, 1], role: "podelnik-zadni-horni" },
];
const novaParts = [...kept, ...nove];

const meshCache = new Map();
function meshFor(f) { if (!meshCache.has(f)) meshCache.set(f, parseGlbMesh(f)); return meshCache.get(f); }
function box3Of(p) {
  if (R.jeKaroserie(p.part_id)) return null;
  const glb = R.glbPath(p.part_id);
  if (!glb) return null;
  const mesh = meshFor(glb);
  const obj = new THREE.Mesh(mesh.geometry);
  obj.position.set(...p.position); obj.quaternion.set(...p.quaternion);
  if (p.scale) obj.scale.set(...p.scale); else obj.scale.set(1, 1, 1);
  obj.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(obj);
}
function osaOverlap(mn1, mx1, mn2, mx2) { return Math.min(mx1, mx2) - Math.max(mn1, mn2); }
function overlap3D(b1, b2) {
  const ox = osaOverlap(b1.min.x, b1.max.x, b2.min.x, b2.max.x);
  const oy = osaOverlap(b1.min.y, b1.max.y, b2.min.y, b2.max.y);
  const oz = osaOverlap(b1.min.z, b1.max.z, b2.min.z, b2.max.z);
  return ox > 2 && oy > 2 && oz > 2;
}
function jeOcekavanyNestingPar(rA, rB) {
  const jeBox = r => r.startsWith("eurobox-");
  const jeNS = r => r.startsWith("nosnik-") || r.startsWith("spojnice-");
  return (jeBox(rA) && jeNS(rB)) || (jeBox(rB) && jeNS(rA));
}
const boxes = novaParts.map(p => ({ p, b: box3Of(p), isNew: nove.includes(p) })).filter(x => x.b);
const kolize = [];
for (let i = 0; i < boxes.length; i++) {
  if (!boxes[i].isNew) continue;
  for (let j = 0; j < boxes.length; j++) {
    if (i === j) continue;
    if (jeOcekavanyNestingPar(boxes[i].p.role, boxes[j].p.role)) continue;
    if (overlap3D(boxes[i].b, boxes[j].b)) kolize.push({ a: boxes[i].p.role, b: boxes[j].p.role, box: boxes[j].b });
  }
}
console.log(`puvodne=${d.parts.length} kept=${kept.length} nove=${nove.length} celkem=${novaParts.length} kolize=${kolize.length}`);
kolize.forEach(k => console.log("  KOLIZE:", k.a, "<->", k.b));

// dodatecne over: dotyka se novy podelnik FLUSH predni-svislice/cap (Y top 1220)?
const psTop = Math.max(...boxes.filter(x => x.p.role === "predni-svislice").map(x => x.b.max.y));
const capTop = Math.max(...boxes.filter(x => x.p.role === "cap").map(x => x.b.max.y));
const podTop = Math.max(...boxes.filter(x => x.p.role === "podelnik-celni-horni").map(x => x.b.max.y));
console.log("predni-svislice top:", psTop, "cap top:", capTop, "podelnik top:", podTop, "(mely by byt VSECHNY stejne)");

fs.writeFileSync("/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/fix_379_output.json",
  JSON.stringify({ parts: novaParts, kolize }));
console.log("zapsano fix_379_output.json");
