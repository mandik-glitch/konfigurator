# Kontrakt: 3D model online nabídky z karty Vandr (doplněk, bot10, 2026-10-02)

Pro **bot16** (tlačítko „Vytvořit online nabídku“ na produktu) a **bot5** (nabídky, `nabidka-online.html`).
Endpoint, idempotence, práva, `can_create_offer` a montáž jsou v `docs/KONTRAKT_VANDR_NABIDKA_ENDPOINT.md` a tady se **neopakují**.
Tohle je jen 3D část: nová pole odpovědi, jak stránka získá model a spec, jak volá prohlížeč a co dělá, když 3D nevzniklo.
Všechna nová pole přibývají **zpětně kompatibilně** (nic se nemění ani neubývá).

## 1) Co se děje na serveru (stručně)

`POST /api/admin/vandr-vyroba/<shop_product_id>/nabidka` (beze změny vstupu) nově **nejdřív postaví 3D model** a teprve pak založí nabídku:

1. data z Vandru (`vandr:offer-data <uuid> --v3d`), 2. build zákaznického GLB (Blender na CPU, nebo **cache** `private-files/v3d-cache/`,
klíč = hash kódu + dat; při shodě žádný Blender), 3. serverová pojistka `v3d_glb.sanitize` + `final_check`, 4. založení nabídky,
5. volitelné neviditelné značení číslem nabídky (jen když Robert uložil klíč), 6. uložení modelu **stejnou cestou jako dosud** (`save_offer_model_bytes`).

**Selhání 3D nikdy nezakáže vznik nabídky** (a od 2026-10-02 ani chybějící Vandr obrázky, viz oddíl 5d). Když build, kontrola nebo značení selže (nebo Vandr strana ještě nemá volbu `--v3d`),
nabídka vznikne dosavadní cestou se **statickým modelem bez v3d** (přesně jako dnes) a odpověď to řekne polem `v3d:false` + důvodem.

## 2) Odpověď 201 - nová pole

Dosavadní pole (`status, offer_id, offer_number, online_url, rozmer_mm, pocet_profilu, vandr_car_name`) beze změny. Přibývá:

| pole | typ | význam |
|---|---|---|
| `v3d` | `true`/`false` | `true` = nabídka má 3D model s pohyby (spec v3d); `false` = statický model jako dosud |
| `v3d_duvod` | text / `null` | při `v3d:false` česká věta pro admina (např. „Vandr příkaz bez --v3d“, „Sestaveni 3D modelu prekrocilo 27 s …“, „3D model je vypnutý souborem private-files/v3d-vypnuto …“); jinak `null` |
| `v3d_varovani` | pole textů | **jen pro admina** (obsahují jména dílů z Vandru, tedy nikdy do zákaznického UI); `[]` při `v3d:false` |
| `v3d_ms` | číslo | čas 3D části v ms (cache hit je řádově desítky až stovky ms, studený build 7-17 s); u `v3d:false` čas marného pokusu |
| `v3d_cache` | `true`/`false`/`null` | `true` = model z cache bez Blenderu; `null` při `v3d:false` |
| `v3d_build` | text / `null` | verze buildu (např. `b3-19e78e`; mění se s kódem), jen informativně |
| `v3d_znacka` | `"zapnuto"`/`"vypnuto"`/`null` | neviditelné značení: `vypnuto` = není klíč `V3D_MARK_SECRET` v prostředí služby, model je **bez značky** (nic se nehlásí jako forenzní stopa) |
| `obrazky_zdroj` | `{"narys": "vandr"\|"nahrada", "view3d": "vandr"\|"nahrada"\|"kombinace"}` | odkud jsou obrázky nabídky (viz oddíl 5d); vždy přítomno |
| `poznamka` | text / `null` | jen pro admina: když šlo o náhradu, „Vandr nemá obrázky, použity naše náhledy: …“ (co přesně se použilo) |
| `obrazky_rozmery_mm` | `{"sirka","hloubka","vyska"}` / `null` | rozměry z náhradního výkresu (skutečný produkt **bez podlahy a loga**), jen když nárys vyrobil server |

Chování pro UI:
- `v3d:false` **není chyba** (HTTP 201 jako vždy): nabídka je platná, jen bez pohybů. Doporučení: zobrazit odkaz na nabídku a vedle něj poznámku z `v3d_duvod`
  (např. „Nabídka vznikla bez 3D pohybů: …“). Nemazat ji, nezakazovat odkaz.
- `v3d_varovani` ukázat jen role s právem `sdileny_disk/zobrazit` (jako celý endpoint), třeba složit do „Podrobnosti“.
- **Doba odezvy:** studená cache (první nabídka z karty po změně kódu nebo dat karty) trvá 7-17 s (měřeno při zátěži serveru, 7 karet), výjimečně déle, nejvýš 55 s
  (pevný strop požadavku, gunicorn/nginx 60 s). UI proto drží stav „Vytvářím…“ nejméně 60 s a tlačítko je zablokované do odpovědi.
  Další nabídka z téže karty jde z cache (1-3 s). Endpoint dál **není idempotentní**.
- Rozměr `rozmer_mm` je u `v3d:true` rozměr regálu **bez obalu a loga** (z buildu), u `v3d:false` dosavadní hodnota; mezi nabídkami je nesrovnávat.

Chyby: 400 jen když karta nesplňuje `can_create_offer` (**už ne kvůli chybějícím obrázkům z Vandru**, viz oddíl 5d), 404 (karta neexistuje), 500 („Načtení dat z Vandru
selhalo“, „Výpočet geometrie selhal“ - tj. selhal i **dosavadní** statický model; „Obrázky nabídky nevznikly“ - Vandr je nemá a **náhradu** se nepodařilo vyrobit, neočekávané).
Nově se **nikdy** nevrací 500 jen proto, že selhalo 3D.

### Záznam nabídky (bez migrace schématu)
Do `scene_offers` se nic nepřidává (`offer_options` zůstává jen s dosavadními klíči, nic 3D není ve veřejném JSON). Záznam je v `audit_log`:
`action = "v3d_model"`, `entity_type = "scene_offer"`, `entity_id = <offer_id>`, `detail` = JSON
`{"v3d": bool, "build": "b3-…"|null, "duvod": text|null, "znacka": "zapnuto"|"vypnuto"|null, "cache_hit": bool|null, "ms": int, "varovani": <počet>}`
(vedle běžného řádku `create`). Chceš-li příznak jako sloupec, je připravena **volitelná** migrace (viz README; nedělá se bez schválení).

## 3) Jak stránka `nabidka-online.html` získá model a spec

**Stav stránky:** od 2026-10-06 je integrace PŘÍMO v `webapp/nabidka-online.html` (bot10 na Robertův pokyn; `fetchOfferModel` + `modelMaV3d` + `initViewerV3dBuf`, hák v `initViewer3d` za větví `source === "configurator"`, sdílený loader `loadV3dLib`). GLB se spec v3d → V3D (pohyby, kóty), bez něj → dosavadní `initViewer3d`; selhání = obrázková záloha. Test: `scripts/2026-10-02_v3d_testy/harness_page.js` (33 kontrol, atrapa API, skutečný prohlížeč).

Žádný nový endpoint. Stejný token, který dnes nese obrázky a model nabídky:

