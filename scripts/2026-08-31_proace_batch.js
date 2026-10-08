const fs = require("fs");
const { execSync } = require("child_process");
const { runOne } = require("/opt/konfigurator/scripts/2026-08-31_proace_run_one.js");
const { buildFull } = require("/opt/konfigurator/scripts/2026-08-31_proace_full_build.js");
const { generate2D } = require("/opt/konfigurator/scripts/2026-08-31_proace_gen_2d.js");

const BASE = "/opt/konfigurator/webapp/katalog/car_bodies/";
const DEFAULT = { D: 349, T: 30, CUTOUT_H: 395, CAP_H: 260 };

// vehicles: name, glb base suffix, car_body ids [L,R,B], H (parametrizovano
// dle rule2 - door opening height), doorHeight (jen pro report), skip=uz hotovo
const VEHICLES = [
  { name: "TO08", base: BASE + "Toyota_Proace_TO08_2020-", ids: [813, 814, 815], H: 1180, door: 1220, label: "Proace Medium 16-" },
  { name: "TO09", base: BASE + "Toyota_Proace_TO09_2020-", ids: [816, 817, 818], H: 1180, door: 1220, label: "Proace Long 16-" },
  { name: "TO12", base: BASE + "Toyota_Proace_TO12_2020-", ids: [819, 820, 821], H: 1180, door: 1220, label: "Proace Medium Crew Cab (L2) 20-" },
  { name: "TO17", base: BASE + "Toyota_Proace_TO17_2020-", ids: [822, 823, 824], H: 1180, door: 1220, label: "Proace Long Crew Cab (L3) 20-" },
  { name: "TO21", base: BASE + "Toyota_Proace_TO21_2020-", ids: [825, 826, 827], H: 1180, door: 1220, label: "Proace Medium Electric 20-" },
  { name: "TO22", base: BASE + "Toyota_Proace_TO22_2020-", ids: [828, 829, 830], H: 1180, door: 1220, label: "Proace Long Electric 20-" },
  { name: "TO23", base: BASE + "Toyota_Proace_TO23_2020-", ids: [831, 832, 833], H: 1180, door: 1220, label: "Proace Compact Electric 20-" },
  { name: "TO10", base: BASE + "Toyota_Proace_City_TO10_2020-", ids: [105, 106, 107], H: 1180, door: 1196, label: "Proace City_TO10_2020-" },
  { name: "TO11", base: BASE + "Toyota_Proace City_TO11_2020-", ids: [780, 781, 782], H: 1180, door: 1196, label: "Proace City L2 20-" },
  { name: "TO19", base: BASE + "Toyota_Proace City_TO19_2020-", ids: [783, 784, 785], H: 1075, door: 1075, label: "Proace City L1 Electric 20-" },
  { name: "TO20", base: BASE + "Toyota_Proace City_TO20_2020-", ids: [786, 787, 788], H: 1075, door: 1075, label: "Proace City L2 Electric 20-" },
  { name: "TO14", base: BASE + "Toyota_Proace Max_TO14_2024-", ids: [789, 790, 791], H: 1180, door: null, label: "Proace Max L2H2 24-" },
  { name: "TO15", base: BASE + "Toyota_Proace Max_TO15_2024-", ids: [792, 793, 794], H: 1180, door: null, label: "Proace Max L3H2 24-" },
  { name: "TO16", base: BASE + "Toyota_Proace Max_TO16_2024-", ids: [795, 796, 797], H: 1180, door: null, label: "Proace Max L4H2 24-" },
  { name: "TO18", base: BASE + "Toyota_Proace Max_TO18_2024-", ids: [798, 799, 800], H: 1180, door: null, label: "Proace Max L2H1 24-" },
  { name: "TO24", base: BASE + "Toyota_Proace Max_TO24_2024-", ids: [801, 802, 803], H: 1180, door: null, label: "Proace Max L3H3 24-" },
  { name: "TO25", base: BASE + "Toyota_Proace Max_TO25_2024-", ids: [804, 805, 806], H: 1180, door: null, label: "Proace Max L1H1 24-" },
  { name: "TO26", base: BASE + "Toyota_Proace Max_TO26_2024-", ids: [807, 808, 809], H: 1180, door: null, label: "Proace Max L4H3 24-" },
];

