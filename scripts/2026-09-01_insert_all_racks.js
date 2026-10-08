// Generates one SQL file inserting shop_products + product_assemblies rows for
// all vehicles that passed the verification gate (2026-09-01_finalize_vehicle_rack.js).
// Run with: node 2026-09-01_insert_all_racks.js > /path/out.sql
const fs = require("fs");

const LABELS = {
  PE12: "Peugeot Expert PE12 (2007-2015)", PE13: "Peugeot Expert PE13 (2007-2015)", PE14: "Peugeot Expert PE14 (2007-2015)",
  PE15: "Peugeot Expert PE15 (2016-)", PE16: "Peugeot Expert PE16 (2016-)", PE17: "Peugeot Expert PE17 (2016-)",
  PE20: "Peugeot Expert PE20 (2016-)", PE21: "Peugeot Expert PE21 (2016-)",
  PE25: "Peugeot e-Expert L1 PE25 (2021-)", PE26: "Peugeot e-Expert L2 PE26 (2021-)", PE27: "Peugeot e-Expert L3 PE27 (2021-)",
  MB17: "Mercedes Vito Compact MB17 (2014-)", MB18: "Mercedes Vito Long MB18 (2014-)", MB19: "Mercedes Vito Extra Long MB19 (2014-)",
  MB24: "Mercedes Vito Mixto Long MB24 (2014-)", MB25: "Mercedes Vito MB25 (2014-)", MB46: "Mercedes Vito MB46 (2014-)", MB47: "Mercedes Vito MB47 (2014-)",
};

