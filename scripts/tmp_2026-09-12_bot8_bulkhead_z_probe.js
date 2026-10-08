const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const THREE = require("three");
const KAT = "/opt/konfigurator/webapp/katalog/";

const BODIES = {
  "K-160e": "car_bodies/Peugeot_Partner_PE23_2021-",
  "K-090e": "car_bodies/Peugeot_Expert_PE25_2021-",
  "K-296":  "car_bodies/Opel_Vivaro_OP31_2020-",
  "K-020":  "car_bodies/Volkswagen_Caddy_VW32_2021-",
  "K-091":  "car_bodies/Peugeot_Expert_PE12_2007-2015",
  "K-096":  "car_bodies/Peugeot_Expert_PE17_2016-",
  "K-120":  "car_bodies/Citroën_Jumpy_CI13_2016-",
  "K-158":  "car_bodies/Peugeot_Partner_PE02_2008-2018",
  "K-237":  "car_bodies/Ford_Connect_FO12_2014-",
  "K-247":  "car_bodies/Ford_Custom_FO29_2012-2023",
  "K-254e": "car_bodies/Ford_Custom_FO39_2023-",
  "K-287":  "car_bodies/Volkswagen_Transporter_VW29_2024-",
  "K-294":  "car_bodies/Mercedes_Vito_MB25_2014-",
};

const out = {};
for (const [code, base] of Object.entries(BODIES)) {
  const path = KAT + base + "_B.glb";
  const m = parseGlbMesh(path);
  m.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(m);
  out[code] = { base, zmin: box.min.z, zmax: box.max.z, zcenter: (box.min.z+box.max.z)/2 };
  console.log(code, base, "Z:", box.min.z.toFixed(2), "..", box.max.z.toFixed(2));
}
require("fs").writeFileSync("/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/bulkhead_z.json", JSON.stringify(out, null, 1));
