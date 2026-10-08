// Horní blok, VARIANTA 05 (Robert 2026-09-17, nové pravidlo - doplňuje
// dosavadní 01-04 z 2026-09-05_horni_ram.js, protože ty "fungují dobře jen
// u některých aut a některých vzdáleností mezi nohama"). Doslovné zadání:
//
//   "přidat rám 5mm nad úhelníkama dokola mezi nohama tj 2xpodélník a 2x
//   příčka; rámu přidat mdf dno; čelní podélník osadit plastem 8mm do
//   výšky 89mm; zadní podélník osadit mdf 8mm do výšky 130mm; boční
//   příčky osadit mdf 8mm do výšky 130mm."
//
// INTERPRETACE (bot8, ověřeno na reálné geometrii #127, zapsat spolu s
// výsledkem k Robertovu potvrzení - viz AGENTS_LOG.md):
//   "úhelníky" = shape_geometry_methods.id=7 (uhelnik-noha<i>) - JIŽ
//   uložené v datech sestavy, GLOBÁLNÍ nejvyšší bod (Box3.max.y) přes
//   VŠECHNY nohy. Na #127 vychází 870,5mm - těsně nad spojem
//   spojnice-horni/cap, HLUBOKO pod vrcholem nohy (1092mm, 186mm rezervy)
//   -> proto by mělo fungovat nezávisle na tom, kolik místa zbývá ke
//   stropu (na rozdíl od 01-04, kotvených k vrcholu nohy).
//   "dokola mezi nohama" = JEDEN uzavřený obdélníkový rám přes CELOU
//   sestavu (ne po sloupcích): 2 podélníky (celní, zadní) souvislé od
//   první do poslední nohy, 2 příčky JEN na koncových nohách (uzavírají
//   obdélník) - středová noha/nohy se pod rámem STEJNÝM mechanismem jako
//   u variant 01-04 zkrátí (zkratitKlice v main() horni_ram.js), aby jí
//   podélník mohl "projet" nad jejím zkráceným koncem.
//   Stěny (plast/mdf) se montují STEJNĚ jako existující panelSvisly()
//   (podélníky) / vypln-bok-prepazka (příčky) - zasun 7mm do drážky
//   shora, dál rostou nahoru o zadanou výšku.
//
// Pouziti: node 2026-09-17_horni_blok_var05.js <AID> <VOZIDLO>
//   -> zapise scripts/../<SCRATCH>/var05_<AID>.json { parts, ok, report }
const fs = require("fs");
const THREE = require("three");
global.THREE = THREE;
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { verifyAssembly } = require("/opt/konfigurator/scripts/2026-09-12_wide_verify_lib.js");

const T = 30, L0 = 1000, ZASUN = 7, DNO_VULE = 1;
const NAD_UHELNIKY = 5;
// bot8 2026-09-21: povinna mezera 30mm nad nejvyssim euroboxem (Robert
// 2026-09-06: "k tomu mezera 30 milimetru povinna a teprve tam muze
// zacinat horni blok"). Do 2026-09-21 tady NEBYLA vubec - ram se kotvil
// VYHRADNE k uhelnikum, takze u aut s vysokymi boxy vysel horni blok POD
// vrchem nejvyssiho boxu (zmereno: az -69mm, tedy realny prunik).
const MEZERA_NAD_BOXY = 30;
const KAT = "/opt/konfigurator/webapp/katalog/";
const DESKA_MDF = "product_3939", DESKA_PLAST = "product_3950";
const PLAST_TL = 89, MDF_ZADA_TL_MM = 130, MDF_BOK_TL_MM = 130; // vysky sten (nazvy dle zadani, ne tloustka materialu)
const Q_PODELNY = [-0.7071067811865475, 0, 0, 0.7071067811865476];
const Q_PRICNY = [0, 0, -0.7071067811865475, 0.7071067811865476];
const Q_PANEL_SVISLY = [0, 0.7071067811865476, 0, 0.7071067811865475]; // panelSvisly() z horni_ram.js
const Q_PANEL_BOK = [0, 0, 0, 1]; // vypln-bok-prepazka orientace z horni_ram.js
const Q_DNO = [-0.7071067811865475, 0, 0, 0.7071067811865476]; // stavDna() z horni_ram.js

