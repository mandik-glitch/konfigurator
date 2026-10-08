// Horní blok, VARIANTA 06 (Robert 2026-09-17): "výplně jako 05, ale nechceme
// zkracovat žádné nohy, tzn budou to sloupce původní."
//
// Rozdíl proti 05: podélníky NEjsou jeden průběžný kus přes celou sestavu
// (což u 05 vyžadovalo zkrátit prostřední nohu, aby jí podélník "projel"
// nad koncem) - misto toho jsou SEGMENTOVANE po PŮVODNÍCH sloupcích (stejná
// topologie jako euroboxové lůžko - sloupec = úsek mezi dvěma sousedními
// nohama). Žádná noha se nezkracuje. Příčka je na KAŽDÉ noze (ne jen na
// krajních jako u 05), protože každý sloupcový segment potřebuje svou
// vlastní hranici na obou koncích - přesně stejný vzor jako existující
// stavPricky()/"pricka-spodni-<i>" v 2026-09-05_horni_ram.js pro spodní
// pásmo. Díky tomu, že yHor (5mm nad úhelníkem + 30) je HLUBOKO pod
// vrcholem nohy, podelnik() v "segmentovaném" režimu (`nahore=false`)
// nastává automaticky, beze změny sdíleného kódu.
//
// Pouziti: node 2026-09-17_horni_blok_var06.js <AID> <VOZIDLO>
const fs = require("fs");
const THREE = require("three");
global.THREE = THREE;
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { verifyAssembly } = require("/opt/konfigurator/scripts/2026-09-12_wide_verify_lib.js");
const { analyzuj, podelnik } = require("/opt/konfigurator/scripts/2026-09-05_horni_ram.js");

const T = 30, L0 = 1000, ZASUN = 7, DNO_VULE = 1;
const NAD_UHELNIKY = 5;
// bot8 2026-09-21: povinna mezera 30mm nad nejvyssim euroboxem (Robert
// 2026-09-06). Do 2026-09-21 se ram kotvil VYHRADNE k uhelnikum, takze
// u aut s vysokymi boxy vysel horni blok POD vrchem nejvyssiho boxu
// (zmereno az -76mm). analyzuj() nejvyssiBox uz vracela - jen se nepouzila.
const MEZERA_NAD_BOXY = 30;
const DESKA_MDF = "product_3939", DESKA_PLAST = "product_3950";
const PLAST_TL = 89, MDF_ZADA_TL_MM = 130, MDF_BOK_TL_MM = 130;
const Q_PRICNY = [0, 0, -0.7071067811865475, 0.7071067811865476];
const Q_PANEL_SVISLY = [0, 0.7071067811865476, 0, 0.7071067811865475];
const Q_PANEL_BOK = [0, 0, 0, 1];
const Q_DNO = [-0.7071067811865475, 0, 0, 0.7071067811865476];

