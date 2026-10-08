// CERSTVY audit orientace VSECH karoserii - mereno ZE SOUCASNEHO STAVU GLB.
// bot8 2026-09-05.
//
//   node scripts/2026-09-05_orientace_audit.js            # zapise /tmp/orient_audit_fresh.jsonl
//   node scripts/2026-09-05_orientace_audit.js --report   # jen vypis, nic nezapise
//
// PROC EXISTUJE (kriticke): `mass_orientation_fix.js` cte hotovy audit ze
// souboru /tmp/orient_audit_fresh.jsonl. Ten se ale generoval jednou (2026-09-05
// 10:47) a od te doby uz nekolik karoserii flipnuto BYLO - v tom starem souboru
// jsou ale porad vedene jako NEEDS_FLIP. Spusteni `--all` nad zastaralym auditem
// by je flipnulo PODRUHE, tedy zpatky do spatne orientace.
//
// Tenhle skript audit pokazde PREMERI z aktualnich GLB souboru, takze:
//   - uz spravne otocene karoserie se preskoci (nikdy dvojity flip),
//   - cely postup je IDEMPOTENTNI a nezavisly na poradi drivejsich behu
//     (nevadi, jestli uz nekdo drive flipnul CI18 nebo pet Jumpy zvlast),
//   - opakovane spusteni celeho procesu nic nerozbije.
//
// Kriterium (KAROSERIE_UMISTENI.md, Robert: "kdyz se vlozi do sceny, musim se
// divat do zadnich dveri auta"): B_midZ = stred bounding boxu prepazky "B"
// v ose Z. B_midZ < -50 = OK, > +50 = NEEDS_FLIP.
//
// Format vystupu je zamerne shodny s puvodnim auditem, aby ho
// `mass_orientation_fix.js` precetl beze zmeny (klice base / ids / verdict).
const fs = require("fs");
const path = require("path");

const KAT = "/opt/konfigurator/webapp/katalog/";
const OUT = "/tmp/orient_audit_fresh.jsonl";
const REPORT_ONLY = process.argv.includes("--report");

// B_midZ primo z hlavicky GLB (accessors[].min/max) - nemusi se dekodovat
// binarni chunk, staci JSON chunk. Stejna technika jako puvodni audit.
function accBounds(file) {
  const b = fs.readFileSync(file);
  if (b.readUInt32LE(0) !== 0x46546c67) throw new Error(`${file}: neni glb`);
  let off = 12;
  while (off < b.length) {
    const len = b.readUInt32LE(off), type = b.readUInt32LE(off + 4);
    if (type === 0x4e4f534a) {
      const j = JSON.parse(b.slice(off + 8, off + 8 + len).toString("utf8"));
      let min = null, max = null;
      for (const mesh of j.meshes || []) {
        for (const prim of mesh.primitives || []) {
          const ai = prim.attributes && prim.attributes.POSITION;
          if (ai == null) continue;
          const a = j.accessors[ai];
          if (!a.min || !a.max) continue;
          min = min ? min.map((v, i) => Math.min(v, a.min[i])) : a.min.slice();
          max = max ? max.map((v, i) => Math.max(v, a.max[i])) : a.max.slice();
        }
      }
      if (!min) throw new Error(`${file}: zadny POSITION accessor s min/max`);
      return { min, max };
    }
    off += 8 + len;
  }
  throw new Error(`${file}: chybi JSON chunk`);
}

function main() {
  // Seznam karoserii se cte z dumpu, ktery pripravi doprovodny python skript
  // (Node tu nema pristup k MySQL). Format radku: <id>\t<glb_file>\t<model_name>
  const DUMP = "/tmp/orient_car_bodies_dump.tsv";
  if (!fs.existsSync(DUMP)) {
    console.error(`CHYBI ${DUMP} - spust nejdriv scripts/2026-09-05_orientace_dump.py`);
    process.exit(1);
  }
  const rows = fs.readFileSync(DUMP, "utf8").split("\n").filter(l => l.trim())
    .map(l => { const [id, glb, model] = l.split("\t"); return { id: Number(id), glb, model }; });

  // seskup po modelech podle spolecneho zakladu cesty (bez _L/_R_D/_B pripony)
  const SUF = ["_L.glb", "_R_D.glb", "_B.glb", "_B_wall.glb"];
  const models = new Map();
  for (const r of rows) {
    const sufHit = SUF.find(s => r.glb.endsWith(s));
    if (!sufHit) continue;
    const base = r.glb.slice(0, -sufHit.length);
    if (!models.has(base)) models.set(base, { base, model: r.model, ids: [], files: {} });
    const m = models.get(base);
    m.ids.push(r.id);
    m.files[sufHit] = r.glb;
  }

  const out = [];
  let need = 0, ok = 0, unc = 0, missing = 0;
  for (const m of [...models.values()].sort((a, b) => a.base.localeCompare(b.base))) {
    const bFile = m.files["_B.glb"] || m.files["_B_wall.glb"];
    if (!bFile || !fs.existsSync(KAT + bFile)) { missing++; continue; }
    let bnd;
    try { bnd = accBounds(KAT + bFile); }
    catch (e) { console.error(`  CHYBA ${bFile}: ${e.message}`); missing++; continue; }
    const midZ = (bnd.min[2] + bnd.max[2]) / 2;
    const verdict = midZ > 50 ? "NEEDS_FLIP" : midZ < -50 ? "OK" : "UNCERTAIN";
    if (verdict === "NEEDS_FLIP") need++; else if (verdict === "OK") ok++; else unc++;
    out.push({
      base: m.base, name: m.model || null,
      ids: m.ids.join("/"),
      B_minZ: bnd.min[2], B_maxZ: bnd.max[2], B_midZ: midZ,
      B_minX: bnd.min[0], B_maxX: bnd.max[0],
      verdict,
    });
  }

  console.log(`Modelu zmereno: ${out.length}`);
  console.log(`  NEEDS_FLIP (opacne): ${need}`);
  console.log(`  OK:                  ${ok}`);
  console.log(`  UNCERTAIN:           ${unc}`);
  if (missing) console.log(`  bez souboru B / chyba: ${missing}`);

  if (REPORT_ONLY) {
    console.log("\n--- prvnich 25 NEEDS_FLIP ---");
    out.filter(r => r.verdict === "NEEDS_FLIP").slice(0, 25)
      .forEach(r => console.log(`  ${r.base.split("/").pop()}  B_midZ=${Math.round(r.B_midZ)}`));
    console.log("\n(--report: nic se nezapsalo)");
    return;
  }
  fs.writeFileSync(OUT, out.map(r => JSON.stringify(r)).join("\n") + "\n");
  console.log(`\nZapsano: ${OUT}`);
}

main();
