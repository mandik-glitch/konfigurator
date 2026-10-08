// Prekompletni prestavba jedne Proace "A" sestavy proti DNESNI geometrii
// karoserie: runOne+buildFull (nova noha/boxy) + joint_count
// (autoRegisterTouchedProfileJoints - JEN Object_7<->Object_7, presne
// Robertovo pravidlo z scene.html:16397) + bom/price_summary presne podle
// computeAssemblyBomAndPrice (scene.html:4903), NE dnesni davkovou cestou.
//
// Vstup (argv[2], JSON): { cfg: {name,base,D,H,T,CUTOUT_H,CAP_H}, variant,
//   car_body_ids: [id,id,id] }
// Vystup: JSON {parts, join_groups:[], frame_groups:[], bom, price_summary, _note}
const fs = require("fs");
const THREE = require("three");
const { runOne } = require("/opt/konfigurator/scripts/2026-08-31_proace_run_one.js");
const { buildFull } = require("/opt/konfigurator/scripts/2026-08-31_proace_full_build.js");
const { planColumnExact } = require("/opt/konfigurator/scripts/2026-08-31_proace_heights.js");
const uhelLib = require("/opt/konfigurator/scripts/2026-09-01_uhelniky_leg_joints_lib.js");
const KAT_DIR = "/opt/konfigurator/webapp/katalog/";
const OBJ7_PATH = KAT_DIR + "Object_7.glb";
const UHEL_CATALOG = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/2026-09-01_uhelnik_catalog.json", "utf8"));

// Presna kopie predikatu z 2026-09-05_add_uhelniky_all_legs.js (overeny
// batch skript, READ-ONLY driv) - profil nohy, NE pricka patra/nosnik/
// eurobox.
function isLegProfile(p) {
  if (p.part_id !== "Object_7") return false;
  const r = p.role || "";
  if (/^spojnice-(sloupec|col)\d/.test(r)) return false;
  if (/^nosnik|^eurobox/.test(r)) return false;
  return /svislice|sloupek|spojnice-dolni|spojnice-horni|^cap$|pricka/.test(r);
}

function addUhelnikyToLegs(parts) {
  const byZ = {};
  for (const p of parts) {
    if (!p.position) continue;
    if (isLegProfile(p)) (byZ[Math.round(p.position[2])] ||= []).push(p);
  }
  const zs = Object.keys(byZ).map(Number).sort((a, b) => a - b);
  const nove = [];
  zs.forEach((z, legIdx) => {
    const legParts = byZ[z];
    const legEntries = legParts.map((p, idx) => uhelLib.makeProfileEntry(OBJ7_PATH, { ...p, idx, cross_section_mm: [30, 30] }));
    const { results } = uhelLib.applyUhelnikyToLeg(legEntries, UHEL_CATALOG, KAT_DIR);
    const badNaN = results.filter(r => r.position.some(v => !Number.isFinite(v)) || r.quaternion.some(v => !Number.isFinite(v)));
    if (!results.length || badNaN.length) {
      throw new Error(`uhelniky pro nohu z=${z} selhaly (results=${results.length}, badNaN=${badNaN.length})`);
    }
    for (const r of results) {
      nove.push({
        part_id: r.part_id,
        position: r.position.map(v => +v.toFixed(4)),
        quaternion: r.quaternion.map(v => +v.toFixed(6)),
        scale: r.scale ? r.scale.map(v => +v.toFixed(6)) : [1, 1, 1],
        role: "uhelnik-noha" + legIdx,
      });
    }
  });
  return nove;
}

const PRICING = {
  joint_price_czk: 110.0,
  profile_flat_fee_czk: 5.0,
  accessories_hardware_czk_per_joint: 0.0, // cfg_accessories je dnes prazdna
};
const CATALOG = {
  "Object_7": { is_profile: true, length_mm: 1000, price_czk: 231.33, weight_kg: 0.79, price_per_cut_czk: 50.0 },
  "product_3788": { price_czk: 160.0, weight_kg: 0 },
  "product_3793": { price_czk: 190.0, weight_kg: 0 },
  "product_3794": { price_czk: 210.0, weight_kg: 0 },
  "product_3795": { price_czk: 250.0, weight_kg: 0 },
  "product_3071": { price_czk: 5.0, weight_kg: 0.004 },
  "product_3045": { price_czk: 17.0, weight_kg: 0.021 },
};

