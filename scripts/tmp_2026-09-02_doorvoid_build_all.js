// bot16 2026-09-02 - build all 10 rows (FO31 A/B/C/D/E, VW25 A/B/C/D/E) with
// the door-void-fixed front leg anchor, id=7 corner brackets, id=8 leg-height
// extension, and full mandatory verification (car-body collision, self-
// collision, sanity gate). Writes results to scratchpad JSON for DB insert.
const fs = require("fs");
const THREE = require("three");
const { createEngine } = require("/opt/konfigurator/scripts/tmp_2026-08-31_batch_engine.js");
const { runPipelineDoorFixed } = require("/opt/konfigurator/scripts/tmp_2026-09-02_doorvoid_pipeline.js");
const { assemble, validateHeights, applyDoorHeightRule } = require("/opt/konfigurator/scripts/tmp_2026-09-02_doorvoid_assemble.js");

const SCRATCH = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad";

const VEHICLES = {
  FO31: {
    base: "Ford_Custom_FO31_2023-",
    doorHeightMm: 1314,
    plans: { A: [270, 120], B: [220, 170], C: [220, 120], D: [170, 120], E: [120, 120, 120] },
  },
  VW25: {
    base: "Volkswagen_Transporter_VW25_2024-",
    doorHeightMm: 1316,
    plans: { A: [270, 170], B: [270, 120], C: [220, 170], D: [220, 120], E: [120, 120, 120] },
  },
};

function sanityCheckOverall(parts, engine) {
  // Box3 obalka VSECH profil dilu (Object_7) - vyska/hloubka sanity gate
  const OBJ7 = "/opt/konfigurator/webapp/katalog/Object_7.glb";
  const box = new THREE.Box3();
  parts.filter(p => p.part_id === "Object_7").forEach(p => {
    const m = engine.parseGlbMesh(OBJ7);
    m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
    m.updateMatrixWorld(true);
    box.union(new THREE.Box3().setFromObject(m));
  });
  return { minX: box.min.x, maxX: box.max.x, minY: box.min.y, maxY: box.max.y, minZ: box.min.z, maxZ: box.max.z,
    depthX: box.max.x - box.min.x, heightY: box.max.y - box.min.y, lengthZ: box.max.z - box.min.z };
}

function fullVerify(parts, engine) {
  const KAT = "/opt/konfigurator/webapp/katalog/";
  const uhelnikCatalog = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/2026-09-01_uhelnik_catalog.json", "utf8"));
  function glbFor(id) {
    if (id === "Object_7") return KAT + "Object_7.glb";
    if (id === "product_3071") return KAT + "product_3071.glb";
    if (id === "product_3788") return KAT + "product_3788.glb";
    if (id === "product_3793") return KAT + "product_3793.glb";
    if (id === "product_3794") return KAT + "product_3794.glb";
    if (id === "product_3795") return KAT + "product_3795.glb";
    const meta = uhelnikCatalog.find(c => c.part_id === id);
    if (meta) return KAT + meta.glb_file;
    throw new Error("neznamy part_id pro glbFor: " + id);
  }
  function meshOf(p) {
    const m = engine.parseGlbMesh(glbFor(p.part_id));
    m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
    m.updateMatrixWorld(true);
    return m;
  }
  const carCollisions = [];
  parts.forEach(p => {
    const grp = new THREE.Group(); grp.add(meshOf(p)); grp.updateMatrixWorld(true);
    if (engine.collidesWithWalls(grp)) carCollisions.push({ role: p.role, part_id: p.part_id, position: p.position });
  });
  const meshes = parts.map(meshOf);
  let unexpected = 0; const unexpectedDetails = [];
  for (let i = 0; i < meshes.length; i++) for (let j = i + 1; j < meshes.length; j++) {
    const A = new THREE.Box3().setFromObject(meshes[i]), B = new THREE.Box3().setFromObject(meshes[j]);
    const ox = Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x);
    const oy = Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y);
    const oz = Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z);
    if (ox > 0.5 && oy > 0.5 && oz > 0.5) {
      const bothProfile = parts[i].part_id === "Object_7" && parts[j].part_id === "Object_7";
      const isUhelnik = parts[i].role.startsWith("uhelnik") || parts[j].role.startsWith("uhelnik");
      const isEuroboxCap = (parts[i].part_id.startsWith("product_37") || parts[i].part_id === "product_3071" || parts[i].role.startsWith("uhelnik")) &&
                            (parts[j].part_id === "Object_7");
      const isEuroboxCap2 = (parts[j].part_id.startsWith("product_37") || parts[j].part_id === "product_3071" || parts[j].role.startsWith("uhelnik")) &&
                             (parts[i].part_id === "Object_7");
      const nestOk = (!bothProfile) || isUhelnik;
      if (!nestOk) { unexpected++; unexpectedDetails.push([parts[i].role, parts[j].role]); }
    }
  }
  return { carCollisions, unexpected, unexpectedDetails };
}

