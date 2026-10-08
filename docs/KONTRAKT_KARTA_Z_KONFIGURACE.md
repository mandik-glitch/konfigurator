# Kontrakt: karta produktu z konfigurace generátoru stolu (bot10, 2026-10-07)

Zadání Roberta (2026-10-07): přes bot4 „budu vyrábět sestavy stolů z generátoru (karty) stejně jako u Vandr sestav, postav automatickou frontu“; přímo mně: **„přidat do generátorů: tlačítko které
z aktuální sestavy vytvoří aktivní kartu“.** Navazuje na dohodu bot4 + bot8 (TASKS.md, SKU `STUL-S<systém>-<hash8>`); vlastník: **bot10** (převzal od bot8 2026-10-07 večer).

## Rozhodnutí
- **Karta vzniká AKTIVNÍ hned po kliknutí** (Robertův výslovný pokyn; ostatní skripty zakládají karty neaktivní). Pravidlo 54 zakazuje RUČNÍ zásah bota do `active`; tady o aktivaci rozhodl Robert a udělá ji
  člověk kliknutím (funkce, ne ruční přepnutí). Aktivní karta bez obrázků je v e-shopu bez fotky, dokud je nedoplní render (automat bot4, výchozí VYPNUTO).
- **Kdo:** tlačítko vidí a mačká uživatel s právem `sklad_karty` / `vytvorit` (admin vždy). **Aktivní** karta jen s právem `sklad_karty` / `upravit`; bez něj vznikne karta neaktivní (server rozhoduje, klient jen žádá).
- **Karta = konfigurátor s uloženou výchozí konfigurací.** Stránka karty ukazuje generátor otevřený na TÉTO konfiguraci (zákazník ji může upravit); košík, objednávka, online nabídka a 3D jedou beze změny stejnou
  cestou jako u karty generátoru, cena na stránce je vždy ŽIVÁ cena generátoru. Cena v kartě (`price_czk_placeholder`) je SNÍMEK bez DPH v okamžiku vzniku (dlaždice v katalogu); po změně ceníku se na kartě
  neobnovuje samo.
- **Idempotentní:** stejná konfigurace = stejné SKU = stejná karta; podruhé server vrátí existující kartu (200, `existing: true`) a nic nemění (ani `active`). Po změně pravidel generátoru (RULES_VERSION / prahy)
  se kanonický hash změní → nové SKU → nová karta; stará karta zůstává (její hash už „nesedí“, viz CLI).

## Co vznikne (jedna transakce; GLB se zapíše PŘED vložením karty a při selhání se smaže)
| Co | Kde |
|---|---|
| karta | `shop_products`: SKU `STUL-S<systém>-<hash8>` (hash8 = prvních 8 znaků `stul_glb.kanonicky_hash`), název `<název karty generátoru bez „– konfigurovatelný“> – <š> × <h> × <v> mm` (upravitelný v dialogu), popis = text karty generátoru + „Parametry této konfigurace:“ (souhrn generátoru česky), cena = prodejní cena bez DPH, `active` 1 + `activated_at`, `glb_file` = `stul/<SKU>.glb`, kategorie (viz níže), jednotka / dostupnost / zobrazení ceny / `render_material_key` kopie z karty generátoru |
| model | `webapp/katalog/stul/<SKU>.glb` S razítky loga (`konfigurator_registr.glb_bytes(…, razitka=True)`; pravidlo 61, Robert 2026-10-08: razítka na všech 3D modelech ve všech generátorech – soubor je veřejně dostupný přímým odkazem, proto ho chrání stejně jako model v nabídce), musí mít `scenes[0].extras.v3d.front` (jinak karta nevznikne); zápis atomicky (tmp + rename) |
| registr | `app_settings.configurator_products` + `<id nové karty>`: recept zdrojové karty (zamčeno `SELECT … FOR UPDATE`, souběžné zakládání se serializuje, cizí záznamy se nemění) |
| výchozí konfigurace | `app_settings.configurator_default_<id>` = efektivní výběr (stránka karty se otevře s ním; mechanismus „Uložit jako výchozí“) |
| záznam pro audit a CLI | `app_settings.stul_karta_<id>` = `{v, system, selection, rules_version, hash, kod, zdroj_karta, sku}` (neměnný; bez DDL) |
| audit | `audit_log`: `create_from_configuration` / `shop_product`, detail = SKU, systém, kód, hash, zdroj, aktivní, cena, kategorie |

**Kategorie:** výchozí podle systému 30→206, 35→312, 40→311, 41→183, **45 → žádná** (kategorie pro systém 45 zatím neexistuje); v dialogu jde zvolit jakoukoli viditelnou kategorii z větve 182
„Balicí stoly a pracoviště na míru“ nebo „bez kategorie“ (karta bez kategorie se v katalogu nezobrazí, jen přímým odkazem).
**Generátorové karty (4934 / 4954 / 4955 / 4959 / 5353) se nemění.** Kopie se do `shop_product_categories`, galerie ani dokumentů nedělají (generátorová karta je nemá).

## Endpoint (`api/stul_karta.py`)
- `GET /api/admin/konfigurace/karta` = **sonda**: `200 {"ok": true, "verze": 1, "muze_aktivovat": bool, "kategorie": [{id, name}], "vychozi_kategorie": {"30": 206, …, "45": null}}` jen s právem
  `sklad_karty/vytvorit`; `401`/`403` bez práva, `404` = backend ještě není nasazen (UI tlačítko nezobrazí; statika jde živě dřív než API).
