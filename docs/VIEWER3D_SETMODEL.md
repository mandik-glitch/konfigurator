# V3D viewer 1.2.0 - nové API pro product-configurator.js (bot16)

Soubor: `webapp/js/v3d/viewer3d.js` (classic script, globální `V3D`). Vše zpětně kompatibilní:
nabídka 103 legacy a Vandr náhled beze změny, bez nových voleb se chová jako 1.1.0.

## 1) Mount - veřejná stránka

```js
var v = V3D.mount(container, {
  modelUrl: url,            // nebo arrayBuffer: počáteční GLB
  mode: 'real',
  dims: 0,                  // kóty vypnuté: nestaví se vůbec (ani čáry, ani DOM popisky "NNN mm")
  hudKoty: false,           // HUD bez přepínače Kóty (vlevo nahoře zůstane jen Vzhled)
  onPick: function (slot) { ... },   // klik/klepnutí na díl, viz 3)
  track: function (key, detail) {},  // beze změny (detail: jen id pohybu, druh, úroveň; žádná jména uzlů)
  allowReal: false, bom: null, ...   // beze změny
});
v.ready                     // Promise: první model zobrazen (setModel ho NERUŠÍ)
```

- `hudKoty:false` bez vyslovného `dims` = kóty vypnuté (0). S `hudKoty:false, dims:1` se kóty ukážou
  bez přepínače (vědomá volba stránky). Programové `v.setDims(1)` kóty postaví a zapne i bez přepínače.
- Před touto změnou se kóty při `dims:0` stavěly a jen skrývaly (DOM popisky s rozměry v textu byly v
  DOM-u). Teď se při `dims:0` nestaví nic (0 záznamů, 0 čar, 0 popisků v DOM); postaví se až při zapnutí
  (HUD tlačítko / `setDims`) a vždy v zavřeném stavu pohybů.

## 2) v.setModel(src, {keepCamera, bom}) -> Promise<api>

```js
v.setModel(urlNeboArrayBufferNeboUint8Array, { keepCamera: true })
  .then(function (api) { /* nový model zobrazen */ })
  .catch(function (err) {
    if (err && err.superseded) return;     // nahrazeno novějším setModel - ignorovat
    /* jinak: nenačetlo se / rozbitý GLB; starý model zůstal a funguje */
  });
```

- `src`: URL (string), `ArrayBuffer`, nebo typed array (`Uint8Array`, i pohled s odsazením).
- Starý model zůstává vidět a ovladatelný, dokud se nový nenačte a nepostaví; pak se vymění naráz
  (žádný prázdný snímek). `v.state().loading === true` po dobu načítání (pro vlastní spinner).
- `keepCamera:true` = pozice, target i vzdálenost kamery beze změny (limity vzdálenosti se jen rozšíří,
  aby ji nic neposunulo). `false` nebo vynecháno = jako po prvním načtení (3D pohled na celý nový model).
  Při změně `spec.front` se zvýraznění pojmenovaného pohledu v HUD zruší (kamera zůstane).
- Přepočítá se vše z nového GLB: `scenes[0].extras.v3d` (pivoty, motions, blokující dvojice, strany,
  kóty, box, look), `g` kusovníku, stín, chipy. GLB bez spec = legacy (jako dnes). Stav pohybů se
  resetuje na zavřeno (rozjeté animace se zruší), zvýraznění `highlight` se vymaže.
- Zachová se volba stránky/zákazníka: Vzhled (Skutečný/Drátěný) i Kóty (`setMode`, `setDims`, HUD).
- Volitelně `{bom:{items,onPick}}` (jako `opts.bom`) vymění gating kusovníku (`items[].mesh_group`) až po
  úspěšné výměně; bez něj zůstává `opts.bom`. `onPick(slot)` z mountu se nemění.
- Paměť: geometrie, materiály, textury (vč. ImageBitmap), cíle renderu (stín), hrany drátěného režimu
  a DOM popisky kót starého modelu se uvolní. Ověřeno 25 výměn (real i drátěný, URL i ArrayBuffer):
  `renderer.info.memory` (geometries/textures) i počty zdrojů ve scéně se při opakování stejného modelu
  nemění, všechny zdroje dříve načtených GLB mají `dispose()`; totéž pro GLB s texturami.
