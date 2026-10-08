// Regresní sada matematiky 3D scény - spustí všechny ověřovací skripty z
// hloubkové kontroly 2026-08-19 (bot8) najednou a vyhodnotí souhrn.
//
// Každý skript v tomhle adresáři je PŘESNÁ kopie logiky odpovídající
// AKTUÁLNÍMU produkčnímu stavu webapp/scene.html + webapp/js/
// scene-geometry-shared.js (po opravách: kvádr pivot-fix, záslepka/wall
// thinFace-fix, L_length zub-fix) a měří skutečné dotyky na REÁLNÉ .glb
// geometrii z webapp/katalog/ (viz VLASTNOSTI_PROFILU.md, pravidlo
// "pivot dílu NENÍ vždy geometrický střed").
//
// POZOR na interpretaci výstupů (viz VLASTNOSTI_PROFILU.md, pravidlo
// "dvě topologie rohu"): skripty samy vypisují OK/FAIL podle správného
// kritéria pro svou topologii - tenhle runner jen hlídá exit kódy a
// výskyt "FAIL"/"PROBLEM" ve výstupu.
//
// Použití: `npm install` v ROOTU repa, pak
//   node scripts/2026-08-19_regression_scene/run_all.js
// Kdy spouštět: po KAŽDÉ změně webapp/js/scene-geometry-shared.js nebo
// build*/refit*/run*Aut funkcí ve scene.html - před commitem. Když se
// produkční funkce ZÁMĚRNĚ změní, aktualizuj odpovídající skript tady
// (jsou to kopie - viz .claude/skills/3d-scena-spoje/SKILL.md).
//
// Datové účetnictví (joint_count/lic_peers) má samostatný nástroj
// scripts/2026-08-19_bookkeeping_validator.js (potřebuje DB dump, proto
// není součástí téhle čistě geometrické sady).
const { execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const dir = __dirname;
const scripts = fs.readdirSync(dir)
  .filter(f => /^\d\d_.*\.js$/.test(f))
  .sort();

let failed = [];
for (const f of scripts) {
  process.stdout.write(`\n########## ${f} ##########\n`);
  try {
    const out = execFileSync(process.execPath, [path.join(dir, f)], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
    process.stdout.write(out);
    // "FAIL"/"PROBLEM"/"NALEZEN" ve vystupu = selhani, i kdyz exit=0
    if (/\bFAIL\b|PROBLEM|NALEZEN PROBLEM|SELHAL/.test(out)) failed.push(f);
  } catch (e) {
    process.stdout.write((e.stdout || "") + (e.stderr || ""));
    failed.push(f);
  }
}

console.log("\n==================================================");
if (failed.length) {
  console.log(`SELHALO ${failed.length}/${scripts.length}: ${failed.join(", ")}`);
  process.exit(1);
} else {
  console.log(`VSECH ${scripts.length} SKRIPTU OK - matematika sceny odpovida overenemu stavu 2026-08-19`);
}
