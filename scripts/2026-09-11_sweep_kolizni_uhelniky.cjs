// DRY-RUN: kolizni uhelniky napric CELYM katalogem. NIC NEZAPISUJE.
//
// Pouziti:
//   node scripts/2026-09-11_sweep_kolizni_uhelniky.cjs <sestavy.json> <out.json> [--jen-verdikt]
// kde <sestavy.json> je dump `SELECT id,name,data FROM product_assemblies`.
//
// `--jen-verdikt` vynecha vsechno, co slouzi jen k POPISU nalezu (odsun,
// rozmery spolecne hmoty, hledani nahradni polohy) a nechá jen odpoved
// "koliduje / nekoliduje". Je to tentyz vypocet nad temitez daty, jen bez
// domerovani - proto to NENI druhy skript. Rozdil je radovy:
//   cista sestava      0.09 s  ->  0.09 s   (domerovat neni co)
//   sestava s kolizi   2.26 s  ->  0.19 s
// Rezim je urceny pro PRIZNAK na sestave (cerveny nazev ve scene, sloupec
// v prehledove tabulce), ktery se prepocitava pri ulozeni sestavy. Podklad
// k Robertovu posouzeni se porad dela plnym behem.
//
// === KRITERIUM (Robert 2026-09-11, verze 3) ===
// Doslova: „Je jasné že různé auta mají různé tvary takže pokud se vyskytne
// kolizní úhelník tak nemusí mít stejnou pozici jako v doublu."
//
// Tim se rusi dosavadni dvoji podminka „prunik A soucasne DOLE V NOZE".
// Kriterium je nove CISTE GEOMETRICKE: dva dily koliduji, kdyz se prekryva
// jejich HMOTA. Kde na sestave to je, na verdiktu nic nemeni - jine auto ma
// jiny tvar, takze tataz vada sedi pokazde jinde.
//
// Ze zapisu k verzi 2 to ostatne uz vyplyvalo: zmereno bylo, ze „dole" a
// „jinde" jsou TATAZ vada (prekryv v X 29mm a Z 28mm je vzdy plny prurez
// profilu, lisi se jen Y), a bylo tam napsano, ze pravidlo mazat jen kusy
// „dole" nema fyzikalni oporu a drzi se jen protoze tak znelo zadani.
// Robert to ted rozhodl.
//
// === JAK SE KOLIZE ROZHODUJE ===
// NE `Box3` prekryvem. Ten je jen PREDFILTR (broad phase) - je to horni mez
// skutecneho pruniku, takze co jim neprojde, nemuze kolidovat. Verdikt dava
// `scripts/2026-09-11_mesh_kolize_lib.js`: navzorkuje prekryvovou oblast a
// hleda bod uvnitr OBOU skutecnych siti. Duvod je past c.8 ze skillu
// `3d-scena-spoje` - `Box3` prekryv sam o sobe neni dukaz kolize u dilu se
// stohovaci/vnorovaci geometrii (eurobox s vybranim na nozce vykazuje 12mm
// prekryv obalu a realne nekoliduje) a u POOTOCENEHO dilu nadhodnocuje.
// Rozdil neni teoreticky: zmereno nize v tabulce „obal vs hmota".
//
// Kalibrace + regresni test: scripts/2026-09-11_test_mesh_kolize.cjs
// (musi skoncit „VSECHNY KONTROLY OK"). Overuje mimo jine, ze test vybere
// ze sestavy 337 prave ty DVA uhelniky, ktere Robert 2026-09-10 nechal
// smazat - ani min, ani vic.
//
// === CO SE JESTE MERI ===
// U kazdeho nalezu se zkousi, jestli by kolizi odstranil POSUN uhelniku
// (±40mm po svetovych osach po 0.5mm) tak, aby si zaroven udrzel aspon dva
// dosedy na profily. To odlisuje „sestava je jen rozhozena" od „uhelnik tam
// nema co drzet" - viz `posun` ve vystupu. Je to MERENI, ne doporuceni;
// o osudu kazdeho kusu rozhoduje Robert.
const fs = require("fs");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const M = require("/opt/konfigurator/scripts/2026-09-11_mesh_kolize_lib.js");