- Selhání = `reject` (vždy `Error`): nenačtení/HTTP chyba, rozbitý nebo useknutý GLB, GLB bez scény,
  výjimka při stavbě. Starý model, kamera i stav zůstanou přesně beze změny (transakční výměna),
  viewer nespadne a nepřejde do chybového stavu, další `setModel` funguje.
- Rychlé opakování = poslední vyhrává: každé další volání okamžitě odmítne nedokončená starší
  (`err.superseded === true`); starší (i když dobíhá později) nikdy nic nezobrazí a jeho zdroje se
  uvolní. Nikdy nejsou zobrazeny dva modely. `dispose()` odmítne nedokončená volání (`Error('V3D: disposed')`).
- Volání bez `.catch` nehlásí unhandled rejection.
- `setModel` před dokončením úvodního načtení: úvodní GLB se zahodí, `ready` se vyřeší zobrazením modelu
  z `setModel` (onReady jednou). Mount bez `modelUrl/arrayBuffer` a hned `setModel` (ve stejném ticku) funguje.
  Po neúspěšném mountu (ready rejected, chybová obrazovka) úspěšné `setModel` model zobrazí a chybový stav sundá
  (`ready` zůstane rejected - použijte návratovou hodnotu `setModel`).

## 3) onPick(slot)

- Klik/klepnutí (tah < 6 px a kratší než 0,9 s - stejně jako u pohybů) na díl: `onPick(g)`, kde `g` je
  celé číslo `userData.g` nejbližšího předka uzlu (dědí se na potomky). Jediný argument, nic jiného
  (žádná jména uzlů, žádné interní údaje) - ani do `track()`.
- Uzly bez `g` klik ignorují (žádné volání, žádný pohyb, kurzor bez pointeru). Legacy názvy `bomgrp_N`
  se do `onPick` nepočítají (jen `userData.g`).
- Přednost: díl pod pivotem z `motions[].pick` = pohyb (otevře/zavře), `onPick` se nevolá. Díl pod
  pivotem kroku pohybu, který v `pick` není (např. panel dvířek, když `pick` = jen pin), a nese `g` = `onPick`,
  pohyb se nespustí. Bez `onPick` platí stará logika (pohyb i z pivotu kroku).
- Výjimka v `onPick` se spolkne (viewer nespadne). Souběžně lze mít i `bom.onPick` (volá se s legacy
  skupinou, stejný klik zavolá oba).
- Kurzor `pointer` nad dílem s `g` (jen myš).
- `g` je neprůhledné číslo slotu; mapování na slot dělá server/stránka. Po `setModel` platí `g` nového GLB.

## 4) Ostatní změny

- `v.state()` navíc: `loading`, `modelSeq` (kolikátý model je zobrazen), `hudKoty`, `onPick` (bool).
- Debug hook `window.__v3d` (jako dosud, jen harness): přibyly `resources()`, `idle()`; `pickInfo()` vrací i `slot`.
- `V3D.version` = `1.2.0`.

## Testy

`node tests/harness_viewer.js` (scénář I = tyto funkce; `V3D_SCEN=I` jen on; vstupy karet z `V3D_OUT`,
doporučeno zmrazená kopie, ne živý `out*/`; `V3D_JS=<adresář>` = jiný `viewer3d.js` pro mutační zkoušku).

## Kóty ve spec: pole `m` a stránky s přepínačem Kóty (bot8, 2026-10-05, Generátor stolu; verze vieweru beze změny 1.10.0)

- `scenes[0].extras.v3d.dims[]` smí mít **volitelné `m` (0–1)** = poloha popisku na čáře kóty: 0 u bodu `a`, 1 u bodu `b`, **0,5 (výchozí, beze změny) uprostřed**. Používá ho generátor stolu: svislé kóty „výška od podlahy“ mají popisek u horního konce čáry (`m: 1`), ať se u více polic popisky nepřekrývají a je jasné, kterou rovinu číslo měří; délka a hloubka desky mají popisek mimo střed (tam jsou úchyty 3D ovládání).
  Starý viewer pole ignoruje. **Přísný serverový validátor `api/v3d_glb.validate_spec` (Vandr / online nabídka) pole `m` NEZNÁ** (odmítl by ho): GLB stolu přes něj nejde, Vandr GLB `m` nemají.