- `GET /api/public/offers/<token>` → `offer.model_url = "/api/public/offers/<token>/model"` a `offer.has_3d_model` (**platí pro `v3d:true` i `v3d:false`**).
- `GET /api/public/offers/<token>/model` → tělo GLB, hlavičky: `Content-Type: model/gltf-binary`, `X-Content-Type-Options: nosniff`,
  **`Cache-Control: private, no-cache`** + **`ETag`** (prohlížeč při dalším otevření jen revaliduje, `If-None-Match` → `304` bez těla; model nelze
  uložit do sdílených cache; po výměně modelu adminem se změní ETag). Neplatný/expirovaný/deaktivovaný token → `404 {"error": …}` (JSON).
  Velikost typicky 0,6-1,9 MB (strop serveru 15 MB). **CORS není potřeba** (stránka i API jsou na stejném původu a volají se relativní cestou).
- **Spec nese sám GLB** v `scenes[0].extras.v3d` (pivoty `p<N>`, `motions`, `dims`, `front`, `box`, `look`…). Žádný druhý soubor ani druhé volání.
  (Poznámka bot8 2026-10-05: viewer navíc čte VOLITELNÉ `dims[].m` = poloha popisku na čáře kóty 0–1, výchozí 0,5; používá ho generátor stolu (Vandr GLB `m` nemají). Od 2026-10-06 ho `api/v3d_glb.validate_spec` zná: volitelné konečné číslo 0–1, bez `m` se ve výstupu neobjeví, jinak (text, null, bool, NaN, mimo 0–1) chyba; klíč `m` je i v globálním whitelistu `final_check`. Viz `docs/VIEWER3D_SETMODEL.md`.)
- Katalog `/katalog/vandr/` se zákazníkovi nikdy nedává; zákaznický GLB prošel `v3d_glb.sanitize` + `final_check`: jména uzlů jen `n<i>`/`p<i>`,
  materiály `m<i>`, **bez textur**, `extras` jen `{g}` na uzlech a `v3d` na scéně, bez jmen dílů/SKU/`unity_id` (varování buildu jsou jen v odpovědi endpointu).
  Při zapnutém značení jsou polohy vrcholů posunuté o < 0,05 mm (neviditelné, geometrie ani AABB se nemění).

### Jak poznat 3D model od dosavadního statického
`v3d:false` model je GLB **bez** `scenes[0].extras.v3d`. Stránka to pozná z obsahu GLB (funkce `modelMaV3d(buf)` ve snippetu; čte jen JSON chunk),
nebo až po `V3D.mount` z `api.state().legacy`. Doporučeno **před** mountem, aby statický model šel dosavadním kódem `initViewer3d` beze změny.
(Chceš-li příznak z API místo čtení GLB, napiš: server by do `GET /api/public/offers/<token>` přidal `viewer:"v3d"`, odvozeno z uloženého souboru; dnes neexistuje.)

## 4) Jak se volá prohlížeč (viewer3d.js 1.7.x, `/js/v3d/viewer3d.js`, `/css/v3d.css`)

```js
var api = V3D.mount(container, {
  arrayBuffer: buf,            // nebo modelUrl: offer.model_url
  mode: 'real',                // Skutečný vzhled (spec -> výchozí), přepínač Drátěný zůstává
  allowReal: true,
  hudKoty: true,               // HUD s přepínačem Kóty (výchozí úroveň 1 u spec); dims:1 bez přepínače jen vědomou volbou stránky
  hudDock: 'top',              // jen na úzkém displeji (tlačítka nad plátnem); jinak vynechat
  track: function (key) { trackClick(key); },    // interact_3d_model, v3d_view, v3d_dims, v3d_mode, v3d_anim (viz CLICK_TARGETS)
  onError: function (err) { /* záloha: ploché obrázky jako dnes */ }
  // BEZ ladeni:true (to je jen pro kontrolní scénu), bez bom (Vandr nabídka má 1 řádek kusovníku bez mesh_group)
});
api.ready.then(...).catch(...);
```
- Prohlížeč si sám dotáhne své statické prostředí `/js/v3d/env/crossfit_1024.hdr` (1,6 MB, soubor z repa, běžná statická cache; není to HDRI nabídky z `/katalog/hdri/`,
  to se u V3D nestahuje, `offer.hdri` se ignoruje). Proto musí `/js/v3d/env/` servírovat web (dnes ano).
- Skripty v pořadí `V3D.deps` (three r128, OrbitControls, GLTFLoader, RoomEnvironment, CSS2DRenderer, oba blur shadery), pak `/js/v3d/viewer3d.js?v=<10 znaků sha256>`
  a `/css/v3d.css?v=<10 znaků sha256>` (dnes `253f5459a7` a `fdd405fc1d`; po změně souboru přepočítat). Stránka už three + OrbitControls + GLTFLoader načítá
  (`loadThreeJs`), stačí dotáhnout zbytek.
- Texty HUD jsou česky (volitelně `labels`). Pohyby (šuplíky, výsuvy, dvířka, boxy, „Otevřít vše“) a kóty řeší prohlížeč sám.
- Hotový vložitelný kus kódu (nic jsem neaplikoval do souboru): `nabidka-online.snippet.html` (CSS + JS + 3 řádky háčků).

## 5) Co dělá stránka při `v3d:false` (nebo když 3D selže v prohlížeči)

- `v3d:false` (statický model bez spec): **dnešní zobrazení beze změny** (vestavěný Three.js prohlížeč `initViewer3d`, drátěný vzhled, kóty jako dnes).
- `v3d:true`, ale `V3D.mount` selže (WebGL, CDN, rozbitý GLB): `onError` → kontejner pryč, ploché obrázky `#viewer3dFallback` zpět - tedy totéž, co dnes
  při chybě modelu. Zákazník nikdy nevidí chybovou hlášku.

## 5b) Okamžité vypnutí 3D bez nasazení
`touch /opt/konfigurator/private-files/v3d-vypnuto` → další nabídky vznikají dosavadní cestou (`v3d:false`, `v3d_duvod` to řekne); `rm` souboru 3D zase zapne.
Už vzniklé nabídky se nemění. (Stejné je to, co se děje, když Blender/Vandr/kontrola selže; vypínač jen nečeká na selhání.)

## 5c) `can_create_offer(karta_row)` pro staff JSON produktu (bot16)
`api/vandr_scene_offers.py::can_create_offer(karta_row, katalog_dir=None) -> (ok: bool, duvod: str | None)` - **jediné místo pravidla**, endpoint ho používá taky
(statusy a texty chyb 400/404 beze změny). Vstup: dict s `sku`, `glb_file`, `price_czk_placeholder` (řádek `shop_products`). Čistá funkce (čte jen disk, bez DB);
`duvod` je česká věta pro admina (`None`, když `ok`). Do JSON karty: `{"ok": ok, "duvod": duvod}`. Z jiného modulu ji **importuj líně uvnitř funkce**
(`import vandr_scene_offers` až při požadavku): modul při importu bere `app` a `scene_offers`, na úrovni souboru by hrozil kruhový import.

