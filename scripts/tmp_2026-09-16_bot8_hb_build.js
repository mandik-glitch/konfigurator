const fs = require("fs");
const THREE = require("three");
const { execSync } = require("child_process");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { verifyAssembly } = require("/opt/konfigurator/scripts/2026-09-12_wide_verify_lib.js");

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const ZASUN = 7, TOP_CLEAR = 11, SIDE_ZASUN = 8;

function worldBox(p) {
  const glb = R.glbPath(p.part_id); if (!glb) return null;
  const mesh = parseGlbMesh(glb);
  mesh.position.set(...p.position); mesh.quaternion.set(...p.quaternion); mesh.scale.set(...p.scale);
  mesh.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(mesh);
}
// Prevzato 1:1 z tmp_2026-09-15_bot8_gap70_check.js (Robert 2026-09-15
// pravidlo, jiz overene na 24 existujicich sestavach - 21 Jumpy 47-66.5mm,
// 3 Doblo 81.7mm, presne sedi na rucne zmerene id=405/409/413). PUVODNI
// pokus tehle zmeny pocital mezeru z `res.svetlaVyskaRamu` (horni_ram.js,
// yHornihoDol-ySpodnihoHor) - to je CELY kanal PRED vlozenim police, ne
// skutecna mezera KOLEM police po jejim vlozeni (na K-121e A vyslo 155mm
// misto realnych 62.5mm - police + jeji ram zabere stred kanalu a rozdeli
// ho na 2 mensi mezery). `najdiMezery()` meri PRAVE tyhle realne mezery
// primo na GLB geometrii hotovych dilu (XZ-prekryv + nejblizsi Y-sousede
// mezi "lezicimi" profily podelnik/pricka) - stejna logika jako kotovaci
// kod ve scene.html.
function najdiMezery(parts) {
  const horiz = [];
  for (const p of parts) {
    if (R.jeKaroserie(p.part_id)) continue;
    const role = p.role || "";
    if (!/^(podelnik|pricka)/.test(role)) continue;
    const b = worldBox(p); if (!b) continue;
    if (b.max.y - b.min.y > 60) continue;
    horiz.push({ role, box: b });
  }
  const mezery = [];
  for (let i = 0; i < horiz.length; i++) for (let j = i + 1; j < horiz.length; j++) {
    const A = horiz[i], B = horiz[j];
    const ox = Math.min(A.box.max.x, B.box.max.x) - Math.max(A.box.min.x, B.box.min.x);
    const oz = Math.min(A.box.max.z, B.box.max.z) - Math.max(A.box.min.z, B.box.min.z);
    if (ox < 10 || oz < 10) continue;
    const lower = A.box.max.y <= B.box.min.y ? A : B;
    const upper = lower === A ? B : A;
    const gap = upper.box.min.y - lower.box.max.y;
    if (gap <= 2 || gap > 400) continue;
    const blocked = horiz.some(C => {
      if (C === A || C === B) return false;
      const cox = Math.min(C.box.max.x, A.box.max.x, B.box.max.x) - Math.max(C.box.min.x, A.box.min.x, B.box.min.x);
      const coz = Math.min(C.box.max.z, A.box.max.z, B.box.max.z) - Math.max(C.box.min.z, A.box.min.z, B.box.min.z);
      if (cox < 10 || coz < 10) return false;
      return C.box.min.y > lower.box.max.y - 2 && C.box.max.y < upper.box.min.y + 2;
    });
    if (blocked) continue;
    mezery.push({ a: lower.role, b: upper.role, gap: +gap.toFixed(1) });
  }
  return mezery;
}
function addDorazovaDeska(parts) {
  const pricka = parts.find(p => p.role === "pricka-spodni-0");
  const z = pricka.position[2];
  const atZ = parts.filter(p => Math.abs(p.position[2] - z) < 1 && !R.jeKaroserie(p.part_id));
  // bot8 2026-09-17: role noh mohou nest priponu "-noha<i>" (postup_stavby_
  // regalu_krok_za_krokem_2026_09_17, krok 14) - stejna tolerance jako v
  // 2026-09-05_horni_ram.js.
  const bezNohyIdx = role => String(role || "").replace(/-noha\d+$/, "");
  const predni = atZ.find(p => bezNohyIdx(p.role) === "predni-svislice");
  const cap = atZ.find(p => bezNohyIdx(p.role) === "cap");
  const zaslepky = atZ.filter(p => String(p.role || "").startsWith("zaslepka")).map(p => ({ p, box: worldBox(p) })).sort((a, b) => b.box.max.y - a.box.max.y).slice(0, 2);
  const prickaBox = worldBox(pricka);
  const zaslepkaMinY = Math.min(...zaslepky.map(zz => zz.box.min.y));
  const bottomY = prickaBox.max.y - ZASUN, topY = zaslepkaMinY - TOP_CLEAR;
  const xMid = (predni.position[0] + cap.position[0]) / 2;
  const width = Math.abs(cap.position[0] - predni.position[0]) - 2 * SIDE_ZASUN;
  return { role: "vypln-bok-prepazka", part_id: "product_3939", position: [xMid, (bottomY + topY) / 2, z],
    quaternion: [0, 0, 0, 1], scale: [width / 1000, (topY - bottomY) / 1000, 1] };
}
const RAMOVE = /^(podelnik|pricka|cap|predni-svislice)/;
function jeZamernyZasun(roleA, roleB, dims) {
  const a1 = roleA.startsWith("vypln"), b1 = roleB.startsWith("vypln");
  if (a1 === b1) return false;
  const profil = a1 ? roleB : roleA;
  if (!RAMOVE.test(profil)) return false;
  const h = dims.filter(v => v > 0.5).sort((m, n) => m - n);
  return h.length > 0 && h[0] <= ZASUN + 0.5;
}

