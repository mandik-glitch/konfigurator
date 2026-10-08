// REGRESNI TEST mesh kolizniho testu (scripts/2026-09-11_mesh_kolize_lib.js).
// Spust po KAZDE zmene te knihovny:  node scripts/2026-09-11_test_mesh_kolize.cjs
//
// Testuje proti jedine autorite, kterou u tehle otazky mame - ROBERTOVU
// ODPOVEDI. 2026-09-10 mel vzor Dobla C (sestava 337) 29 uhelniku; Robert
// nechal cervene oznacit kolizni a rekl "tak presne ty 2 cervene uhelniky
// smazat a je to." Test tedy musi z tech 29 vybrat PRAVE TY DVA - ani min
// (slepy test), ani vic (mazal by kusy, ktere drzi).
// Data: backups/2026-09-10_pred_oznacenim_uhelniku.json (stav PRED smazanim).
//
// Druha cast overuje ZAKLADNI CHOVANI na syntetickych kvadrech, aby slo
// poznat, jestli pripadne selhani je v matematice nebo v datech:
//   dosed (sdilena rovina, prekryv 0)  -> NEKOLIDUJE   (jinak by test mazal spoje)
//   prunik 5mm                          -> KOLIDUJE, hloubka 5mm
//   mensi kvadr CELY uvnitr vetsiho     -> KOLIDUJE     (past c.7 skillu)
//   mezera 1mm                          -> NEKOLIDUJE
const fs = require("fs");
const THREE = require("/opt/konfigurator/node_modules/three");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const M = require("/opt/konfigurator/scripts/2026-09-11_mesh_kolize_lib.js");

let selhani = 0;
const ok = (podm, popis) => { console.log(`  ${podm ? "OK  " : "CHYBA"} ${popis}`); if (!podm) selhani++; };

// --- cast 1: synteticke kvadry (matematika) ---
function kvadr(cx, cy, cz, sx, sy, sz) {
  const g = new THREE.BoxGeometry(sx, sy, sz).toNonIndexed();
  const pos = g.attributes.position.array;
  const T = new Float64Array(pos.length);
  let mi = [Infinity, Infinity, Infinity], ma = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < pos.length; i += 3) {
    const v = [pos[i] + cx, pos[i + 1] + cy, pos[i + 2] + cz];
    T[i] = v[0]; T[i + 1] = v[1]; T[i + 2] = v[2];
    for (let k = 0; k < 3; k++) { if (v[k] < mi[k]) mi[k] = v[k]; if (v[k] > ma[k]) ma[k] = v[k]; }
  }
  const vrch = [], vid = new Set();
  for (let i = 0; i < T.length; i += 3) {
    const k = `${T[i].toFixed(3)},${T[i + 1].toFixed(3)},${T[i + 2].toFixed(3)}`;
    if (!vid.has(k)) { vid.add(k); vrch.push([T[i], T[i + 1], T[i + 2]]); }
  }
  return { T, vrch, box: { min: mi, max: ma } };
}
console.log("cast 1 - synteticke kvadry:");
const zaklad = kvadr(0, 0, 0, 100, 100, 100);
ok(M.kolize(zaklad, kvadr(100, 0, 0, 100, 100, 100)).koliduje === false, "dosed cela na celo (prekryv 0) -> NEKOLIDUJE");
const pr = M.kolize(zaklad, kvadr(95, 0, 0, 100, 100, 100));
ok(pr.koliduje === true && Math.abs(pr.odsun - 5) < 0.05, `prunik 5mm -> KOLIDUJE, odsun ${pr.odsun}mm (ocekavano 5)`);
ok(Math.abs(Math.min(...pr.oblast) - 5) < 1.0, `spolecna hmota ${pr.oblast.join(" x ")}mm (ocekavano 5 x 100 x 100)`);
const vnor = M.kolize(zaklad, kvadr(0, 0, 0, 20, 20, 20));
// POZOR: odsun NENI delka pruniku obalek. Obaly se prekryvaji o 20mm (cely
// maly kvadr), ale dostat ho z velkeho ven chce 60mm - a to je to, co
// odpovida na "slo by to spravit posunutim".
ok(vnor.koliduje === true && Math.abs(vnor.odsun - 60) < 0.2,
   `mensi kvadr CELY uvnitr -> KOLIDUJE (past c.7), odsun ${vnor.odsun}mm (ocekavano 60, prekryv obalek je pritom jen ${vnor.prunikBox}mm)`);
