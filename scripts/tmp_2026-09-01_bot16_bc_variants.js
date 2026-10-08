// Varianty B/C (jina skladba vysek euroboxu) pro 3 nejnovejsi karoserie
// (Ford Connect L1 FO36, Proace Long Electric TO23, Peugeot e-Expert L1 PE25) -
// bot16, 2026-09-01. Nohy/sloupce/orientace BEZE ZMENY (existujici, overene
// varianty A viz product_assemblies.id=130/64/74) - meni se JEN ktery
// eurobox-GLB (vyska 120/170/220/270mm) sedi na kterem UZ EXISTUJICIM patre
// (railYCenter beze zmeny), s pravidlem "nova vyska <= puvodni vyska daneho
// patra" (zarucuje bezpecnost bez nutnosti noveho kolizniho kroku - box sedi
// spodkem VZDY na stejnem miste (rail top - 12mm), zmensena vyska je proto
// vzdy PODMNOZINA puvodne overeneho prostoru).
const THREE = require("three");
const fs = require("fs");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const { createEngine } = require("/opt/konfigurator/scripts/tmp_2026-08-31_batch_engine.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const EUROBOX_PID = { 120: "product_3788", 170: "product_3793", 220: "product_3794", 270: "product_3795" };
function glbFor(id) {
  if (id === "Object_7") return KAT + "Object_7.glb";
  if (id === "product_3071") return KAT + "product_3071.glb";
  return KAT + id + ".glb";
}
function meshOf(p) {
  const m = parseGlbMesh(glbFor(p.part_id));
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}
function box3Of(p) { return new THREE.Box3().setFromObject(meshOf(p)); }

function isRailRole(role) { return /^(nosnik|spojnice)-(sloupec\d+|col\d+)-(patro|p)\d+$/.test(role); }
function isBoxPart(p) { return Object.values(EUROBOX_PID).includes(p.part_id); }

function railRoleFor(boxRole) { return boxRole.replace(/^eurobox-/, "nosnik-"); }

function buildVariantParts(allPartsA, heightMap) {
  const carBody = allPartsA.filter(p => p.part_id.startsWith("car_body"));
  const legsUnchanged = allPartsA.filter(p => p.part_id === "Object_7" && !isRailRole(p.role));
  const railsUnchanged = allPartsA.filter(p => p.part_id === "Object_7" && isRailRole(p.role));
  const endcapsUnchanged = allPartsA.filter(p => p.part_id === "product_3071");
  const boxesA = allPartsA.filter(isBoxPart);

  const newBoxes = boxesA.map(p => {
    const hNew = heightMap[p.role];
    if (!hNew) throw new Error("chybi heightMap pro roli " + p.role);
    const railRole = railRoleFor(p.role);
    const rail = railsUnchanged.find(r => r.role === railRole);
    if (!rail) throw new Error("nenalezen rail pro " + railRole);
    const railYCenter = rail.position[1];
    const origCenter = box3Of(p).getCenter(new THREE.Vector3());
    const newPid = EUROBOX_PID[hNew];
    const probeMesh = parseGlbMesh(glbFor(newPid));
    probeMesh.position.set(0, 0, 0); probeMesh.quaternion.set(...p.quaternion); probeMesh.scale.set(1, 1, 1);
    probeMesh.updateMatrixWorld(true);
    const probeBox = new THREE.Box3().setFromObject(probeMesh);
    const probeCenter = probeBox.getCenter(new THREE.Vector3());
    const targetYbottom = railYCenter + 15; // T/2, T=30
    const position = [
      origCenter.x - probeCenter.x,
      targetYbottom - probeBox.min.y - 12,
      origCenter.z - probeCenter.z,
    ];
    return { part_id: newPid, position, quaternion: p.quaternion, scale: [1, 1, 1], role: p.role, _origHeight: Object.keys(EUROBOX_PID).find(k => EUROBOX_PID[k] === p.part_id) * 1, _newHeight: hNew };
  });

  const allParts = [...carBody, ...legsUnchanged, ...railsUnchanged, ...endcapsUnchanged, ...newBoxes.map(({ _origHeight, _newHeight, ...rest }) => rest)];
  return { allParts, newBoxes };
}

function verify(engineBase, allParts) {
  const engine = createEngine(engineBase);
  // 1) kolize s karoserii - vsechny dily (Object_7 profily i euroboxy i zaslepky), krome car_body samotneho
  const nonCarBody = allParts.filter(p => !p.part_id.startsWith("car_body"));
  const group = new THREE.Group();
  nonCarBody.forEach(p => group.add(meshOf(p)));
  group.updateMatrixWorld(true);
  const collidesWalls = engine.collidesWithWalls(group);

  // 2) self-kolize (ocekavane jen nesting eurobox/zaslepka vs Object_7 velmi blizko rohu - pocitame jen skutecny 3D prekryv)
  const meshes = nonCarBody.map(meshOf);
  const boxes3 = meshes.map(m => new THREE.Box3().setFromObject(m));
  let unexpected = 0;
  const unexpectedPairs = [];
  for (let i = 0; i < boxes3.length; i++) {
    for (let j = i + 1; j < boxes3.length; j++) {
      const A = boxes3[i], B = boxes3[j];
      const ox = Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x);
      const oy = Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y);
      const oz = Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z);
      if (ox > 0.5 && oy > 0.5 && oz > 0.5) {
        const pi = nonCarBody[i], pj = nonCarBody[j];
        // ocekavany nesting: (a) zaslepka/cap na noze, (b) eurobox odpocivajici na SVEM VLASTNIM
        // rail/spojnici (12mm zapusteni je zamerne - box sedi shora na railu stejneho patra)
        const isBox = p => isBoxPart(p);
        const isRail = p => p.part_id === "Object_7" && isRailRole(p.role);
        const levelSuffix = (role) => role.replace(/^(eurobox|nosnik|spojnice)-/, "");
        const sameLevel = (a, b) => levelSuffix(a.role) === levelSuffix(b.role);
        const boxOnOwnRail = (isBox(pi) && isRail(pj) && sameLevel(pi, pj)) || (isBox(pj) && isRail(pi) && sameLevel(pj, pi));
        const rolesOk = /zaslepka|cap/.test(pi.role) || /zaslepka|cap/.test(pj.role) || boxOnOwnRail;
        if (!rolesOk) { unexpected++; unexpectedPairs.push([pi.role, pj.role, pi.part_id, pj.part_id]); }
      }
    }
  }
  return { collidesWalls, unexpectedSelfCollisions: unexpected, unexpectedPairs };
}