const VARIANTY = {
  "01": { flags: ["--jedno-pasmo"], dorazova: true, odeberRoli: null },
  "02": { flags: ["--bez-hornich-pricek", "--police-bez-podelniku", "--bez-vyplni"], dorazova: true, odeberRoli: "pricka-police-0" },
  "03": { flags: ["--bez-police", "--horni-pricka-jen-prepazka"], dorazova: false, odeberRoli: null },
  "04": { flags: ["--horni-pricka-jen-prepazka"], dorazova: false, odeberRoli: null },
};
// Robert 2026-09-17 ("uprav pravidlo horniho bloku var 04, nestavet
// geometrii vubec pokud neni splnena podminka mezery 70mm"): drivejsi
// pravidlo (PLAN_TVORBY_SESTAV.md Faze 4, 2026-09-15) blokovalo jen
// PRIPOJENI na kartu (shop_product_id), geometrie se pod limitem
// pripojena poresila SMELA POSTAVIT a ulozit jako nepouzivana - to
// necham silent-NULL mezeru (render_auto_dispatch.py._mezera_ok bere
// NULL jako "projde", coz je presne diru, kterou Robert ted zaviral).
// Od tehle zmeny: pod limitem se "04" vubec NEPOSTAVI (ok=false), zadna
// mezera-NULL geometrie uz nevznika. Mereni mezery viz najdiMezery() nize
// (prevzato z gap70_check.js, NE res.svetlaVyskaRamu - viz komentar tam).
const MEZERA_POLICE_LIMIT_MM = 70;

const AID = process.argv[2];
const VOZ = process.argv[3];
const srcPath = `${SCRATCH}/hb_src_${AID}.json`;
const src = { data: JSON.parse(fs.readFileSync(srcPath, "utf8")) };
const out = {};
for (const [label, cfg] of Object.entries(VARIANTY)) {
  const raw = execSync(`node /opt/konfigurator/scripts/2026-09-05_horni_ram.js "${srcPath}" --vozidlo="${VOZ}" ${cfg.flags.join(" ")} --json`, { maxBuffer: 1024 * 1024 * 80 }).toString();
  const res = JSON.parse(raw);
  let parts = res.upraveneParts;
  if (cfg.odeberRoli) parts = parts.filter(p => p.role !== cfg.odeberRoli);
  if (cfg.dorazova) parts = parts.concat([addDorazovaDeska(parts)]);
  const orig = src.data.parts;
  const report = verifyAssembly({ partsNew: parts, partsOrig: orig, carBodyBase: VOZ, notchChecks: [], label: `${AID}-${label}` });
  const novyProblem = report.newProblems.filter(p => !jeZamernyZasun(p.a, p.b, p.overlap_mm));
  const mezery = najdiMezery(parts);
  const mezeraPoliceMm = mezery.length ? Math.min(...mezery.map(m => m.gap)) : null;
  const mezeraOk = label !== "04" || mezeraPoliceMm == null || mezeraPoliceMm >= MEZERA_POLICE_LIMIT_MM;
  const ok = mezeraOk && report.collisions === 0 && novyProblem.length === 0 && res.kolize.length === 0 && res.kolizeKaroserie.length === 0;
  console.log(`${label}: dilu=${parts.length} wall=${report.collisions} self-nove=${novyProblem.length} script-kolize=${res.kolize.length} mezera=${mezeraPoliceMm}mm OK=${ok}` + (!mezeraOk ? " (POD LIMITEM 70mm - NEPOSTAVENO)" : ""));
  out[label] = { parts, ok, mezera_police_mm: mezeraPoliceMm };
}
fs.writeFileSync(`${SCRATCH}/hb_build_${AID}.json`, JSON.stringify(out));
console.log("CELKEM OK:", Object.values(out).filter(v => v.ok).length, "/4");