## 5d) Obrázky nabídky mohou být náhradní (Robert 2026-10-02: tlačítko vracelo 400 u karet s FBX a náhledy, např. #4053, #4482)
Vandr generuje kótovaný výkres a dva 3D pohledy jen z Unity klienta; u asi poloviny karet jsou prázdné. Endpoint proto **už nevrací 400**, když Vandr obrázky nemá:
za každý chybějící obrázek použije náhradu, **kde Vandr obrázek existuje, má přednost Vandr** (kombinace je povolená; chybějící soubor na disku se chová jako chybějící obrázek).
Klíče `views` stránky se nemění (`narys`, `view3d_a`, `view3d_b`), `nabidka-online.html` pro náhradní obrázky nic nemění.

| obrázek | náhrada (v tomto pořadí) |
|---|---|
| `narys` (kótovaný 2D výkres) | server ho **vyrobí z čistého GLB** (`api/vandr_vykres_nahrada.py`, numpy + PIL, bez Blenderu a GPU, ~1 s, deterministicky): vlevo nárys zepředu (kóty šířky a výšky), vpravo bokorys (kóty hloubky a výšky), mm, 1600×1000 PNG, světle šedá plocha, hrany dílů a tmavý obrys na bílém. Čísla = skutečné rozměry modelu (AABB), u v3d modelu totožná s `rozmer_mm`; u dosavadního statického modelu **bez podlahy a loga** (ty statický GLB ještě obsahuje, proto se `rozmer_mm` takové nabídky může lišit od čísel ve výkresu; správné jsou `obrazky_rozmery_mm`). Žádný text s názvem dílu, SKU ani `unity_id` |
| `view3d_a`, `view3d_b` | 1. **naše snímky otočky** karty (`product_turntable_frames`, `is_active=1`): `a` = zepředu doprava (přední azimut +35°), `b` = zepředu doleva (−35°), nejbližší dostupný azimut, elevace nejbližší 17,5° (z dostupných −40/0/40 vyjde 0), největší tier ≥1024 px se souborem do 1,5 MB, soubor musí existovat; JPEG se ukládá beze změny. 2. jinak první dvě fotky z galerie karty (`content_gallery_items` veřejné, pak `shop_product_images`). 3. jinak stínovaný pohled z modelu (PNG 1280×960). Přední azimut = `shop_products.vandr_predni_azimut_deg` (stejný jako `front_azimuth_deg` v kontrolní scéně) |

`obrazky_zdroj.view3d`: `"vandr"` (oba z Vandru), `"nahrada"` (oba naše), `"kombinace"` (jeden Vandr, druhý náš). Text `poznamka` je určen pro admina (UI může ukázat jako „Podrobnosti“).
Datové URI obrázků: PNG nebo JPEG (`scene_offers.DATA_URI_RE` oba povoluje, strop 6 MB na obrázek; `_validate_data_uri` se na tuto cestu nevolá, nemusel se upravovat).

## 5e) Kontrolní scéna staví model sama (bot10, 2026-10-06; Robert: „automatizovat proces bez zásahu ručně botem na každou FBX“)
Kontrolní scéna `?items=vd:<karta>,…&rezim=nabidka` už nečte ručně udělané soubory `webapp/katalog/vandr/v3d_nahled/<karta>.glb` (byly jen 7). Pro každou položku si vyžádá
**`GET /api/kontrola-scena/v3d/<karta>.glb`** (`api/vandr_scene_offers.py::kontrolni_scena_v3d_model`, jen zaměstnanci, `staff_required`): stejný build + cache (`private-files/v3d-cache`,
sdílená s nabídkou – nabídka z karty, kterou jsi už otevřel v kontrolní scéně, je pak bez Blenderu) + pojistka (`v3d_glb.sanitize` + `final_check`) jako při založení nabídky, jen bez nabídky,
bez forenzního značení, bez zápisu do DB/audit_logu a bez nutnosti ceny karty. První build ~4–10 s, pak z cache. Hlavičky: `X-V3D-Cache: hit|miss`, `X-V3D-Warnings: <počet>`.
Chyba = JSON `{"error": "<česká věta>"}` (400 není Vandr karta / bez modelu, 401 nepřihlášen, 502 data z Vandru, 500 build, 503 vypnuto `private-files/v3d-vypnuto`), **nikdy tichý náhradní model**:
stránka chybu ukáže nahlas a na hotový soubor nepadá (kontrola nesmí tiše ukázat jiný model, než uvidí zákazník). Hotový soubor `v3d_nahled/<karta>.glb` je jen záloha, když server tu trasu nemá
(HTML 404 před nasazením API). Hotové modely drží stránka v paměti (přepínání sem a zpět je hned). Testy: `scripts/2026-10-02_v3d_testy/test_kontrola_route.py` (trasa, 22), `_mutace_kontrola_route.py`
(11 mutací), `test_kontrola_nabidka_auto.js` (stránka v prohlížeči, 16).

## 5f) Vzhled online nabídek: HDRI, hliník, AO, sytost a barvy materiálů (bot10, 2026-10-06; Robert: „potřebuju upravovat materiály v online nabídce a HDRI, tzn. v kontrolní scéně“)
- **Co:** jedna uložená volba pro VŠECHNY online nabídky: HDRI prostředí (`{hdri, strength 0,1–3, rot_deg ±180, hemi 0–1,2}`, knihovna `crossfit | tv_studio | berg_inner | teufelsberg | mistnost`),
  povrch hliníku (`puvodni | satin | matny | eloxovany | bez`), AO (`vyp | jemne | stredni | silne`), **sytost barev** `sat` (0–2, 1 = beze změny) a **barvy materiálů** `barvy` (`{"#původní": "#nová"}`, sRGB hex, max 40 dvojic;
  Robert 2026-10-06: „chci upravit barvy a sytost materiálů v 3D pohledu kontrolní scény / v nabídce“). `null` = výchozí vzhled prohlížeče (u zákazníka AO vypnuté, hliník „dnešní lesklý kov“, barvy z modelu).
  Sytost a barvy se uplatní na NE-hliníkové materiály podle jejich PUVODNÍ barvy v modelu (stejná původní barva = stejná změna ve všech nabídkách; hliník má vlastní volbu); viewer 1.12.0 `setMatConfig`, výpočet z původní barvy (nikdy se nenásobí opakovaně), sytost v HSL (sRGB).
- **Kde se nastavuje:** kontrolní scéna `?items=vd:<karta>,…&rezim=nabidka` → tlačítko **Vzhled nabídek** (vpravo nahoře): HDRI v okně (`V3D.envPicker`), hliník a AO tlačítky v levém horním rohu 3D;
  Pod HDRI je sekce **Materiály – sytost a barvy**: jezdec Sytost barev (0–200 %) a vzorky původních barev modelu (výběr nové barvy, ↺ vrátí původní). **Uložit vzhled pro nabídky** uloží vše naráz, **Vrátit výchozí vzhled** smaže. Neuložené změny se v kontrolní scéně přenášejí mezi kartami. Při otevření scéna ukáže uložený vzhled (= co uvidí zákazník).
- **API** (`api/v3d_vzhled.py`): `GET /api/public/v3d-vzhled` (veřejné, `{env, alu, ao, sat, barvy}`, `Cache-Control: no-cache`); `PUT /api/admin/v3d-vzhled` (oprávnění `nastaveni/upravit`; tělo `{env?, alu?, ao?, sat?, barvy?}` nebo `null` = výchozí; `sat` 1 se uloží jako `null`, dvojice se stejnou barvou se zahodí;
  neznámý klíč / mimo meze / špatný typ = 400, nic se neořezává potichu). Uloženo v `app_settings.v3d_nabidka_vzhled` (zapisuje jen endpoint, nikdy bot), audit_log `update` / `v3d_vzhled`. Klíče a meze hlídá test proti `viewer3d.js` a `stul_api.py`.
