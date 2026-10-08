# Jak vyrenderovat skutečný 3D model z Vandr (postup, ne teorie)

Tenhle soubor je návod krok za krokem, jak vzít reálný FBX model z
Vandr zdrojáků (`/opt/vandrawee/unity/Assets/Models/vandrawee/`) a
vyrenderovat ho jako skutečný obrázek (ne kresbu/řez) — ověřeno funkční
2026-09-06/07. Cíl: příští session tohle nemusí znovu objevovat.

**Kdy tenhle postup použít:** když chceš Robertovi UKÁZAT sestavu (on
řekl explicitně "Mě nezajímají tvoje řezy, chci vidět sestavený
regál") — technické řezy (`scripts/2026-08-20_live_section_cut.js` -
OPRAVENO audit bot9 2026-09-12) jsou
pro schvalování PŘESNÉ POZICE dílu v naší vlastní geometrii, tohle je
pro rychlou vizuální kontrolu "vypadá to jako ta věc". **`section_cut.js`
(samostatný rig, díl si orientuje sám) se pro schvalovací řez NESMÍ
použít** - viz `PRAVIDLA_SPOJU.md`, incident kolečko 3404; je platný jen
pro tabulky variant před výběrem.

## ⭐ ZÁVAZNÉ pravidlo — 2D kontrola je AUTOMATICKÁ SOUČÁST, ne bonus na vyžádání

**Robert (2026-09-07, po opakovaném "ukaž mi to ve 2D... proč to mám
pořád opakovat"): U KAŽDÉHO nově umístěného Vandr komponentu (noha i
komponenta v zóně) se 2D kontrola (bokorys + čelní, izolovaný wireframe
pár, viz krok 3d) dělá VŽDY, BEZ VYZVÁNÍ — hned jak je 3D render
hotový, ne až Robert řekne "ukaž mi 2D".** Není to volitelný krok pro
zvlášť podezřelé případy — je to POVINNÁ součást každého "postav
nohy/vlož komponentu" úkolu, stejně samozřejmá jako číselná kontrola
(3c). Pořadí u nové sestavy: (1) 3D náhled pro celkový dojem, (2) 2D
bokorys+čelní pro KAŽDÝ nově přidaný díl vůči noze, automaticky, ve
STEJNÉ odpovědi — ne až po dotazu.

## ⭐ ZÁVAZNÉ pravidlo — otočka podle strany regálu (pravý/levý)

**Robert (2026-09-22): Vandr regály mají DVĚ různé otočky podle strany:**

* **pravé regály** (right): azimuty **30°, 60°, 90°, 120°, 150°**
* **levé regály** (left): azimuty **210°, 240°, 270°, 300°, 330°**

Určeno na základě prohlídky celé 100-vzorkové otočky Ducata L1H1
(sestava 672).