function boxOf3(pos, quat, scale, halfExtents) {
  // half-extents lokalniho boxu (mm) - Object_7 je 30x1000x30 (T x L x T),
  // scale.y nese delku, x/z zustavaji 1.
  const m = new THREE.Matrix4().compose(
    new THREE.Vector3(...pos),
    new THREE.Quaternion(...quat),
    new THREE.Vector3(...scale)
  );
  const corners = [];
  for (const sx of [-1, 1]) for (const sy of [-1, 1]) for (const sz of [-1, 1]) {
    corners.push(new THREE.Vector3(sx * halfExtents[0], sy * halfExtents[1], sz * halfExtents[2]).applyMatrix4(m));
  }
  const box = new THREE.Box3();
  corners.forEach(c => box.expandByPoint(c));
  return box;
}

// autoRegisterTouchedProfileJoints presne: 1 osa faceClose<0.75, zbyle 2 osy
// FULL prekryv (min(sizeA,sizeB)-0.5). Jen Object_7<->Object_7.
function computeJointCounts(parts) {
  const profIdx = [];
  const boxes = [];
  parts.forEach((p, i) => {
    if (p.part_id !== "Object_7") return;
    profIdx.push(i);
    boxes[i] = boxOf3(p.position, p.quaternion, p.scale, [15, 500, 15]);
  });
  const jointCount = new Array(parts.length).fill(0);
  const AX = ["x", "y", "z"];
  for (let ii = 0; ii < profIdx.length; ii++) {
    for (let jj = ii + 1; jj < profIdx.length; jj++) {
      const i = profIdx[ii], j = profIdx[jj];
      const A = boxes[i], B = boxes[j];
      let touching = false;
      for (let ax = 0; ax < 3 && !touching; ax++) {
        const a = AX[ax];
        const faceClose = Math.abs(A.max[a] - B.min[a]) < 0.75 || Math.abs(A.min[a] - B.max[a]) < 0.75;
        if (!faceClose) continue;
        let overlaps = true;
        for (let k = 0; k < 3; k++) {
          if (k === ax) continue;
          const oa = AX[k];
          const lo = Math.max(A.min[oa], B.min[oa]), hi = Math.min(A.max[oa], B.max[oa]);
          const sizeA = A.max[oa] - A.min[oa], sizeB = B.max[oa] - B.min[oa];
          const minSize = Math.min(sizeA, sizeB);
          if ((hi - lo) < (minSize - 0.5)) { overlaps = false; break; }
        }
        if (overlaps) touching = true;
      }
      if (touching) jointCount[i] += 1; // pocitano jen jednou za dvojici (na strane i)
    }
  }
  return jointCount;
}