const jeUhelnik = (p) => String(p.role || "").startsWith("uhelnik");
const TOL = M.TOL_MM;

// --- popis, KDE na sestave uhelnik sedi (pro cloveka, ne pro stroj) ---
const POPIS_PARTNERA = {
  "spojnice-dolni": "spodní spojnice nohy",
  "spojnice-dolni-kratka": "spodní krátká spojnice nohy",
  "spojnice-horni": "horní spojnice nohy",
  "spojnice-horni-uzavreni": "horní uzavírací spojnice",
  "pricka-uzavreni-vyrezu": "příčka uzavírající výřez (podběh)",
  "pricka-spodni-prepazka": "spodní příčka přepážky (horní blok)",
  "predni-svislice": "přední svislice",
  "zadni-svislice": "zadní svislice",
  "zadni-svislice-dolni": "zadní svislice, dolní část",
  "zadni-svislice-nad-zarezem": "zadní svislice nad zářezem",
  "sloupek-pred-podbehem": "sloupek před podběhem",
};
function popisPartnera(role) {
  if (POPIS_PARTNERA[role]) return POPIS_PARTNERA[role];
  let m = /^nosnik-sloupec(\d+)-patro(\d+)$/.exec(role) || /^nosnik-col(\d+)-p(\d+)$/.exec(role);
  if (m) return `nosník lůžka, sloupec ${m[1]} patro ${m[2]}`;
  m = /^spojnice-sloupec(\d+)-patro(\d+)$/.exec(role) || /^spojnice-col(\d+)-p(\d+)$/.exec(role);
  if (m) return `spojnice lůžka, sloupec ${m[1]} patro ${m[2]}`;
  m = /^eurobox-sloupec(\d+)-patro(\d+)$/.exec(role) || /^eurobox-col(\d+)-p(\d+)$/.exec(role);
  if (m) return `eurobox, sloupec ${m[1]} patro ${m[2]}`;
  m = /^vypln-dno-(\d+)$/.exec(role);
  if (m) return `dno horního bloku (MDF výplň ${m[1]})`;
  m = /^vypln-(\w+?)-/.exec(role);
  if (m) return `výplň horního bloku (${role})`;
  m = /^pricka-(\w+)/.exec(role);
  if (m) return `příčka horního bloku (${role})`;
  m = /^podelnik-/.exec(role);
  if (m) return `podélník horního bloku (${role})`;
  if (role === "zaslepka" || role.startsWith("zaslepka-")) return `záslepka (${role})`;
  if (role === "cap") return "čelo/cap profilu";
  return role || "(bez role)";
}
// Svisle zarazeni v ramci sestavy - jen orientacni popisek do vypisu.
function kdeSvisle(Y, orient) {
  if (orient.nosnikMin != null && Y < orient.nosnikMin) return "dole v noze, pod nejnižším nosníkem";
  if (orient.blokMin != null && Y >= orient.blokMin) return "v horním bloku";
  if (orient.nosnikMax != null && Y > orient.nosnikMax) return "nad nejvyšším nosníkem";
  return "uprostřed nohy, v pásmu lůžka";
}

// Dosed = obaly se DOTYKAJI na jedne ose (mezera do 0.2mm) a na zbylych dvou
// se plne prekryvaji. Heuristika pro popis, NE verdikt - verdikt dela mesh.
function maDosed(a, b) {
  const ov = M.prekryvBoxu(a.box, b.box);
  let dotyk = 0, prekryv = 0;
  for (const v of ov) { if (Math.abs(v) <= 0.2) dotyk++; else if (v > 1) prekryv++; }
  return dotyk === 1 && prekryv === 2;
}