**Mechanismus, JAK poznat stranu podle kódu (Robert: "zjisti mechanismus
z adminu podle kodu, vsechny sestavy tam maji tabulku") — je to skutečná
DB hodnota, nehádej ji z 3D pohledu:**

1. `shop_products.sku` u Vandr karet má tvar `VD-<uuid>` — ten `<uuid>`
   je `vandrawee_work.stored_models.uuid` (BINARY16, stejný postup jako
   `_lookup_vandr_metadata()` v `scripts/2026-09-22_vandr_fbx_watcher.py`).
2. `stored_models` má **PRÁVĚ JEDEN** ze sloupců `left_part_id` /
   `right_part_id` / `bulkhead_part_id` vyplněný (ostatní dva NULL) —
   to je strana. `bulkhead_part_id` = regál za přepážkou (kabina),
   nemá levou/pravou stranu vůbec, netýká se týhle otočky.
3. Náš `product_assemblies` má na tohle mířený sloupec `umisteni_id`
   (FK na `regal_umisteni`: `RL`=regal_levy, `RP`=regal_pravy,
   `RK`=kabina) — u nových Vandr sestav ho při zakládání rovnou vyplň
   podle bodu 2, ať to admin panel "Přehledy > Typologie/umístění
   regálů" (`api/regal_osy_prehled.py`) ukazuje živě, ne až
   dodatečně.

**Ověřeno k 2026-09-22:**
- **Ducato L1H1 (672 / shop_products 4903 / uuid `2b6d4dd7-...`)** →
  `stored_models.id=661`, `right_part_id=659` (type `right`),
  `left_part_id=NULL` → **PRAVÝ regál** → otočka 30/60/90/120/150°.
  Zapsáno i do `product_assemblies.umisteni_id=7` (RP).
- **Trafic L2H1 (671 / shop_products 4902 / uuid `2f89b425-...`)** →
  odpovídající `stored_models.id=338` **v DB už neexistuje** (byl to
  úplně první ruční test 2026-09-20, před watcherem/retencí) — stranu
  nelze zpětně ověřit stejným mechanismem. `shop_products.name` má
  text "leva police", ale to je popisek napsaný botem, NE ověřená DB
  hodnota — neber ho jako důkaz strany, dokud nepřijde nový export
  se zachovaným `stored_models` řádkem.

## ⭐ ZÁVAZNÉ pravidlo — JEDINÁ platná barevná konvence

**Robert (2026-09-07): tahle barevná kombinace pomáhá procesu učení
postupu skládání — je JEDINÁ platná, jak pro pracovní, tak pro učební
režim. Žádné jiné barevné schéma se pro Vandr rendery nepoužívá.**

Kanonická implementace (kopíruj doslovně, neupravuj paletu ani logiku):
```js
const PALETTE = [0x9fb6cc, 0xd98c8c, 0xc9c9c9, 0x8fbf8f, 0xd9c17a, 0xb08cd9];
function colorize(obj) {
  let i = 0;
  obj.traverse(n => { if (n.isMesh) { n.material = new THREE.MeshStandardMaterial({ color: PALETTE[i % PALETTE.length], metalness: 0.2, roughness: 0.6 }); i++; } });
}
```
- Barva se přiřazuje podle POŘADÍ SUB-MESHŮ uvnitř jednoho modelu
  (`obj.traverse()`), NIKDY podle toho, KTERÝ je to model/díl. Volej
  vždy `colorize(obj)` bez druhého argumentu — funkce nesmí přijímat
  pevnou barvu.
- Když renderuješ víc modelů vedle sebe (např. noha 1 a noha 2), OBĚ
  volání `colorize()` začnou cyklus od stejného indexu (0 = první
  barva palety) — to je záměr, ne chyba: ukazuje se tak vnitřní
  struktura KAŽDÉ sestavy zvlášť (hlavní profil/patka/výztuha), což při
  učení postupu skládání odhaluje skutečné rozdíly mezi díly (např.
  přídavná diagonální výztuha u nohy s výřezem, kterou plochá jedna
  barva na celý objekt schová).
- Pro rozlišení IDENTITY modelu (která noha je která) NIKDY nepoužívej
  barvu — použij textový popisek (canvas sprite) nad/vedle modelu.
- Tohle nahrazuje dřívější pokus barvit celý objekt jednou pevnou
  barvou podle identity (noha 1 = modrá, noha 2 = červená) — ten smazal
  vnitřní strukturu a byl to krok zpět ("v prvním pokusu ta barevná
  kombinace byla ještě jinak a užitečnější").

## Hotové nástroje (nepiš znovu od nuly — commitnuté, ne ve scratchpadu)

**`scripts/2026-09-07_vandr_render/vandr_geometry_lib.js`** — sdílená
knihovna se všemi funkcemi z tohohle návodu (`colorize`,
`structuralZRange`, `innerWallZRangeOf`, `endBracketOf`,
`redStopsYRange`, `exposedFloorYOf`, `mainZoneTopOf`, `makeTextSprite`,
`dimensionLine`, `makeAspectCorrectOrtho`) — KAŽDÁ odpovídá jednomu
reálně chycenému a opravenému bugu (viz komentáře uvnitř + křížové
odkazy do `VANDR_SKLADANI_REGALU.md`/`VANDR_DILY_ZNACENI.md`). Importuj
odtud, nekopíruj inline do nového skriptu. **POZOR na
`structuralZRange()` vs `innerWallZRangeOf()`** — pro flush-check
komponenty vůči noze v ose Z použij VŽDY `innerWallZRangeOf()` (vnitřní
stěna sloupků), `structuralZRange()` dá celkovou 459mm obálku VČETNĚ
vnějších stran obou sloupků a použitá jako dotyková reference vyrobí
falešnou 45mm mezeru (viz `VANDR_SKLADANI_REGALU.md`, nález 2026-09-07
na Ducatu).

**`scripts/2026-09-07_vandr_render/render_ducato_l2h2.html`** +
**`render_ducato_l2h2_2dcheck.html`** — druhý funkční příklad (Ducato
L2H2, 2 normální nohy + 1 police na podlaze v hlavní zóně) + jeho
izolovaná 2D kontrola obou konců. Stejný FBX/import-map postup jako u
Movano příkladu níže.

**`scripts/2026-09-07_vandr_render/render_movano_assembly.html`** —
funkční příklad použití (2 nohy + 2 šuplíky, floor-flush i stack-flush
kontrola). FBX zdroje NEJSOU v gitu (vendor assety z `/opt/vandrawee`)
— cesty k nim jsou v komentáři na začátku souboru, zkopíruj je do
`./fbx/` (gitignored) před spuštěním.

**DŮLEŽITÁ změna oproti dřívějšímu postupu:** `three`/`FBXLoader` se
teď importují PŘÍMO z `node_modules` přes relativní cestu v import
mapě (`"three": "../../node_modules/three/build/three.module.js"`),
ŽÁDNÉ kopírování knihoven do pracovního adresáře. Podmínka: HTTP
server musí běžet z KOŘENE repa (`cd /opt/konfigurator && python3 -m
http.server`), ne z podadresáře — `http.server` odmítá `../` nad svůj
vlastní kořen (404), takže server v `scripts/2026-09-07_vandr_render/`
by cestu `../../node_modules/...` nenašel. URL pak vypadá takto:
`http://127.0.0.1:PORT/scripts/2026-09-07_vandr_render/soubor.html`.

## Nástroje (obecně, pro psaní NOVÉHO skriptu/scratchpad experiment)

- `three` a `playwright` jsou v `/opt/konfigurator/node_modules/` (root
  repa, ne `scripts/`).
- FBXLoader/GLTFLoader jsou v `node_modules/three/examples/jsm/loaders/`
  — POZOR, FBXLoader importuje i `../libs/fflate.module.js` a
  `../curves/*.js` (NURBSCurve atd.). Pokud NEmůžeš serverovat z kořene
  repa (viz výše), musíš zkopírovat CELOU strukturu `jsm/loaders/`,
  `jsm/libs/`, `jsm/curves/` vedle sebe (zachovat relativní cesty), ne
  jen jeden soubor — jinak radši použij relativní import z kořene repa.
- **OPRAVENO (audit bot9, 2026-09-12): Matplotlib je od 2026-09-11
  nainstalovaný přímo v produkčním `api/venv`** (`api/venv/bin/python3 -c
  "import matplotlib"` funguje, ověřeno živě) - pro 2D řezy použij rovnou
  `api/venv/bin/python3`. Dočasné venv (`python3 -m venv /cesta/plot_venv
  && /cesta/plot_venv/bin/pip install matplotlib`) zůstává jen jako
  záložní varianta, kdyby produkční `venv` z nějakého důvodu nešel použít.

## Postup (2 nohy, ověřeno funkční)

1. **Zkopíruj FBX + tři.js moduly do jednoho pracovního adresáře**
   (scratchpad, ne `webapp/` — `webapp/` se servíruje přímo na
   produkci, i nezacommitovaný soubor by byl okamžitě živý!):
   ```bash
   mkdir -p $SP/render3d/jsm/{loaders,libs,curves}
   cp /opt/konfigurator/node_modules/three/build/three.module.js $SP/render3d/
   cp .../three/examples/jsm/loaders/FBXLoader.js $SP/render3d/jsm/loaders/
   cp -r .../three/examples/jsm/libs/* $SP/render3d/jsm/libs/
   cp .../three/examples/jsm/curves/*.js $SP/render3d/jsm/curves/
   cp "/opt/vandrawee/unity/Assets/Models/vandrawee/Legs/<Auto>/<soubor>.fbx" $SP/render3d/noha.fbx
   ```

2. **HTML s import mapou** (bez ní `import ... from 'three'` uvnitř
   FBXLoaderu nenajde modul):
   ```html
   <script type="importmap">
   { "imports": { "three": "./three.module.js" } }
   </script>
   <script type="module">
   import * as THREE from 'three';
   import { FBXLoader } from './jsm/loaders/FBXLoader.js';
   // scene, camera, renderer, světla, GridHelper - běžné Three.js
   const loader = new FBXLoader();
   loader.load('./noha.fbx', (obj) => {
     obj.rotation.x = -Math.PI / 2;   // <-- KRITICKÉ, viz níže
     obj.updateMatrixWorld(true);
     scene.add(obj);
     renderer.render(scene, camera);
     window.__RENDER_DONE__ = true;
   });
   </script>
   ```

3. **KRITICKÁ oprava orientace:** Vandr FBX modely mají výšku podél
   OSY Z (potvrzeno měřením bounding boxu — `size.z` je dominantní
   rozměr před rotací), naše scéna má výšku podél Y. Bez
   `obj.rotation.x = -Math.PI/2` leží model na boku (Robert to chytil:
   "za první noha ti leží"). Po rotaci ověř, že `size.y` je teď
   dominantní (viz krok 5) — nikdy nehádej, vždy změř.

3b. **Obarvování:** viz ⭐ ZÁVAZNÉ pravidlo na začátku souboru — vždy
   `colorize(obj)` bez pevné barvy, identitu modelu řeš textovým
   popiskem, ne barvou.

3c. **KRITICKÉ — hloubka "459" se kontroluje na HLAVNÍ (hliníkové)
   části nohy, ne na celém bboxu** (Robert 2026-09-07: "musí tady
   proběhnout kontrola... že je noha v hlavní části hluboká 459 a
   komponent taktéž 459, ať mi jeden nepřečnívá přes druhý"). Reálně
   chycená chyba: `THREE.Box3().setFromObject(noha)` dá 468,9mm, ne
   459mm — obsahuje navíc šroubovací úchyt (`parent.name==='sroub'`),
   který čte dopředu o ~9,9mm navíc mimo hlavní hliníkovou konstrukci.
   Když se komponenta (459mm) vystředí podle TOHOTO nesprávného bboxu,
   posune se o ~4,94mm — vznikne skutečný přesah vepředu A mezera
   vzadu zároveň, přestože obě čísla (459 a 459) na první pohled sedí.
   **Postup:** počítej hloubkový rozsah nohy JEN z meshů, jejichž
   přímý rodič se jmenuje `alu` (vylučuje `sroub`/úchyt, `black`/
   záslepky, `plast_gr`/plastový panel):
   ```js
   function structuralZRange(obj) {
     let min = Infinity, max = -Infinity;
     obj.traverse(n => {
       if (n.isMesh && n.parent && n.parent.name === 'alu') {
         const box = new THREE.Box3().setFromObject(n);
         min = Math.min(min, box.min.z); max = Math.max(max, box.max.z);
       }
     });
     return { min, max, span: max - min };
   }
   ```
   Po umístění komponenty ověř ČÍSELNĚ (ne jen okem): `komponenta.max.z
   - noha.structZ.max` (přesah vepředu) a `noha.structZ.min -
   komponenta.min.z` (přesah/mezera vzadu) — OBĚ musí být 0 (v rámci
   mm zaokrouhlení), ne jen "vypadá to zarovnaně". Tohle je stejná
   třída chyby jako "pivot dílu NENÍ vždy geometrický střed" ze
   `skills/3d-scena-spoje` — NEODVOZOVAT hranu z celého bboxu, vždy
   ZMĚŘIT tu SPRÁVNOU (funkční, ne náhodně-nejširší) hranu.
   **POZOR:** ne všechny komponenty mají stejnou hloubku jako noha —
   `.uzka` (úzká) a `.top` varianty jsou ZÁMĚRNĚ mělčí (viz číslo v
   názvu, např. `.414.top` = 414mm hluboká, ne 459) — u nich se plný
   flush-fit NEOČEKÁVÁ, jen u komponent se STEJNÝM číslem v názvu jako
   noha.

3d. **Vizuální dvojkontrola previsu (Robert 2026-09-07: "chci vidět dva
   2D pohledy... drátěné"):** číselná kontrola (3c) stačí na důkaz, ale
   pro RYCHLOU vizuální kontrolu udělej samostatný, IZOLOVANÝ render jen
   té dvojice dílů, co se kontroluje (ne celou sestavu — u více dílů
   najednou se dráty ve wireframe pohledu shora/z boku beznadějně
   překrývají a nejde nic přečíst):
   - Nový, samostatný HTML soubor jen se 2 objekty (ne recyklovat scénu
     s celou sestavou).
   - `new THREE.MeshBasicMaterial({ color, wireframe: true })` — KAŽDÝ
     díl jinou plnou barvou (např. noha modře, komponenta červeně) —
     ne `colorize()` po sub-částech (to je pravidlo pro PŘEHLEDOVÉ
     rendery s jedním dílem, tady jde o odlišení DVOU dílů od sebe).
   - `THREE.OrthographicCamera` (ne perspektivní) — žádné zkreslení,
     hrana buď lícuje, nebo ne.
   - Pohled SHORA (`up.set(0,0,-1)`, kamera nad středem, `lookAt` dolů)
     ukáže přesah v ose Z na první pohled. Pohled Z BOKU (kamera podél
     X) totéž z druhého úhlu.
   - Zorné okno (`OrthographicCamera(-halfW,halfW,halfH,-halfH,...)`)
     nastav úzké (řádově stovky mm) a vycentrované na kontrolovaný roh
     — ne na celou sestavu.
   - Správný výsledek: hrana barvy A a hrana barvy B se PŘEKRÝVAJÍ do
     jedné čáry na obou stranách. Barva A viditelně vyčnívající za
     hranici barvy B = přesah. Mezera mezi hranami = vůle/nedosažení.
   - **POVINNÝ popisek na obrázku samotném** (Robert 2026-09-07: "2d
     pohledy jsou nějaké zpřeházené" — bez popisku nejde z více
     poslaných obrázků poznat, který díl/pohled je který). Přidej do
     HTML fixed-position `<div>` přes celý screenshot (Playwright ho
     zachytí spolu s canvasem) s textem "NÁZEV KOMPONENTY — BOKORYS/
     ČELNÍ" + legendu barev (modrá=noha, červená=komponenta) — aktualizuj
     ho v JS při každém přepnutí pohledu, PŘED screenshotem.
   - **2D MUSÍ pokrývat totéž, co 3D náhled — OBĚ nohy, ne jen jednu**
     (Robert 2026-09-07: "některé 2D pohledy nekorespondují s 3D
     náhledem" — chyba: 2D kontrola dřív ověřovala spoj jen proti JEDNÉ
     noze/JEDNOMU konci komponenty, zatímco 3D náhled ukazuje sestavu s
     OBĚMA nohama). Když sestava má 2 nohy (běžný případ — komponenta
     přemosťuje mezeru), izolovaný 2D check musí obsahovat OBĚ nohy a
     kontrolovat OBA konce komponenty zvlášť (bokorys zoomovaný na roh
     nohy 1, samostatný bokorys zoomovaný na roh nohy 2 — zvlášť
     důležité, pokud je jedna z noh varianta s výřezem, protože i když
     Z-stěny vycházejí stejné, je to potřeba OVĚŘIT, ne předpokládat).
     Čelní pohled pak ukazuje celý rozpon s oběma nohama najednou,
     stejně jako 3D iso náhled.

3e. **KRITICKÁ past — NIKDY neposouvej geometrii kvůli tomu, aby se
   "vešla" do záběru kamery.** Reálná chyba (Robert 2026-09-07 chytil
   na screenshotu: "Toto je špatně"): v diagnostickém skriptu jsem
   komponentu po SPRÁVNÉM (změřeném, gap=0) umístění navíc posunul o
   libovolných "-300mm", aby ji bylo v úzkém okně kamery vidět celou —
   tenhle posun ale zůstal aplikovaný NAVÍC, takže výsledný obrázek
   ukazoval falešnou ~210mm mezeru, přestože číselná kontrola hlásila
   0. **Kamera se přizpůsobuje geometrii, nikdy ne naopak** — spočti
   správnou pozici dílu JEDNOU, ulož ji, a teprve pak nastav kameru
   (`cam.position`/`cam.lookAt`) tak, aby mířila přesně na tu spočtenou
   pozici. Žádné "aby se to vešlo" posuny objektů.

3f. **Středění vždy podle FUNKČNÍHO nosníku, nikdy podle celého bboxu
   dílu** (další reálně chycená chyba, Sprinter dvířka
   `Police.door.20.120.1057.459`): dvířka mají mimostředový pant/kliku,
   který posune CELKOVÝ bbox střed o ~7mm, i když koncový nosník
   (`alu` mesh s nejmenším/největším X) sám o sobě přesně sedí na
   mezeru. Vždy najdi konkrétní koncový nosník (`endBracketOf()` —
   `alu` mesh s nejmenším X) a středi/zarovnávej PODLE NĚJ, ne podle
   `Box3().setFromObject(celyDil)`. Stejná třída chyby jako šroubovací
   úchyt nohy (3c) — obecné pravidlo: **žádné referenční měření nikdy
   neodvozuj z celého objektu, pokud objekt může obsahovat asymetrické
   příslušenství (šrouby, panty, kliky, úchyty)**, vždy z konkrétní
   funkční sub-části.

3g. **KRITICKÉ — `OrthographicCamera` MUSÍ mít stejný poměr stran jako
   plátno** (Robert 2026-09-07: "je jakoby stlačený na výšku... podle
   řezu profilu že není čtverec" — reálně chycená chyba, ne jen
   dojem). Čtvercové zorné okno (`halfW === halfH`) vykreslené do
   NEčtvercového plátna (`W !== H`, typicky 1600×1100) natáhne obraz
   nerovnoměrně — skutečně čtvercový profil 45×45 pak vyjde jako
   obdélník. Vždy: `const aspect = W / H; const halfH = <cokoli>;
   const halfW = halfH * aspect;` — NIKDY `halfW = halfH` na
   neètvercovém plátně. Geometrie/pozice dílů tím nejsou ovlivněné (jen
   projekce), ale zkreslený obrázek je jako DŮKAZ k ničemu.

4. **Serveruj adresář lokálně a vyfoť Playwrightem** (GLTFLoader/FBXLoader
   potřebuje HTTP, ne `file://`):
   ```bash
   cd $SP/render3d && python3 -m http.server 8931 &
   node -e "
   const { chromium } = require('/opt/konfigurator/node_modules/playwright');
   (async () => {
     const browser = await chromium.launch();
     const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
     await page.goto('http://127.0.0.1:8931/render.html');
     await page.waitForFunction('window.__RENDER_DONE__ === true', { timeout: 20000 });
     await page.screenshot({ path: '$SP/render3d/vysledek.png' });
     await browser.close();
   })();
   "
   ```
   Server po dokončení ukonči (`pkill -f "http.server 8931"`).

5. **VŽDY změř, nikdy nehádej** (stejné pravidlo jako `PRAVIDLA_SPOJU.md`
   pro naši vlastní geometrii): po načtení každého FBX vypiš
   `new THREE.Box3().setFromObject(obj)` do `window.__DEBUG__` a čti ho
   přes `page.evaluate()` — přesně takhle se odhalilo, že komponenta
   `Police.S40.0D.univerzalni` (1347×349×207mm) je širší než mezera
   mezi nohama, a že orientace komponenty byla "čelem k podlaze" (další
   Robertův postřeh, oprava: stejná rotace `-Math.PI/2` na X).

6. **Poslat výsledek Robertovi:** `SendUserFile` s `display: "render"`,
   `status: "normal"` — NE jen popsat text, on to chce reálně vidět.

7. **Víc pohledů na stejnou scénu (Robert 2026-09-07: "Nevidím to ze
   všech úhlů"):** jeden statický screenshot NESTAČÍ na potvrzení
   umístění — vystav v HTML globální hook, co jen přepozicuje kameru a
   znovu vykreslí, a zavolej ho z Playwright vícekrát mezi screenshoty
   (BEZ znovunačítání stránky/modelů):
   ```js
   window.__setView__ = function (view) {
     if (view === 'front') { camera.position.set(cx, cy, cz + dist*1.4); camera.lookAt(cx, cy, cz); }
     else if (view === 'side') { camera.position.set(cx + dist*1.4, cy, cz); camera.lookAt(cx, cy, cz); }
     else if (view === 'top') { camera.position.set(cx, cy + dist*1.6, cz + 0.001); camera.lookAt(cx, cy, cz); }
     else { /* iso */ camera.position.set(cx, cy + dist*0.55, cz + dist*1.05); camera.lookAt(cx, cy*0.7, cz); }
     renderer.render(scene, camera);
   };
   ```
   V Playwright pak: `for (const v of ['iso','front','side','top']) { await page.evaluate(v => window.__setView__(v), v); await page.screenshot({path: ...}); }`.
   Pošli VŠECHNY pohledy najednou (`SendUserFile` s polem cest) — jeden
   obrázek z jednoho úhlu nechává skryté kolize/přesahy z jiných stran.

## ⭐ Skutečný export CELÉ sestavy z appky (Robert klikne "Exportovat FBX") — jiný soubor, jiné pasti než katalogové díly

Přidáno 2026-09-20 (bot10) po prvním reálném použití tlačítka "Exportovat
FBX" v adminu (`work-stored-model`). Tohle NENÍ stejný typ souboru jako
jednotlivé katalogové díly výše (`Assets/Models/vandrawee/...`) — appka
ho generuje za běhu (`UnityFBXExporter`, open-source knihovna, viz
`vandrawee_fbx_export_dead_ends.md` bod 4: "can not serialize textures at
runtime (yet)") a je to ASCII FBX, ne binární. Tři reálně nalezené pasti:

1. **Appka umí nahlásit "export proveden", i když se soubor vůbec
   neuložil.** `ExportApiController::store()`
   (`/opt/vandrawee/web/app/Http/Controllers/Api/ExportApiController.php`)
   nekontroluje návratovou hodnotu `Storage::put()` — pokud cílová
   složka `storage/app/exported_models/{uuid}/` z jakéhokoli důvodu
   nejde zapsat (typicky: zbyla tam root-vlastněná složka po dřívějším
   ručním ladění spuštěném jako root, PHP-FPM běží jako `www-data`),
   appka i tak vrátí 200. Diagnóza: `tail /var/log/nginx/*.access.log`
   (hledej `POST /api/export`), pak `ls -la storage/app/exported_models/{uuid}/`
   — pokud tam chybí `.fbx` a/nebo vlastník není `www-data`, tohle je ono.
   Pravidlo: jakýkoli ruční test proti `/opt/vandrawee/web/storage/`
   spouštěj přes `systemd-run -p User=www-data`, nikdy rovnou jako root.

2. **Blenderův `bpy.ops.import_scene.fbx` odmítá ASCII FBX úplně**
   ("ASCII FBX files are not supported") — tenhle export je ASCII.
   Použij misto toho Three.js `FBXLoader` (ten umí oboje, má vlastní
   `TextParser`/`BinaryParser`) přesně podle postupu výše, ale POZOR na
   dvě konkrétní chyby v `FBXLoader.js` (ověřeno three@0.128.0), na
   které tenhle konkrétní soubor narazí (běžné katalogové díly ne,
   protože mají kompletnější UV/geometry data):
   - `parseUVs()` čte `UVNode.UVIndex.a` bez kontroly, že `UVIndex`
     vůbec existuje (na rozdíl od `parseNormals()` o pár řádků výš,
     která tuhle kontrolu MÁ) — když appka nedoserializuje textury,
     občas napíše `LayerElementUV` s `ReferenceInformationType:
     "IndexToDirect"` ale bez `UVIndex` pole. Oprava (přidej stejnou
     podmínku jako u normál): `if (referenceType === 'IndexToDirect'
     && 'UVIndex' in UVNode)`.
   - `createMesh()` počítá s tím, že ke KAŽDÉMU Model uzlu typu `"Mesh"`
     existuje navázaná Geometry — pokud ne (prázdný/nevyplněný mesh
     filtr na straně Unity, appka ho přesto vyexportuje jako typ
     `"Mesh"`), `geometry` zůstane `null` a pád je hned na dalším
     řádku (`'color' in geometry.attributes`). Oprava: `if (geometry
     === null) return null;` v `createMesh()` + v `parseModels()` po
     switchi doplnit `if (!model) model = new Group();` (stejný
     fallback, jaký kód už používá pro typ `'Null'`/neznámý typ).
   Obě opravy dělej jen v PRACOVNÍ KOPII knihovny (zkopírované do
   scratchpadu), ne v `node_modules` — je to obcházení mezery v
   parseru pro tenhle konkrétní zdroj dat, ne oprava sdíleného kódu.

3. **Uzel jménem `"colliders"` NENÍ pomocná fyzikální geometrie k
   vyloučení — je to skutečný kontejner CELÉHO umístěného regálu.**
   Na rozdíl od katalogových dílů (kde "colliders"/"dimensions" jsou
   fakt jen UI pomůcky) tenhle scénový export má strukturu
   `colliders > left/right > Nohy.../Police.../Multibox...` — všechny
   SKUTEČNÉ nohy/police/zásuvky. Vyloučení podle jména `colliders`
   smaže CELÝ regál a zůstane jen prázdná karoserie (přesně tak to
   dopadlo napoprvé). Bezpečné (ověřeně prázdné, `childCount`/mesh=0)
   je vylučovat jen `^dimensions?$|^text$` (rozměrové popisky a jejich
   `New_Game_Object` deti) — NIC jiného podle jména automaticky
   nevylučuj, dokud vizuálně (vlastní diagnostický render, NIKDY
   Robertovi do chatu — pravidlo 48) neověříš, že tam fakt nic není.

**⭐ ZÁVAZNÉ pravidlo (Robert, 2026-09-20): renderujeme VŽDY BEZ
KAROSERIE.** Uzel `karoserie` (a jen ten - `podlaha`/logo/zbytek
zůstává) se z exportu vylučuje stejným mechanismem jako
`dimensions`/`text` výše, ve VŠECH budoucích renderech tohohle typu
souboru, ne jen v prvním testu. Vystavuje se jen samotný regál.

**⭐ VYŘEŠENO 2026-09-20 (bot10+bot4) — barvy/materiály, kompletní
recept.** Prošlo 4 koly, ať se příště nemusí znovu hledat od nuly:

1. **Phong→PBR převod před exportem, ne až spoléhat na GLTFExporter.**
   `FBXLoader` staví z Phong dat `THREE.MeshPhongMaterial`, ale
   `GLTFExporter` (three@0.128) ho neumí spolehlivě přeložit do glTF
   `baseColorFactor` (sám hlásí "Use MeshStandardMaterial or
   MeshBasicMaterial for best results" - to je přímo ta indicie).
   PŘED voláním `exporter.parse()` projdi `obj.traverse()` a každý
   Phong materiál nahraď novým `MeshStandardMaterial` se zkopírovaným
   `color`/`emissive`/`opacity`/`transparent`/`side` (skutečné hodnoty
   z FBX, nic nové).
2. **`roughness`/`metalness` NEPÍŠ natvrdo** (první verze týhle opravy
   dala `roughness:1.0, metalness:0.0` úplně všem 216 materiálům -
   vypadalo to ploše/lacně, bot4 to chytil přímým rozborem glTF JSON).
   Spočti roughness ze SKUTEČNÉHO `material.shininess`, co FBXLoader
   parsuje z FBX `Shininess`/`ShininessExponent`
   (`roughness = clamp(sqrt(2/(shininess+2)), 0.05, 1)` - standardní
   Blinn-Phong-exponent→GGX-roughness aproximace). U tohohle vzorku
   vyšlo jednotně 0.25 pro všechno (FBX `Shininess` se píše jen JEDNOU
   jako sdílená šablona vlastností, ne zvlášť pro každý materiál -
   `grep '"Shininess"' export.fbx` na ověření), takže žádná umělá
   diverzita navíc - jen informovanější číslo než hádaná 1.0.
   Metalness nemá v Phongu ekvivalent (nevymýšlet) - JEDINÁ výjimka:
   materiál doslova POJMENOVANÝ "alu" (`\balu\b` case-insensitive) smí
   dostat `metalness≈0.6`, protože to je popisek ze zdroje, ne odhad.
3. **Katalog je v MILIMETRECH, glTF/three.js defaultně v METRECH.**
   `PRODUKTOVE_RENDERY.md` bod 8 ("scéna je v MILIMETRECH... regál má
   přes 2000 jednotek") - GLTFExporter u tohohle zdroje vyrobí soubor
   se skutečnými reálnými METRY (protože appka dumpuje Unity world-
   space přímo, viz invarianty níže), a bot4ova fixní (ne auto-fit)
   turntable kamera pak zobrazí objekt jako neviditelnou tečku (1000×
   moc malý). Po všech ostatních opravách vynásob VŠECHNY POSITION
   accessory a node `translation`/`matrix`-translace ×1000 (NE
   `normal`/`rotation`/`scale` - ty jsou na jednotkách nezávislé).
4. **Po každém FBXLoader/GLTFExporter běhu spusť sanitizační průchod
   NAD hotovým GLB, nespoléhej že se upstream parser trefí napoprvé.**
   I po opravě 2 konkrétních `FBXLoader.js` bugů výše (UVIndex,
   prázdná geometrie) se objevily DALŠÍ NaN na jiných místech (nejdřív
   `node.matrix`, pak by teoreticky mohlo být cokoli dalšího - kořenová
   příčina byla `parseNumberArray('')` vracející `[NaN]` místo `[]` pro
   FBX pole zapsané jako `a: ` bez obsahu, `''.split(',')` je `['']`,
   `parseFloat('')` je `NaN` - opraveno i tam, ale sanitizace zůstává
   jako pojistka). Skript (`accessors[].min/max` přepočítat přímo
   z bufferu nebo zahodit, `nodes[].matrix/translation/rotation/scale`
   nahradit identitou/výchozí hodnotou když nejsou platné číslo-pole,
   `materials[].baseColorFactor/emissiveFactor` totéž, finální sweep
   celého JSON stromu) je commitnutá jako
   `scripts/2026-09-20_vandrawee_real_export/sanitize_glb.py`, spolu s
   patchnutým `FBXLoader.js`, `convert_template.html` a
   `scale_to_mm.py` (bod 3) — viz `README.md` tamtéž pro přesný postup
   použití na NOVÉM FBX exportu.

**Pořadí kroků shrnutě:** FBXLoader (patchnutá kopie) → vyloučit
`dimensions`/`text`/`karoserie`/**`logo`** (viz ⭐ pravidlo o razítkách
níže — `logo` je cizí "vanDrawee" branding na podlaze, ne naše razítko)
→ Phong→Standard s roughness/metalness z bodu 2 → GLTFExporter →
sanitizovat NaN (bod 4) → škálovat ×1000 na mm (bod 3) → nasadit do
`webapp/katalog/` → **spočítat 3D razítka** (viz ⭐ pravidlo níže,
POVINNÉ, jinak karta nemá žádnou ochranu) → teprve pak render. Ověřeno
funkční na Renault Trafic L2H1 (`vd_export_trafic_2f89b425.glb`, commity
`e176faae` až `b9c430f6`), potvrzeno bota4 (Blender import i render OK)
a Robertem živě ve scéně.

## FBX MIMO Vandr admin (CAD/Rhino, soubor od Roberta) → Vandr karta (bot8, 2026-10-06, karta #4969)

Robert: *„pokračuj s tím stejně, jako bych to vyexportoval z Vandr systému“* (FBX „Přepážka ponk s výsuvným svěrákem“, vozidlo MAN TGE L3H3, přepážka). Hotové automaty to nezvládnou: watcher zakládá kartu s názvem/vozidlem jen z `vandrawee_work` a **konverze bere jen `stored_models` z vandrawee_work a VŽDY škáluje ×1000** (Unity = metry, osa Y nahoru) - soubor v **mm s osou Z nahoru** by vyšel 1000× větší a ležel na boku. Proto ruční krok, jednou příkazem:
`api/venv/bin/python3 scripts/2026-10-06_vandr_cizi_fbx_na_kartu.py --fbx <soubor> --nazev "<název karty>" --vozidlo "<vozidlo>" --umisteni RK|RL|RP [--osa-nahoru Z|Y] [--jednotky mm|m] [--popis …] [--apply]` (bez `--apply` = náhled s ověřením Blenderem).
Dělá přesně kroky Vandr konverze (patchnutý FBXLoader → sanitizace → stejné `overit_final_glb` brzdy; metry→mm jen s `--jednotky m`; Z→Y nahoru obalením kořene rotací, vrcholy se nemění), GLB do chráněné `webapp/katalog/vandr/` (commit pod zámkem bot8), kartu `VD-<uuid>` (**neaktivní, bez ceny a kategorie** - pravidlo 54, kategorii/cenu doplní Robert), štítek umístění, `nativni_material=1`, `vandr_hlavni_prurez_mm`, řádek `vandr_fbx_queue`, původní FBX na Sdílený disk (`vanDrawee sestavy/<uuid>.fbx`) a úkol na zeď pro bot5. **Razítka (vč. předního azimutu, u přepážky RK vyšlo 180° z kování) a render pak dělají beze změny existující automaty**; aktivace až bude cena. Cena se ze Vandr DB nesynchronizuje (UUID tam není).
Ověřeno: #4969, 132 meshů, 1565 × 473 × 1203 mm, hlavní profil 45×45, razítka 8 log (2 na stranu) do minuty od nasazení GLB. Kvalita materiálů je z FBX (bílé profily, modré čela šuplíků) - render je přebírá podle role z panelu Rendering → HDRi, ne z FBX barev.

## ⭐ ZÁVAZNÉ pravidlo (Robert, 2026-09-23) — 3D razítka POVINNÁ na KAŽDÉ kartě

**"3D razitka dodelat zpetne a dopredu"** — týká se KAŽDÉ Vandr karty,
ne jen prvních dvou testovacích. `razitkovac.py::orazitkuj()` na
monolitický Vandr import nedosáhne (hledá jen mezi katalogovými
`Object_7/8/9` profily) — bez tohodle kroku má render **nulovou
ochranu**, tiše, bez chybové hlášky.

**⭐ AUTOMATIZOVÁNO 2026-09-23** (Robert ostře přes bot3: "proc to neni
automatizovane? mas to za ukol koordinovat!!!") — systemd timer
`konfigurator-vandr-razitka-dispatch` (`deploy/konfigurator-vandr-
razitka-dispatch.{service,timer}`, každých 15 minut, `www-data`) sám
najde `shop_products` karty (`sku LIKE 'VD-%%'`, mimo `VD-TEST-%%`) s
hotovým `glb_file` a bez aktuálního otisku a spustí
`scripts/2026-09-23_vandr_razitka_auto_dispatch.py`, který kartu
orazítkuje. RUČNÍ spuštění (níže) už není potřeba pro běžný provoz -
zůstává pro ladění/ověření jedné konkrétní karty:
```
/opt/blender-5.2/blender -b -P scripts/2026-09-23_vandr_razitka_spocitat.py \
    -- webapp/katalog/<soubor>.glb --shop-product-id <shop_product_id>
```
(`--assembly-id <id>` = STARÝ režim, zachovaný jen pro dvě testovací
sestavy 671/672 založené před pravidlem "Vandr karty product_assemblies
nemají" - žádná NOVÁ karta ho nepoužívá.)

Spočítá polohu na všech objektech obsahujících `noha` v názvu (Ducato
45×45mm, Trafic 40×40mm — konvence napříč Vandr exporty, ověř na dalším
vozidle znovu, neber to jako univerzální rozměr) a zapíše je do
`shop_products.vandr_razitka_json` (NE `product_assemblies` - Vandr
karty tuhle tabulku vůbec nemají, viz `2026-09-22_vandr_fbx_watcher.py`
hlavička) jako obyčejné díly (`part_id="logo_logiman_cz"`) — **žádná
změna v `api/blender_render_turntable.py` není potřeba**, díly projdou
úplně stejným skleněným materiálem jako nativní Logiman razítka
(`_material_for()`, šablona `"logo Logiman"`). Idempotentní - otisk GLB
souboru (`vandr_razitka_glb_otisk`) rozhoduje, jestli je potřeba
přepočítat.

Render Vandr karty bez `product_assemblies`: `scripts/2026-09-09_
turntable_render.py --shop-product-id <id> ...` (místo pozičního
`assembly_id`) - `build_job_vandr()` v `turntable_job.py` sestaví "sestavu"
narovinu z monolitického GLB + `vandr_razitka_json`, žádný SELECT do
`product_assemblies`.

**Dvě konkrétní pasti, na které jsme narazili (obě opravené, zůstávají
zapsané, ať se neopakují):**
1. **Orientace textu** — `osa_text = -osa_world`,
   `treti = normala.cross(osa_text)` (přesně tohle pořadí křížového
   součinu). Obrácené pořadí/znaménko vyrobí čitelně vyhlížející, ale
   VZHŮRU NOHAMA otočená písmena (ne jen špatný směr čtení — chyba se
   dá snadno přehlédnout na malém náhledu, ověřuj přiblíženým
   výřezem/otočeným o 90°, ne od oka).
2. **Rozestup dvou razítek na TÉŽE noze** — Robert: *"dve loga na
   jednom profilu musi byt minimalne pul metru od sebe"*
   (`MIN_ROZESTUP_LOG_MM=500`, stejná konstanta jako `razitkovac.py`).
   Bez posunu podél délky nohy sedí obě razítka (různé stěny, STEJNÁ
   výška středu) jen přes roh ~45mm od sebe.
3. **⭐ Kolize se sousedním dílem (konzole, panty)** — vlastní generátor
   nemá katalog volných úseků jako `razitkovac.py` (ten čte uložené
   pozice ostatních dílů), takže náhodný posun páru NEGARANTUJE
   bezkolizní pozici (Robert po druhém nahlášeném případu: *"tohle se
   nam n 1.vetvi nestalo nikdy, blbecku"*). Řešení: skutečná AABB
   kolize testovacího bodu (na SKUTEČNÉM povrchu razítka, ne na ose
   profilu - první verze testu tuhle chybu měla a hlásila kolizi skoro
   všude) proti VŠEM ostatním mesh objektům v GLB. Když je jedna celá
   strana profilu po celé délce kryta sousedním dílem (typicky police),
   jednorázítkový případ zkusí druhou stěnu, párový případ tu stranu
   VYNECHÁ (ne vynutí kolizní pozici). Kód:
   `scripts/2026-09-23_vandr_razitka_spocitat.py::_najdi_bezkolizni_posun`.
4. **⭐ Hlavní profil MÁ skutečnou T-drážku, není to plochá stěna** —
   a KAŽDÝ průřez může mít JINOU drážku, takže KAŽDÝ profil má i VLASTNÍ
   zapuštěný čep (katalogový díl) - nikdy nepřevzít čep jiného profilu.
   Než razítkuješ DALŠÍ Vandr vozidlo s jiným hlavním profilem, ověř
   drážku znovu (přesné přečtení vrcholů jednoho průřezového prstence na
   obou koncích profilu - stejná přesnost jako raycast, u čistého
   hranolu bez raycastu vůbec) - NEBER čísla nižšího řádku jako
   univerzální, ani šířku, ani hloubku.

   | profil | příruba | dno | šířka drážky | čep (dl.×hl.×šíř.) | `part_id` | zdroj |
   |---|---|---|---|---|---|---|
   | 45×45 (Ducato) | 22,500mm | 7,500mm | 10,2mm | 222,204×16×10mm | `vypln_placka` | bot10 2026-09-23 |
   | 40×40 (Trafic) | 20,000mm | 6,668mm | 10,2mm | 222,204×16×10mm | `vypln_placka` | bot10 2026-09-23 |
   | 30×30 (#4586) | 15,000mm | 5,000mm | 8,2mm | 222,204×11×8,2mm | `vypln_placka_30` | bot10 2026-09-25 |

   45×45 a 40×40 sdílí JEDEN díl (`vypln_placka`) - vyšla jim náhodou
   stejná šířka drážky (10,2mm), přestože jsou to jinak odlišné profily.
   30×30 vyšla užší (8,2mm - shodou okolností stejná šířka jako nativní
   `vypln_drazky_30`, to je ale JINÝ díl s JINOU geometrií, viz past
   níže) I mělčí (příruba jen 15mm) - **existující `vypln_placka`
   (16mm hloubka) by na 30×30 vyšla za STŘED profilu** (příruba 15mm <
   16mm), proto vznikl samostatný `vypln_placka_30` (11mm hloubka, špička
   4mm od středu, 1mm rezerva za dno - stejný bezpečnostní vzor jako u
   ostatních dvou, jen s menšími čísly). Volba dílu podle profilu je v
   `2026-09-23_vandr_razitka_spocitat.py::VYPLN_PODLE_PRUREZU_MM` (klíč =
   `min(průřez)`, ČTVERCOVÉ profily - kdyby někdy přibyl obdélníkový,
   klíč se musí předělat na dvojici, ne hádat).

   **⭐ past — `vypln_drazky_30` z NATIVNÍ větve NENÍ zapuštěný čep, i
   když vyšel na stejnou šířku (8,2mm).** Je to `1000×30×10mm` krycí
   lišta pro RŮZNÉ použití v branch 1 geometrii (viz `razitkovac.py`) -
   jiné rozměry, jiný účel, jiné umístění. Vandr čepy jsou VŽDY vlastní,
   samostatně zaváděné díly (`vypln_placka*`), i když by se nějaké číslo
   shodovalo - to je koincidence rozměru, ne důvod ke sdílení dílu mezi
   větvemi (viz CLAUDE.md bod 6: vanDrawee logika a naše vlastní logika
   se nesmí míchat).

   **⭐ past — "hlavní profil" počítají DVA nezávislé regexy, které se
   dají rozejít.** `2026-09-23_vandr_fbx_konverze_auto_dispatch.py`
   (bezpečnostní brzda `overit_final_glb`) i
   `2026-09-23_vandr_razitka_spocitat.py` (`KANDIDATNI_VZOR_RE`, skutečný
   výběr stěn k orazítkování) NEZÁVISLE detekují "profil podle jména
   `NNxNNxLLL`" - jsou to DVA různé stringy ve dvou různých procesech
   (jeden běží jako vnořený Blender skript přes `subprocess`, druhý přímo
   v Blenderu), nejde je sdílet importem. Když `KANDIDATNI_VZOR_RE`
   dostal 2026-09-24 podporu písmenného prefixu (`SL40x40x1267_Zx2` -
   vodorovné příčky), dispatch skriptu zůstal STARÝ vzor bez prefixu -
   **karta #4586 tím dostala FALEŠNĚ hlavní profil (30,30) místo
   skutečného (40,40)** (bez SL-prefixu vyšlo 12:10 pro (30,30), se
   správným prefixem 24:12 pro (40,40) - SL-příčky se před opravou vůbec
   nepočítaly). Opraveno bot10 2026-09-25 (`cand_re` v dispatchi teď má
   stejný `^[A-Za-z_]*` prefix jako `KANDIDATNI_VZOR_RE`) - při dalším
   rozšiřování jednoho vzoru VŽDY zkontroluj/rozšiř i ten druhý.
5. **⭐ Appka občas neserializuje jméno uzlu → generický "SomeName<N>_
   Mesh_<M>" s AABB přes CELOU sestavu, blokuje VŠECHNA razítka
   najednou** — nalezeno 2026-09-23 na první dávce skutečných FBX
   konverzí (3 karty VW Transporter, 0 razítek na CELÉ kartě, každá
   noha "úplně bez razítka"). U Ducato/Ford Connect je to jen tenká
   12mm deska přes půdorys (ztracené jméno "podlaha", stejná kategorie
   jako `vynechat_objekty`, jen appka jí tady dala jiné jméno). U
   Transporter/Trafic vyšla DVOJICE se skutečným materiálem `plexi`
   (reálný průhledný panel, NE odpad) s AABB spanujícím celou sestavu.
   `scripts/2026-09-23_vandr_razitka_spocitat.py` proto vylučuje
   `SomeName*` jen z KOLIZNÍ kontroly razítek, NE z renderu (plexi se
   renderovat MÁ - `build_job_vandr()` na tenhle filtr nesahá).

Materiál razítka (Robert 2026-09-23: "zvýraznit, snížit průsvitnost") —
upraveno přímo v produkční šabloně, materiál `"logo Logiman"`: `Mix
Shader` 40 % `Diffuse BSDF` / 60 % `Glass BSDF` (uzel
`KOVOVOST_RAZITKO_MIX`), barva mírně sytější než originál. Čistý Glass
BSDF (Robertova původní GUI volba) nemá žádný "kolik % sklo" parametr,
proto přimíchání diffuse.

**Změřené invarianty pro TENHLE typ souboru** (jiné vozidlo bude mít
jiná čísla, ale postup měření je stejný): `GlobalSettings.UnitScaleFactor
= 100` a syrové souřadnice ve FBX jsou ROVNOU v metrech, beze změny
(žádné `0.1/UnitScaleFactor` přepočítávání jako u katalogových dílů –
to je vzorec pro JINOU rodinu souborů, aplikovat by ho tu bylo o 3 řády
vedle). Ověřeno porovnáním naměřené hloubky uzlu `karoserie` (2.9803m)
s reálnou délkou nákladového prostoru Renault Trafic L2 (2.937m dle
`vandrawee.car_models.name = "L2H1 3498 mm"` / veřejné specifikace) —
match na pár cm. Orientace je už Y-up (výška = Y, na rozdíl od
katalogových dílů, které jsou Z-up a potřebují `-90°` rotaci na X) —
před další rotací/škálováním na NOVÉM souboru tohohle typu vždy změř
znovu, neopakuj čísla odsud naslepo.

## Past, na kterou jsme narazili — NEVYBÍREJ komponentu podle názvu

Robert (2026-09-06): "Ty tam nemůžeš vybrat jaký komponent si zamaneš."
První pokus vybral `Police.S40.0D.univerzalni.fbx` jen proto, že název
zněl vhodně — ve skutečnosti patří do `components_list_id=9` ("Nohy
40x40"), ne do seznamu nohy, se kterou se testovalo (45x45,
`components_list_id=10`). **Před vložením JAKÉKOLI komponenty k noze
vždy ověř v DB**, že spolu skutečně patří:
```sql
SELECT l.id, l.components_list_id, cl.name
FROM vandrawee_work.legs l
JOIN vandrawee_work.single_legs sl ON sl.id IN (l.normal_leg_id, l.replacement_leg_id)
JOIN vandrawee_work.components_lists cl ON cl.id = l.components_list_id
WHERE sl.unity_id LIKE '%<jméno nohy>%';

SELECT c.id, c.name, c.unity_id, c.is_universal, c.min_width, c.max_width
FROM vandrawee_work.components c
JOIN vandrawee_work.components_components_lists ccl ON ccl.component_id = c.id
WHERE ccl.components_list_id = <stejné list_id jako u nohy>;
```
Pak teprve hledej FBX podle `unity_id` z DB — ne naopak (podle jména
souboru, co "vypadá vhodně").

**`is_universal=1`** (min_width/max_width `NULL`) = komponenta se
škáluje na šířku mezery (`SetWidth()`, viz `VANDR_SKLADANI_REGALU.md`).
**`is_universal=0`** s vyplněným `min_width=max_width` = PEVNÁ šířka,
NESKALOVAT, jen umístit — u ověřeného páru (noha Jumpy H1.1180.459 +
`Police.1D.1057.459`) vlastní šířka FBX komponenty (1057mm) odpovídala
VNĚJŠÍMU rozponu noh (okraj vany se opírá o nohy zvenčí), ne vnitřní
mezeře (967mm) — nepředpokládej, který rozměr to je, změř oboje.
