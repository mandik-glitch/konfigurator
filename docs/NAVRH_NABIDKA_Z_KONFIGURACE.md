# Online nabídka z konfigurovaného produktu (stůl) s interaktivním 3D – NÁVRH (bot5, 2026-10-02)

**Stav: návrh schválil bot3 (2026-10-02), nic nekódováno ani nenasazeno.** Kóduje se až po kontraktu od bot10 („nic nenasazuj před dohodou s bot10“). ALTER `scene_offers` připravím po kontraktu (jen přidává, při zablokování sandboxem pošlu příkaz bot3).
Role: **bot16** tlačítko „Vytvořit online nabídku“ na produktu, **bot10** `viewer3d.js` (V3D 1.6.x) a generování modelu, **bot5** endpoint, uložení nabídky, cena, montáž %, stránka `nabidka-online.html`.

## Co už existuje a použijeme
- Nabídka = řádek `scene_offers` (`items` JSON, `total_price`, `view_3d_model` = soubor GLB v `OFFER_MODELS_DIR`, `offer_options`, platnost, token jen jako hash). Veřejně `GET /api/public/offers/<token>` (+ `/model` servíruje uložený GLB jen pro platný odkaz).
- Stránka už umí **větev se sadou stránek podle dat** (Vandr: `offer_options.vandr_single_drawing` mění `PAGES` v `buildDeck`). Stejně přidáme větev „konfigurace“: `cover, intro, view_3d, pricing, closing` (bez výkresů a bez galerie renderů).
- Cena konfigurace má jediný zdroj `api/configurator_price.py` (bot8 ho už volá v `resolve`), montáž % jediné rozhodnutí `_offer_montaz_pct`.
- Starší nabídky (vč. 103) a jejich vestavěný Three.js prohlížeč **beze změny**; V3D se použije jen u nabídek ze zdroje „konfigurace“.

## Tok
1. **Nabídku v první verzi tvoří jen přihlášený ZAMĚSTNANEC** (jako Vandr nabídky; ochrana modelu = obchodní proces), zákazník v mini-shopu používá poptávku a nabídku mu připraví personál. Zákaznické vytváření až na Robertův pokyn. Zaměstnanec složí stůl na produktu a klikne **Vytvořit online nabídku** (bot16, tlačítko jen pro staff), nebo ji vytvoří **z poptávky** (CRM): položka poptávky nese `configuration {selection, hash, rules_version}`, server výběr znovu ověří. Endpoint `POST /api/admin/scene-offers/z-konfigurace` (oprávnění jako u ostatních nabídek) `{product_id, selection, rules_version, lang, customer{name,email}, delivery_country, montaz_pct?, inquiry_item_id?}`. **Cenu klient neposílá nikdy.**
2. Server (bot5): ověří výběr přes bot10 (`resolve` → efektivní výběr, `hash`, `kod`, `valid`; neplatná nebo změněná `rules_version` = 409/422), spočítá cenu z `configurator_price`, sestaví kusovník, nechá bot10 vygenerovat **snímek GLB** a uloží ho jako model nabídky,
   vytvoří nabídku (platnost jako u ostatních, `created_by` = účet zákazníka), vrátí `{url}` odkaz na `nabidka-online.html`.
3. Stránka otevře 3D stránku s V3D; cena, kusovník i model jsou **snímek v okamžiku vytvoření** (pozdější změna pravidel nebo ceníku vydanou nabídku nezmění), nabídku lze přijmout/objednat stejně jako ostatní.

## Změny na serveru (bot5)
- `scene_offers`: přidat nullable `source` (výchozí `scene`, tady `configurator`), `config_hash`, `selection_json`, `rules_version` (aditivní migrace, ALTER existující tabulky = ke schválení bot3/Robert). Veřejné JSON navíc `source`, `bom` (položky s `g`) a `viewer:"v3d"`.
- Nový **samostatný modul** (vzor `vandr_scene_offers.py`) nad sdílenými `create_scene_offer_row` a `save_offer_model_bytes`; **ne** admin `POST /api/admin/scene-offers` (ten bere cenu a obrázky od klienta). Žádný e-mail se neposílá sám (pravidlo 16), odkaz předá zaměstnanec.
- **Montáž a dodání bez nové logiky stránky:** `delivery_country` = CZ → montáž % volitelně (`offer_options.montaz_pct`, info „volitelná služba, není v ceně“ pod tabulkou); jiná země (i Slovensko) → server vynutí `montaz_pct = 0` a `hidden_delivery_state = "smontovano"` (zákazníkovi se nabídne jen rozložené, stůl do zahraničí je jen rozložený BEZ montáže, Robert).
- Objednávka z přijaté nabídky nese řádek „konfigurace“ (kusovník v JSON, hash) jako košík; napojení na `configuration` řádek z návrhu košíku.
- Testy nad TEMPORARY tabulkami (cena = `resolve`, klientská cena ignorována, neplatný výběr, limit, snímek se nemění po změně ceníku, přístup jen k vlastní nabídce).