function main() {
  const AID = process.argv[2], VOZIDLO = process.argv[3];
  const SCRATCH = process.argv[4] || "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
  const srcData = JSON.parse(fs.readFileSync(`${SCRATCH}/hb_src_${AID}.json`, "utf8"));
  const a = analyzuj(srcData);
  const nejvyssiUhelnik = a.nejvyssiUhelnik;
  if (nejvyssiUhelnik == null) throw new Error("sestava nema uhelniky");

  if (a.nejvyssiBox == null) throw new Error("sestava nema zadny eurobox - nelze overit povinnou 30mm mezeru nad boxem");
  // yDol = VYSSI ze dvou podminek, stejne jako 2026-09-05_horni_ram.js:271
  const yDolUhelnik = nejvyssiUhelnik + NAD_UHELNIKY;
  const yDolBox = a.nejvyssiBox + MEZERA_NAD_BOXY;
  const yDol = Math.max(yDolUhelnik, yDolBox);
  const yHor = yDol + T;
  console.log(`nejvyssiUhelnik=${nejvyssiUhelnik.toFixed(2)} (yDol ${yDolUhelnik.toFixed(2)}) nejvyssiBox=${a.nejvyssiBox.toFixed(2)} (yDol ${yDolBox.toFixed(2)}) rozhodlo=${yDolBox > yDolUhelnik ? "BOX" : "UHELNIK"} -> yDol=${yDol.toFixed(2)} yHor=${yHor.toFixed(2)} (nohy: ${a.celni.length}, sloupcu: ${a.celni.length - 1})`);
  // Over, ze zadna noha nesaha nad yHor (jinak by "segmentovany" rezim
  // podelnik() prepnul do "nahore" a zacal by zkracovat - presny opak
  // zadani "nechceme zkracovat zadne nohy").
  const prilisNizka = [...a.celni, ...a.zadni].find(s => s.y1 < yHor - 1e-6);
  if (prilisNizka) throw new Error(`noha ${prilisNizka.role}@${prilisNizka.z0} konci pod yHor (${prilisNizka.y1} < ${yHor}) - segmentovany rezim by ji zkratil, coz zadani zakazuje`);

  // --- 2x N-1 podelnik segmentu (celni, zadni) - PRESNA produkcni funkce, zadny zkratit ---
  const celniOut = podelnik(a.celni, yDol, yHor, "podelnik-celni-06");
  const zadniOut = podelnik(a.zadni, yDol, yHor, "podelnik-zadni-06");
  if (celniOut.zkratit.length || zadniOut.zkratit.length) throw new Error("podelnik() vratil zkratit i v segmentovanem rezimu - neocekavano, zkontrolovat yHor vs vysky noh");
  const nove = [...celniOut.dily, ...zadniOut.dily];

  // --- pricka NA KAZDE noze (stejny vzor jako stavPricky() pro spodni pasmo) ---
  // Pricka musi sahat od VNITRNI hrany jednoho podelniku k VNITRNI hrane
  // druheho (jako box-level "spojnice" D-2T mezi nosniky) - NE od stredu k
  // stredu druhe nohy (to by nechalo pulku cela podelniku nekryteho,
  // nalezeno pri dosed-kontrole: X-prekryv 15mm misto pozadovanych 30mm).
  const xCelni0 = (a.celni[0].x0 + a.celni[0].x1) / 2, xZadni0 = (a.zadni[0].x0 + a.zadni[0].x1) / 2;
  const xPrickaOd = Math.min(xCelni0, xZadni0) + T / 2;
  const xPrickaDo = Math.max(xCelni0, xZadni0) - T / 2;
  a.zadni.forEach((noha, i) => {
    const z = (noha.z0 + noha.z1) / 2;
    nove.push({ part_id: "Object_7", position: [(xPrickaOd + xPrickaDo) / 2, (yDol + yHor) / 2, z],
      quaternion: Q_PRICNY, scale: [1, (xPrickaDo - xPrickaOd) / L0, 1], role: `pricka-06-${i}` });
  });

  // --- mdf dno + steny, SEGMENTOVANE po sloupcich (N-1 kusu, jako vypln-zada/-dno u 01-04) ---
  const xCelni = (a.celni[0].x0 + a.celni[0].x1) / 2, xZadni = (a.zadni[0].x0 + a.zadni[0].x1) / 2;
  const xDnaA = Math.max(...a.zadni.map(s => s.x1)) - ZASUN, xDnaB = Math.min(...a.celni.map(s => s.x0)) + ZASUN;
  const xDnaOd = Math.min(xDnaA, xDnaB), xDnaDo = Math.max(xDnaA, xDnaB);
  for (let i = 0; i + 1 < a.zadni.length; i++) {
    const zOd = a.zadni[i].z1 + DNO_VULE / 2, zDo = a.zadni[i + 1].z0 - DNO_VULE / 2;
    if (zDo <= zOd) continue;
    nove.push({ part_id: DESKA_MDF, position: [(xDnaOd + xDnaDo) / 2, (yDol + yHor) / 2, (zOd + zDo) / 2],
      quaternion: Q_DNO, scale: [(xDnaDo - xDnaOd) / L0, (zDo - zOd) / L0, 1], role: `vypln-dno-06-${i}` });

    const zPanOd = a.celni[i].z1 - ZASUN, zPanDo = a.celni[i + 1].z0 + ZASUN;
    const bottomY = yHor - ZASUN, centerY = bottomY + PLAST_TL / 2;
    nove.push({ part_id: DESKA_PLAST, position: [xCelni, centerY, (zPanOd + zPanDo) / 2],
      quaternion: Q_PANEL_SVISLY, scale: [(zPanDo - zPanOd) / L0, PLAST_TL / L0, 1], role: `vypln-celo-06-${i}` });
    const centerYz = bottomY + MDF_ZADA_TL_MM / 2;
    nove.push({ part_id: DESKA_MDF, position: [xZadni, centerYz, (zPanOd + zPanDo) / 2],
      quaternion: Q_PANEL_SVISLY, scale: [(zPanDo - zPanOd) / L0, MDF_ZADA_TL_MM / L0, 1], role: `vypln-zada-06-${i}` });
  }
  // boční stěny - na KAŽDÉ noze (stejně jako příčky, žádná výjimka pro krajní/prostřední)
  a.zadni.forEach((noha, i) => {
    const z = (noha.z0 + noha.z1) / 2;
    const bottomY = yHor - ZASUN, centerY = bottomY + MDF_BOK_TL_MM / 2;
    nove.push({ part_id: DESKA_MDF, position: [(xPrickaOd + xPrickaDo) / 2, centerY, z],
      quaternion: Q_PANEL_BOK, scale: [(xPrickaDo - xPrickaOd) / L0, MDF_BOK_TL_MM / L0, 1], role: `vypln-bok-06-${i}` });
  });

  const parts = [...srcData.parts, ...nove]; // zadna zmena existujicich dilu - zadne zkraceni
  const report = verifyAssembly({ partsNew: nove, partsOrig: srcData.parts, carBodyBase: VOZIDLO, notchChecks: [], label: `${AID}-var06` });
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
  console.log(`dilu_novych=${nove.length} dilu_celkem=${parts.length} wall=${report.collisions} self-nove=${report.newProblems.length} (skutecnych ${skutecneProblemy.length}) OK=${ok}`);
  if (skutecneProblemy.length) console.log("SKUTECNE problemy:", JSON.stringify(skutecneProblemy, null, 1));

  fs.writeFileSync(`${SCRATCH}/var06_${AID}.json`, JSON.stringify({ parts, ok, yDol, yHor }));
}
main();