- **Stránka nabídky:** `nactiVzhledNabidek()` (max 3 s, chyba / chybějící API = výchozí) → `V3D.mount({envConfig, aluVariant, aoVariant, matConfig})` ve větvi Vandr (`initViewerV3dBuf`) i konfigurace (`initViewerV3d`).
  Vzhled je volba prohlížeče, ne součást GLB → platí i pro už vytvořené nabídky; do cache modelu ani do zákaznického GLB se nic nepeče.
- **Materiály dílů podle role** (barva boxů, desek…) se dál mění v panelu Rendering → HDRi (`render_prirazeni_materialu`) a platí pro nově stavěné modely (hotová nabídka má model zafixovaný).
- Testy: `scripts/2026-10-06_v3d_vzhled_testy/` (`test_vzhled_api.py` 23, `_mutace_vzhled.py` 18 mutací, `test_kontrola_vzhled.js` 24, `run_all.sh`), `scripts/2026-10-06_v3d_rady_testy/test_material_barvy.js` (UI sytosti a barev, ukládání, načtení při mountu) + `scripts/2026-10-02_v3d_testy/harness_page.js` scénář 9.

## 5h) Tlačítka pohybů po stranách a rozměry vybraného dílu (viewer 1.11.0; bot10, 2026-10-06; Robert: „interaktivní tlačítka musí být ve více řadách a rozlišené pro kterou jsou stranu, zároveň nech se vybranému komponentu zobrazí rozměry“)
- **Řady podle strany:** má-li model pohyby s `g` (`left | right | bulkhead`, volitelné pole spec pohybu; u společné nabídky ho doplňuje `v3d_merge.sluc_glb`), viewer postaví spodní lištu jako řádky: popisek strany („Levá strana / Pravá strana / Přepážka“, barevně
  zelená / oranžová / modrá) + tlačítka pohybů té strany + **Otevřít vše / Zavřít vše jen pro tu stranu** (tlačítko řádku otevírá vždy celou stranu bez ohledu na kameru). Číslování pohybů začíná v každé straně znovu („Šuplík 1“ vlevo i vpravo).
  Na úzkém displeji se každý řádek posouvá do strany, popisek strany zůstává vidět (sticky). Model bez `g` (jednotlivá karta) = dosavadní jedna řada beze změny (CSS proměnná výšky řad se nenastavuje).
- **Výběr komponentu s rozměry:** `V3D.mount({selDims: true})` (stránka nabídky i kontrolní scéna): klik na díl ve 3D nebo na tlačítko pohybu komponent vybere (tlačítko dostane oranžový obrys) a ukáže jeho 3 rozměry (šířka, výška, hloubka v rámu čela, oranžové popisky),
  počítané z obálky dílu v ZAVŘENÉM stavu a nesené s pivotem (vyjedou s šuplíkem); vidět i při „Kóty: Vyp“. Zruší se kliknutím mimo model, tlačítkem Výchozí pohled nebo výběrem jiného dílu; `v.selectMotion(id|null)`. Bez `selDims: true` (generátory, mini-shopy) se nic nemění.
- Testy: `scripts/2026-10-06_v3d_rady_testy/test_rady_vyber.js` (skutečná kontrolní scéna + viewer; řady, číslování, Otevřít vše po stranách, výběr, rozměry při Kóty Vyp, zrušení, tři strany, model bez `g`, neplatné `g`, mobil) + `vyrob_glb.py`.

## 5i) Výzva ke kliknutí při najetí myší na pohyblivý díl (viewer 1.13.0; bot10, 2026-10-07; Robert: „nech se nabídne při najetí myší na dynamický komponent pobídka kliknout intuitivně“)
- `V3D.mount({hoverHint: true})` – zapnuto na stránce nabídky (obě větve `V3D.mount`) a v kontrolní scéně; výchozí vypnuto (generátory, mini-shopy, Připni cokoli beze změny; kurzor ruka nad klikacím dílem je jako dřív vždy).
- **Jen myš** (`pointerType === 'mouse'`, dotyk nemá najetí). Nad pohyblivým dílem: (1) díl se podsvítí oranžovou průhlednou vrstvou (0,45) na svých meshích – materiál modelu se nemění, takže vrstva nepřebije barvy / sytost / hliník / AO;
  díl = všechny meshe, jejichž klik spustí tentýž pohyb (`motionOfMesh`, stejné pravidlo jako `hitAt`/`pickAt`), (2) kurzor ruka, (3) popisek u kurzoru `<Druh N> · <Strana>` + `Kliknutím otevřete` / `Kliknutím zavřete` (podle cílového stavu; po kliknutí se text hned přepne).
  Box na zavřeném výsuvu: první klik vysune výsuv, proto `Kliknutím otevřete: Výsuv N` (stejné pravidlo jako `pickAt`).
- **Kdy ne:** díl mimo `motions[].pick`; díl, jehož klik jde do `onPick` stránky (`!motionExplicit`); při tažení / otáčení modelu (zmizí a nepřepočítává se, dokud je tlačítko myši stisknuté – jinak by se výzva počítala na staré poloze kurzoru, zatímco se otáčí kamera);
  dotyk; v drátěném vzhledu je jen popisek a kurzor (bez vrstvy). Zmizí i při odjetí z plátna, výměně modelu (`setModel`), `setMode`, `snapshot()` (snímek bez podsvícení) a `dispose()`.
- Dovyhodnocení (trailing 100 ms): po zastavení myši, po animaci pohybu, po pohybu kamery (kolečko, doběh otáčení) a po kliknutí (poloha kurzoru se bere z události `pointerup`). Totéž zpoždění platí i pro kurzor ruka bez `hoverHint` (dřív se poslední poloha při rychlém pohybu nevyhodnotila).
- Texty: `L.hover_open`, `L.hover_close` (+ `side_left|right|bulkhead`), přepsatelné přes `opts.labels`; slovníky mini-shopů `miniweb/i18n/en.json|sk.json` je mají (test `test_en_mini_shop.js` P1c hlídá, že slovník pokrývá všechny `V3D.labelKeys` – u 1.11.0 chyběly `side_*`, doplněno).
- CSS `.v3d-tip` (`__name`, `__act`, `__ico`; `pointer-events: none`, `role="tooltip"`), ladicí hook `window.__v3d.hoverInfo()` (`{id, overlays, on, name, act, cursor, tip}`).
- Testy: `scripts/2026-10-07_v3d_hover_testy/test_hover_pobidka.js` (oddíl A myš + B drátěný vzhled, C dotyk, D druhé instance vieweru: bez `hoverHint`, `labels`, `setModel`, `snapshot`, `dispose`; `H_ONLY=A|C|D`) + `_mutace_hover.py` (16 mutací).