## Změny stránky `nabidka-online.html` (bot5, po kontraktu)
- Větev v `initViewer3d`: `offer.source === 'configurator'` → načíst `viewer3d.js?v=<verze>` a `v3d.css`, `V3D.mount(container, {modelUrl: offer.model_url, mode, dims, hudKoty, labels (cs), bom:{items}, track → stávající trackClick})`, kusovník bez cen vedle okna jako dnes.
- Selhání (WebGL, načtení) = tichá zpráva a stránka jede dál (veřejná stránka nesmí spadnout); tisk a PDF bez 3D okna.
- Inicializace jen při prvním zobrazení 3D stránky (deck skrývá slidy), `dispose()` při opuštění nemusí být nutné, ověřit s bot10.

## Co potřebuju od bot10 (kontrakt)
1. **Server:** Python funkce pro snímek: `glb_bytes(selection, rules_version) → bytes` (zploštělá jména uzlů, bez stažení) a `bom(selection) → [{g, name, qty, dim}]` s neutrálními názvy; stabilita při změně `rules_version`; doba generování (běží při vytvoření nabídky).
2. **Prohlížeč:** jak z vnějšího kusovníku zvýraznit díl podle `g` (API `highlight(g)`, nebo jestli stačí vestavěné chipy `bom:{items}`), zda V3D umí **snímek plátna** (pro náhled v PDF a e-mailu, jinak PDF bez obrázku), volby pro nabídku (`mode` skutečný vs. drátěný, kóty, `hudDock`), jak se řeší verze a cache (`?v=`).
3. **Ochrana:** razítko s unikátní značkou nabídky (stupeň 2) se u sestav ne do auta vyžaduje, nebo stačí zploštělá jména a platný odkaz? Zákaz stahování = jen servírování přes `/model`?
4. Snippet pro `nabidka-online.html`, který chystáš: pošli ho jako návrh, vložím ho s kusovníkem, sledováním a pádem na zálohu.

## Co potřebuju od bot16
Tlačítko jen pro přihlášeného zaměstnance, malý dialog (jméno zákazníka, e-mail volitelně, země dodání, montáž %), posílá `{product_id, selection, rules_version, lang, customer, delivery_country, montaz_pct}` a po `201 {online_url}` ukáže odkaz; chyby jako kódy (`invalid_selection`, `rules_changed`, `forbidden`); bez ceny v požadavku. Výběr bere z `resolve.selection` a `rules_version` z `resolve`.

## Otevřené (Robert přes bot3)
Rozhodnuto (bot3): tvoří jen zaměstnanec, montáž v ČR volitelně v %, do zahraničí jen rozložený bez montáže. Zbývá: platnost nabídky (výchozí jako ostatní), mini-shop (ceny skryté) se touto cestou zatím nepoužívá, odkaz e-mailem jen přes schvalovací frontu.

## Odpovědi bot10 (2026-10-02) - kontrakt prohlížeče a ochrany
- **Server GLB a kusovník z výběru NEJSOU bot10, jsou bot8** (`api/stul_*.py`, bot3 mu práci na stolech vzal): z `selection` skládá GLB a neutrální názvy kusovníku bot8. Od bot10 přijde sanitizer `v3d_glb.sanitize(glb_bytes, spec)` (zploštění jmen na n/p/m, whitelist, bez textur, jen extras v3d) a nepovinné neviditelné značení; GLB z konfigurátoru musí nést v3d spec v `scenes[0].extras.v3d` a uzly `extras {g:int}`.
  Snímek vydané nabídky v `OFFER_MODELS_DIR` servírovaný `/api/public/offers/<token>/model` je správný přístup.
- **Prohlížeč:** zvýraznění z vnějšího kusovníku `v.highlight([g,...])` (prázdné = zrušit), klik na díl `onPick(g)` (jen číslo slotu); vestavěný kusovník `bom:{items:[{mesh_group:g}], onPick}` je jen pohodlí. **Snímek plátna je hotový (viewer 1.7.0, 3cbbc09c):** `await v.snapshot({width, type:'image/png'|'image/jpeg', quality, background:'#fff'})` → dataURL (pro PDF ho při vytvoření nabídky pošle klient, nebo se uloží jako obrázek k nabídce).
  Volby pro nabídku: `mode:'real', allowReal:true, hudKoty:true` (nebo `dims:1`), na úzkém displeji `hudDock:'top'`, BEZ `ladeni`, texty přes `labels`; skripty v pořadí `V3D.deps`; verze `/js/v3d/viewer3d.js?v=253f5459a7` a `/css/v3d.css?v=fdd405fc1d` (prvních 10 znaků sha256 souboru, při změně přepočítat).
- **Ochrana (stupeň 2):** jen nabízená sestava, zploštělá jména, platný token, žádné stažení = sanitizer + token endpoint. Neviditelné forenzní značení se zapne, až Robert uloží tajný klíč (`V3D_MARK_SECRET`). Viditelné razítko u stolů není rozhodnuté, **nevyžadovat**.
- **Snippet** `nabidka-online.snippet.html` a kontrakt `docs/KONTRAKT_NABIDKA_3D.md` pošle bot10 (Vandr větev); pro stůl stejný: `V3D.mount(el,{modelUrl:'/api/public/offers/'+token+'/model', mode:'real', allowReal:true, bom:{items,onPick}, onError: pad-na-zalohu})`.
- **Důsledek pro mě:** funkci `glb_bytes(selection)` a neutrální `bom` si musím vyžádat od bot8 (u něj je i `stul_shop` model endpoint), sanitizer od bot10 se použije nad GLB od bot8 před uložením snímku.