- **Přepínač Kóty mají VŠECHNA místa, kde běží modul voleb** (Robert 2026-10-05: „prvky napříč generátory na všech místech: interní ve scéně, minishopy, iframe na logiman.cz“; dřív jen Generátor stolu 01–03, mini-shop a vložený generátor měly `dims: 0, hudKoty: false`): `product-configurator.js` (`mountOpts`) dává každé stránce `hudKoty: true` a kóty z modelu (model s kótami ve spec = úroveň 1 „Rozměry“); na okně ≤ 700 px jsou po načtení vypnuté (`dims: 0`, přepínač zůstává). Stránka je smí vypnout jen výslovně (`viewerOpts.hudKoty: false` → `dims: 0` = nestaví se geometrie ani popisky) nebo přebít úroveň (`viewerOpts.dims`). Dnes: Generátor stolu 01–04 (`js/stul-host.js`), mini-shop (`miniweb/miniweb-pages.js`), vložený generátor (`embed/stul-embed.js`). Testy: `test_stul_koty_verejne.js`, souhrnně `scripts/2026-10-05_prvky_napric_testy/`.
- **Při živém tažení ve 3D se kóty na dobu tažení vypnou** (`kotyBehemTazeni` v `product-configurator.js`: model se mění jen v prohlížeči, kóty by ukazovaly původní čísla) a vrátí se s přesným modelem (`kotyZpet`: po dotažení modelu, při chybě, nejpozději 8 s po puštění). Volba „Vyp“ od uživatele se tažením nikdy nezapne.
- Obsah kót stolu: `docs/OVLADANI_3D.md`, `MAPA_3D_A_GENERATORU.md` (řádek „Kóty ve 3D náhledu“), kód `api/stul_koty.py`.

## Hliník a prostředí (viewer 1.5.0, bot10 2026-10-02)

- **Prostředí (Robert: „používat pouze HDRI tlumené“):** výchozí a jediné nabízené je `hdri_tlumene` = HDRI karet (`crossfit_gym`, zmenšená na 1024x512, `env/crossfit_1024.hdr` vedle skriptu), rotace Blender 177° = three `sphere.rotation.y` 3° (ověřeno číselně), síla `LOOK_ENV` x 0,6, bez bílého světla shora. HDRI jen osvětluje, pozadí kreslí CSS. Viewer si `THREE.RGBELoader` (r128 examples) dotáhne sám z CDN, stránky nic přidávat nemusí; když se HDRI nebo loader nenačte, použije se záložní `mistnost` (RoomEnvironment + světlo 0,6) a do `state().warnings` přibude hláška. V HUD žádná volba prostředí není.
- API: `v.setEnvironment(klíč)` (`mistnost`, `hdri`, `hdri_bez_svetla`, `hdri_tlumene`), `state().env`, `state().envHdriLoaded`, `V3D.envVariants`, volba mountu `envVariant`; v ladění `?env=<klíč>` v URL jen pro srovnání.
- **HDRI až po prvním modelu (viewer 1.10.0, bot10 2026-10-04; podnět bot8/bot16: model se na mobilní síti načítal pomalu):** velké HDRI (`env/<klíč>_1024.hdr`, 1,7–2,1 MB) se dřív stahovalo hned při mountu souběžně s GLB a zdržovalo ho (mobilní síť 5 Mb/s: GLB 2,0 s místo 1,1 s). Teď se při mountu stáhne jen malý náhled téhož HDRI (`env/<klíč>_256.hdr`, 256×128, 133 kB; vyrábí ho `scripts/2026-10-04_v3d_hdri_nahledy/zmensi_hdri.py --nahledy`), osvětluje jím první snímek a plné HDRI se začne stahovat **po prvním zobrazeném modelu** (`markShown`), jakmile dorazí, prostředí se vymění a náhled se uvolní. Konečný vzhled je přesně jako dřív (snímky pixel po pixelu shodné), náhled se od něj liší nejvýš o 2/255 (u kovu drsnosti ≥ 0,3 prakticky nic; u zrcadlových ploch viditelněji, v katalogu žádné nejsou). Měřeno (mobilní síť, kartou mini-shopu / embed): čas do zobrazení modelu 4,3 → 3,6 s / 4,0 → 3,2 s. Plné HDRI se pustí hned (bez čekání na model) při `opts.envEager: true` (chování do 1.9.0), při explicitní změně prostředí (`setEnvironment`, `setEnvConfig`, `resetEnvConfig`), při `snapshot()` (ten počká nejvýš 4 s na plné HDRI, takže snímek je v plné kvalitě) a nejpozději po 12 s, kdyby model nedorazil. Chybí-li náhled (404), plné HDRI přijde po modelu stejně; nenačte-li se plné HDRI, platí záložní místnost a varování jako dosud. `state().envHdriLoaded` = plné HDRI je načtené (náhled se nepočítá), `state().envSeed` = prostředí je právě náhled. Testy: `scripts/2026-10-04_v3d_prostredi_testy/` (sekce 9). Nová HDRI do knihovny (`HDRI_LIBRARY`) potřebují i `_256.hdr` náhled (`lo`), jinak se pro ně náhled přeskočí.
- **Hliník (jen ladění):** `V3D.mount(el, { ladeni: true })` přidá do HUD vlevo nahoře řádek **Hliník** (na úzkém displeji klepnutí přepne na další), volba se pamatuje (`localStorage v3dAlu`), předvolba `?alu=<klíč>`. API `v.setAluminium(klíč)`, `state().alu`, `V3D.aluVariants`, volba mountu `aluVariant`. Klíče: `puvodni` (výchozí, beze změny), `satin`, `matny`, `eloxovany`, `bez`. Hliník se pozná podle podpisu materiálu (neutrální šedá, kov, drsnost 0,15 až 0,45), ne podle jména (sanitizer jména přejmenuje).

