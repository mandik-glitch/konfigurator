# Generátor 06 – ochranný kryt a oplocení strojů z profilů 40×40: kontrakt (bot8, 2026-10-08)

Robert 2026-10-08: *„udělej generátor ochranného oplocení a krytování strojů z profilů 40×40“* (fotka klece z profilů s čirými panely a dveřmi kolem pískovacího stroje), *„nahrát všechno hned“*.
Tenhle dokument je **kontrakt shop vrstvy a stránky** (fáze 2). Geometrie, kusovník a konstrukční rozhodnutí jádra jsou v `scripts/2026-10-08_oploceni/README.md` (fáze 1); obecný kontrakt voleb, `resolve`,
`model`, `glb` a košíku je `docs/KONTRAKT_KONFIGURATOR_UI.md` – oplocení ho **dodržuje beze změn tvaru**, takže sdílený modul voleb `webapp/js/product-configurator.js` jede nezměněný.

## 1) Kde co je

| vrstva | soubor | poznámka |
|---|---|---|
| jádro (geometrie, kusovník, `entries` pro cenu) | `api/oploceni_konfigurator.py` | čistá funkce, bez DB a Flasku; `VERZE_PRAVIDEL` = `RULES_VERSION` |
| 3D model (GLB) | `api/oploceni_glb.py` | dva režimy: veřejný/zaměstnanecký (zjednodušená patka a zámek, textura sítě) a nabídkový (plný detail, bez obrázků) |
| cena | `api/oploceni_cena.py` | `configurator_price.price_entries` + výplně jako virtuální desky, dokud nemají karty |
| shop vrstva | `api/oploceni_shop.py` | schéma cs/en/sk, `resolve`, úprava výběru na proveditelný, token modelu, `pro_objednavku`, `glb_bytes`, `odpoved_*` |
| rozcestník recept → modul | `api/konfigurator_registr.py` | `MODULY = {dopravnik_valeckovy: dopravnik_shop, oploceni_kryt: oploceni_shop}`; stůl zůstává v `stul_shop.py`; staré názvy (`dopravnik_modul`, `dopravnik_pro`, `je_dopravnik`) se nemění |
| routy | `api/stul_shop.py` | **všechny** routy zůstávají tady (Flask nedovolí registrovat routy po prvním požadavku, modul se načítá líně); modul jen vrací `odpoved_*` |
| košík, nabídka | `api/konfigurace_kosik.py`, `api/nabidka_z_konfigurace.py` | zobecněné přes registr (`bez_montaze`, `mimo_stul`, `jmeno_radku(..., rozmery_text)`) |
| stránka pro zaměstnance | `webapp/oploceni-konfigurator.html` + `webapp/js/oploceni-host.js` | „Generátor 06“; verze `?v=` přes `scripts/2026-10-08_oploceni/oploceni_verze.py` |
| karta produktu | `scripts/2026-10-08_oploceni/zaloz_kartu_oploceni.py` | neaktivní, `OPLOCENI.KRYT.KONF`, zápis `app_settings.configurator_products` |
| karty výplní | `scripts/2026-10-08_oploceni/zaloz_karty_vyplni.py` | 5 neaktivních karet desek; po zápisu se cena výplní bere z nich |

Recept se jmenuje `oploceni_kryt` (`app_settings.configurator_products` = `{"<id karty>": "oploceni_kryt"}`; smazání záznamu = API 404, jako u stolu).

## 2) Výběr zákazníka (`selection`) – veřejná ID slotů

Veřejná ID jsou **neutrální** (bez názvů dílů a dodavatelů). Server výběr vždy **upraví na proveditelný** a změnu oznámí v `notices` (`action: "adjusted"`, `slot` = slot, kterého se týká); špatný vstup není HTTP chyba.