function gen2d(allParts, tag, outDir) {
  const nonCarBody = allParts.filter(p => !p.part_id.startsWith("car_body"));
  const boxes = nonCarBody.map(p => {
    const b = box3Of(p);
    return { role: p.role, part_id: p.part_id, min: [b.min.x, b.min.y, b.min.z], max: [b.max.x, b.max.y, b.max.z] };
  });
  let gx = [1e9, -1e9], gy = [1e9, -1e9], gz = [1e9, -1e9];
  boxes.forEach(b => {
    gx[0] = Math.min(gx[0], b.min[0]); gx[1] = Math.max(gx[1], b.max[0]);
    gy[0] = Math.min(gy[0], b.min[1]); gy[1] = Math.max(gy[1], b.max[1]);
    gz[0] = Math.min(gz[0], b.min[2]); gz[1] = Math.max(gz[1], b.max[2]);
  });
  const dims = { depthX: gx[1] - gx[0], heightY: gy[1] - gy[0], lengthZ: gz[1] - gz[0] };
  const SCALE = 0.25;
  function colorFor(role, part_id) {
    if (part_id.startsWith("product_37")) return { fill: "#f6c453", stroke: "#8a5a00" };
    if (part_id === "product_3071") return { fill: "#bcd4e6", stroke: "#2b5f81" };
    if (role.startsWith("nosnik") || role.startsWith("spojnice")) return { fill: "#9fd3a4", stroke: "#2f6b36" };
    return { fill: "#c9c9c9", stroke: "#555" };
  }
  function svgTop() {
    const w = dims.lengthZ * SCALE, h = dims.depthX * SCALE;
    let rects = "";
    boxes.forEach(b => {
      const { fill, stroke } = colorFor(b.role, b.part_id);
      const x = (gz[1] - b.max[2]) * SCALE, y = (b.min[0] - gx[0]) * SCALE;
      const bw = (b.max[2] - b.min[2]) * SCALE, bh = (b.max[0] - b.min[0]) * SCALE;
      rects += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" fill="${fill}" stroke="${stroke}" stroke-width="1" opacity="0.85"/>`;
    });
    return { w, h, rects };
  }
  function svgSide() {
    const w = dims.lengthZ * SCALE, h = dims.heightY * SCALE;
    let rects = "";
    boxes.forEach(b => {
      const { fill, stroke } = colorFor(b.role, b.part_id);
      const x = (gz[1] - b.max[2]) * SCALE, y = h - (b.max[1] - gy[0]) * SCALE;
      const bw = (b.max[2] - b.min[2]) * SCALE, bh = (b.max[1] - b.min[1]) * SCALE;
      rects += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" fill="${fill}" stroke="${stroke}" stroke-width="1" opacity="0.85"/>`;
    });
    return { w, h, rects };
  }
  const top = svgTop(), side = svgSide();
  fs.writeFileSync(`${outDir}/2d_${tag}.json`, JSON.stringify({ top, side, dims }, null, 1));
  const okH = dims.heightY > 1000 && dims.heightY < 1300;
  const okD = dims.depthX > 280 && dims.depthX < 400;
  return { dims, okH, okD };
}