## Slovník textů `labels` (viewer 1.5.2, bot10 2026-10-02, na žádost bot16/anglický mini-shop)

`V3D.mount(el, { labels: { view_front: 'Front', ... } })` přepíše texty HUD. Chybějící klíč, neznámý klíč, ne-řetězec nebo text delší než 200 znaků
= **česká výchozí hodnota jako dosud** (bez `labels` je HUD pixelově i textově shodný s 1.5.1, ověřeno testem). Texty jdou jen přes `textContent` /
`setAttribute`, HTML se nevykoná. Seznam klíčů: `V3D.labelKeys`. Pro popisky pohybů `V3D.motionLabel(m, labels)` bere volitelně slovník.

Klíče: `view_front view_side view_top view_iso`, `dims_cap dims_off dims_1 dims_2`, `mode_cap mode_real mode_wire`, `alu_cap` (jen ladění),
`reset zoom_in zoom_out fullscreen fullscreen_exit`, `chips_aria open_all close_all open_all_title open_all_title_two_sided`, `loading load_failed`,
`kind_drawer kind_door kind_floor_door kind_slide kind_box kind_klt kind_multibox kind_eurobox kind_kufrik`, `hint_mouse hint_touch hint_click_tail hint_tap_tail`.
Nepřekládá se: číslování pohybů, hodnoty kót (mm), názvy variant hliníku (jen ladění), vývojářské chyby ve `state().error`/`warnings`.

## Kamera: `cameraInfo()` a `onCamera(cb)` (viewer 1.6.0, bot10 2026-10-02, na žádost bot16)

Oficiální náhrada ladicího hooku `window.__v3d.camera()` (hook zůstává a vrací totéž).
- `v.cameraInfo()` -> `{ pos, target, dir, screenUp, up, dist, fov, aspect, near, far, minDistance, maxDistance }` (mm, osy three, pole `[x,y,z]`).
- `v.onCamera(cb)` -> `cb(info)` se volá po KAŽDÉM vykresleném snímku (tah, přelet, přiblížení, resize); vrací funkci pro odhlášení. Výjimka v `cb` nezastaví vykreslování. Po `dispose()` vrací prázdnou funkci. Nevolá se hned při přihlášení; počáteční stav vezmi z `cameraInfo()` po `ready`.

## AO (ambient occlusion, viewer 1.6.0, bot10 2026-10-02)