| slot | typ | hodnoty | výchozí | poznámka |
|---|---|---|---|---|
| `w`, `d`, `h` | slider | šířka 600–4000, hloubka 600–4000, výška 1000–3000 mm, krok 10 | 1500, 1500, 2200 | jádro umí až 6000 × 6000; veřejnost 4000 (strop dílů modelu, viz 5). U jedné rovné strany bez střechy (oplocení) se rozměr kolmý na stěnu nepoužije (`options.d.hidden`) |
| `front`, `right`, `back`, `left` | chips | `wall` (stěna), `door` (dveře), `open` (bez stěny) | `door`, `wall`, `wall`, `wall` | dveře se na kratkou nebo nízkou stranu nevejdou → server nechá `wall` a oznámí; volba `door` je pak `disabled` s důvodem |
| `roof` | chips | `none`, `frame`, `fill` | `fill` | bez stěn a bez střechy by nezbylo nic → server dá `frame` |
| `fill` | select | `pc_clear` (polykarbonát čirý 4 mm), `pc_smoke` (kouřový 4 mm), `acrylic` (plexisklo 5 mm), `mesh` (svařovaná síť), `solid` (hliníkový kompozit 3 mm) | `pc_clear` | má `price_delta` (přesné přecenění) |
| `fill_front/right/back/left/roof` | select | `auto` + hodnoty `fill` | `auto` | jiná výplň na jedné straně nebo střeše (skryté, když tam není stěna / výplň střechy); ve stránce okno „Výplň po stranách“ (sbalené) |
| `door_w` | slider | 600–1200, krok 10 | 800 | všechny dveře stejné; horní mez dle nejkratší strany s dveřmi (vedle dveří pole ≥ 150 mm), `options.door_w.max` |
| `door_h` | slider | 1500–2400, krok 10, `null` = automaticky | `null` | `options.door_h {value, auto}`; nad dveřmi vždy nadpraží ≥ 150 mm |
| `door_pos` | chips | `left`, `center`, `right` (při pohledu na stranu zvenku) | `right` | |
| `door_hinge` | chips | `left`, `right` | `right` | dveře se otevírají ven, 3 závěsy |
| `lock` | chips | `latch` (kuličková západka), `lock` (bezpečnostní zámek), `none` | `latch` | |
| `feet` | toggle | ano / ne | ne | stavitelné patky M10; zvednou konstrukci o 79 mm, **celková výška zůstává** (sloupky kratší); s patkami min. výška 1079 mm (oznámení `h_feet`) |

Dveře, `door_*` a `lock` se skrývají (`options.<slot>.hidden`), pokud žádná strana nemá dveře.

## 3) Veřejné API (stejné routy jako u stolu a dopravníku, `api/stul_shop.py`)

* `GET  /api/shop/products/<id>/configurator?lang=cs|en|sk` → schéma `{rules_version, recipe: "oploceni_kryt", profile: "40x40", groups, slots, default_selection, systems: [], env: null, default_saved: false}`.
* `POST /api/shop/configurator/resolve` `{product_id, selection, lang, rules_version?, staff?}` →
  `{selection (EFEKTIVNÍ), hash, kod ("OPL-" + 6 znaků hashe), rules_version, valid, errors, notices, offers: [], price {net, vat_rate, gross, currency}, dims {width_mm, depth_mm|null, height_mm}, options, model {stav, url, odhad_ms}}`.
  Cena je **celkem z `price_entries` bez DPH, celé Kč, bez montáže** (montáž se u oplocení zatím nenabízí; `typ_produktu` → `None`). Chybí-li dílu cena, `valid: false` a `errors` – **nikdy „cena 0“**.
  `rules_version` jiné než server → HTTP 409 `rules_changed`. Hash = sha256 normalizovaných parametrů + `RULES_VERSION` (16 znaků; jedna kanonická podoba = jeden hash).
* `GET  /api/shop/configurator/model/<hash>` → nový podepsaný odkaz (jen pro hash, který tenhle proces viděl; jinak 404).
* `GET  /api/shop/configurator/glb/<token>` → GLB. Token `"opl." + tělo.exp.podpis` (HMAC z `app.secret_key`, platnost 15 min, tělo = jen čísla a krátké kódy). Odpověď komprimovaná podle `Accept-Encoding` (br / gzip, cache na hash),
  `Cache-Control: private, max-age=600`, `X-Robots-Tag: noindex`. Neplatný podpis 403, prošlý 410, příliš velká konfigurace 413 (`too_large`).