const results = [];
for (const veh of VEHICLES) {
  const cfg = { name: veh.name, base: veh.base, D: DEFAULT.D, H: veh.H, T: DEFAULT.T, CUTOUT_H: DEFAULT.CUTOUT_H, CAP_H: DEFAULT.CAP_H };
  let rec = { name: veh.name, label: veh.label, door: veh.door, H: veh.H };
  try {
    const step = runOne(cfg);
    if (!step.ok) { rec.status = "no_fit"; rec.reason = step.reason; results.push(rec); console.log(veh.name, "NO FIT:", step.reason); continue; }
    const full = buildFull(step);
    if (!full.ok) {
      rec.status = "build_fail";
      rec.detail = { carCollisionProfiles: full.carCollisionProfiles, euroboxCarCollision: full.euroboxCarCollision, unexpected: full.unexpected };
      results.push(rec);
      console.log(veh.name, "BUILD FAIL:", JSON.stringify(rec.detail));
      fs.writeFileSync(`/tmp/proace_fail_${veh.name}.json`, JSON.stringify(full, null, 1));
      continue;
    }
    const svgPath = `/tmp/proace_2d_${veh.name}.svg`;
    const check2d = generate2D(full.parts, svgPath, veh.name);
    if (check2d.issues.length) { rec.status = "2d_check_fail"; rec.issues = check2d.issues; results.push(rec); console.log(veh.name, "2D CHECK FAIL", check2d.issues); continue; }

    const fullPath = `/tmp/proace_full_${veh.name}.json`;
    fs.writeFileSync(fullPath, JSON.stringify(full));
    const heightsStr = full.distinctHeights.slice().sort((a, b) => b - a).join("x");
    const totalBoxes = full.totalBoxes;
    const name = `${veh.label} - boxy43-${heightsStr}`;
    const note = `Automaticky build (bot16, 2026-08-31, generalizovany ProAce pipeline) - ${full.columnSummaries.length} sloupec/u, ${full.legCount} noh, ${totalBoxes} euroboxu celkem, vysky pouzite: ${full.distinctHeights.join(",")}mm. Noha 30x30 (D=349,H=${veh.H}) prevedena z custom_shapes.id=506/507. ` +
      (veh.door ? `Zadni dvere ${veh.door}mm (karoserie_model_reference) - ${veh.H <= veh.door ? "leg H beze zmeny, pod limitem" : "leg H ZKRACENA na limit"}. ` : `Vyska zadnich dveri neznama (NULL v karoserie_model_reference) - kontrola dle rule2 neoverena, H ponecháno na standardnich 1180mm. `) +
      `Karoserie fyzicky otocena 180 (2026-08-31_flip_proace_family_180.js). Sloupce: ${JSON.stringify(full.columnSummaries.map(c => ({ N: c.N, patra: c.levels, vysky: c.boxHeights })))}`;
    const out = execSync(`api/venv/bin/python3 scripts/2026-08-31_proace_insert.py ${JSON.stringify(fullPath)} ${JSON.stringify(name)} ${JSON.stringify(note)} ${veh.ids[0]} ${veh.ids[1]} ${veh.ids[2]}`, { cwd: "/opt/konfigurator" }).toString();
    console.log(veh.name, "INSERTED:", out.trim());
    rec.status = "inserted";
    rec.insertOut = out.trim();
    rec.summary = { columns: full.columnSummaries.length, legs: full.legCount, boxes: totalBoxes, heights: full.distinctHeights };
    results.push(rec);
  } catch (e) {
    rec.status = "error";
    rec.error = e.message;
    results.push(rec);
    console.log(veh.name, "ERROR:", e.message);
  }
}

fs.writeFileSync("/opt/konfigurator/scripts/2026-08-31_proace_batch_results.json", JSON.stringify(results, null, 1));
console.log("\n=== SUMMARY ===");
results.forEach(r => console.log(r.name, r.status, r.summary || r.reason || r.error || ""));
