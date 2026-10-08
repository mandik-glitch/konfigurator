// bot8 2026-09-21. Oprava porusene POVINNE 30mm mezery nad nejvyssim euroboxem
// (Robert 2026-09-06: "k tomu mezera 30 milimetru povinna a teprve tam muze
// zacinat horni blok") u sestav postavenych generatory variant 05/06/07, ktere
// pravidlo do 2026-09-21 nevynucovaly vubec (kotvily ram jen k uhelnikum).
//
// ROZSAH: jen sestavy s JEDNIM blokem (ram 05/06/07). Sestavy, kde je ram
// SOUCASNE s pasmem "01", se tudy NEOPRAVUJI - tam ram lezi pod pasmem a je to
// konstrukcni stret, ktery potrebuje rozhodnuti, ne mechanicky posun.
//
// POSTUP: tuha skupina (ram + vyplne + dvirka) se posune nahoru o (30 - mezera).
// U varianty 05 se navic PRODLOUZI stredova noha, kterou generator zkratil presne
// na spodek ramu - bez toho by pod posunutym podelnikem zustala viset ve vzduchu.
// Zaslepky NEmigruji (sedi na nezkracenych nohach) - stejna past jako u v11.
//
// Pouziti: node scripts/2026-09-21_bot8_oprava_30mm_mezery.js <hb_all.json> <split2.json> <out.json>
const THREE = require("three");
const fs = require("fs");
const { verifyAssembly, partMesh } = require("/opt/konfigurator/scripts/2026-09-12_wide_verify_lib.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");

const MIN_GAP = 30, L0 = 1000;
const RAM   = /-0[567](\b|-|$)/i;              // dily ramu varianty 05/06/07
const DVIRKA = /^dvirka/i;                      // dvirka varianty 07 (jedou s ramem)
const LEG   = /^(predni-svislice|cap)(\b|-|$)/i;
const ZAKAZ = /^(eurobox-|nosnik-|spojnice-|uhelnik|zaslepka|logo-ochrana|sloupek-pred-podbehem|zadni-svislice|pricka-uzavreni-vyrezu)/i;

const asms = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const jen = JSON.parse(fs.readFileSync(process.argv[3], "utf8")).jen;
const cile = new Map(jen.map(r => [r.id, r]));

const opraveno = [], blokovano = [];
for (const a of asms) {
  if (!cile.has(a.id)) continue;
  const parts = a.parts.filter(p => !R.jeKaroserie(p.part_id));
  const wb = parts.map(p => ({ p, box: new THREE.Box3().setFromObject(partMesh(p)) }));

  const eb = wb.filter(x => /^eurobox-/i.test(x.p.role || ""));
  const skupina = wb.filter(x => RAM.test(x.p.role || "") || DVIRKA.test(x.p.role || ""));
  if (!eb.length || !skupina.length) { blokovano.push({ id: a.id, duvod: "chybi eurobox nebo ram" }); continue; }

  // pojistka: v posouvane skupine nesmi byt nic, co k ramu nepatri
  const cizi = skupina.filter(x => ZAKAZ.test(x.p.role || ""));
  if (cizi.length) { blokovano.push({ id: a.id, duvod: "do skupiny spadly cizi role: " + cizi.map(x => x.p.role).join(",") }); continue; }

  const boxTop = Math.max(...eb.map(x => x.box.max.y));
  const ramBot = Math.min(...skupina.map(x => x.box.min.y));
  const gap = ramBot - boxTop;
  if (gap >= MIN_GAP - 0.01) { blokovano.push({ id: a.id, duvod: "uz vyhovuje, gap=" + gap.toFixed(1) }); continue; }
  const shift = MIN_GAP - gap;

  const movedIds = new Set(skupina.map(x => x.p));
  // varianta 05: stredova noha zkracena presne na spodek ramu -> prodlouzit o shift
  const prodlouzit = wb.filter(x => LEG.test(x.p.role || "") && Math.abs(x.box.max.y - ramBot) < 0.6);
  const partsNew = a.parts.map(p => {
    if (movedIds.has(p)) return { ...p, position: [p.position[0], p.position[1] + shift, p.position[2]] };
    if (prodlouzit.some(x => x.p === p)) {
      const sc = (p.scale || [1, 1, 1]).slice();
      sc[1] = sc[1] + shift / L0;                       // delka += shift
      return { ...p, scale: sc, position: [p.position[0], p.position[1] + shift / 2, p.position[2]] };
    }
    return p;
  });

  const vr = verifyAssembly({ partsNew, partsOrig: a.parts, carBodyBase: a.carBodyBase, notchChecks: [], label: `${a.id} +${shift.toFixed(1)}mm` });
  // kontrola vysledku: mezera i dosed prodlouzenych noh
  const wb2 = partsNew.filter(p => !R.jeKaroserie(p.part_id)).map(p => ({ p, box: new THREE.Box3().setFromObject(partMesh(p)) }));
  const ramBot2 = Math.min(...wb2.filter(x => RAM.test(x.p.role || "") || DVIRKA.test(x.p.role || "")).map(x => x.box.min.y));
  const gap2 = ramBot2 - boxTop;
  const dosedOk = prodlouzit.every(x => {
    const n = wb2.find(y => y.p.role === x.p.role && Math.abs(y.p.position[2] - x.p.position[2]) < 0.5);
    return n && Math.abs(n.box.max.y - ramBot2) < 0.6;
  });
  const zaznam = { id: a.id, kod: cile.get(a.id).kod, ok: cile.get(a.id).ok, gapPred: +gap.toFixed(1),
                   shift: +shift.toFixed(1), gapPo: +gap2.toFixed(1), posunuto: movedIds.size,
                   prodlouzenoNoh: prodlouzit.length, dosedOk, verifyOK: !!(vr && vr.OK) };
  if (!vr || !vr.OK) { zaznam.duvod = "verifyAssembly: " + JSON.stringify({ collisions: vr && vr.collisions, newProblems: vr && vr.newProblems && vr.newProblems.length }); blokovano.push(zaznam); continue; }
  if (Math.abs(gap2 - MIN_GAP) > 0.05) { zaznam.duvod = `mezera po oprave ${gap2.toFixed(1)}mm != 30`; blokovano.push(zaznam); continue; }
  if (!dosedOk) { zaznam.duvod = "prodlouzena noha nedoseda na ram"; blokovano.push(zaznam); continue; }
  zaznam.parts = partsNew;
  opraveno.push(zaznam);
}
console.log(`ROZSAH: ${cile.size} sestav k oprave (jen jeden blok)`);
console.log(`OPRAVENO (projde vsemi kontrolami): ${opraveno.length}`);
console.log(`BLOKOVANO: ${blokovano.length}`);
const perK = {}; opraveno.forEach(r => (perK[r.kod] = perK[r.kod] || []).push(r));
Object.keys(perK).sort().forEach(k => {
  const rs = perK[k];
  console.log(`   kod ${k}: ${rs.length}, posun ${Math.min(...rs.map(r=>r.shift)).toFixed(1)}-${Math.max(...rs.map(r=>r.shift)).toFixed(1)}mm, prodlouzenych noh celkem ${rs.reduce((s,r)=>s+r.prodlouzenoNoh,0)}`);
});
if (blokovano.length) { console.log("\nBLOKOVANE:"); blokovano.slice(0, 15).forEach(b => console.log(`   #${b.id} ${b.duvod}`)); }
fs.writeFileSync(process.argv[4], JSON.stringify(opraveno.map(({ parts, ...m }) => ({ ...m, parts })), null, 1));
console.log(`\nzapsano k nahrani: ${process.argv[4]}`);