- `POST /api/admin/konfigurace/karta` (JSON), stejné právo:
```json
{"product_id": 4954, "configuration": {"selection": {"...": "..."}, "rules_version": "2026-10-06.1"}, "hash": "volitelné", "nahled": false,
 "name": "volitelné, 3–200 znaků, bez [ ] < >", "category_id": 311, "active": true}
```
  `product_id` = karta generátoru (nebo karta vzniklá z konfigurace) – systém se pozná z jejího receptu. Cenu, kód, hash, model ani popis nebere server od klienta (`konfigurace_kosik.vyres` = stejný zdroj jako
  košík a online nabídka). **`nahled: true`** nic nezapisuje a nestaví model, jen vrátí `{nahled, sku, system, name, kod, hash, price, category_id, kategorie, active, muze_aktivovat, rules_version, existing}`.
- Odpovědi: `201` `{ok, existing:false, id, sku, system, name, kod, hash, price{net_czk,vat_rate,vat_czk,gross_czk}, active, category_id, url:"/produkt/<slug>", glb_file, rules_version, poznamka}`;
  `200` `existing:true` (stejné SKU už existuje); chyby `{error, message}`: `400 invalid_selection|invalid_name|invalid_category`, `404 not_configurable`, `409 rules_changed|configuration_changed|exists|price_on_request`,
  `422 invalid_configuration` (+ `errors`), `429 rate_limited` (20 karet za hodinu na uživatele; náhled se nepočítá), `500 glb_failed|glb_invalid|selection_not_storable|save_failed|registry_*`.
- Pasti: `current_user()` a `has_permission()` se volají PŘED `get_conn()` (sdílené spojení: `close()` = rollback); po commitu se obnoví cache registru v procesu, **ostatní gunicorn workery se osvěží do 60 s**
  (do té doby může nově vzniklá karta na jiném workeru krátce působit jako nekonfigurovatelná).

## UI (`webapp/js/stul-karta.js`, mount v `js/stul-host.js`)
Tlačítko **„Vytvořit kartu“** v okně „Cena a scéna“ každého zaměstnaneckého generátoru (01–05) pod „Do online nabídky“; skryté, dokud sonda nevrátí 200. Klik → dialog: nejdřív `nahled`, pak pole název,
kategorie, „Aktivní hned“ (jen s právem aktivovat), cena (snímek) a kód karty; „Vytvořit aktivní kartu“ → výsledek s odkazem „Otevřít kartu“ (jen http(s) na naše domény). Existuje-li karta, dialog to řekne
a nic nezakládá. Texty z odpovědí serveru se vkládají jen jako text. Nová verze modulu = `scripts/stul_verze.py` (pin `?v=` v HTML generátorů).

## Pro bot4 (automat otoček stolů z generátoru, výchozí VYPNUTO) – „hotová k renderu“
SKU `^STUL-S(30|35|40|41|45)-[0-9a-f]{8}$` + `active` + `glb_file` vyplněné + soubor existuje v `webapp/katalog/` + hash8 v SKU = kanonický hash uloženého výběru + v GLB `extras.v3d.front`.
Model uložený na kartě je od 2026-10-08 S razítky (dřív bez nich a razítka se jen dopočítávala pro render; soubor existující karty #5361 byl přegenerován). `scripts/stul_karta_glb.py <id> [--razitka] -o x.glb` postaví model znovu z `stul_karta_<id>` (s `--razitka` totéž co uložený soubor – to používá render, bez přepínače model BEZ razítek = diagnostika; kontroluje SKU, systém, hash dnes = uložený = hash8; kód 3 = pravidla se od
založení změnila, model by neodpovídal kartě). **CLI před výpočtem načte uložená pravidla stolu stejně jako API** (`app_settings.stul_pravidla` = prahy po systémech, formát tabule karty 4933; `stul_api.obnov_pravidla`) – bez toho počítá s výchozími prahy (např. šířka střední nohy u systému 40: výchozích 1500 místo uložených 2000) a končí kódem 3 i u nezměněných pravidel (chyba z 2026-10-08, karta #5361). Stejně musí být pravidla načtena u KAŽDÉ trasy, která stůl z konfigurace počítá: `/api/admin/konfigurace/` (karta, nabídka) je od 2026-10-08 v `_STUL_CESTY` (`api/stul_api.py`), jinak by čerstvý worker počítal hash, cenu i model s výchozími prahy. `--info` jen vypíše záznam a ověří hash. Skript „produkty bez obrázku“ karty `STUL-S*` přeskakuje (renderuje je automat).
Veřejné `GET /api/shop/products/<id>` vrací u `STUL-S*` karet `glb_file: null` (jako u `VD-*`); model v `webapp/katalog/stul/` je ale přes nginx `/katalog/` dostupný přímým odkazem – je to týž model, který
veřejně dává generátor (`/api/shop/configurator/glb/<token>`), takže nic navíc neprozrazuje (od pravidla 61 má razítka loga i on).

## Testy (`scripts/2026-10-07_stul_karta/`)
`test_karta_db.py` (jádro nad dočasnými tabulkami, vč. skutečných modelů všech 5 systémů; `--rychle` bez nich), `test_karta_route.py` (endpoint přes Flask test client: RBAC, náhled, vznik, idempotence, chyby,
neaktivní bez práva, limit, `glb_file` null ve veřejném detailu), `test_karta_cli.py` (CLI), `test_karta_tlacitko.js` (prohlížeč: sonda, dialog, chyby, XSS, klávesnice, všechny systémy, statika/piny; endpoint
simulovaný `page.route`). Úspěšnou cestu proti ostré DB testovat nelze (zakládá skutečnou kartu) – zápisy jdou do TEMPORARY tabulek, ostré tabulky a `webapp/katalog/stul/` se kontrolují před a po.
Spuštění: viz hlavičky souborů (DB přes `systemd-run --property=EnvironmentFile=/opt/konfigurator/api/.env`). Mosty testů (`_most_stul.py`, `bridge.py`) odpovídají na sondu 200.
