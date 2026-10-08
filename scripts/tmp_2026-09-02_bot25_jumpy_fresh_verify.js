// bot25, 2026-09-02 - NEZAVISLY druhy pruchod: cte primo z DB (product_assemblies)
// PO commitu (fresh, ne z pameti stavebniho behu), samostatna engine instance
// per car body, samostatna self-kolizni logika (napsana znovu).
const fs = require("fs");
const _envText = fs.readFileSync("/opt/konfigurator/api/.env", "utf8");
const _env = {};
for (const _l of _envText.split("\n")) {
  const l = _l.trim();
  if (!l || l.startsWith("#") || !l.includes("=")) continue;
  const i = l.indexOf("=");
  _env[l.slice(0, i).trim()] = l.slice(i + 1).trim().replace(/^["']|["']$/g, "");
}
const THREE = require("three");
const { execSync } = require("child_process");
const { createEngine } = require("/opt/konfigurator/scripts/tmp_2026-08-31_batch_engine.js");
const uhelnikCatalog = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/2026-09-01_uhelnik_catalog.json", "utf8"));
const KAT = "/opt/konfigurator/webapp/katalog/";
const SCRATCH = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad";

const IDS_TO_BASE = {
  181: "Citroën_Jumpy_CI13_2016-", 182: "Citroën_Jumpy_CI14_2016-", 183: "Citroën_Jumpy_CI15_2016-",
  184: "Citroën_Jumpy_CI18_2016-", 185: "Citroën_Jumpy_CI19_2016-", 186: "Citroën_Jumpy_CI24_2021-",
  187: "Citroën_Jumpy_CI25_2021-", 188: "Citroën_Jumpy_CI26_2021-",
};

function glbFor(id) {
  if (id === "Object_7") return KAT + "Object_7.glb";
  if (["product_3071", "product_3788", "product_3793", "product_3794", "product_3795"].includes(id)) return KAT + id + ".glb";
  const meta = uhelnikCatalog.find(c => c.part_id === id);
  if (meta) return KAT + meta.glb_file;
  throw new Error("neznamy part_id: " + id);
}

const rows = [];
let allPass = true;
for (const [id, base] of Object.entries(IDS_TO_BASE)) {
  // fresh dump PRIMO z DB (ne z pameti predchoziho behu)
  const sql = `SELECT data, name FROM product_assemblies WHERE id=${id}`;
  const out = execSync(`mysql -h ${_env.DB_HOST} -P ${_env.DB_PORT || 3306} -u ${_env.DB_USER} -p'${_env.DB_PASSWORD}' ${_env.DB_NAME} --raw -N -e "${sql}"`, { maxBuffer: 50 * 1024 * 1024 }).toString();
  const lines = out.split("\n").filter(l => !l.startsWith("mysql:"));
  const tabIdx = lines[0].indexOf("\t");
  const dataStr = lines[0].slice(0, lines.findIndex((l,i)=>false)); // will fix below
  // data and name are tab-separated on ONE line (data has no literal tabs/newlines since JSON.dumps compact... but python json.dumps default uses no newlines, safe)
  const rawLine = lines.join("\n");
  const lastTab = rawLine.lastIndexOf("\t");
  const dataJson = rawLine.slice(0, lastTab);
  const name = rawLine.slice(lastTab + 1);
  const data = JSON.parse(dataJson);
  const parts = data.parts.filter(p => !p.part_id.startsWith("car_body_"));

  const engine = createEngine(base);
  function meshOf(p) {
    const m = engine.parseGlbMesh(glbFor(p.part_id));
    m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
    m.updateMatrixWorld(true);
    return m;
  }
  let carColl = 0; const carCollDetails = [];
  const meshes = parts.map(meshOf);
  meshes.forEach((m, i) => {
    const g = new THREE.Group(); g.add(m); g.updateMatrixWorld(true);
    if (engine.collidesWithWalls(g)) { carColl++; carCollDetails.push(parts[i].role); }
  });

  const boxes = meshes.map(m => new THREE.Box3().setFromObject(m));
  let unexpected = 0; const unexpectedDetails = [];
  for (let i = 0; i < parts.length; i++) for (let j = i + 1; j < parts.length; j++) {
    const A = boxes[i], B = boxes[j];
    const ox = Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x);
    const oy = Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y);
    const oz = Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z);
    if (ox > 0.5 && oy > 0.5 && oz > 0.5) {
      const bothProfile = parts[i].part_id === "Object_7" && parts[j].part_id === "Object_7";
      const isUhelnik = parts[i].role.startsWith("uhelnik") || parts[j].role.startsWith("uhelnik");
      if (!(!bothProfile || isUhelnik)) { unexpected++; unexpectedDetails.push([parts[i].role, parts[j].role]); }
    }
  }

  const profBox = new THREE.Box3();
  parts.forEach((p, i) => { if (p.part_id === "Object_7") profBox.union(boxes[i]); });
  const heightY = profBox.max.y - profBox.min.y, depthX = profBox.max.x - profBox.min.x, lengthZ = profBox.max.z - profBox.min.z;
  const sanityOk = heightY > 1000 && heightY < 1400 && depthX > 280 && depthX < 400;
  const yRangeOk = profBox.min.y > -50 && profBox.min.y < 100; // class E check: no +-1500/2000mm offset regression

  const boxParts = parts.filter(p => p.role.startsWith("eurobox"));
  const distinctHeights = [...new Set(boxParts.map(p => p.part_id))];

  const pass = carColl === 0 && unexpected === 0 && sanityOk && yRangeOk;
  allPass = allPass && pass;
  rows.push({ id, base, name, carColl, carCollDetails, unexpected, unexpectedDetails, sanityOk, yRangeOk,
    minY: +profBox.min.y.toFixed(2), heightY: +heightY.toFixed(1), depthX: +depthX.toFixed(1), lengthZ: +lengthZ.toFixed(1),
    totalBoxes: boxParts.length, distinctBoxTypes: distinctHeights.length, partsCount: parts.length, pass });
  console.log(`id=${id} (${base}): carColl=${carColl} unexpectedSelf=${unexpected} sanityOk=${sanityOk} yRangeOk=${yRangeOk} (minY=${profBox.min.y.toFixed(2)}) heightY=${heightY.toFixed(0)} depthX=${depthX.toFixed(0)} lengthZ=${lengthZ.toFixed(0)} boxes=${boxParts.length} distinctBoxTypes=${distinctHeights.length} partsCount=${parts.length} PASS=${pass}`);
  if (carColl > 0) console.log("  CAR COLLISIONS:", JSON.stringify(carCollDetails));
  if (unexpected > 0) console.log("  UNEXPECTED SELF-COLLISIONS:", JSON.stringify(unexpectedDetails));
}
console.log("\nVSECH 8/8 NEZAVISLE OVERENO Z FRESH DB DAT:", allPass);
fs.writeFileSync(`${SCRATCH}/jumpy_fresh_verify_summary.json`, JSON.stringify(rows, null, 1));
process.exit(allPass ? 0 : 1);