const results = {};
for (const [vKey, vCfg] of Object.entries(VEHICLES)) {
  const engine = createEngine(vCfg.base);
  const plan = runPipelineDoorFixed(engine, {});
  const merged = { ...plan, collidesWithWalls: engine.collidesWithWalls, buildLegObject: engine.buildLegObject, parseGlbMesh: engine.parseGlbMesh };
  results[vKey] = { doorGap: plan.doorGap, legs: plan.legs, columns: plan.columns, step5: plan.step5, step7: plan.step7, variants: {} };

  for (const [variantKey, heights] of Object.entries(vCfg.plans)) {
    const v = validateHeights(heights, plan.step5[0].finalFloorY, plan.step7[0].maxSafeBoxTop);
    if (!v.ok) throw new Error(`${vKey} ${variantKey}: neplatna skladba - ${v.reason}`);
    const asm = assemble(merged, [heights]);
    if (!asm.ok) throw new Error(`${vKey} ${variantKey}: assemble selhal: ${JSON.stringify({ badProfiles: asm.badProfiles, badOther: asm.badOther, unexpectedDetails: asm.unexpectedDetails })}`);

    const changes = applyDoorHeightRule(asm.parts, asm.legsMeta, vCfg.doorHeightMm, engine);

    // FRESH druhy pruchod - nezavisle overeni na hotovych (i po id=8 zmene) datech
    const verify = fullVerify(asm.parts, engine);
    const sanity = sanityCheckOverall(asm.parts, engine);

    results[vKey].variants[variantKey] = {
      heights, totalBoxes: asm.totalBoxes, distinctHeights: asm.distinctHeights,
      columnSummaries: asm.columnSummaries, bracketStats: asm.bracketStats,
      id8Changes: changes,
      verify: { carCollisions: verify.carCollisions.length, unexpected: verify.unexpected, unexpectedDetails: verify.unexpectedDetails },
      sanity,
      partsCount: asm.parts.length,
      parts: asm.parts,
    };
    console.log(`${vKey} ${variantKey}: boxes=${asm.totalBoxes} heights=${JSON.stringify(asm.distinctHeights)} carCollisions=${verify.carCollisions.length} unexpectedSelf=${verify.unexpected} id8changes=${changes.length} sanity(h/d/l)=${sanity.heightY.toFixed(0)}/${sanity.depthX.toFixed(0)}/${sanity.lengthZ.toFixed(0)}`);
    if (verify.carCollisions.length > 0) console.log("  CAR COLLISIONS:", JSON.stringify(verify.carCollisions.slice(0, 5)));
    if (verify.unexpected > 0) console.log("  UNEXPECTED SELF-COLLISIONS:", JSON.stringify(verify.unexpectedDetails.slice(0, 10)));
  }
}

fs.writeFileSync(`${SCRATCH}/doorvoid_build_all_result.json`, JSON.stringify(results, null, 1));
console.log("\nsaved to", `${SCRATCH}/doorvoid_build_all_result.json`);