* **Jen zaměstnanci:** `GET /api/shop/configurator/recepty/oploceni_kryt` → `{recept, product_id, active}` (id karty s receptem; ne-zaměstnanec 403, žádná karta 404). Stránka podle něj najde kartu sama.
* `resolve` se `staff: true` + platnou staff session přidá blok `staff` (úplný kusovník s cenami, hmotnost, počet spojů, kód, rozměry, počet dílů); veřejnosti ho nikdy nevrátí.
* Limity požadavků na IP jsou **společné se stolem** (`LIMIT_RESOLVE` 120/60 s a 3000/h, `LIMIT_GLB` 60/60 s a 600/h, `LIMIT_SCHEMA`).

### Cena výplní, než existují karty

Výplně se do ceny počítají jako **virtuální desky** `navrh:<typ>` s orientační cenou za m² (`oploceni_konfigurator.VYPLNE`: PC čirý/kouřový, plexi, síť, kompozit) a těsnění z karet #3218 / #3199. Po `zaloz_karty_vyplni.py --apply`
vznikne `app_settings.oploceni_karty_vyplni` = `{typ: id karty}` a `oploceni_cena.cena` bere `product_<id>` z cenového kontextu (karta musí být deska `is_board_material` s GLB) – **bez změny kódu a API**
(cache ceny 60 s). Ceny karet pak upraví Robert v adminu.

## 4) Košík, objednávka, nabídka

* `oploceni_shop.pro_objednavku(selection, rules_version, lang, product_id)` – stejný tvar jako u stolu a dopravníku: `{ok, selection (efektivní), hash, kod, valid, errors, notices (texty), price, bom [{nazev, mnozstvi, rozmer}], pocet_spoju, souhrn [{id, label, value}], hmotnost_kg, hmotnost_uplna, hmotnost_chybi, cenovy_souhrn, rozmery_text}`.
  Kusovník je **neutrální** (bez čísel dílů a dodavatelů): profily 40×40 podle délky, výplně podle rozměru tabule, kusy, těsnění v metrech, spojovací materiál.
* Název řádku objednávky: `<karta> – <kód> – <rozměry text>` (např. „… – OPL-1A2B3C – 1500 × 1500 × 2200“), rozměry jen ty, které se uplatní (bez hloubky u oplocení).
* Košík přijme jen **aktivní** kartu (`active=1`, neprovedeno archivováno); neaktivní karta se nedá koupit. Generátor (schema / resolve / model / glb) ale pracuje i pro neaktivní kartu (jako u stolů 41 a 45).
* Online nabídka: `glb_bytes(selection, razitka=True)` = **plný detail bez obrázků** → `v3d_glb.sanitize` + `final_check` → `v3d_mark.mark` (razítka loga; sdílené meshe razítkovat nejdou, proto žádná instancing optimalizace).
  Zákaznický model nesmí obsahovat textury; síť má textu jen veřejný/zaměstnanecký model.

## 5) 3D model a velikost GLB

* Veřejný/zaměstnanecký model: patka a zámek jsou **zjednodušené** shlukováním vrcholů (patka tolerance 0,8 mm, zámek 1,6 mm), síť má texturu, přidají se kóty (`spec.dims`: šířka, hloubka jen když se uplatní, výška).
  Největší veřejná konfigurace ~4 MB (plný detail 7,7 MB; konfigurace 6000 × 6000 z jádra 21,7 MB se veřejnosti nenabízí). Komprese br/gzip jako u ostatních GLB.
* **Strop dílů modelu** `MAX_DILU_MODEL = 600`: větší konfigurace dostane v `resolve` `model {stav: "chyba", kod: "prilis_velky"}` (cena a košík fungují) a route `glb` 413.
* Dveře jsou v modelu zavřené (`otevrit_dvere=0`); otevřené jen pro náhledové obrázky.

## 6) Stránka Generátor 06 (zaměstnanci)

