// Reference ceny konfigurace = SKUTECNE funkce ze scene.html (bot5, 2026-10-02).
// Vytahne computeAssemblyBomAndPrice, currentWeightPrice, partDisplayName, JOINT_RULE_VERSION a isImportPreviewEntry ze
// webapp/scene.html a isProfilePart/isStampPart/isKontrolniPart/isCarBodyPart (+ jejich konstanty) ze sdileneho
// webapp/js/scene-geometry-shared.js a pusti je ve vm. Jedine ATRAPY: currentLengthMm() a currentBoardDimsMm() - ve scene meri
// delku/rozmery z konektoru ve 3D (geometrie, kterou v konfiguraci dodava compose()), tady vraci hodnoty zadane scenarem;
// cela ARITMETIKA (soucty, zaokrouhleni, seskupeni kusovniku, balne, montaz) je puvodni kod ze sceny.
//
// Pouziti: node reference_scena.js < vstup.json > vystup.json
//   vstup : {"parts": {id: dil v tvaru CATALOG ze sceny}, "scenarios": [{"pricing": {...PRICING_CONFIG}, "entries":
//            [{"id", "length_mm", "width_mm", "height_mm", "joint_count", "custom_color"}]}]}
//   vystup: [{"bom": [...], "price_summary": {...}}, ...] ve stejnem poradi jako scenare
// Kandidat/jina verze sceny: SCENE_HTML=... SHARED_JS=... node reference_scena.js
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const REPO = path.join(__dirname, '../..');
const SCENE_HTML = process.env.SCENE_HTML || path.join(REPO, 'webapp/scene.html');
const SHARED_JS = process.env.SHARED_JS || path.join(REPO, 'webapp/js/scene-geometry-shared.js');

// vytahne zdroj funkce (od "function <jmeno>(" po jeji parovou "}") - pocitanim slozenych zavorek
function vytahniFunkci(src, jmeno) {
  const start = src.indexOf('function ' + jmeno + '(');
  if (start < 0) throw new Error('funkce nenalezena: ' + jmeno);
  let i = src.indexOf('{', src.indexOf(')', start)), depth = 0, inStr = null, inLine = false, inBlock = false;
  for (; i < src.length; i++) {
    const c = src[i], n = src[i + 1];
    if (inLine) { if (c === '\n') inLine = false; continue; }
    if (inBlock) { if (c === '*' && n === '/') { inBlock = false; i++; } continue; }
    if (inStr) { if (c === '\\') { i++; continue; } if (c === inStr) inStr = null; continue; }
    if (c === '/' && n === '/') { inLine = true; continue; }
    if (c === '/' && n === '*') { inBlock = true; continue; }
    if (c === '"' || c === "'" || c === '`') { inStr = c; continue; }
    if (c === '{') depth++;
    else if (c === '}') { depth--; if (depth === 0) return src.slice(start, i + 1); }
  }
  throw new Error('nenalezen konec funkce ' + jmeno);
}
function vytahniRadek(src, re, popis) {
  const m = re.exec(src);
  if (!m) throw new Error('radek nenalezen: ' + popis);
  return m[0];
}

const scene = fs.readFileSync(SCENE_HTML, 'utf8');
const shared = fs.readFileSync(SHARED_JS, 'utf8');
const kod = [
  vytahniRadek(shared, /^const STAMP_ROLE_PREFIX = .*;$/m, 'STAMP_ROLE_PREFIX'),
  vytahniRadek(shared, /^const KONTROLNI_ROLE_PREFIX = .*;$/m, 'KONTROLNI_ROLE_PREFIX'),
  vytahniRadek(shared, /^const CAR_BODY_ID_PREFIX = .*;$/m, 'CAR_BODY_ID_PREFIX'),
  vytahniFunkci(shared, 'isProfilePart'),
  vytahniFunkci(shared, 'isStampPart'),
  vytahniFunkci(shared, 'isKontrolniPart'),
  vytahniFunkci(shared, 'isCarBodyPart'),
  vytahniFunkci(scene, 'isImportPreviewEntry'),
  vytahniFunkci(scene, 'partDisplayName'),
  vytahniFunkci(scene, 'currentWeightPrice'),
  vytahniRadek(scene, /^const JOINT_RULE_VERSION = \d+;$/m, 'JOINT_RULE_VERSION'),
  vytahniFunkci(scene, 'computeAssemblyBomAndPrice'),
  // ATRAPY merení geometrie (ve scene z konektoru ve 3D): vraci hodnoty z entry
  'function currentLengthMm(entry) { return entry._len == null ? null : entry._len; }',
  'function currentBoardDimsMm(entry) { return entry._dims || null; }',
  `var PRICING_CONFIG = {};
   var __parts = {};
   function __run(scenarioJson) {
     const sc = JSON.parse(scenarioJson);
     PRICING_CONFIG = sc.pricing;
     const entries = sc.entries.map(e => ({
       part: __parts[e.id], jointCount: e.joint_count, customColor: e.custom_color,
       _len: e.length_mm == null ? null : e.length_mm,
       _dims: e.width_mm == null ? null : { widthMm: e.width_mm, heightMm: e.height_mm },
     }));
     return JSON.stringify(computeAssemblyBomAndPrice(entries));
   }
   function __setParts(json) { __parts = JSON.parse(json); }
   function __version() { return JOINT_RULE_VERSION; }`,
].join('\n');

const ctx = vm.createContext({});
vm.runInContext(kod, ctx);

let vstup = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', d => { vstup += d; });
process.stdin.on('end', () => {
  const data = JSON.parse(vstup);
  ctx.__setParts(JSON.stringify(data.parts));
  const vysledky = data.scenarios.map(sc => JSON.parse(ctx.__run(JSON.stringify(sc))));
  process.stdout.write(JSON.stringify({ joint_rule_version: ctx.__version(), vysledky }));
});