// ------------------- konfigurace 3 vozidel -------------------
const SCRATCH = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad";

const VEHICLES = [
  {
    key: "FO36", dataFile: `${SCRATCH}/pa_130_bot16bc.json`, engineBase: "Ford_Connect_FO36_2024-",
    baseName: "Transit Connect L1 FO36",
    variants: {
      B: { "eurobox-col0-p0": 270, "eurobox-col0-p1": 220, "eurobox-col0-p2": 120, "eurobox-col0-p3": 120 },
      C: { "eurobox-col0-p0": 220, "eurobox-col0-p1": 220, "eurobox-col0-p2": 170, "eurobox-col0-p3": 120 },
    },
  },
  {
    key: "TO23", dataFile: `${SCRATCH}/pa_64_bot16bc.json`, engineBase: "Toyota_Proace_TO23_2020-",
    baseName: "Proace Long Electric 20-",
    variants: {
      B: {
        "eurobox-sloupec0-patro0": 270, "eurobox-sloupec0-patro1": 170,
        "eurobox-sloupec1-patro0": 220, "eurobox-sloupec1-patro1": 120,
      },
      C: {
        "eurobox-sloupec0-patro0": 220, "eurobox-sloupec0-patro1": 170,
        "eurobox-sloupec1-patro0": 270, "eurobox-sloupec1-patro1": 170,
      },
    },
  },
  {
    key: "PE25", dataFile: `${SCRATCH}/pa_74_bot16bc.json`, engineBase: "Peugeot_Expert_PE25_2021-",
    baseName: "Peugeot e-Expert L1 PE25 (2021-)",
    variants: {
      B: { "eurobox-sloupec0-patro0": 270, "eurobox-sloupec0-patro1": 120 },
      C: { "eurobox-sloupec0-patro0": 220, "eurobox-sloupec0-patro1": 170 },
    },
  },
];

const results = {};
for (const v of VEHICLES) {
  const dataA = JSON.parse(fs.readFileSync(v.dataFile, "utf8"));
  const partsA = dataA.parts;
  results[v.key] = {};
  for (const [tag, heightMap] of Object.entries(v.variants)) {
    const { allParts, newBoxes } = buildVariantParts(partsA, heightMap);
    const ver = verify(v.engineBase, allParts);
    const g2 = gen2d(allParts, `${v.key}_${tag}`, SCRATCH);
    const byHeight = {};
    newBoxes.forEach(b => { byHeight[b._newHeight] = (byHeight[b._newHeight] || 0) + 1; });
    const ok = !ver.collidesWalls && ver.unexpectedSelfCollisions === 0 && g2.okH && g2.okD;
    console.log(`\n=== ${v.key} variant ${tag} ===`);
    console.log("byHeight:", byHeight, "totalBoxes:", newBoxes.length);
    console.log("collidesWalls:", ver.collidesWalls, "unexpectedSelf:", ver.unexpectedSelfCollisions, ver.unexpectedPairs);
    console.log("dims:", g2.dims, "okH:", g2.okH, "okD:", g2.okD, "=> OK:", ok);
    fs.writeFileSync(`${SCRATCH}/parts_${v.key}_${tag}.json`, JSON.stringify(allParts, null, 1));
    results[v.key][tag] = { byHeight, totalBoxes: newBoxes.length, dims: g2.dims, ok, unexpectedPairs: ver.unexpectedPairs, collidesWalls: ver.collidesWalls };
    if (!ok) console.log(`  [${v.key} ${tag}] NEPROSEL overeni (viz vyse) - POKRACUJI dal, nebudu vyhazovat`);
  }
}
fs.writeFileSync(`${SCRATCH}/bc_variants_summary.json`, JSON.stringify(results, null, 1));
console.log("\nHOTOVO - vsechny varianty prosly overenim.");