- `V3D.aoVariants` = `vyp`, `jemne`, `stredni`, `silne`; `v.setAO(klíč)` (false u neznámé volby nebo prohlížeče bez highp), `state().ao / aoActive / aoSupported`, volba mountu `aoVariant`.
- Zákazník (bez `ladeni`): výchozí `vyp` = vykreslení pixelově shodné s dřívějším (ověřeno). S `ladeni:true` je v HUD řádek **AO**, výchozí `stredni`, volba se pamatuje (`localStorage v3dAO`), předvolba `?ao=<klíč>`.
- Technika: vlastní GTAO (bez EffectComposeru a dalších skriptů), světový poloměr v mm, násobí obraz beze změny alfy, čáry a kóty kreslí nad AO, v drátěném režimu vypnuto, kreslení na vyžádání (žádná smyčka rAF navíc). Kalibrace na `alu_ao_sila` 0,4 z renderů (vzdálenost 8 mm; „střední“ je spíš jemná, „silné“ výraznější). Výkon na skutečném GPU a mobilu neověřen (jen SwiftShader).

## HUD nad plátnem: `hudDock: 'top'` (viewer 1.6.1, bot8 2026-10-02, na žádost Roberta pro mobil konfigurátoru stolu)

- `V3D.mount(c, { hudDock: 'top', ... })`: tlačítka HUD (pohledy, reset, Kóty, Vzhled, zoom, celá obrazovka) jsou v **pruhu NAD plátnem**, nezakrývají model; root je flex sloupec, plátno (`.v3d-stage`) je zbytek výšky a renderer se měří podle něj (ne podle rootu). Pruh se zalomí do dvou řádků; na úzkém displeji (< 640 px) bez popisků „KÓTY/VZHLED“ a bez nápovědy „Táhněte prstem“.
- Bez volby se nemění nic (třída `v3d-dock-top` se nepřidá, pravidla v `v3d.css` jsou jen pod ní). Celá obrazovka funguje (pruh je součást rootu). Pozadí pruhu `--v3d-dock-bg` (výchozí `#1b2028`).
- `cameraInfo()` / `onCamera()` se vztahují k plátnu (aspect = plátno, ne root); projekce HTML značek musí brát `canvas.getBoundingClientRect()` (plátno začíná pod pruhem).

## Snímek plátna `snapshot()` (viewer 1.7.0, bot10 2026-10-02, na žádost bot5: obrázek pro PDF a náhled nabídky)

`v.snapshot({ width, type, quality, background })` -> `Promise<dataURL>`.
- Vykreslí čerstvý snímek a přečte ho ve stejném JS tasku (plátno nemá `preserveDrawingBuffer`), takže zachytí aktuální pohled, pohyby, zvýraznění i zapnuté AO.
- Rozměr = pixely plátna (kontejner x devicePixelRatio); `width` jen **zmenší** (poměr stran se zachová), větší než plátno se omezí na plátno.
- `type`: `image/png` (výchozí) nebo `image/jpeg`; `quality` 0,1 až 1 (výchozí 0,92). Průhledné pozadí plátna se vyplní `background` (`#rgb(a)`/`#rrggbb(aa)`/`rgb(...)`; neplatná hodnota se ignoruje); JPEG bez `background` má bílé pozadí, PNG zůstává průhledné.
- V obraze jsou čáry kót, texty kót (DOM popisky) ne. Do snímku se nedostane HUD ani CSS pozadí stránky.
- Před `ready` a po `dispose()` Promise odmítne chybou. Snímek je jen na straně prohlížeče zákazníka; server si obrázek nevyžaduje.

## Pluginy `opts.plugins` (viewer 1.8.0, bot10 2026-10-03)

`V3D.mount(el, { plugins: [function (ctx) { ...; return function dispose() {} }] })`: rozšíření, která se po **každém úspěšném postavení modelu** (první načtení i `setModel`) zavolají s kontextem; předchozí pluginy se před tím ukončí (jejich `dispose`). Příklad: `js/v3d/demo-stavebnice.js` (animovaná ukázka stavebnice).
- `ctx` = `{ THREE, gltf (načtený GLB: scene, animations, parser), model, scene, camera, controls, renderer, root, stage, container, state(), labels, requestRender(), setAnimating(bool), onFrame(fn(tMs)) -> odhlášení }`.
- Prohlížeč kreslí na vyžádání; plugin, který potřebuje plynulou animaci, zavolá `ctx.setAnimating(true)` (smyčka běží nepřetržitě, dokud plugin nezavolá `false`) a pohybuje věcmi v `ctx.onFrame(fn)` (volá se na začátku každého snímku s časem v ms).
- Výjimka v pluginu (při inicializaci i ve snímku) nikdy nezruší vykreslování: do `state().warnings` přibude `plugin: ...`. Bez `opts.plugins` se nic nemění.