// Zkusi posunout uhelnik tak, aby nekolidoval a zaroven si udrzel >= 2 dosedy.
// Vraci popis nalezeneho posunu, nebo null.
//
// POZOR, JAK SE TU MERI: hledani posunu pracuje s OBALKAMI, ne se siti -
// zkousena poloha se bere jako cista, kdyz obalka uhelniku nema s nicim
// prekryv > TOL. To je (a) konzervativni spravnym smerem (bez prekryvu obalek
// nemuze byt prunik siti) a (b) v teto scene i presne: z 351 941 porovnanych
// dvojic ma prekryv obalek vic nez 0.05mm jen 76 - spravne umisteny uhelnik
// lezi v rohu, kde se s profily jen DOTYKA (prekryv presne 0). Verdikt o
// kolizi ale dal dava sit, ne tohle; tohle je jen prohledavani prostoru
// poloh, ktere by se siti trvalo radove hodiny misto sekund.
function zkusPosun(u, ostatni) {
  const KROK = 0.5, MAX = 40;
  const puvodniDosedy = ostatni.filter(o => maDosed(u.g, o.g)).length;
  const cil = Math.min(2, puvodniDosedy);
  const box = u.g.box;
  const posunutyBox = (osa, d) => ({
    min: box.min.map((v, a) => a === osa ? v + d : v),
    max: box.max.map((v, a) => a === osa ? v + d : v),
  });
  for (let d = KROK; d <= MAX; d += KROK) {
    for (const osa of [0, 1, 2]) {
      for (const zn of [1, -1]) {
        const nb = posunutyBox(osa, zn * d);
        let kolize = false, dosedy = 0;
        for (const o of ostatni) {
          const ov = M.prekryvBoxu(nb, o.g.box);
          const mn = Math.min(ov[0], ov[1], ov[2]);
          if (mn > TOL) { kolize = true; break; }
          let dotyk = 0, prekryv = 0;
          for (const v of ov) { if (Math.abs(v) <= 0.2) dotyk++; else if (v > 1) prekryv++; }
          if (dotyk === 1 && prekryv === 2) dosedy++;
        }
        if (!kolize && dosedy >= cil) {
          return { o: Math.round(d * 10) / 10, osa: "XYZ"[osa], smer: zn > 0 ? "+" : "-", dosedy, puvodniDosedy };
        }
      }
    }
  }
  return null;
}

// ============================ BEH ============================
const vstup = process.argv[2], vystup = process.argv[3];
const jenVerdikt = process.argv.includes("--jen-verdikt");
if (!vstup || !vystup) {
  console.error("pouziti: node <skript> <sestavy.json> <out.json> [--jen-verdikt]");
  process.exit(2);
}
const vse = JSON.parse(fs.readFileSync(vstup, "utf8"));

let sestavSUhelniky = 0, uhCelkem = 0, paruCelkem = 0, paruBroad = 0;
let nezmereno = 0; const nezmereneDily = new Set();
const nalezy = [];
const t0 = Date.now();