ok(M.kolize(zaklad, kvadr(101, 0, 0, 100, 100, 100)).koliduje === false, "mezera 1mm -> NEKOLIDUJE");
ok(M.kolize(zaklad, kvadr(0, 100, 0, 100, 100, 100)).koliduje === false, "dosed shora (prekryv 0) -> NEKOLIDUJE");

// PAST c.8 skillu `3d-scena-spoje`: `Box3` prekryv sam o sobe NENI dukaz
// kolize u dilu se stohovaci/vnorovaci geometrii. Zde: dil slozeny ze dvou
// kvadru s drazkou uprostred a lista, ktera do drazky presne zapada.
// Obaly se prekryvaji o celou sirku listy (20mm), hmota se neprekryva vubec.
// Kdyby verdikt delal `Box3`, hlasil by 20mm kolizi - proto ho nedela.
function spoj(...dily) {
  const T = new Float64Array(dily.reduce((n, d) => n + d.T.length, 0));
  let o = 0; for (const d of dily) { T.set(d.T, o); o += d.T.length; }
  const mi = [Infinity, Infinity, Infinity], ma = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < T.length; i += 3) for (let a = 0; a < 3; a++) { if (T[i + a] < mi[a]) mi[a] = T[i + a]; if (T[i + a] > ma[a]) ma[a] = T[i + a]; }
  const vrch = [], vid = new Set();
  for (let i = 0; i < T.length; i += 3) { const k = `${T[i].toFixed(3)},${T[i + 1].toFixed(3)},${T[i + 2].toFixed(3)}`; if (!vid.has(k)) { vid.add(k); vrch.push([T[i], T[i + 1], T[i + 2]]); } }
  return { T, vrch, box: { min: mi, max: ma } };
}
const sDrazkou = spoj(kvadr(-30, 0, 0, 40, 100, 100), kvadr(30, 0, 0, 40, 100, 100));  // drazka x od -10 do 10
const lista = kvadr(0, 0, 0, 20, 100, 100);                                             // presne do drazky
const vnoreni = M.kolize(sDrazkou, lista);
ok(Math.min(...M.prekryvBoxu(sDrazkou.box, lista.box)) >= 19.9, `obal hlasi prekryv ${Math.min(...M.prekryvBoxu(sDrazkou.box, lista.box))}mm (Box3 by rekl kolize)`);
ok(vnoreni.koliduje === false, "dil zapadly do drazky -> NEKOLIDUJE (past c.8: obal prekryv ma, hmota ne)");
const zaboreno = M.kolize(sDrazkou, kvadr(0, 0, 0, 26, 100, 100));
ok(zaboreno.koliduje === true, "sirsi lista do teze drazky -> KOLIDUJE");
// `oblast` se mericonecnou mrizkou pres celou prekryvovou oblast, takze ma
// presnost jednoho kroku (tady 26mm/32 = 0.8mm). Je to POPIS tvaru prekryvu;
// cislo, na kterem zalezi, je `odsun` - ten se doladuje pulenim na 0.05mm.
ok(Math.abs(Math.min(...zaboreno.oblast) - 3) < 1.0,
   `spolecna hmota je po ~3mm na obou stranach: ${zaboreno.oblast.join(" x ")}mm (nejmensi rozmer ocekavan 3, presnost mrizky ~0.8mm)`);
