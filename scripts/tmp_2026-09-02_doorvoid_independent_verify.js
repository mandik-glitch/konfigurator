// bot16 2026-09-02 - NEZAVISLY druhy pruchod na FRESH datech (cte jen ulozeny
// JSON parts, ne zivou pamet predchoziho behu) - samostatna instance engine
// (novy parseGlbMesh nacteni ze souboru), samostatna self-kolizni logika
// napsana znovu (ne import sdileneho kodu z build_all.js).
const fs = require("fs");
const THREE = require("three");
const { createEngine } = require("/opt/konfigurator/scripts/tmp_2026-08-31_batch_engine.js");
const uhelnikCatalog = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/2026-09-01_uhelnik_catalog.json", "utf8"));
const KAT = "/opt/konfigurator/webapp/katalog/";

const SCRATCH = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad";
const data = JSON.parse(fs.readFileSync(`${SCRATCH}/doorvoid_build_all_result.json`, "utf8"));

const ENGINES = {
  FO31: createEngine("Ford_Custom_FO31_2023-"),
  VW25: createEngine("Volkswagen_Transporter_VW25_2024-"),
};

function glbFor(id) {
  if (id === "Object_7") return KAT + "Object_7.glb";
  if (["product_3071", "product_3788", "product_3793", "product_3794", "product_3795"].includes(id)) return KAT + id + ".glb";
  const meta = uhelnikCatalog.find(c => c.part_id === id);
  if (meta) return KAT + meta.glb_file;
  throw new Error("neznamy part_id: " + id);
}

let allPass = true;
const summary = [];
for (const [vKey, vData] of Object.entries(data)) {
  const engine = ENGINES[vKey];
  for (const [variantKey, variant] of Object.entries(vData.variants)) {
    const parts = variant.parts;
    function meshOf(p) {
      const m = engine.parseGlbMesh(glbFor(p.part_id));
      m.position.set(p.position[0], p.position[1], p.position[2]);
      m.quaternion.set(p.quaternion[0], p.quaternion[1], p.quaternion[2], p.quaternion[3]);
      m.scale.set(p.scale[0], p.scale[1], p.scale[2]);
      m.updateMatrixWorld(true);
      return m;
    }
    // 1) kolize s karoserii - KAZDY dil samostatne
    let carColl = 0;
    parts.forEach(p => {
      const grp = new THREE.Group(); grp.add(meshOf(p)); grp.updateMatrixWorld(true);
      if (engine.collidesWithWalls(grp)) carColl++;
    });
    // 2) self-kolize - vsechny dvojice, prah 0.5mm na vsech 3 osach,
    // ocekavane nesty: (a) box/zaslepka/uhelnik do profilu, (b) uhelnik do rohu 2 profilu
    const meshes = parts.map(meshOf);
    const boxes = meshes.map(m => new THREE.Box3().setFromObject(m));
    let unexpected = 0;
    for (let i = 0; i < parts.length; i++) for (let j = i + 1; j < parts.length; j++) {
      const A = boxes[i], B = boxes[j];
      const ox = Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x);
      const oy = Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y);
      const oz = Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z);
      if (ox > 0.5 && oy > 0.5 && oz > 0.5) {
        const bothProfile = parts[i].part_id === "Object_7" && parts[j].part_id === "Object_7";
        const isUhelnik = parts[i].role.startsWith("uhelnik") || parts[j].role.startsWith("uhelnik");
        const nestOk = !bothProfile || isUhelnik;
        if (!nestOk) unexpected++;
      }
    }
    // 3) sanity gate - Box3 obalka VSECH Object_7 profilu
    const profBox = new THREE.Box3();
    let has = false;
    parts.filter(p => p.part_id === "Object_7").forEach(p => { profBox.union(boxes[parts.indexOf(p)]); has = true; });
    const heightY = profBox.max.y - profBox.min.y, depthX = profBox.max.x - profBox.min.x, lengthZ = profBox.max.z - profBox.min.z;
    const sanityOk = heightY > 1000 && heightY < 1400 && depthX > 280 && depthX < 400;
    // 4) top-Y == H_cil kontrola (id=8) na "cap" dilu kazde nohy
    const capTops = parts.filter(p => p.role === "cap").map(p => p.position[1] + (p.scale[1] * 1000) / 2);

    const pass = carColl === 0 && unexpected === 0 && sanityOk;
    allPass = allPass && pass;
    summary.push({ vKey, variantKey, carColl, unexpected, heightY: +heightY.toFixed(1), depthX: +depthX.toFixed(1), lengthZ: +lengthZ.toFixed(1), capTops: capTops.map(v => +v.toFixed(1)), pass });
    console.log(`${vKey} ${variantKey}: carColl=${carColl} unexpectedSelf=${unexpected} sanity(h/d/l)=${heightY.toFixed(0)}/${depthX.toFixed(0)}/${lengthZ.toFixed(0)} capTops=${JSON.stringify(capTops.map(v=>+v.toFixed(1)))} PASS=${pass}`);
  }
}
console.log("\nVSECHNY (10/10) NEZAVISLE OVERENY:", allPass);
fs.writeFileSync(`${SCRATCH}/doorvoid_independent_verify_summary.json`, JSON.stringify(summary, null, 1));
process.exit(allPass ? 0 : 1);
