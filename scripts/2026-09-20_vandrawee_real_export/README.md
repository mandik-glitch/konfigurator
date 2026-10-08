# Skutečný vanDrawee FBX export → katalogový GLB

Kompletní, ověřený pipeline pro převod FBX z tlačítka "Exportovat FBX"
v `test.logiman.cz/admin/work-stored-model` na GLB použitelný v
`webapp/katalog/`. Kontext a proč jednotlivé kroky existují: viz
`VANDR_RENDER_HOWTO.md`, sekce "⭐ Skutečný export CELÉ sestavy z
appky". Ověřeno na Renault Trafic L2H1 (2026-09-20), potvrzeno bota4
(Blender import/render) a Robertem živě ve scéně.

## Soubory

- `FBXLoader_patched.js` — patchnutá kopie `three@0.128.0`
  `examples/jsm/loaders/FBXLoader.js`. NENÍ totožná s `node_modules`
  verzí — opravuje 3 reálné bugy specifické pro tenhle typ exportu
  (prázdné `a: ` FBX pole parsovaná jako `[NaN]` místo `[]`, chybějící
  `UVIndex`, Model typu "Mesh" bez navázané Geometry). Nekopírovat
  zpátky do `node_modules` (sdílený balíček), jen používat odsud.
- `convert_template.html` — šablona pro Playwright/prohlížeč: načte
  `./model.fbx`, vyloučí `dimensions`/`text`/`karoserie`, převede
  Phong materiály na Standard (roughness ze skutečného shininess,
  metalness=0.6 jen pro `\balu\b`-pojmenované), vyexportuje GLB jako
  base64 do `window.__GLB_BASE64__`.
- `sanitize_glb.py` — pojistka po exportu: přepočítá/zahodí neplatné
  `accessors[].min/max`, `nodes[].matrix/translation/rotation/scale`,
  `materials[].baseColorFactor/emissiveFactor`, finální sweep na
  zbytkové NaN/Infinity. Spouštět VŽDY, i když `convert_template.html`
  neohlásí chybu — NaN se v three.js/prohlížeči neprojeví, ale rozbije
  striktní validátory (Blender).
- `scale_to_mm.py` — převod POSITION dat a node translací z metrů
  (glTF/three.js default, appka dumpuje Unity world-space přímo) na
  milimetry (katalogová konvence, `PRODUKTOVE_RENDERY.md` bod 8).
  NEmění `normal`/`rotation`/`scale` (jednotkově nezávislé).

## Použití (nové FBX)

```bash
SP=<scratchpad pracovní adresář>
mkdir -p "$SP/render3d/jsm/loaders" "$SP/render3d/jsm/libs" "$SP/render3d/jsm/curves" "$SP/render3d/jsm/exporters"
cp /opt/konfigurator/node_modules/three/build/three.module.js "$SP/render3d/"
cp /opt/konfigurator/scripts/2026-09-20_vandrawee_real_export/FBXLoader_patched.js "$SP/render3d/jsm/loaders/FBXLoader.js"
cp /opt/konfigurator/node_modules/three/examples/jsm/exporters/GLTFExporter.js "$SP/render3d/jsm/exporters/"
cp -r /opt/konfigurator/node_modules/three/examples/jsm/libs/* "$SP/render3d/jsm/libs/"
cp /opt/konfigurator/node_modules/three/examples/jsm/curves/*.js "$SP/render3d/jsm/curves/"
cp /opt/konfigurator/scripts/2026-09-20_vandrawee_real_export/convert_template.html "$SP/render3d/convert.html"
cp <novy_export>.fbx "$SP/render3d/model.fbx"

cd "$SP/render3d" && python3 -m http.server <PORT> &
node -e "
const { chromium } = require('/opt/konfigurator/node_modules/playwright');
const fs = require('fs');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('http://127.0.0.1:<PORT>/convert.html');
  await page.waitForFunction('window.__RENDER_DONE__ === true', { timeout: 30000 });
  const b64 = await page.evaluate(() => window.__GLB_BASE64__);
  fs.writeFileSync('$SP/raw.glb', Buffer.from(b64, 'base64'));
  await browser.close();
})();
"
pkill -f "http.server <PORT>"

python3 /opt/konfigurator/scripts/2026-09-20_vandrawee_real_export/sanitize_glb.py "$SP/raw.glb" "$SP/sanitized.glb"
python3 /opt/konfigurator/scripts/2026-09-20_vandrawee_real_export/scale_to_mm.py "$SP/sanitized.glb" "$SP/final_mm.glb"
# -> nasadit final_mm.glb do webapp/katalog/ (přes lock.sh, guarded path)
```

**Před nasazením vždy ověř** (GLTFLoader round-trip, ne jen důvěřovat
exportu): velikost bounding boxu proti reálnému rozměru vozidla/regálu
a `meshCount` — viz `verify_sanitized.html` vzor v týhle session
(neuložen, byl to jednorázový diagnostický skript, ale je triviální
znovu napsat: `new THREE.Box3().setFromObject(gltf.scene)`).

## Co se NEŘEŠÍ tímhle pipeline (vědomě mimo rozsah)

- Karoserie se vždy vylučuje (Robertovo trvalé pravidlo) - žádný
  přepínač na "chci i karoserii".
- Žádná per-materiál diverze roughness/metalness nad rámec toho, co
  FBX skutečně nese (viz VANDR_RENDER_HOWTO.md bod 2) - není to
  fotorealistické PBR, je to nejinformovanější přiblížení z dostupných
  dat.