## 5j) Odlesky materiálů, hliníku a AO (viewer 1.14.0; bot10, 2026-10-07; Robert: „ještě bych potřeboval v té online scéně nabídky řešit odlesky materiálů, jejich AO a také možnost přidat další HDRI ze sdíleného disku“)
- **Uložení** (`app_settings.v3d_nabidka_vzhled`, `api/v3d_vzhled.py`, stejná cesta jako HDRI / sytost / barvy): nová volitelná pole `lesk` `{"#původní": 0–2}` (lesk NE-hliníkového materiálu podle jeho původní barvy; 1 = beze změny se neukládá), `alu_cfg` `{refl 0–1,5, rough 0,5–2}` (odlesky = síla odrazu a matnost hliníku jako NÁSOBKY zvolené varianty hliníku), `ao_cfg` `{k 0–2, r 0,25–3}` (síla a dosah AO jako násobky zvolené varianty AO). `null` = výchozí, mimo meze / neznámý klíč = 400. Meze jsou shodné s viewerem (`GLOSS_MAX`, `ALU_REFL_MAX`, `ALU_ROUGH_MIN/MAX`, `AO_K_MAX`, `AO_R_MIN/MAX`), shodu hlídá `test_vzhled_api.py`.
- **Viewer:** `matConfig.gloss` (`setMatConfig` / `getMatConfig`), `opts.aluConfig` / `v.setAluConfig({refl, rough})` / `getAluConfig` / `resetAluConfig`, `opts.aoConfig` / `v.setAoConfig({k, r})` / `getAoConfig` / `resetAoConfig`. Lesk: drsnost = původní^lesk (0 % = mat = 1, 100 % beze změny, 200 % druhá mocnina; omezeno na 0,02–1). Hliník: `envMapIntensity` × odrazy (i u varianty „Dnešní“) a drsnost × matnost. AO: `aoEff()` = varianta × posuvníky (jedno místo pro vykreslení i hook; při AO „Vyp“ bez účinku). Ladicí hooky: `matInfo()` (`rough`, `rough0`), `aluInfo()`, `aoValues()`.
- **UI** (`kontrola.html` → Vzhled nabídek → Materiály): posuvník „Lesk“ u každé barvy (↺), „Hliník – odlesky / matnost“, „AO – síla / dosah“ (při vypnutém AO šedé; od 1.16.0 viz 5l: AO po komponentech a automatické ukládání); ukládá se spolu s ostatním tlačítkem „Uložit vzhled pro nabídky“, „Vrátit výchozí vzhled“ vrací vše. Stránka nabídky předává hodnoty z veřejného GET (`matConfig.gloss`, `aluConfig`, `aoConfig`).
- **Probe backendu (statika je živá dřív než `api/*.py`):** nová část okna (odlesky, AO, lesk u barev, přidání HDRI) se ukáže až když GET `/api/public/v3d-vzhled` vrací klíče `lesk` a `hdri_extra` (třída `nove-api` na `#vzhledPanel`); do té doby PUT nese jen stará pole (starý server nová odmítá 400).
- Testy: `scripts/2026-10-07_v3d_lesk_testy/test_lesk_ao.js` (37 kontrol včetně starého serveru) + `_mutace_lesk.py` (16 mutací, před vyhodnocením ověří nemutovaný základ), `test_vzhled_api.py` (29) + `_mutace_vzhled.py` (32), harness stránky nabídky scénář 9 (e, f).

## 5k) Přidání HDRI ze Sdíleného disku (viewer 1.15.0; bot10, 2026-10-07)
- Knihovna HDRI vieweru je v kódu (crossfit, tv_studio, berg_inner, teufelsberg). **Admin v okně „Vzhled nabídek“ → „+ Přidat HDRI ze Sdíleného disku…“** vybere soubor `.hdr` (libovolná složka Sdíleného disku, ke které má přístup; ≤ 150 MB, šířka ≤ 8192 px, equirectangular 2:1), zadá název a server ho převede: `api/v3d_env_prevod.py` (podproces s limitem paměti 3 GB, časový limit 50 s; ploché průměrování v lineární radianci, RGBE s RLE) na `<klíč>_1024.hdr` (1024×512) a `<klíč>_256.hdr` (náhled) do `private-files/v3d-env/` (mimo nginx docroot a mimo git; jde vždy znovu vyrobit ze Sdíleného disku). Normalizace jasu `mul0` = střední jas `crossfit_1024.hdr` / střední jas nového HDRI (u tří ručně změřených HDRI knihovny vychází do 5 % od dřívějších hodnot 0,53 / 1,44 / 0,89). Okamžitě se nové HDRI ukáže v náhledu a uloží se obvyklým tlačítkem.
- **API** (`api/v3d_env_import.py`, importuje ho `api/v3d_vzhled.py`, `app.py` se nemění): `GET /api/admin/v3d-env/zdroje`, `POST /api/admin/v3d-env/import` `{file_id, label?}`, `DELETE /api/admin/v3d-env/<klíč>` (409 když je HDRI uložené ve vzhledu nabídek), `GET /api/public/v3d-env/<klíč>_<1024|256>.hdr` (jen klíče z evidence, `nosniff`, cache 1 h). Evidence = `app_settings.v3d_env_extra` (JSON seznam; veřejný GET vzhledu ji vrací jako `hdri_extra` bez ID a názvů zdrojů). `env.hdri` v uloženém vzhledu smí být i klíč doplněného HDRI.
- **Hlídáno:** oprávnění `nastaveni/upravit` + přístup ke složce disku (`drive._user_can_access_folder`); zdroj JEN podle id souboru (nikdy cesta od klienta, `realpath` musí zůstat v adresáři disku); jen `.hdr` (EXR zatím ne – chtěl by novou závislost OpenEXR); hlavička `#?RADIANCE`; **zakázaná HDRI `modern_buildings`** (stejný seznam jako `api/render_hdri.py`); klíč se generuje na serveru (`[a-z][a-z0-9_]{2,39}`, bez kolize s vestavěnými ani doplněnými), nejvýš 12 doplněných; jeden import naráz (`flock`); atomický zápis (tmp + `os.replace`, nejdřív soubory, pak evidence, při selhání evidence se soubory odstraní); audit.
- **Viewer:** `V3D.addEnvLibrary([{key, label, mul0, rot0_deg, url, lo}])` rozšíří `V3D.envLibrary` (před „Místnost“) i knihovnu pro `normalizeEnvConfig` / `setEnvConfig` / `opts.envConfig`; volat PŘED `V3D.mount` a `V3D.envPicker` (stránka nabídky a kontrolní scéna to dělají po načtení vzhledu). Jen klíče `[a-z][a-z0-9_]{2,39}` bez kolize s vestavěnými a URL jen `/api/public/v3d-env/<klíč>_1024.hdr` (cizí adresy, `..`, velká písmena se zahodí).
- **Pasti:** HDRI smazané z knihovny zmizí ze seznamu až po obnovení stránky (`V3D.envLibrary` je sdílená); převod 8k trvá ~10 s a chce ~1,2 GB RAM (gunicorn timeout je 60 s, proto vlastní limit 50 s – při velké zátěži serveru (naměřeno 39 s u 97MB 8k souboru při zátěži 5–20) může padnout s větou „trval déle“, stačí zopakovat); ukládaný vzhled s klíčem, který mezitím zmizel z evidence, se čte jako výchozí (`DELETE` to hlídá 409).
- Testy: `scripts/2026-10-07_v3d_env_testy/test_env_import_api.py` (44, skutečný převod syntetického HDRI) + `_mutace_env.py` (42 mutací zabezpečení a převodu), `test_env_import_ui.js` (23: seznam, import, výběr v náhledu, uložení, obnovení stránky, smazání, chyby, neplatné `hdri_extra`), harness stránky nabídky scénář 9 (f).

