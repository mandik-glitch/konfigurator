// car_body zaklad (bez _L/_R_D/_B pripony) pro kazdy z 12 pridelenych modelu
// (K-119 vynechano - uz hotovo drivejsi session). Dohledano z car_bodies
// tabulky pres car_models.name LIKE '%[K-XXX]%'.
module.exports = {
  "K-021":  { carModelId: 284, carBodyBase: "Volkswagen_Caddy_VW31_2021-" },
  "K-284":  { carModelId: 301, carBodyBase: "Volkswagen_Transporter_VW25_2024-", noWallLeg: true },
  "K-009":  { carModelId: 52,  carBodyBase: "Citroën_Berlingo_CI17_2019-" },
  "K-019":  { carModelId: 283, carBodyBase: "Volkswagen_Caddy_VW22_2021-" },
  "K-089":  { carModelId: 235, carBodyBase: "Peugeot_Expert_PE20_2016-" },
  "K-095e": { carModelId: 239, carBodyBase: "Peugeot_Expert_PE27_2021-" },
  "K-125e": { carModelId: 46,  carBodyBase: "Citroën_Jumpy_CI26_2021-" },
  "K-236":  { carModelId: 261, carBodyBase: "Renault_Trafic_RE29_2026-" },
  "K-246e": { carModelId: 95,  carBodyBase: "Ford_Custom_FO47_2023-" },
  "K-253":  { carModelId: 90,  carBodyBase: "Ford_Custom_FO28_2012-2023" },
  "K-286":  { carModelId: 302, carBodyBase: "Volkswagen_Transporter_VW27_2024-", noWallLeg: true },
  "K-293e": { carModelId: 188, carBodyBase: "Mercedes_Vito_MB46_2014-" },
};