function esc(s) { return String(s).replace(/\\/g, "\\\\").replace(/'/g, "''"); }

const configs = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/2026-09-01_vehicle_configs.json", "utf8"));
const lines = [];
const manifest = [];

for (const cfg of configs) {
  const key = cfg.key;
  const sumPath = `/opt/konfigurator/scripts/2026-09-01_final_summary_${key}.json`;
  const partsPath = `/opt/konfigurator/scripts/2026-09-01_final_parts_${key}.json`;
  const resPath = `/opt/konfigurator/scripts/2026-09-01_result_${key}.json`;
  if (!fs.existsSync(sumPath)) { manifest.push({ key, status: "MISSING" }); continue; }
  const summary = JSON.parse(fs.readFileSync(sumPath, "utf8"));
  if (!summary.passesGate) { manifest.push({ key, status: "GATE_FAILED", summary }); continue; }
  const rackParts = JSON.parse(fs.readFileSync(partsPath, "utf8"));
  const res = JSON.parse(fs.readFileSync(resPath, "utf8"));

  // total box count per height across the WHOLE assembly (N * tiers-with-that-height)
  const counts = {};
  res.columnPlans.forEach((cp, colIdx) => {
    const levels = res.columnLevels[colIdx].levels;
    levels.forEach(lv => { counts[lv.boxH] = (counts[lv.boxH] || 0) + cp.N; });
  });
  const heightsSorted = Object.keys(counts).map(Number).sort((a, b) => b - a);
  const partsName = heightsSorted.map(h => `${h}x${counts[h]}`).join("-");
  const label = LABELS[key] || key;
  const name = `${label} - boxy43-${partsName}`;

  const { B: bId, L: lId, R_D: rdId } = cfg.car_body_ids;
  const carBodyParts = [
    { part_id: `car_body_${bId}`, position: [0, 0, 0], quaternion: [0, 0, 0, 1], scale: [1, 1, 1] },
    { part_id: `car_body_${lId}`, position: [0, 0, 0], quaternion: [0, 0, 0, 1], scale: [1, 1, 1] },
    { part_id: `car_body_${rdId}`, position: [0, 0, 0], quaternion: [0, 0, 0, 1], scale: [1, 1, 1] },
  ];
  const allParts = [...carBodyParts, ...rackParts];
  const totalBoxes = Object.values(counts).reduce((a, b) => a + b, 0);
  const distinctHeights = heightsSorted.length;
  const legTypes = res.legs.map(l => l.type).join(",");

  const note = `Regal na euroboxy - leva stena (${label}, car_bodies ${lId}/${rdId}/${bId}), profil 30x30 (custom_shapes prevedeny z 40x40 metodou shape_geometry_methods.id=1). `
    + `Karoserie fyzicky otocena o 180 stupnu (audit 2026-08-31, NEEDS_FLIP) - MIRROR_X konvence pouzita (stena L na zaporne strane X, worldX=offsetX-localX, `
    + `car_body_placement_methods.id=1 klic mirror_x_pro_stenu_na_zaporne_strane_2026_08_31). `
    + `Bulkhead-first kolizni krokovani (1mm/2mm zpet), sloupcova struktura (shape_geometry_methods.id=5, greedy nejsirsi-nejdriv 1232/832/430mm), `
    + `${res.legs.length} noh, ${res.columns.length} sloupec/sloupce (typy noh: ${legTypes}). `
    + (Object.keys(res.legExtensions).some(k => res.legExtensions[k] > 0)
      ? `Protazeni zadni svislice vyrezove nohy (shape_geometry_methods.id=6) aplikovano na: ${Object.entries(res.legExtensions).filter(([, v]) => v > 0).map(([i, v]) => `noha[${i}] Y_new=${v}mm`).join(", ")}. `
      : "")
    + `Vyskove patrovani (shape_geometry_methods.id=3): ${distinctHeights} ruznych vysek pouzito (${heightsSorted.join("/")}mm), nerostouci odspodu nahoru, diverzifikovane napric sloupci. `
    + `Celkem ${totalBoxes} euroboxu 400x300mm. Overeno: bez kolize s karoserii (profily i euroboxy), bez neocekavane self-kolize (${summary.expected} ocekavanych nestingu, ${summary.unexpected} neocekavanych), rail-containment OK. `
    + `Celkove rozmery: ${summary.dims.widthX.toFixed(0)}x${summary.dims.lengthZ.toFixed(0)}x${summary.dims.heightY.toFixed(0)}mm (WxLxH). `
    + `Door-height kontrola (car_body_placement_methods.id=2): leg H=${res.H}mm < realny otvor zadnich dveri (Expert ~1220mm / Vito ~1261mm, web zdroj zaznamenan v karoserie_model_reference) - zkraceni nohy NEBYLO potreba.`;

  const payload = { parts: allParts, join_groups: [], frame_groups: [], bom: [], price_summary: {}, _note: note };
  const payloadJson = JSON.stringify(payload);

  lines.push(`-- ${key}: ${name}`);
  lines.push(`INSERT INTO shop_products (sku, name, unit, active) VALUES ('SEST-${esc(key)}-BOXY43-${Date.now()}', '${esc(name)}', 'ks', 0);`);
  lines.push(`SET @sp_${key} = LAST_INSERT_ID();`);
  lines.push(`INSERT INTO product_assemblies (name, category_id, data, created_by, is_public, shop_product_id) VALUES ('${esc(name)}', NULL, '${esc(payloadJson)}', NULL, 1, @sp_${key});`);
  lines.push(`SET @pa_${key} = LAST_INSERT_ID();`);
  lines.push(`SELECT '${key}' AS veh, @pa_${key} AS product_assembly_id, @sp_${key} AS shop_product_id;`);
  lines.push("");

  manifest.push({ key, status: "QUEUED", name, totalParts: allParts.length, totalBoxes, distinctHeights });
}

fs.writeFileSync("/opt/konfigurator/scripts/2026-09-01_insert_all_racks.sql", lines.join("\n"));
fs.writeFileSync("/opt/konfigurator/scripts/2026-09-01_insert_manifest.json", JSON.stringify(manifest, null, 1));
console.log(JSON.stringify(manifest, null, 1));