## 5l) AO po komponentech a automatické ukládání vzhledu (viewer 1.16.0; bot10, 2026-10-07; Robert: „nenašel jsem AO pro jednotlivé komponenty, jen pro hliníkové profily, doplnit“ a „úpravy barev a lesků chci aby se uložily i pro ostatní další nabídky“)
- **AO po komponentech:** `matConfig.ao` `{"#původní": 0–2}` = váha AO na dílech té PŮVODNÍ barvy (1 = beze změny, 0 = bez AO, 2 = dvojnásobná; stejný klíč jako `lesk` a `barvy`) a `aluConfig.ao` 0–2 = totéž pro hliníkové profily. Ukládá se jako nová pole `ao_mat` a `alu_cfg.ao` (`api/v3d_vzhled.py`, strop `AO_MAT_MEZE` = `AO_MAT_MAX` ve viewerem; shodu hlídá `test_vzhled_api.py`). `null` = výchozí, mimo meze / neznámý klíč = 400.
- **Jak to viewer dělá:** AO se dál počítá z hloubky celého obrazu (GTAO, viz 5j). Váha se jen přikládá k ztmavení každého pixelu podle materiálu, který pixel zakrývá: má-li aspoň jeden viditelný mesh váhu ≠ 1, přibude jeden průchod scény do `rtW` (stejná viditelnost jako hloubka, každý mesh barvou 0,5 × váha; materiály meshů se po průchodu vždy vrátí) a skládání AO (`uK × váha`) ho přečte. Bez vah se nekreslí nic navíc, při AO „Vyp“ se váhy ignorují. Hooky: `matInfo()` / `aluInfo()` `aoW`, `aoValues()` `wPasses` / `wMeshes`; `getMatConfig()` / `getAluConfig()` / `materialPalette()` nesou `ao`.
- **UI** (`kontrola.html` → Vzhled nabídek → Materiály): u každé barvy druhý posuvník „AO“ (0–200 %, ↺), v sekci hliníku „Hliník – AO“; dřívější „AO – síla / dosah“ se jmenuje „AO celkově – síla / dosah“ (platí pro celou scénu, váhy se s ním násobí). Při vypnutém AO (levý horní roh 3D) jsou všechny posuvníky AO šedé.
- **Automatické ukládání:** každá změna barvy, lesku, AO, sytosti a hliníku v okně se po 0,9 s ticha uloží sama pro všechny nabídky (PUT `/api/admin/v3d-vzhled`; změny v rychlém sledu se spojí, ukládání jde po jednom, při zavření stránky se čekající změna pošle hned). Ukládání na pozadí **nemění** uložené HDRI ani volbu hliníku / AO z rohu 3D (zůstane uložená hodnota, takže se náhled HDRI nepustí k zákazníkům); ty se dál ukládají tlačítkem „Uložit vzhled pro nabídky“, které uloží vše. Stav pod nadpisem sekce: „Změny se uloží za chvilku…“ / „Ukládám…“ / „Uloženo pro všechny nabídky (čas)“ / „Neuloženo: důvod“.
- **Platí pro ostatní nabídky podle PŮVODNÍ barvy materiálu:** materiály v modelech jsou anonymní (`m01`…), proto je klíčem původní sRGB hex; stejná barva v jiné nabídce = stejná změna (ověřeno proti živému uloženému vzhledu na modelu karty 4918 přes stránku nabídky). Paleta se mění s tabulkou přiřazení materiálů (jiný hash `b3-…` v `private-files/v3d-cache`) a mezi kartami (karty 4964 / 4965 nemají #0700ff ani #00039a): úprava barvy, kterou model nemá, se v něm neprojeví. Úpravy barev, které v aktuální scéně nejsou, ukáže sbalený seznam „Uloženo i pro barvy, které v této scéně nejsou (N)“ s tlačítkem „Zrušit“.
- **Probe (statika je živá dřív než `api/*.py`):** AO po komponentech je v okně jako náhled už s třídou `nove-api`; ukládá se až když GET vrací klíč `ao_mat` (třída `ao-mat-api`). Do té doby je v okně poznámka „zatím jen náhled“ a PUT nese starší pole (`alu_cfg` bez `ao`, bez `ao_mat`; starý server by je odmítl 400).
- Testy: `scripts/2026-10-07_v3d_aomat_testy/test_ao_mat.js` (65 kontrol: pixelové porovnání snímků – váha 0 / 1 / 2, jen díly dané barvy, hliník, AO vyp, obnova materiálů; posuvníky; automatické ukládání vč. pořadí, chyby, zavření stránky; starý server; seznam mimo scénu; načtení uloženého; oddíly `ONLY=AB…`, `WEB_OVERRIDE`) + `_mutace_aomat.py` (34 mutací, před vyhodnocením ověří nemutovaný základ), `test_vzhled_api.py` (30) + `_mutace_vzhled.py` (38), harness stránky nabídky scénář 9 (h; `H_NO_TIMING=1` vypne hlídání 12 s ve scénáři c, které při zátěži stroje selhává i na nezměněném kódu).

## 5m) Okno Vzhled online nabídek v generátorech stolů a odkaz u každé karty (bot10, 2026-10-07; Robert: „to nemá být jen v jedné kartě, ale automaticky v každé“, „ať se to negeneruje pořád dokola, může to být propojené do generátorů stolů a tam to může sídlit“)
- **Jedno nastavení pro všechny nabídky** (5f, 5l) se dá upravit na třech místech, vždy tímtéž oknem (kód v `kontrola.html`, nic se neduplikuje): kontrolní scéna u Vandr karty, **okno „Vzhled online nabídek“ v každém generátoru stolů (01–05, jen admin)** a odkaz „Vzhled online nabídek…“ **u každé karty produktu** (jen admin).
- **Model zadaný adresou:** `kontrola.html?items=mu:<adresa GLB>&rezim=nabidka` (adresa = `encodeURIComponent` cesty `/api/shop/configurator/glb/<token>`, jiná cesta se zahodí hláškou „Neplatný formát ?items=“) otevře STEJNÉ okno Vzhled nad GLB, který generátor už má (v kontrolní scéně se nic nestaví na serveru, na rozdíl od `vd:<karta>`). `&embed=1` skryje horní popisek (iframe), `&vzhled=1` otevře okno Vzhled samo.
- **Generátor stolu (`js/stul-host.js`, `initVzhled`):** okno „Vzhled online nabídek (barvy, lesk, AO, HDRI – pro všechny nabídky)“ jako POSLEDNÍ ŘÁDEK mřížky oken přes celou šířku (inline `grid-column: 1 / -1` = nový implicitní řádek; UVNITŘ mřížky, ne pod ní – jinak lišta s cenou na mobilu při rolování na konec nedrží dole, test C23 `test_stul_host.js`; NEPOUŽÍVAT `grid-area: desc` – stránky generátorů mají vlastní `grid-template-areas` bez `desc` a okno by rozhodilo rozložení, testy C4 / C6 / C17), sbalené; **iframe se načte až při prvním rozbalení** a ukazuje model právě otevřené konfigurace (adresa z `onModel`). Po změně konfigurace se iframe sám nemění (rozdělané úpravy by se ztratily): tlačítko „Načíst aktuální model“; odkaz „Otevřít ve zvláštním panelu“. `?vzhled=1` v adrese generátoru okno rozbalí a ukáže (odkaz z karty).
- **Odkaz u každé karty (`product.html`, `#pdAdminVzhled` / `#pdOfferVzhled`):** admin ho vidí u KAŽDÉ karty nezávisle na tom, zda z ní jde udělat nabídku; Vandr karta (SKU `VD-`) → kontrolní scéna s jejím modelem (`vd:<id>`), jiná karta → `/stul-konfigurator-40.html?vzhled=1`. Zákazník a ostatní role odkaz nevidí.
- Testy: `scripts/2026-10-07_vzhled_generator/test_kontrola_mu.js` (18: model z adresy bez stavby serverem, embed, ukládání barev, odmítnutí cizích adres), `test_vzhled_okno_generator.js` (okno u generátorů 01 / 02 / 05, lazy iframe, adresa modelu = adresa GLB, Načíst aktuální model, `?vzhled=1`), `scripts/2026-10-02_nabidka_tlacitko_testy/offer_button_test.js` (35: odkaz u každé karty jen pro admina).

## 5g) Společná online nabídka z více karet: levá + pravá strana + přepážka (bot10, 2026-10-06; Robert: „v jedné online nabídce nabídnout dohromady levou stranu, i pravou stranu i přepážku“)
- **Co:** jedna nabídka ze 2–3 karet Vandr TÉHOŽ vozu, každá karta jiná strana (levý regál `left`, pravý `right`, přepážka `bulkhead`). Karty stran zůstávají samostatné (každá má svou cenu a Vandr data);
  nabídka je spojí: **řádek ceny za každou kartu** (popis produktu – umístění – SKU), cena celkem = součet, **jedna 3D scéna** se všemi stranami (pohyby všech dílů), **kótovaný výkres ke každé straně**.
- **Vytvoření:** `POST /api/admin/vandr-vyroba/nabidka-spolecna`, tělo `{"karty": [id, id, (id)]}` (oprávnění `sdileny_disk/zobrazit` jako u nabídky z jedné karty). Karty se seřadí levá, pravá, přepážka (pořadí v těle je jedno).
  Odpověď 201 jako u nabídky z jedné karty + `karty`, `strany` (kanonické pořadí), `cena_celkem`. **Bez 3D se nezakládá** (společný statický model neexistuje): kterákoli karta se nepostaví / sloučení selže = chyba s důvodem
  (`{"error": "<česká věta>"}`, u karet s předponou „Karta <id>: “) a NIC nevznikne; postavené karty zůstanou v cache (další pokus je rychlý). Kontroly před stavbou: karta existuje, SKU `VD-`, hotový GLB, cena,
  stejné vozidlo (`car_name`), každá karta má právě jednu stranu, žádná strana dvakrát, ne víc než 3, ne duplicitní karta (400/404/502/503).
- **Model:** `api/v3d_merge.py::sluc_glb` – zákaznická GLB jednotlivých karet (už po `v3d_glb.sanitize`) mají STEJNÉ souřadnice vozu (levá strana x > 0, pravá x < 0), takže se jen spojí uzly/mesh/materiály/accessory;
  pivoty dalších zdrojů se přečíslují (`p01` → `p<N+01>`), id pohybů (`m1` → `m<N+1>`); každý pohyb dostane **`g` = strana zdroje** (`left | right | bulkhead`, volitelné pole spec pohybu, validace `v3d_glb.validate_spec`; strany předává endpoint, bez nich odhad levá/pravá z `front` a polohy boxu) a pořadové `n` se počítá **v rámci strany a druhu** (druhá strana začíná „Šuplík 1“ znovu ve své řadě tlačítek; viewer 1.11.0 řadí tlačítka pohybů do řádků podle `g` s popiskem „Levá strana / Pravá strana / Přepážka“ a Otevřít / Zavřít vše jen pro stranu); `box` = sjednocení, `front` z levé karty
  (viewer podle pohybů před/proti čelu pozná oboustrannou scénu), `dims` = kóty VŠECH zdrojů za sebou (Robert 2026-10-06: kótování se nikdy nedělá na sestavu jako celek, každá strana si drží své vlastní; souřadnice beze změny, vazba `dims[].p` na pivot se přečísluje jako pohyby), `look/u/up` musí být shodné. Výsledek znovu projde `v3d_glb.sanitize` + `final_check` a forenzním značením
  jako každý zákaznický model. Jakákoli nesrovnalost = `V3DError` → chyba, nikdy tichý neúplný model.
- **Nastavení nabidky:** `offer_options.vandr_single_drawing: true` + **`offer_options.vandr_drawings = [{slot: narys|bokorys|pudorys, label: "Levá strana"|"Pravá strana"|"Přepážka"}]`** (2–3 různé sloty, popisek max 40 znaků);
  výkres strany je uložen v obrázku nabídky se stejným názvem slotu (`view_narys`, `view_bokorys`, `view_pudorys`), 3D pohledy `view_3d_a/b` jsou z levé karty. **ID karet v `offer_options` nejsou** (veřejné JSON nabídky; jsou jen v audit_logu `v3d_model` → `karty`, `strany`).
  `api/scene_offers.py::_sanitize_offer_options` klíč propouští jen s `vandr_single_drawing` a jen platný (jinak ho zahodí celý, ne neúplný) a `admin_scene_offer_update` ho bere z uloženého řádku (z těla požadavku se nastavit nedá) –
  úprava nabídky v adminu („Upravit nabídku“) a uložení ruční ceny dopravy ho proto nesmažou. **Společné nabídky se skládají při VYTVOŘENÍ, ne přes PUT** (PUT drží obyčejné řádky kusovníku beze změny počtu a názvů; admin smí přidat jen ruční položky, ty jdou na konec).
- **Stránka:** `nabidka-online.html`, slide `drawings_vandr`: při 2–3 položkách `vandr_drawings` jedna stránka „Technické výkresy“ se všemi výkresy vedle sebe (`.views-grid-multi`, na mobilu pod sebou; popisek jako text),
  jinak dosavadní jeden výkres. 3D scéna: stejná jako u jedné karty (V3D s modelem nabídky), vzhled podle 5f.
- **Kontrolní scéna:** `?items=vd:<a>+<b>+<c>&rezim=nabidka` (jen v režimu nabídky, 2–3 různé karty, `+` nebo `%2B`) ukáže PŘESNĚ sloučený model, jaký dostane zákazník: `GET /api/kontrola-scena/v3d/<a>+<b>+<c>.glb` (stejná trasa jako u jedné karty,
  pořadí v adrese je jedno, hlavička `X-V3D-Karty` ukazuje kanonické pořadí). Nezakládá nabídku, nic nezapisuje.
  **Tlačítko „Vytvořit společnou nabídku“** (jen u skupiny karet, v horní liště pod popiskem): po potvrzení dialogem `POST /api/admin/vandr-vyroba/nabidka-spolecna {"karty":[…]}`; vedle tlačítka se ukáže číslo nabídky, součet cen karet a odkaz
  **Postup bez psaní do URL (Robert 2026-10-06 „nebudu nic přidávat do řádku URL“):** na webu na kartě Vandr produktu (admin pruh vedle „Vytvořit online nabídku“, `product.html`, oprávnění `sdileny_disk`) je odkaz **„Společná nabídka…“** → otevře
  kontrolní scénu `?items=vd:<karta>&rezim=nabidka`; v horní liště je select **„+ přidat stranu (společná nabídka)…“** se sourozeneckými kartami TÉHOŽ vozu (stejný název karty, jiné umístění v autě – karta bez umístění se nenabízí, hotový GLB a cena; popisek ukazuje umístění, číslo karty a cenu z `cena_czk` v `prehled`; ze stávajícího `GET /api/admin/vandr-vyroba/prehled`, právo `dash_vandr_vyroba`,
  bez práva se select neukáže); volba přepíše `?items=` na `vd:<a>+<b>` (max 3) a načte scénu se slučeným modelem; tlačítko „Vytvořit společnou nabídku“ je u skupiny karet. Konečnou kontrolu (stejný vůz podle Vandr dat, každá jiná strana) dělá server.
  „Otevřít nabídku“ (jen tvar `/nabidka-online.html?t=…`), případně červeně česká chyba ze serveru nebo „POZOR: vznikla BEZ 3D (důvod)“. Běží jedna stavba naráz (tlačítko je během ní zakázané), další klik po úspěchu upozorní, že nabídka z těchto karet už vznikla. Texty ze serveru se vkládají jako text.
- Testy: `scripts/2026-10-02_v3d_testy/test_spolecna_nabidka.py` (endpoint + sloučení + kontrolní trasa, skutečný Blender, 26), `test_spolecna_nabidka_admin.py` (úpravy nabídky a veřejné JSON nad dočasnými tabulkami, 34),
  `test_kontrola_nabidka_auto.js` oddíl 6 (skupina karet v kontrolní scéně) a 7 (tlačítko společné nabídky: potvrzení, POST, výsledek, chyby, bez 3D, text místo HTML, souběh; celkem 45 kontrol, 5 mutací chyceno), `harness_page.js` scénář A (výkres ke každé straně, mobil, neplatné sloty, popisek jako text).

## 5h) Ochranná razítka LOGIMAN.CZ v modelu nabídky (bot4, 2026-10-06; Robert: „v modelu 3D v online nabídce postrádám razítka logo“)

Pravidlo 2026-09-06: razítkování = stupeň 2 = model v nabídce. Build (`scripts/v3d/vandr_offer_build.py`) vkládá razítka karty
(`shop_products.vandr_razitka_json`: výplň drážky `vypln_placka` + `logo_logiman_cz`, pozice v mm a quaternion v glTF rámu katalogového GLB)
jako další díly PŘED slučováním (`RAZITKA`, `_nacti_razitkovy_dil`, `_pivot_pod_razitkem`):

- **Data** přes `ctx["razitka"]` (`build_ctx._razitka_pro_ctx`: díly, cesty+otisky katalogových GLB, barva loga z `scripts/razitkovac.py`
  `LOGO_BARVA_HEX`) - Blender build nemá DB. Chybí-li/je-li vadné cokoli, `ctx["razitka"]=None` + varování a model vznikne bez razítek (nabídka se nikdy nezastaví kvůli razítkům).
- **Cache:** `ctx_hash` zahrnuje `razitka` (pozice, barva, otisk GLB) a `verze_buildu()` je hash kódu buildu → nasazení tohoto kódu zneplatní staré modely bez razítek, nová nabídka z karty se postaví s nimi; **staré nabídky se nemění** (model je v nich uložený).
- **Neutrální jména:** razítko je mesh `v3dpridany_r<N>` → po slučování/přejmenování uzel `n<i>` a materiál `m<NN>`; `v3d_glb.sanitize` (jména logo|vandr|...) je přijme beze změny. „logo“ ve ZDROJOVÉM modelu (`VYNECHAT`) = logo dodavatele a dál se vyřazuje.
- **Pohyb:** razítko se přiřadí pohyblivé skupině (pivotu), jejíž díl (AABB ± 4 mm) obsahuje střed razítka (při více shodách nejmenší díl), jinak je statické. Razítka nepatří do rozměrů ani kót (`PROFIL_V` je jen z profilů; test: `overall_size` beze změny).
- **Materiál:** logo = barva z `razitkovac.py` (oranžová `#EB8E23`, neprůhledné; skleněný vzhled z turntable se pro web nepřenáší), výplň = hliníková šedá z dat razítka; razítka jsou vyňata z `omez_materialy_pivotu`, aby oranžová nesplynula s okolím.
- **Velikost:** katalogové logo má 8152 trojúhelníků, v modelu se zjednoduší na ~1000 (Decimate, `RAZITKO_TRI_MAX`; logo je řada zaoblených hranolů, mění se jen rohy): model karty 0,8 → ~1,3 MB.
- **Testy:** `scripts/2026-10-06_razitka_nabidka_testy/test_razitka.py` (24; skutečný Blender CPU, karta 4454 s razítky v pohyblivých skupinách, sanitize). Ověřeno i stavbou všech 40 aktivních karet s razítky (bez chyb).

## 5l) Multiboxy ve spec: `mbx` (příčky do multiboxů; bot8, 2026-10-07; Robert: „sety příček vždy pro celou polici / šuplík s multiboxy“)

Spec v3d má nepovinný seznam `mbx` – polohy Multiboxů pro výběr příček v nabídce: `[{"id":"b01","min":[x,y,z],"max":[x,y,z],"e":1,"p":"p22","n":1,"s":1,"sk":1,"g":"left"}]` (svět zavřeného stavu, glTF mm; `e` = strana konce s výkrojem;
`p` pivot boxu nebo `null`; `s` číslo skupiny = police / šuplík, `sk` druh jako číslo 1 police / 2 výsuv / 3 samostatné; `g` strana společné nabídky). **Žádná jména komponent** (`api/v3d_glb.validate_spec` zná klíče `mbx`, `e`, `s`, `sk`, id `b<N>`;
`final_check` je pustí, jména ne). Blender build ho generuje z kontejnerů `Multibox_Arc` (`scripts/v3d/vandr_offer_build.py`), `api/v3d_merge.sluc_glb` ho slučuje (id a čísla skupin navazují, pivoty se přečíslují, `g` = strana zdroje). Viewer (`validateSpec`) neznámé klíče ignoruje –
čte je jen plugin `webapp/js/v3d/pricky-multibox.js`. Vše ostatní (sety, ceny, geometrie příček, výběr, objednávka) viz `docs/KONTRAKT_NABIDKA_PRICKY.md`.

## 6) Co mění server mimo endpoint (`api/scene_offers.py`, jen hlavičky a statistiky)
- `public_offer_model`: `Cache-Control: private, no-cache` + `ETag` (viz výše). Tělo se nemění.
- `CLICK_TARGETS` doplněno o `v3d_view`, `v3d_dims`, `v3d_mode`, `v3d_anim` (bez nich by `/event` vracel 400 na kliky v prohlížeči).
- Nativní nahrání modelu (`POST /api/admin/scene-offers/<id>/model`) a `save_offer_model_bytes` jsou **beze změny**.