### Plugin `js/v3d/demo-stavebnice.js` a stránka „Připni cokoli“ (bot10 2026-10-03)

Samopohyblivá 3D ukázka stavebnice (jeden profil 40×40, kámen a otočná matice): `webapp/pripni-cokoli.html` + `js/pripni-cokoli-page.js` + `pripni-cokoli/texty.json` (cs/en/sk aktivní; de/pl až po ověření bot7) + `pripni-cokoli/stavebnice-demo.glb`.
- Model je GLB s klipem `demo` a `scenes[0].extras.demo` (`duration`, `loop`, `poster`, `cues[{id,t0,t1,anchor,side}]`, `steps[{id,t0,t1,g}]`, `camera[{t,pos,target,ease,fit}]`); uzly dílů nesou `extras.g` (klepnutí na díl přehraje jeho krok), `a_*` jsou kotvy popisků. Texty v GLB nejsou, stránka je bere z `texty.json` podle `cue.id`.
- Plugin: `var demo = V3D.demoPlugin({texts, onCue, onTime, onState, autoplay, speed, startTime, reducedMotion, userIdleMs, labels}); V3D.mount(el, {plugins:[demo.plugin], ...}); demo.play()/pause()/toggle()/restart()/seek(t)/playStep(id)/stepForGroup(g)/steps()/cues()/time()/duration()`. Hraje se živě v prohlížeči (žádné video, žádný Cycles); při `prefers-reduced-motion` startuje pozastavené na snímku `poster`; pauza při skryté kartě / mimo obrazovku; uživatel může kdykoli otáčet pohledem, kamera se po klidu plynule vrátí.
- Popisky (`labelLayout`): výchozí `'margin'` = popisek leží v rezervovaném pruhu u okraje (vlevo na širokém okně, nahoře na úzkém < 640 px nebo poměru < 1,1), tenká spojnice vede k dílu a plugin kameru posune (`camera.setViewOffset`) a oddálí tak, aby se aktivní díly vešly do zbývající plochy a popisek je nezakrýval; `'anchor'` = starý popisek přímo u dílu. Pomocné `demo.layout()`, `demo.screenRect([g…])`.
- URL: `?lang=cs|en|sk`, `embed=1` (jen ukázka, vložení do cizí stránky), `bg=rrggbb`, `autoplay=0`, `t=<s>`, `speed=`, `ao=`, `model=<soubor.glb v /pripni-cokoli/>` (zkoušení).
- Testy: `scripts/2026-10-03_pripni_cokoli_testy/run_all.sh` (háček pluginů, plugin, stránka; offline, syntetické GLB).

### Prostředí (HDRI) pro admina generátoru: viewer 1.9.0 + panel `env-picker.js` (bot10 2026-10-04)