let hotovo = 0;
for (const row of vse) {
  if (++hotovo % 25 === 0) process.stderr.write(`  ... ${hotovo}/${vse.length} sestav, nalezu ${nalezy.length}\n`);
  const d = typeof row.data === "string" ? JSON.parse(row.data) : row.data;
  const parts = ((d && d.parts) || []).filter(p => p.position);
  if (!parts.length) continue;
  if (!parts.some(jeUhelnik)) continue;
  sestavSUhelniky++;

  const prip = [];
  for (const p of parts) {
    if (R.jeKaroserie(p.part_id)) continue;       // zamerne vyloucene, viz resolver
    const f = R.glbPath(p.part_id);
    if (!f) { nezmereno++; nezmereneDily.add(p.part_id); continue; }
    prip.push({ p, f, g: M.dilVeSvete(f, p, parseGlbMesh) });
  }
  const uhelniky = prip.filter(e => jeUhelnik(e.p));
  uhCelkem += uhelniky.length;

  // orientacni svisle landmarky sestavy
  const Y = (f) => prip.filter(e => f(e.p.role || "")).map(e => e.p.position[1]);
  // POZOR: "horni blok" NENI kazda role zacinajici na `pricka`.
  // `pricka-uzavreni-vyrezu` je soucast NOHY pod blokem - siroke
  // startsWith("pricka") tady drive posadilo uhelniky z pasma luzka do
  // "horniho bloku". Predikat je zamerne stejny jako v
  // scripts/2026-09-11_smazat_stare_horni_bloky.py, aby si obe mista
  // nemohla vykladat "horni blok" ruzne.
  const jeBlok = (r) => r.startsWith("podelnik") || r.startsWith("vypln-")
    || r.startsWith("pricka-horni") || r.startsWith("pricka-police") || r.startsWith("pricka-spodni");
  const yNos = Y(r => r.startsWith("nosnik")), yBlok = Y(jeBlok);
  const orient = {
    nosnikMin: yNos.length ? Math.min(...yNos) : null,
    nosnikMax: yNos.length ? Math.max(...yNos) : null,
    blokMin: yBlok.length ? Math.min(...yBlok) : null,
  };

  for (const u of uhelniky) {
    // POZOR: partnerem je KAZDY jiny dil sestavy vcetne ostatnich uhelniku
    // a vcetne profilu vlastni nohy. Zadne preskoceni - prave preskakovani
    // vlastni nohy delalo starsi filtr slepym k 44 ze 44 skutecnych pruniku.
    const ostatni = prip.filter(e => e !== u);
    const kolizeS = [];
    for (const o of ostatni) {
      paruCelkem++;
      const ov = M.prekryvBoxu(u.g.box, o.g.box);
      if (Math.min(ov[0], ov[1], ov[2]) <= TOL) continue;   // broad phase
      paruBroad++;
      const k = M.kolize(u.g, o.g, TOL, jenVerdikt);
      if (k.koliduje) kolizeS.push({ o, k });
      if (k.koliduje && jenVerdikt) break;   // dalsi partneri uz verdikt nezmeni
    }
    if (!kolizeS.length) continue;
    kolizeS.sort((a, b) => b.k.odsun - a.k.odsun);
    const nej = kolizeS[0];
    const posun = jenVerdikt ? null : zkusPosun(u, ostatni);
    nalezy.push({
      asm: row.id,
      name: row.name || "",
      role: u.p.role,
      poz: u.p.position.map(v => Math.round(v * 10) / 10),
      Y: Math.round(u.p.position[1] * 10) / 10,
      kde: kdeSvisle(u.p.position[1], orient),
      odsun: nej.k.odsun,
      oblast: nej.k.oblast,
      typ: nej.k.typ,
      prunikBox: nej.k.prunikBox,
      doCeho: nej.o.p.role,
      doCehoPopis: popisPartnera(nej.o.p.role || ""),
      dalsi: kolizeS.slice(1).map(x => ({ role: x.o.p.role, odsun: x.k.odsun, oblast: x.k.oblast })),
      posun,
      dosedy: ostatni.filter(o => maDosed(u.g, o.g)).map(o => o.p.role),
    });
  }
}