function bezNohyIdx(role) { return String(role || "").replace(/-noha\d+$/, ""); }

function worldBox(p) {
  const glb = R.glbPath(p.part_id);
  if (!glb) return null;
  const m = parseGlbMesh(glb);
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(m);
}

function analyzujNohy(parts) {
  const dily = [];
  for (const p of parts) {
    if (R.jeKaroserie(p.part_id)) continue;
    const b = worldBox(p);
    if (!b) continue;
    dily.push({ role: p.role || p.part_id, p, b });
  }
  const podle = r => dily.filter(d => bezNohyIdx(d.role) === r);
  const sloupky = role => podle(role)
    .map(d => ({ role, z0: d.b.min.z, z1: d.b.max.z, y0: d.b.min.y, y1: d.b.max.y, x0: d.b.min.x, x1: d.b.max.x, p: d.p }))
    .sort((a, b) => a.z0 - b.z0);
  const zadni = sloupky("cap").length ? sloupky("cap") : sloupky("zadni-svislice");
  const celni = sloupky("predni-svislice");
  if (!zadni.length || !celni.length) throw new Error("sestava nema 'cap'/'predni-svislice'");
  const uhelniky = dily.filter(d => d.role.startsWith("uhelnik"));
  if (!uhelniky.length) throw new Error("sestava nema uhelniky (shape_geometry_methods.id=7 jeste neaplikovano)");
  const nejvyssiUhelnik = Math.max(...uhelniky.map(d => d.b.max.y));
  // bot8 2026-09-21: euroboxy pro povinnou 30mm mezeru. Chybejici eurobox
  // je HLASITA chyba, ne tiche preskoceni - bez nej nejde pravidlo overit
  // (skill 3d-scena-spoje: "nezmeritelny dil musi byt hlasita chyba").
  const euroboxy = dily.filter(d => /^eurobox-/i.test(d.role));
  if (!euroboxy.length) throw new Error("sestava nema zadny eurobox - nelze overit povinnou 30mm mezeru nad boxem");
  const nejvyssiBox = Math.max(...euroboxy.map(d => d.b.max.y));
  return { dily, zadni, celni, nejvyssiUhelnik, nejvyssiBox };
}