Robert: „v generátoru stolů chci mít možnost měnit jako admin HDRi přímo v generátoru“; odpověď „náhled + uložit pro všechny“.
- **Knihovna** (`V3D.envLibrary`): `crossfit` (HDRI karet), `tv_studio`, `berg_inner`, `teufelsberg`, `mistnost` (bez HDRI). Zmenšené náhledy 1024×512 v `js/v3d/env/*_1024.hdr` (po 1,7 až 2,1 MB, z knihovny Sdíleného disku skriptem `scripts/2026-10-04_v3d_hdri_nahledy/zmensi_hdri.py`; jas vyrovnán proti crossfit, takže síla 1 = zhruba stejné světlo).
- **Konfigurace prostředí** `{hdri, strength 0,1–3, rot_deg −180..180, hemi 0–1,2}`; výchozí `{crossfit, 0,6, 0, 0}` je přesně dnešní `hdri_tlumene`. `V3D.normalizeEnvConfig(c)` (ořez a kontrola, neznámé `hdri` = `null`), `opts.envConfig` (počáteční, např. uložená adminem), `v.setEnvConfig(c)` (živě, vrací normalizovanou konfiguraci nebo `false`), `v.getEnvConfig()`, `v.resetEnvConfig()`. Bez `envConfig` se chování nemění.
- **Oprava (pro všechny volby prostředí):** po změně prostředí se plátno nepřekreslovalo (`kick()` jen spustí smyčku, `requestRender()` ji označí k překreslení); `setEnvironment(klíč)` z HUD ladění to mělo také.
- **Panel** `js/v3d/env-picker.js`: `V3D.envPicker(viewer, kontejner, {saved, onSave(cfg|null) → Promise, labels, onChange})` — výběr HDRI, síla, natočení, světlo shora, tlačítka „Uložit pro všechny“ (pošle `onSave(cfg)`, pro tovární výchozí `onSave(null)`), „Obnovit uložené“, „Výchozí“. Hostitel ho ukáže JEN adminovi; ukládání (server) je na hostiteli.
- **Smlouva pro generátor stolu** (server + stránka, vlastník bot8): uložená konfigurace je jedna na generátor, jedno JSON pole; veřejné `GET /api/shop/products/<id>/configurator` ji nese jako `env` (nebo `null`), stránka ji předá do `V3D.mount({envConfig: schema.env})`; admin (`resp.staff`) má na stránce panel s `saved: schema.env` a `onSave` volá admin-only PUT, který konfiguraci znovu zkontroluje stejnými mezemi (hdri z knihovny, strength 0,1–3, rot_deg ±180, hemi 0–1,2) a při `null` uložené smaže. Nic se nezapisuje z bota přímo do `app_settings`.
- Testy: `scripts/2026-10-04_v3d_prostredi_testy/run_all.sh` (18 kontrol: knihovna, výchozí beze změny, síla, natočení, mezní hodnoty, místnost, reset, `envConfig` při mountu, překreslení plátna, celý panel včetně chyby uložení).

## Výchozí úhel pohledu „3D“: `opts.isoAngles`, `setIsoAngles`, `currentAngles` (viewer 1.17.0, bot10 2026-10-08; Robert: „chci nastavit výchozí úhel pohledu 3D v generátorech“)
- `opts.isoAngles = {az, el}` (stupně): úhel pohledu „3D“ (iso) – `az` = otočení kolem svislé osy od čela modelu (`spec.front`), `el` = náklon nad vodorovnou; výchozí 35 / 25 (konstanty `ISO_AZ` / `ISO_EL`). Platí pro první záběr po načtení, tlačítko „3D“ / „Výchozí pohled“, `v.setView('iso' | 'reset')` i znovuzáběr při změně velikosti okna; vzdálenost se dopočte jako dosud (celý model v záběru). Neplatná hodnota se ignoruje (platí 35 / 25).
- `v.setIsoAngles({az, el} | null, fly)` -> `true` | `false` (mimo meze / špatný tvar, nic se nezmění): změní úhel pohledu „3D“ (`null` = původních 35 / 25); `fly: true` kameru tam hned přeletí (`applyView('iso')`), jinak se uplatní až při dalším „3D“.
- `v.currentAngles()` -> `{az, el}` AKTUÁLNÍ kamery vůči čelu modelu (stejné stupně, zaokrouhleno na 0,1; `az` ve tvaru (-180, 180], `el` −90..90) nebo `null` (model není připraven); to je hodnota, kterou admin ukládá jako výchozí. `state().isoAngles` = platný iso úhel, `V3D.normalizeIsoAngles(c)` = kontrola / normalizace (`az` se zabalí do (-180, 180], `el` smí být −15 až 85, jinak `null`).
- Měření: `az = -(atan2(off.z, off.x) − atan2(front.z, front.x))`, `el = asin(off.y / |off|)`, kde `off` = pozice kamery − `controls.target` (inverze `rotAboutUp(front, az)`).
- Hostitel stolů: `schema.view` → `V3D.mount({isoAngles})` v `js/product-configurator.js` (`mountOpts`, `viewerOpts.isoAngles` má přednost); ukládání v `js/stul-host.js` (okno „Výchozí konfigurace“, jen admin). Bez volby se nic nemění.
