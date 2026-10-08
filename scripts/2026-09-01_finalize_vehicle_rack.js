// Stage 7: full assembly (legs+endcaps+rails+connectors+euroboxes), collision +
// self-collision verification, Box3-derived 2D dimension check, then optional
// DB insert into product_assemblies. Adapted from
// scripts/tmp_2026-08-31_vivaro_build_full.js, generalized across vehicles.
const THREE = require("three");
const fs = require("fs");
const { execSync } = require("child_process");
const { makeCollisionModule } = require("/opt/konfigurator/scripts/2026-09-01_collision_module_factory.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const { T, half, W, buildPlain, buildVyrez, FAMILY } = require("/opt/konfigurator/scripts/2026-09-01_leg_local_shapes.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const CARB = KAT + "car_bodies/";
const OBJ7 = KAT + "Object_7.glb";
const ENDCAP = KAT + "product_3071.glb";
const EUROBOX_GLB = { 120: KAT + "product_3788.glb", 170: KAT + "product_3793.glb", 220: KAT + "product_3794.glb", 270: KAT + "product_3795.glb" };
const EUROBOX_PID = { 120: "product_3788", 170: "product_3793", 220: "product_3794", 270: "product_3795" };
const CONNECTOR_POS = { 1: [15, 415], 2: [15, 415, 816], 3: [15, 415, 816, 1217] };
const Q_ALONG_Z = [-0.707107, 0, 0, 0.707107];
const Q_ALONG_X = [0, 0, -0.707107, 0.707107];
const Q_ENDCAP_UP = [0.7071067811865475, 0, 0, 0.7071067811865475];
const CAP_FLANGE_THICKNESS = 3;

function glbFor(id) {
  if (id === "Object_7") return OBJ7;
  if (id === "product_3071") return ENDCAP;
  for (const h in EUROBOX_PID) if (EUROBOX_PID[h] === id) return EUROBOX_GLB[h];
  return null;
}
function meshOf(p) {
  const m = parseGlbMesh(glbFor(p.part_id));
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}

function finalize(cfg, res) {
  const fam = FAMILY[cfg.family];
  const { H, CAP_H, capOffsetFromW } = fam;
  const mod = makeCollisionModule(CARB + cfg.base);
  const { collidesWithWalls } = mod;
  const { offsetX, offsetY, legs, columnPlans, columnLevels, legExtensions } = res;
  const TOP_Y = H - CAP_H;

  function toWorld(localParts, anchorZ) {
    return localParts.map(p => ({
      part_id: p.part_id || "Object_7",
      position: [offsetX - p.position[0], p.position[1] + offsetY, anchorZ + p.position[2]],
      quaternion: p.quaternion, scale: p.scale, role: p.role,
    }));
  }
  function legEndcapRoles(type) { return type === "vyrez" ? ["predni-svislice", "zadni-svislice-nad-zarezem", "cap"] : ["predni-svislice", "zadni-svislice-dolni", "cap"]; }
  function topEndcapsFor(legParts, roles) {
    return legParts.filter(p => roles.includes(p.role)).map(p => {
      const lenMm = p.scale[1] * 1000;
      const topY = p.position[1] + lenMm / 2 + CAP_FLANGE_THICKNESS;
      return { part_id: "product_3071", position: [p.position[0], topY, p.position[2]], quaternion: Q_ENDCAP_UP, scale: [1, 1, 1], role: "zaslepka-" + p.role };
    });
  }

  let allParts = [];
  legs.forEach((leg, idx) => {
    let localParts;
    if (leg.type === "plain") {
      localParts = buildPlain(H, CAP_H, capOffsetFromW);
    } else {
      const yNew = legExtensions[idx];
      const cutout = (yNew && yNew < fam.CUTOUT_H) ? yNew : fam.CUTOUT_H;
      localParts = buildVyrez(H, CAP_H, cutout, fam.uskok, capOffsetFromW, fam.hasBottomCrossVyrez);
    }
    const endcaps = topEndcapsFor(localParts, legEndcapRoles(leg.type));
    allParts.push(...toWorld([...localParts, ...endcaps], leg.anchorZ));
  });

  columnPlans.forEach((cp, colIdx) => {
    const levels = columnLevels[colIdx].levels;
    levels.forEach((level, levelIdx) => {
      const Y = level.railYCenter;
      allParts.push({ part_id: "Object_7", position: [offsetX - half, Y + offsetY, cp.railZCenter], quaternion: Q_ALONG_Z, scale: [1, cp.railLen / 1000, 1], role: `nosnik-sloupec${colIdx}-patro${levelIdx}` });
      allParts.push({ part_id: "Object_7", position: [offsetX - (W - half), Y + offsetY, cp.railZCenter], quaternion: Q_ALONG_Z, scale: [1, cp.railLen / 1000, 1], role: `nosnik-sloupec${colIdx}-patro${levelIdx}` });
      CONNECTOR_POS[cp.N].forEach(localZ => {
        allParts.push({ part_id: "Object_7", position: [offsetX - cp.crossXCenter, Y + offsetY, cp.railZFrom + localZ], quaternion: Q_ALONG_X, scale: [1, cp.crossLen / 1000, 1], role: `spojnice-sloupec${colIdx}-patro${levelIdx}` });
      });
      const positions = CONNECTOR_POS[cp.N];
      for (let i = 0; i < positions.length - 1; i++) {
        allParts.push({
          part_id: EUROBOX_PID[level.boxH], position: [0, 0, 0], quaternion: Q_ALONG_Z, scale: [1, 1, 1], role: `eurobox-sloupec${colIdx}-patro${levelIdx}`,
          _pending: { slotZFrom: cp.railZFrom + positions[i], slotZTo: cp.railZFrom + positions[i + 1], railYCenter: Y + offsetY, boxH: level.boxH },
        });
      }
    });
  });

  const probeCache = {};
  function probeFor(h) {
    if (probeCache[h]) return probeCache[h];
    const m = parseGlbMesh(EUROBOX_GLB[h]);
    m.position.set(0, 0, 0); m.quaternion.set(...Q_ALONG_Z); m.scale.set(1, 1, 1);
    m.updateMatrixWorld(true);
    const b = new THREE.Box3().setFromObject(m);
    const center = [(b.min.x + b.max.x) / 2, (b.min.y + b.max.y) / 2, (b.min.z + b.max.z) / 2];
    return (probeCache[h] = { box: b, center });
  }
  const targetXcenter = offsetX - W / 2;
  allParts.forEach(p => {
    if (!p._pending) return;
    const { slotZFrom, slotZTo, railYCenter, boxH } = p._pending;
    const probe = probeFor(boxH);
    const targetZcenter = (slotZFrom + slotZTo) / 2;
    const targetYbottom = railYCenter + T / 2;
    p.position = [targetXcenter - probe.center[0], targetYbottom - probe.box.min.y - 12, targetZcenter - probe.center[2]];
    p.quaternion = [...Q_ALONG_Z];
    delete p._pending;
  });

  // ---- verification: collision vs car body (profiles + euroboxes) ----
  const profileParts = allParts.filter(p => p.part_id === "Object_7");
  const profGroup = mod.buildLegObject(profileParts);
  const carCollisionProfiles = collidesWithWalls(profGroup);
  let euroboxCarCollision = false;
  const badEurobox = [];
  allParts.filter(p => p.part_id.startsWith("product_37")).forEach(p => {
    const grp = new THREE.Group(); grp.add(meshOf(p)); grp.updateMatrixWorld(true);
    if (collidesWithWalls(grp)) { euroboxCarCollision = true; badEurobox.push(p.role); }
  });

  // ---- self-collision (expected nesting vs unexpected) ----
  const meshes = allParts.map(meshOf);
  let unexpected = 0, expected = 0;
  const unexpectedList = [];
  for (let i = 0; i < meshes.length; i++) for (let j = i + 1; j < meshes.length; j++) {
    const A = new THREE.Box3().setFromObject(meshes[i]), B = new THREE.Box3().setFromObject(meshes[j]);
    const ox = Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x);
    const oy = Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y);
    const oz = Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z);
    if (ox > 0.5 && oy > 0.5 && oz > 0.5) {
      const nestOk = allParts[i].part_id !== "Object_7" || allParts[j].part_id !== "Object_7";
      if (nestOk) expected++;
      else { unexpected++; unexpectedList.push([allParts[i].role, allParts[j].role, ox.toFixed(1), oy.toFixed(1), oz.toFixed(1)]); }
    }
  }

  // ---- 2D verification gate: Box3-derived overall envelope + per-part dump ----
  const overallBox = new THREE.Box3();
  meshes.forEach(m => overallBox.union(new THREE.Box3().setFromObject(m)));
  const dims = { widthX: overallBox.max.x - overallBox.min.x, heightY: overallBox.max.y - overallBox.min.y, lengthZ: overallBox.max.z - overallBox.min.z };
  // rail-containment check: every rail/connector part's world box must lie within
  // [legFrom.anchorZ, legTo.anchorZ+T] for its column (no overhang past the leg pair)
  let railContainmentOk = true;
  const railIssues = [];
  columnPlans.forEach((cp) => {
    const zLo = cp.railZFrom - 1e-3, zHi = cp.railZTo + 1e-3;
    allParts.filter(p => (p.role || "").includes(`sloupec${cp.colIdx}-`) && p.part_id === "Object_7").forEach(p => {
      const b = new THREE.Box3().setFromObject(meshOf(p));
      if (b.min.z < zLo - 0.5 || b.max.z > zHi + 0.5) { railContainmentOk = false; railIssues.push({ role: p.role, minZ: b.min.z, maxZ: b.max.z, zLo, zHi }); }
    });
  });

  const clean = allParts.map(({ _pending, ...rest }) => rest);
  const summary = {
    key: cfg.key, carCollisionProfiles, euroboxCarCollision, badEurobox,
    unexpected, expected, totalParts: clean.length, dims, railContainmentOk, railIssues: railIssues.slice(0, 5),
    passesGate: !carCollisionProfiles && !euroboxCarCollision && unexpected === 0 && railContainmentOk,
  };
  return { parts: clean, summary };
}

module.exports = { finalize };

if (require.main === module) {
  const key = process.argv[2];
  const configs = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/2026-09-01_vehicle_configs.json", "utf8"));
  const cfg = configs.find(c => c.key === key);
  const res = JSON.parse(fs.readFileSync(`/opt/konfigurator/scripts/2026-09-01_result_${key}.json`, "utf8"));
  const { parts, summary } = finalize(cfg, res);
  fs.writeFileSync(`/opt/konfigurator/scripts/2026-09-01_final_parts_${key}.json`, JSON.stringify(parts));
  fs.writeFileSync(`/opt/konfigurator/scripts/2026-09-01_final_summary_${key}.json`, JSON.stringify(summary, null, 1));
  console.log(key, JSON.stringify(summary));
}