if (jenVerdikt) {
  // Shrnuti PO SESTAVACH - presne to, co se uklada jako priznak na sestave.
  // Do vystupu patri KAZDA sestava, ktera se opravdu prosla - i ta BEZ
  // uhelniku. `uhelniku: 0` rika "zmereno, a zadne uhelniky tu nejsou",
  // coz je pravdivy vysledek, ne diry v mereni. Sestava, ktera tu chybi,
  // se nemerila vubec a jeji priznak musi zustat NULL.
  //
  // `kusy` NEOBSAHUJE milimetry a je to zamerne: tenhle rezim je nedopocital.
  // Kdyby pro ne bylo pole, vyplnilo by se nulou a radek by tvrdil
  // "koliduje o 0 mm". Co v radku neni, rika `rezim`.
  const podleSestav = {};
  for (const r of vse) {
    const d = typeof r.data === "string" ? JSON.parse(r.data) : r.data;
    const parts = ((d && d.parts) || []).filter(p => p.position);
    if (!parts.length) continue;                       // prazdna sestava = nemereno
    podleSestav[r.id] = { pocet: 0, uhelniku: parts.filter(jeUhelnik).length, kusy: [] };
  }
  for (const n of nalezy) {
    const z = podleSestav[n.asm];
    if (!z) continue;
    z.pocet++;
    z.kusy.push({ role: n.role, poz: n.poz, do: n.doCeho, kde: n.kde });
  }
  fs.writeFileSync(vystup, JSON.stringify({
    mereno: new Date().toISOString(),
    pravidlo: "v3",
    rezim: "verdikt",
    nastroj: "scripts/2026-09-11_sweep_kolizni_uhelniky.cjs --jen-verdikt",
    kontroluje: "uhelniky proti ostatnim dilum sestavy (NE vsechny dvojice dilu)",
    sestavy: podleSestav,
  }, null, 1));
} else {
  fs.writeFileSync(vystup, JSON.stringify(nalezy, null, 1));
}

// ---- ROZSAH MERENI patri do vystupu. „0 nalezu" je bez nej nerozeznatelne
// od „nic jsem nezmeril" (AGENTS_LOG.md 2026-09-11, tataz kontrola to
// predvedla trikrat po sobe). ----
console.log(`cas: ${((Date.now() - t0) / 1000).toFixed(1)}s`);
console.log(`sestav se vstupu: ${vse.length} | s uhelniky: ${sestavSUhelniky} | uhelniku: ${uhCelkem}`);
console.log(`mapa GLB: ${R.velikostMapy()} zaznamu`);
console.log(`porovnano paru: ${paruCelkem} | proslo predfiltrem obalu: ${paruBroad}`);
console.log(`KOLIZI POTVRZENYCH NA SITI: ${nalezy.length}`);
if (paruCelkem === 0) { console.error("\nCHYBA: neporovnal se ani jeden par - kontrola fakticky nebezela."); process.exit(1); }

if (nalezy.length) {
  console.log("\nobal vs hmota (proc Box3 nestaci):");
  for (const n of nalezy.slice().sort((a, b) => b.prunikBox - a.prunikBox).slice(0, 6)) {
    console.log(`   #${n.asm} ${n.role}: prekryv obalu ${n.prunikBox}mm -> hmota ${n.oblast.join("x")}mm, odsun ${n.odsun}mm`);
  }
  console.log("\npodle toho, do ceho pronikaji:");
  const h = {}; nalezy.forEach(n => { h[n.doCeho] = (h[n.doCeho] || 0) + 1; });
  Object.entries(h).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => console.log(`   ${k.padEnd(30)} ${v}x`));
  console.log("\npodle svisleho zarazeni (uz NENI kriterium, jen popis):");
  const s = {}; nalezy.forEach(n => { s[n.kde] = (s[n.kde] || 0) + 1; });
  Object.entries(s).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => console.log(`   ${k.padEnd(38)} ${v}x`));
  const lze = nalezy.filter(n => n.posun).length;
  console.log(`\nposunem do 40mm by kolize zmizela a dosedy zustaly: ${lze} z ${nalezy.length}`);
}
console.log(`\nnalezy -> ${vystup}`);

if (nezmereno) {
  console.error(`\nCHYBA: u ${nezmereno} dilu neslo zmerit geometrii: ${[...nezmereneDily].join(", ")}`
    + "\nVysledek NENI duveryhodny - ty dily se do kolizi nezapocitaly.");
  process.exit(1);
}
