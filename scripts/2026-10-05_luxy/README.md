# Počítadlo luxů ve 3D náhledu generátoru stolu (bot10, 2026-10-05)

Zadání (Robert, po náhledu v2 od Johna): „potom hned zakomponuj to počítadlo luxů do generátoru“. John (OpenAI bot, `vystupy/pocitadlo_luxu_v2`) dodal výpočet (`lux-core.js`), katalog svítidla a norem (`lux-data.js`), plugin pro `V3D.mount` (`lux-plugin.js`, `lux.css`) a datový kontrakt (`INTEGRACE.md`): **geometrie pracovní plochy a LED musí pocházet z téhož modelu a stejného posunu skladače jako zobrazený GLB**.

## Co je kde
- `api/stul_osvetleni.py` + volání ve `stul_glb.vodici` → `resolve.vodici.osvetleni` (pracovní rovina, výřezy, LED – měřeno ze skutečných vrcholů, posunuto stejně jako model). Kontrakt: `docs/KONTRAKT_KONFIGURATOR_UI.md` („Počítadlo luxů“).
- `webapp/js/stul-luxy.js` – tlačítko, stupeň 33 W / 21 W, životní cyklus pluginu (spuštění až po `onModel`, vypnutí při tažení); `webapp/js/lux/*`, `webapp/css/lux.css` = Johnovy soubory (viz odchylky v kontraktu).
- `webapp/js/product-configurator.js` – nové háčky `page.viewerPlugins()`, `page.onModel(url, hash)`, `page.onDrag(on)`; hostitelé `webapp/js/stul-host.js`, `webapp/embed/stul-embed.js`; skript `stul-luxy.js` je ve třech stránkách generátoru a v `embed/stul.html`. Piny `?v=`: `scripts/stul_verze.py` a `scripts/miniweb_verze.py` (piny souborů počítadla jsou uvnitř `stul-luxy.js`).

## Testy
- `test_osvetleni.py` (bez DB): payload proti skutečným vrcholům GLB (obálka LED, plocha desky, výřezy = díry v horní ploše), `LuxCore` v node pro oba stupně, **Johnova reference** (jeho zdrojové parametry 1200 × 800: průměr 852 lx, minimum 517 lx, U₀ 0,606).
- `test_luxy_host.js` (přes `_most_stul.py`, viz hlavička): prohlížeč – lazy načtení, cifry v HUD = nezávislý výpočet nad payloadem ze serveru po každé změně, stupně, hover panel, změna rozměru, živé tažení a Esc, vypnutí LED, kompaktní zobrazení na nízkém plátně, embed, mobil.
- Zařazeno do `scripts/2026-10-02_stul_testy/run_all.sh` (kroky 36–37).

## Panel v3 (John, 2026-10-06; převzal bot10 po Robertově schválení)
`lux-plugin.js` / `lux-data.js` (blok `clearPanelTexts`) / `lux.css` nahrazeny verzí v3 (slovní verdikt „Lze / Nelze“, dvě skupiny 13 činností s důvody, tlačítko „přehled“ v souhrnu); `lux-core.js` beze změny, prahy a normy totožné s v2. Piny `?v=` přepsaly `scripts/stul_verze.py` + `miniweb_verze.py`.
**Past:** Johnův `lux.css` vrací globální `[hidden]{display:none!important}` – v živé verzi musí zůstat `.lux-overlay [hidden]` (viz Pasti níže); při příští výměně `lux.css` zkontrolovat řádek 12. Test: `test_luxy_host.js` (31 kontrol, kandidátní překryv webapp se SKUTEČNÝMI kopiemi přepisovaných souborů – symlink by zapisoval do živého).
**Dotyk (mobil), nález z ostré domény 2026-10-06:** tlačítko „Činnosti při tomto osvětlení“ v souhrnu nešlo klepnout – na dotyku je 3D po načtení zamčené (`.pdc-lock`, z-index 4) a přes souhrn leží úchyty ovládání (`.pdc-ov` > `.v3do-h`, z-index 5/6), takže klepnutí trefilo zámek nebo úchyt. Oprava: `.pdc-stage .lux-overlay{z-index:7}` v CSS uvnitř `stul-luxy.js` (overlay má `pointer-events:none`, interaktivní je jen tlačítko a panel).
Test: `test_luxy_touch.js` (15 kontrol: 320 / 360 / 390 s dotykem – v pěti bodech tlačítka nahoře samo tlačítko, klepnutí otevře panel s verdiktem, × zavře; před opravou 6 selhání). Spuštění je v hlavičce testu (přes `_most_stul.py`).

## Co je hypotéza (od Johna, neměnit bez podkladů)
Svítící čára 1200 mm vystředená u spodní plochy tělesa 1247 mm, kosinová charakteristika (n = 1) z úhlu 120°, bez denního světla a odrazů, počáteční stav (údržba neurčena). Výsledek je orientační a UI nedává povolení práce; porovnání s normami a činnostmi je Johnovo orientační mapování.

## Pasti
- Nerozdělená pracovní deska je katalogový díl se sraženými hranami: obálka (workplane) je o ~1,6 / 2,6 mm větší než plochá horní plocha – pro výpočet (síť 100 mm) bez významu, test s tím počítá.
- `lux.css` má v originále globální `[hidden]{display:none!important}` – zúženo na `.lux-overlay [hidden]`, jinak by přebilo `hidden` na celé stránce generátoru.
- Při výměně modelu viewer plugin ukončí a znovu zavolá; payload se proto přiřazuje podle hashe konfigurace (`onModel(url, hash)`), ne podle „posledního resolve“.