`/oploceni-konfigurator.html` – okna: 3D, cena, výroba (kód, počet spojů, odkaz na kartu), rozměry, strany a střecha, výplň + dveře + příslušenství, výplň po stranách (sbalené), kusovník s cenami (profily sbalené do řádku, rozbalí se na délky).
Struktura a modul jako u stránek stolů, ale **bez** „Do online nabídky“ a „Vzhled“ (v1). Hostitel `js/oploceni-host.js` je malý a je jen pro oplocení; **obecný hostitel `generator-host.js` se nevybral**, protože `stul-host.js` je
svázaný se stolem (systémy, luxy, panely, výchozí konfigurace) a obecný hostitel zatím neexistuje – až vznikne, jde host oplocení snadno převést (má ~330 řádků, sdílí jen `PdConfigurator`).
* Zaměstnanecký režim: `PdConfigurator.init` s `resolveExtra {staff: true}`; karta se najde přes `GET /api/shop/configurator/recepty/oploceni_kryt`.
* Veřejná varianta (zkouška, před zveřejněním): `?public=1&id=<id karty>` – bez `staff`, bez kusovníku a odkazu na kartu; `?lang=en|sk`.
* Odkaz na konfiguraci = `#w=2400&d=1800&front=wall&…` (veřejná ID slotů, `feet=1/0`); neplatný hash se ignoruje.
* Po každé úpravě JS/CSS stránky: `api/venv/bin/python3 scripts/2026-10-08_oploceni/oploceni_verze.py` (přepíše `?v=` v HTML a v assetech hostitele).

## 7) Karty (zápis do DB) – jen po nasazení kódu a pod zámkem

1. `scripts/2026-10-08_oploceni/zaloz_kartu_oploceni.py [--apply]` – neaktivní karta `OPLOCENI.KRYT.KONF` + záznam v `configurator_products` (compare-and-set, audit_log, ověření z nového spojení). Zveřejnění = aktivace Robertem (pravidlo 54).
2. `scripts/2026-10-08_oploceni/zaloz_karty_vyplni.py [--apply] [--kategorie <id>]` – 5 neaktivních karet desek (GLB 1000 × 1000 × tloušťka v `webapp/katalog/`, guardovaná složka → zámek) + `app_settings.oploceni_karty_vyplni`.
Obě mají nahled bez `--apply`; zapisují v jedné transakci a při chybě vrátí (vytvořené GLB smažou).

## 8) Testy

| test | co hlídá |
|---|---|
| `test_oploceni.py` | jádro (geometrie, spojky vs. šablona stolu, zanoření, kusovník, ceny, hash, GLB) – hermetický, bez DB |
| `test_oploceni_shop.py` | shop vrstva (schéma, `resolve`, úpravy a oznámení, ceny = jádro, `price_delta`, token, `pro_objednavku`, registr zpětně kompatibilní, veřejné meze, velikost GLB, nabídkový model) |
| `test_oploceni_stranka.js` + `_most_oploceni.py` | skutečná stránka v Chromiu nad skutečným kódem (zaměstnanec i veřejnost, ovládání, odkaz, mobil, nepřihlášený / bez práva / bez karty) |
| `mutace_oploceni.py`, `mutace_oploceni_shop.py` | každá mutace musí shodit příslušný test |
| `run_regrese.py` | existující testy (`test_registr`, `test_dopravnik_shop`, `test_stul_shop`, `test_kosik`, `test_nabidka*`, `test_stul_api`) nad kandidátem i živým stromem – výsledky musí být **shodné** |

## 9) Pasti

* **Routy jen v `stul_shop.py`** (viz 1); nová routa pro další recept = přidat tam, ne do modulu.
* **Stará jména registru nemazat**: `test_registr.py` bota 5 je připíná a podstrkuje falešný modul do `sys.modules["dopravnik_shop"]`.
* Sdílené meshe v GLB nejdou razítkovat (nabídka) – žádný instancing.
* Zákaznický model nesmí mít obrázky (síť je v něm průsvitná bez textury).
* `app.secret_key` se mění = prošlé tokeny modelu (15 min, stránka si vezme nový přes `resolve`).
* Změna `RULES_VERSION` (pravidla, geometrie, ceny dílů v jádře) mění všechny hashe; stará konfigurace v košíku dostane `rules_changed`.
