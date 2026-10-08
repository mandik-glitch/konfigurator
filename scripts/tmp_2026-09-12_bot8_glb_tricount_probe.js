const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";
const BASES = [
 "car_bodies/Peugeot_Partner_PE23_2021-","car_bodies/Peugeot_Expert_PE25_2021-","car_bodies/Opel_Vivaro_OP31_2020-",
 "car_bodies/Volkswagen_Caddy_VW32_2021-","car_bodies/Peugeot_Expert_PE12_2007-2015","car_bodies/Peugeot_Expert_PE17_2016-",
 "car_bodies/Citroën_Jumpy_CI13_2016-","car_bodies/Peugeot_Partner_PE02_2008-2018","car_bodies/Ford_Connect_FO12_2014-",
 "car_bodies/Ford_Custom_FO29_2012-2023","car_bodies/Ford_Custom_FO39_2023-","car_bodies/Volkswagen_Transporter_VW29_2024-",
 "car_bodies/Mercedes_Vito_MB25_2014-",
];
for (const b of BASES) {
  let total = 0;
  for (const suf of ["_L","_R_D","_B"]) {
    const m = parseGlbMesh(KAT + b + suf + ".glb");
    const idx = m.geometry.index;
    const tri = idx ? idx.count/3 : m.geometry.attributes.position.count/3;
    total += tri;
  }
  console.log(b, "total_tri(L+R_D+B)=", total);
}
