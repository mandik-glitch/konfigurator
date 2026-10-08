const CADDY = { family: "caddy", H: 1080, CAP_H: 240, capRight: 260, hasVyrez: true, CUTOUT_H_design: 330, colRight_design: 270 };
const FORD = { family: "ford", H: 1100, hasVyrez: false };
const DOBLO = { family: "doblo", H: 1180, CAP_H: 260, capRight: 279, hasVyrez: true, CUTOUT_H_design: 440, colRight_design: 215 };

const configs = [
  { key: "caddy_VW13", bodyPrefix: "Volkswagen_Caddy_VW13_2004-2020", ...CADDY, rows: [{ id: 836, label: "Caddy VW13 (04-20)" }] },
  { key: "caddy_VW14", bodyPrefix: "Volkswagen_Caddy_VW14_2004-2020", ...CADDY, rows: [{ id: 839, label: "Caddy Maxi VW14 (04-20)" }] },
  { key: "caddy_VW21", bodyPrefix: "Volkswagen_Caddy_VW21_2021-", ...CADDY, rows: [{ id: 842, label: "Caddy Cargo VW21" }] },
  { key: "caddy_VW22", bodyPrefix: "Volkswagen_Caddy_VW22_2021-", ...CADDY, rows: [{ id: 845, label: "Caddy Cargo Maxi VW22" }] },
  { key: "caddy_VW31", bodyPrefix: "Volkswagen_Caddy_VW31_2021-", ...CADDY, rows: [{ id: 848, label: "Caddy Cargo PHEV VW31" }] },
  { key: "caddy_VW32", bodyPrefix: "Volkswagen_Caddy_VW32_2021-", ...CADDY, rows: [{ id: 851, label: "Caddy Cargo Maxi PHEV VW32" }] },

  { key: "ford_FO12", bodyPrefix: "Ford_Connect_FO12_2014-", ...FORD, rows: [{ id: 233, label: "Ford Connect FO12" }] },
  { key: "ford_FO13", bodyPrefix: "Ford_Connect_FO13_2014-", ...FORD, rows: [{ id: 74, label: "Ford Connect FO13" }] },
  { key: "ford_FO36", bodyPrefix: "Ford_Connect_FO36_2024-", ...FORD, rows: [{ id: 236, label: "Transit Connect L1 FO36" }] },
  { key: "ford_FO37", bodyPrefix: "Ford_Connect_FO37_2024-", ...FORD, rows: [{ id: 239, label: "Transit Connect L2 FO37" }] },
  { key: "ford_FO45", bodyPrefix: "Ford_Connect_FO45_2024-", ...FORD, rows: [{ id: 242, label: "Transit Connect PHEV L1 FO45" }] },
  { key: "ford_FO46", bodyPrefix: "Ford_Connect_FO46_2024-", ...FORD, rows: [{ id: 245, label: "Transit Connect PHEV L2 FO46" }] },

  { key: "doblo_FI14", bodyPrefix: "Fiat_Doblo_FI14_2010-2022", ...DOBLO, rows: [{ id: 17, label: "Doblò FI14 (10-22)" }] },
  { key: "doblo_FI15", bodyPrefix: "Fiat_Doblo_FI15_2010-2022", ...DOBLO, rows: [{ id: 68, label: "Doblò Maxi FI15 (10-22)" }] },
  { key: "doblo_FI22", bodyPrefix: "Fiat_Doblo_FI22_2022-", ...DOBLO, rows: [{ id: 137, label: "Doblò L1 FI22" }, { id: 143, label: "E-Doblò L1 FI27" }] },
  { key: "doblo_FI23", bodyPrefix: "Fiat_Doblo_FI23_2022-", ...DOBLO, rows: [{ id: 140, label: "Doblò Maxi L2 FI23" }, { id: 146, label: "E-Doblò L2 FI28" }] },
];

module.exports = { configs };
