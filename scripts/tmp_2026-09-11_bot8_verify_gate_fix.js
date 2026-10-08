// Overeni opravy nestOk gate z 2026-08-31_proace_full_build.js: replikuje
// PRESNE stejnou Box3 logiku (sekce 6) na realnych datech uz ulozenych
// sestav, srovna STAROU vs NOVOU verzi nestOk.
const THREE = require("three");
const fs = require("fs");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";

function meshOf(p) {
  const m = parseGlbMesh(KAT + p.glb);
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...(p.scale || [1,1,1]));
  m.updateMatrixWorld(true);
  return m;
}

const data = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
for (const target of [59, 74]) {
  const a = data.find(x => x.id === target);
  const allParts = a.parts.filter(p => !p.part_id.startsWith("car_body_"));
  const meshes = allParts.map(meshOf);
  let oldFlag = 0, newFlag = 0;
  const newBad = [];
  for (let i = 0; i < meshes.length; i++) for (let j = i + 1; j < meshes.length; j++) {
    const A = new THREE.Box3().setFromObject(meshes[i]), B = new THREE.Box3().setFromObject(meshes[j]);
    const ox = Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x);
    const oy = Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y);
    const oz = Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z);
    if (ox > 0.5 && oy > 0.5 && oz > 0.5) {
      const p1 = allParts[i], p2 = allParts[j];
      const oldNestOk = p1.part_id !== "Object_7" || p2.part_id !== "Object_7";
      if (oldNestOk) oldFlag++;

      const jeZaslepka = (p) => p.part_id === "product_3071";
      const jeEurobox = (p) => p.part_id.startsWith("product_37") && p.part_id !== "product_3071";
      const jeKolejnicka = (p) => p.role.startsWith("nosnik-") || p.role.startsWith("spojnice-sloupec");
      const newNestOk =
        (jeZaslepka(p1) && p2.part_id === "Object_7") || (jeZaslepka(p2) && p1.part_id === "Object_7") ||
        (jeEurobox(p1) && jeKolejnicka(p2)) || (jeEurobox(p2) && jeKolejnicka(p1));
      if (!newNestOk) { newFlag++; newBad.push([p1.role, p1.part_id, p2.role, p2.part_id]); }
    }
  }
  console.log(`#${target}: parů s box-prekryvem>${0.5}mm na vsech osach = (stara verze by je oznacila jako 'expected'): ${oldFlag}   NOVA verze oznaci jako 'unexpected' (bad): ${newFlag}`);
  for (const b of newBad) console.log("   ", b.join(" | "));
}
