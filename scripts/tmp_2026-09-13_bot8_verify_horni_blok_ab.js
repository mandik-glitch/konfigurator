const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");

const dump = JSON.parse(fs.readFileSync(
  "/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/dolba_ab.json", "utf8"));

const meshCache = new Map();
function meshFor(glbFile) {
  if (!meshCache.has(glbFile)) meshCache.set(glbFile, parseGlbMesh(glbFile));
  return meshCache.get(glbFile);
}

function buildEntries(parts) {
  const entries = [];
  parts.forEach((p, idx) => {
    if (R.jeKaroserie(p.part_id)) return;
    const glb = R.glbPath(p.part_id);
    if (!glb) return;
    const mesh = meshFor(glb);
    const obj = new THREE.Mesh(mesh.geometry);
    obj.position.set(...p.position);
    obj.quaternion.set(...p.quaternion);
    if (p.scale) obj.scale.set(...p.scale); else obj.scale.set(1, 1, 1);
    obj.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(obj);
    entries.push({ idx, part_id: p.part_id, role: p.role, box });
  });
  return entries;
}

for (const aid of ["341", "381"]) {
  const { name, parts } = dump[aid];
  const entries = buildEntries(parts);
  console.log(`\n=== id=${aid} ${name} (${entries.length}/${parts.length} entries resolved) ===`);
  const wanted = new Set([
    "podelnik-celni-horni", "podelnik-celni-horni-0", "podelnik-celni-horni-1",
    "podelnik-zadni-horni", "podelnik-zadni-horni-0", "podelnik-zadni-horni-1",
    "eurobox-col0-p2", "eurobox-col0-p3", "eurobox-col1-p1", "eurobox-col1-p2",
    "nosnik-col0-p2", "nosnik-col0-p3", "nosnik-col1-p1", "nosnik-col1-p2",
    "spojnice-col0-p2", "spojnice-col0-p3", "spojnice-col1-p1", "spojnice-col1-p2",
    "sloupek-pred-podbehem", "predni-svislice", "zadni-svislice-nad-zarezem",
  ]);
  entries.filter(e => wanted.has(e.role)).forEach(e => {
    const b = e.box;
    console.log(`  idx=${String(e.idx).padStart(3)} ${e.role.padEnd(24)} Y:[${b.min.y.toFixed(1)}, ${b.max.y.toFixed(1)}] Z:[${b.min.z.toFixed(1)}, ${b.max.z.toFixed(1)}] X:[${b.min.x.toFixed(1)}, ${b.max.x.toFixed(1)}]`);
  });
}
