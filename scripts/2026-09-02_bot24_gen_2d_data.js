const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";
const CARB = KAT + "car_bodies/";

function glbForPart(partId) {
  if (partId === "Object_7") return KAT + "Object_7.glb";
  if (partId === "product_3071") return KAT + "product_3071.glb";
  if (partId.startsWith("product_37")) return KAT + partId + ".glb";
  return null;
}
function boxOf(p) {
  const glb = glbForPart(p.part_id);
  const m = parseGlbMesh(glb);
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale); m.updateMatrixWorld(true);
  const b = new THREE.Box3().setFromObject(m);
  return { min: [b.min.x, b.min.y, b.min.z], max: [b.max.x, b.max.y, b.max.z], role: p.role, part_id: p.part_id };
}

function processRow(rowId, bodyPrefix, offset) {
  const d = JSON.parse(fs.readFileSync(`/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad/final_row_${rowId}.json`, "utf8"));
  const nonCarBody = d.parts.filter(p => !p.part_id.startsWith("car_body_"));
  const boxes = nonCarBody.map(boxOf);
  const wallL = parseGlbMesh(CARB + bodyPrefix + "_L.glb");
  wallL.position.set(...offset); wallL.updateMatrixWorld(true);
  const bw = new THREE.Box3().setFromObject(wallL);
  return { rowId, boxes, wallBox: { min:[bw.min.x,bw.min.y,bw.min.z], max:[bw.max.x,bw.max.y,bw.max.z] } };
}

function processOld(path) {
  const d = JSON.parse(fs.readFileSync(path, "utf8"));
  const nonCarBody = d.parts.filter(p => !p.part_id.startsWith("car_body_"));
  return { boxes: nonCarBody.map(boxOf) };
}

const out = {
  vw31: processRow(126, "Volkswagen_Caddy_VW31_2021-", [0,-1651.5,0]),
  vw22: processRow(125, "Volkswagen_Caddy_VW22_2021-", [0,0,0]),
  vw31_old: processOld("/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad/pa_126_raw.json"),
  vw22_old: processOld("/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad/pa_125_raw.json"),
};
fs.writeFileSync("/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad/gen_2d_data_out.json", JSON.stringify(out));
console.log("done", out.vw31.boxes.length, out.vw22.boxes.length);
