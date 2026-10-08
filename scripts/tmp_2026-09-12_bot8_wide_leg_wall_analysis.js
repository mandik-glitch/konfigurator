const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh, glbBoundingBox } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const KAT = "/opt/konfigurator/webapp/katalog/";

const GROUPS = [
  { label: "PROACE_Compact", file: "rep_PROACE_Compact", carBase: "Toyota_Proace_TO07_2020-" },
  { label: "PROACE_Medium", file: "rep_PROACE_Medium", carBase: "Toyota_Proace_TO08_2020-" },
  { label: "PROACE_Long", file: "rep_PROACE_Long", carBase: "Toyota_Proace_TO09_2020-" },
  { label: "PROACE_MediumCrew", file: "rep_PROACE_MediumCrew", carBase: "Toyota_Proace_TO12_2020-" },
  { label: "PROACE_LongCrew", file: "rep_PROACE_LongCrew", carBase: "Toyota_Proace_TO17_2020-" },
  { label: "PROACE_MediumElec", file: "rep_PROACE_MediumElec", carBase: "Toyota_Proace_TO21_2020-" },
  { label: "PROACE_LongElec", file: "rep_PROACE_LongElec", carBase: "Toyota_Proace_TO22_2020-" },
  { label: "PROACE_CompactElec", file: "rep_PROACE_CompactElec", carBase: "Toyota_Proace_TO23_2020-" },
  { label: "K159", file: "rep_K159", carBase: "Peugeot_Partner_PE18_2019-" },
  { label: "K239", file: "rep_K239", carBase: "Ford_Connect_FO13_2014-" },
  { label: "K248e", file: "rep_K248e", carBase: "Ford_Custom_FO38_2023-" },
  { label: "K255", file: "rep_K255", carBase: "Ford_Custom_FO11_2012-2023" },
  { label: "K288", file: "rep_K288", carBase: "Volkswagen_Transporter_VW30_2024-" },
  { label: "K295", file: "rep_K295", carBase: "Mercedes_Vito_MB24_2014-" },
];

const legRoles = ["predni-svislice","zadni-svislice","zadni-svislice-dolni","zadni-svislice-nad-zarezem","sloupek-pred-podbehem","pricka-uzavreni-vyrezu"];

for (const g of GROUPS) {
  const data = JSON.parse(fs.readFileSync(`/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/data/${g.file}.json`, "utf8"));
  const parts = data.parts.filter(p => !String(p.part_id||"").startsWith("car_body_"));

  // B wall bbox (real GLB)
  let bBox;
  try {
    bBox = glbBoundingBox(KAT + "car_bodies/" + g.carBase + "_B.glb");
  } catch(e) {
    console.log(g.label, "ERROR loading B wall:", e.message);
    continue;
  }

  // cluster Z by column roles
  const zMap = {}; // roundedZ -> {roles:Set, count}
  for (const p of parts) {
    if (!legRoles.includes(p.role)) continue;
    const z = p.position[2];
    // find existing cluster within 2mm
    let key = Object.keys(zMap).find(k => Math.abs(parseFloat(k) - z) < 2);
    if (!key) { key = z.toFixed(3); zMap[key] = { roles: {}, zs: [] }; }
    zMap[key].roles[p.role] = (zMap[key].roles[p.role]||0) + 1;
    zMap[key].zs.push(z);
  }
  console.log(`\n=== ${g.label} ===  B-wall Z range: [${bBox.min.z.toFixed(1)}, ${bBox.max.z.toFixed(1)}]  center=${bBox.center.z.toFixed(1)}`);
  const cols = Object.keys(zMap).map(k => parseFloat(k)).sort((a,b)=>a-b);
  for (const z of cols) {
    const key = Object.keys(zMap).find(k => Math.abs(parseFloat(k)-z)<2);
    const info = zMap[key];
    const avgZ = info.zs.reduce((a,b)=>a+b,0)/info.zs.length;
    const distToWall = Math.min(Math.abs(avgZ - bBox.min.z), Math.abs(avgZ - bBox.max.z));
    const isCutout = !!info.roles["zadni-svislice-nad-zarezem"];
    console.log(`  col Z=${avgZ.toFixed(2)} roles=${JSON.stringify(info.roles)} isCutout=${isCutout} distToBwall=${distToWall.toFixed(1)}`);
  }
}