function computeBomAndPrice(parts) {
  const jointCount = computeJointCounts(parts);
  let totalW = 0, totalMaterial = 0, totalAccessory = 0, totalCut = 0, totalProfiles = 0, totalJoints = 0;
  const itemGroups = new Map();
  parts.forEach((p, i) => {
    const cat = CATALOG[p.part_id];
    if (!cat) throw new Error("neznamy dil v katalogu (pro cenu): " + p.part_id);
    const isProfile = !!cat.is_profile;
    let price, weight, lenRounded = null;
    if (isProfile) {
      const lenNow = cat.length_mm * p.scale[1];
      price = cat.price_czk * p.scale[1];
      weight = cat.weight_kg * p.scale[1];
      lenRounded = Math.round(lenNow);
      totalProfiles++;
      totalCut += cat.price_per_cut_czk || 0;
      totalMaterial += price;
    } else {
      price = cat.price_czk;
      weight = cat.weight_kg || 0;
      totalAccessory += price;
    }
    totalW += weight || 0;
    totalJoints += jointCount[i];
    const key = `${p.part_id}|${lenRounded}`;
    const unit = Math.round(price);
    let g = itemGroups.get(key);
    if (g) g.qty += 1;
    else { g = { part_id: p.part_id, lenRounded, unit_price: unit, qty: 1 }; itemGroups.set(key, g); }
  });
  const totalProfileFlatFee = totalProfiles * PRICING.profile_flat_fee_czk;
  const totalJointPrice = totalJoints * PRICING.joint_price_czk;
  const grandTotal = totalMaterial + totalAccessory + totalCut + totalProfileFlatFee + totalJointPrice;
  const bom = [...itemGroups.values()].map(g => ({
    part_id: g.part_id, dim: g.lenRounded != null ? g.lenRounded + " mm" : "-",
    qty: g.qty, unit_price: g.unit_price, total: Math.round(g.unit_price * g.qty),
  }));
  return {
    bom,
    price_summary: {
      count: parts.length,
      weight_kg: Math.round(totalW * 1000) / 1000,
      material_czk: Math.round(totalMaterial),
      cut_czk: Math.round(totalCut),
      profile_flat_fee_czk: Math.round(totalProfileFlatFee),
      joint_czk: Math.round(totalJointPrice),
      joint_count: totalJoints,
      accessory_czk: Math.round(totalAccessory),
      total_czk: Math.round(grandTotal),
    },
    jointCount,
  };
}

const input = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const step = runOne(input.cfg);
if (!step.ok) { console.error(JSON.stringify({ error: "runOne selhalo", step })); process.exit(1); }

// input.column_heights (volitelne): pole poli vysek bottom->top, JEDNO
// pole na kazdy sloupec (paralelni index se step.columns) - kdyz je
// pritomne, POUZE overi, ze presna predepsana skladba fyzicky sedi
// (planColumnExact), nevybira nic sam (viz komentar u planColumnExact).
let columnsLevelsOverride = null;
if (input.column_heights) {
  if (input.column_heights.length !== step.columns.length) {
    console.error(JSON.stringify({ error: `column_heights ma ${input.column_heights.length} polozek, ale step ma ${step.columns.length} sloupcu` }));
    process.exit(1);
  }
  try {
    columnsLevelsOverride = input.column_heights.map((heights, ci) =>
      planColumnExact(step.floorByCol[ci], step.TOP_Y, step.ceilByCol[ci], step.cfg.T, heights));
  } catch (e) {
    console.error(JSON.stringify({ error: "predepsana skladba boxu se fyzicky nevejde", detail: e.message }));
    process.exit(1);
  }
}

const result = buildFull(step, columnsLevelsOverride);
if (!result.ok) { console.error(JSON.stringify({ error: "buildFull ok=false", carCollisionProfiles: result.carCollisionProfiles, euroboxCarCollision: result.euroboxCarCollision, unexpected: result.unexpected, badPairs: result.badPairs })); process.exit(1); }

const uhelniky = addUhelnikyToLegs(result.parts);
const allConstructionParts = [...result.parts, ...uhelniky];

const carBodyParts = (input.car_body_ids || []).map(id => ({ part_id: `car_body_${id}`, position: [0,0,0], quaternion: [0,0,0,1], scale: [1,1,1] }));
const { bom, price_summary, jointCount } = computeBomAndPrice(allConstructionParts);
const partsOut = allConstructionParts.map((p, i) => {
  const out = { ...p };
  if (jointCount[i] > 0) out.joint_count = jointCount[i];
  return out;
});

const outData = {
  parts: [...carBodyParts, ...partsOut],
  join_groups: [], frame_groups: [],
  bom, price_summary,
  _note: `Přegenerováno ${new Date().toISOString().slice(0,10)} proti aktuální geometrii karoserie (bot8, nález bot9/bot3 - stará data postavena před opravou karoserie).`,
};
console.log(JSON.stringify(outData));
console.error("OK boxes=" + result.totalBoxes + " heights=" + JSON.stringify(result.distinctHeights) + " dily=" + result.parts.length + " uhelniku=" + uhelniky.length + " joint_count=" + price_summary.joint_count + " total_czk=" + price_summary.total_czk);