function main() {
  const AID = process.argv[2], VOZIDLO = process.argv[3];
  const SCRATCH = process.argv[4] || "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
  const srcData = JSON.parse(fs.readFileSync(`${SCRATCH}/hb_src_${AID}.json`, "utf8"));
  const a = analyzujNohy(srcData.parts);

  // yDol = VYSSI ze dvou podminek, stejne jako 2026-09-05_horni_ram.js:271
  // (a) 5mm nad nejvyssim uhelnikem, (b) 30mm nad nejvyssim euroboxem.
  const yDolUhelnik = a.nejvyssiUhelnik + NAD_UHELNIKY;
  const yDolBox = a.nejvyssiBox + MEZERA_NAD_BOXY;
  const yDol = Math.max(yDolUhelnik, yDolBox);
  const yHor = yDol + T;
  console.log(`nejvyssiUhelnik=${a.nejvyssiUhelnik.toFixed(2)} (yDol ${yDolUhelnik.toFixed(2)}) nejvyssiBox=${a.nejvyssiBox.toFixed(2)} (yDol ${yDolBox.toFixed(2)}) rozhodlo=${yDolBox > yDolUhelnik ? "BOX" : "UHELNIK"} -> yDol=${yDol.toFixed(2)} yHor=${yHor.toFixed(2)} (nohy: ${a.celni.length})`);

  const xCelni = (a.celni[0].x0 + a.celni[0].x1) / 2;
  const xZadni = (a.zadni[0].x0 + a.zadni[0].x1) / 2;
  const zOdCelek = a.celni[0].z1 < a.celni[a.celni.length - 1].z1 ? a.celni[0].z1 : a.celni[a.celni.length - 1].z1;
  // celni/zadni jsou uz serazene podle z0 vzestupne (sloupky()) - prvni/posledni jsou krajni nohy.
  const nohaFirst = a.celni[0], nohaLast = a.celni[a.celni.length - 1];
  const zPodelnikOd = nohaFirst.z1, zPodelnikDo = nohaLast.z0;
  if (zPodelnikDo <= zPodelnikOd) throw new Error("mene nez 2 nohy (nebo se dotykaji) - variantu 05 neni na cem postavit");

  const nove = [];
  // --- 2x podelnik (celni, zadni), prubezny mezi krajnimi nohama ---------
  nove.push({ part_id: "Object_7", position: [xCelni, (yDol + yHor) / 2, (zPodelnikOd + zPodelnikDo) / 2],
    quaternion: Q_PODELNY, scale: [1, (zPodelnikDo - zPodelnikOd) / L0, 1], role: "podelnik-celni-05" });
  nove.push({ part_id: "Object_7", position: [xZadni, (yDol + yHor) / 2, (zPodelnikOd + zPodelnikDo) / 2],
    quaternion: Q_PODELNY, scale: [1, (zPodelnikDo - zPodelnikOd) / L0, 1], role: "podelnik-zadni-05" });

  // --- 2x pricka, jen na KRAJNICH nohach (uzavira obdelnik) --------------
  const xPrickaOd = Math.min(xCelni, xZadni) + T / 2, xPrickaDo = Math.max(xCelni, xZadni) - T / 2;
  [nohaFirst, nohaLast].forEach((noha, i) => {
    const z = (noha.z0 + noha.z1) / 2;
    nove.push({ part_id: "Object_7", position: [(xPrickaOd + xPrickaDo) / 2, (yDol + yHor) / 2, z],
      quaternion: Q_PRICNY, scale: [1, (xPrickaDo - xPrickaOd) / L0, 1], role: `pricka-05-${i}` });
  });

  // --- zkraceni STREDOVYCH noh (stejny mechanismus jako horni_ram.js main()) ---
  const stredoveCelni = a.celni.slice(1, -1), stredoveZadni = a.zadni.slice(1, -1);
  const zkratitKlice = new Set([...stredoveCelni, ...stredoveZadni].map(s => `${s.role}@${Math.round((s.z0 + s.z1) / 2)}`));
  const upraveneParts = [];
  const zkraceno = [];
  for (const p0 of srcData.parts) {
    const role = bezNohyIdx(p0.role || p0.part_id);
    const zc = Math.round(p0.position[2]);
    if (zkratitKlice.has(`${role}@${zc}`)) {
      const aktualniVrch = p0.position[1] + p0.scale[1] * L0 / 2;
      const zkratitO = aktualniVrch - yDol;
      if (zkratitO < -1e-6) throw new Error(`stredovy sloupek ${p0.role}@${zc} je NIZSI nez yDol (${aktualniVrch.toFixed(1)} < ${yDol.toFixed(1)})`);
      if (zkratitO > 1e-6) {
        upraveneParts.push({ ...p0, position: [p0.position[0], p0.position[1] - zkratitO / 2, p0.position[2]],
          scale: [p0.scale[0], p0.scale[1] - zkratitO / L0, p0.scale[2]] });
        zkraceno.push({ role: p0.role, z: zc, o: +zkratitO.toFixed(2) });
      } else upraveneParts.push(p0);
      continue;
    }
    // zaslepka na prave zkracenem sloupku - podelnik na nej dosedne, zaslepka by byla plat (stejne pravidlo jako main()).
    if (String(p0.role || "").startsWith("zaslepka") && p0.position[1] > yDol) {
      const patri = [...stredoveCelni, ...stredoveZadni].some(s =>
        Math.abs((s.z0 + s.z1) / 2 - p0.position[2]) < 1 && p0.position[0] > s.x0 - 1 && p0.position[0] < s.x1 + 1);
      if (patri) continue;
    }
    upraveneParts.push(p0);
  }
  console.log("zkraceno stredovych dilu:", JSON.stringify(zkraceno));

  // --- mdf dno (cely obdelnik, jeden kus - zadna stredova pricka neexistuje) ---
  // PRESNE stavDna() z horni_ram.js: zasun od SKUTECNE zmerene vnitrni hrany
  // KAZDE nohy (a.zadni[0].x1 / a.celni[0].x0 - realny GLB bbox, ne odvozeno
  // od stredu podelniku druhe strany).
  const xDnaA = Math.max(...a.zadni.map(s => s.x1)) - ZASUN;
  const xDnaB = Math.min(...a.celni.map(s => s.x0)) + ZASUN;
  const xDnaOd = Math.min(xDnaA, xDnaB), xDnaDo = Math.max(xDnaA, xDnaB);
  const zDnaOd = zPodelnikOd + DNO_VULE / 2, zDnaDo = zPodelnikDo - DNO_VULE / 2;
  nove.push({ part_id: DESKA_MDF, position: [(xDnaOd + xDnaDo) / 2, (yDol + yHor) / 2, (zDnaOd + zDnaDo) / 2],
    quaternion: Q_DNO, scale: [(xDnaDo - xDnaOd) / L0, (zDnaDo - zDnaOd) / L0, 1], role: "vypln-dno-05" });

  // --- steny: celni podelnik=plast 89mm, zadni podelnik=mdf 130mm, obe pricky=mdf 130mm ---
  function stenaPodelnik(x, deska, vyska, role) {
    const bottomY = yHor - ZASUN, centerY = bottomY + vyska / 2;
    nove.push({ part_id: deska, position: [x, centerY, (zPodelnikOd + zPodelnikDo) / 2],
      quaternion: Q_PANEL_SVISLY, scale: [(zPodelnikDo - zPodelnikOd) / L0, vyska / L0, 1], role });
  }
  stenaPodelnik(xCelni, DESKA_PLAST, PLAST_TL, "vypln-celo-05");
  stenaPodelnik(xZadni, DESKA_MDF, MDF_ZADA_TL_MM, "vypln-zada-05");
  [nohaFirst, nohaLast].forEach((noha, i) => {
    const z = (noha.z0 + noha.z1) / 2;
    const bottomY = yHor - ZASUN, centerY = bottomY + MDF_BOK_TL_MM / 2;
    nove.push({ part_id: DESKA_MDF, position: [(xPrickaOd + xPrickaDo) / 2, centerY, z],
      quaternion: Q_PANEL_BOK, scale: [(xPrickaDo - xPrickaOd) / L0, MDF_BOK_TL_MM / L0, 1], role: `vypln-bok-05-${i}` });
  });

  const parts = [...upraveneParts, ...nove];
  const report = verifyAssembly({ partsNew: nove, partsOrig: srcData.parts, carBodyBase: VOZIDLO, notchChecks: [], label: `${AID}-var05` });
  // Stejny filtr jako jeZamernyZasun() v tmp_2026-09-16_bot8_hb_build.js: jeden
  // z dvojice je "vypln-*" (deska), druhy je ramovy profil (podelnik/pricka/
  // cap/predni-svislice), a nejmensi rozmer prekryvu je <= ZASUN(7)+0.5 -> je
  // to zamerne zasunuti desky do drazky profilu, ne kolize.
  const RAMOVE = /^(podelnik|pricka|cap|predni-svislice)/;
  function jeZamernyZasun(roleA, roleB, dims) {
    const a1 = roleA.startsWith("vypln"), b1 = roleB.startsWith("vypln");
    if (a1 === b1) return false;
    const profil = a1 ? roleB : roleA;
    if (!RAMOVE.test(profil)) return false;
    const h = dims.filter(v => v > 0.5).sort((m, n) => m - n);
    return h.length > 0 && h[0] <= ZASUN + 0.5;
  }
  const skutecneProblemy = report.newProblems.filter(p => !jeZamernyZasun(p.a, p.b, p.overlap_mm));
  const ok = report.collisions === 0 && skutecneProblemy.length === 0;
  console.log(`dilu_novych=${nove.length} dilu_celkem=${parts.length} wall=${report.collisions} self-nove=${report.newProblems.length} (zamerny zasun ${report.newProblems.length - skutecneProblemy.length}, skutecnych ${skutecneProblemy.length}) OK=${ok}`);
  if (skutecneProblemy.length) console.log("SKUTECNE problemy:", JSON.stringify(skutecneProblemy, null, 1));

  fs.writeFileSync(`${SCRATCH}/var05_${AID}.json`, JSON.stringify({ parts, ok, yDol, yHor, zkraceno, report: { collisions: report.collisions, newProblems: report.newProblems } }));
}
main();