ok(zaboreno.odsun > 50,
   `posunutim se to nespravi - odsun ${zaboreno.odsun}mm (lista je sirsi nez drazka, musela by z ni cela ven)`);

// Site v katalogu NEJSOU vodotesne: profil je vytlaceny prurez otevreny na
// koncich. Paprsek poslany po ose trubky z hmoty steny vyleti bez jedineho
// pruseciku -> parita by rekla "vne". Tenhle test to drzi zmerene, protoze
// prave na tom 2026-09-11 zkrachovala jedna optimalizace.
console.log("\ncast 1b - vodotesnost katalogovych siti:");
const profil = M.dilVeSvete(R.glbPath("product_3539") || "/opt/konfigurator/webapp/katalog/profil_30x30_uzavreny.glb",
  { position: [0, 0, 0] }, parseGlbMesh);
M.analyzujSit(profil);
ok(typeof profil._vodotesna === "boolean", `vodotesnost se meri (profil: ${profil._vodotesna ? "uzavrena" : "OTEVRENA sit"})`);

// --- cast 2: Robertova odpoved na sestave 337 ---
console.log("\ncast 2 - sestava 337, stav pred 2026-09-10 (Robert smazal prave 2 z 29):");
const zal = JSON.parse(fs.readFileSync("/opt/konfigurator/backups/2026-09-10_pred_oznacenim_uhelniku.json", "utf8"));
const row = zal.find(r => r.id === 337);
const dd = typeof row.data === "string" ? JSON.parse(row.data) : row.data;
const prip = [];
let nezmereno = 0;
for (const p of dd.parts) {
  if (!p.position) continue;
  if (R.jeKaroserie(p.part_id)) continue;
  const f = R.glbPath(p.part_id);
  if (!f) { nezmereno++; continue; }
  prip.push({ p, g: M.dilVeSvete(f, p, parseGlbMesh) });
}
ok(nezmereno === 0, `vsechny dily zmereny (nezmerenych: ${nezmereno})`);
const uh = prip.filter(e => (e.p.role || "").startsWith("uhelnik"));
const ost = prip.filter(e => !(e.p.role || "").startsWith("uhelnik"));
ok(uh.length === 29, `uhelniku v sestave: ${uh.length} (ocekavano 29)`);

const SMAZANE = [[-402.5, 53.5], [-557.5, 53.5]];
const jeSmazany = p => SMAZANE.some(([x, y]) => Math.abs(p.position[0] - x) < 0.5 && Math.abs(p.position[1] - y) < 0.5);
let paru = 0, nalezeno = 0, neshoda = 0;
for (const u of uh) {
  let nej = null;
  for (const o of ost) { paru++; const k = M.kolize(u.g, o.g); if (k.koliduje && (!nej || k.odsun > nej.k.odsun)) nej = { k, o }; }
  const s = jeSmazany(u.p);
  if (nej) nalezeno++;
  if (s !== !!nej) { neshoda++; console.log(`     NESHODA ${u.p.role} poz=[${u.p.position.map(v => Math.round(v * 10) / 10)}] Robert=${s ? "smazal" : "ponechal"} test=${nej ? "kolize" : "cisto"}`); }
  else if (s) console.log(`     shoda: ${u.p.role} poz=[${u.p.position.map(v => Math.round(v * 10) / 10)}] -> odsun ${nej.k.odsun}mm, hmota ${nej.k.oblast.join("x")}mm do ${nej.o.p.role}`);
}
ok(paru > 0, `porovnano paru: ${paru} (nula = test fakticky nebezel)`);
ok(neshoda === 0, `shoda s Robertovym rozhodnutim u vsech 29 uhelniku (neshod: ${neshoda})`);
ok(nalezeno === 2, `nalezeno kolizi: ${nalezeno} (ocekavano prave 2)`);

console.log(selhani ? `\nSELHALO ${selhani} kontrol` : "\nVSECHNY KONTROLY OK");
process.exit(selhani ? 1 : 0);
