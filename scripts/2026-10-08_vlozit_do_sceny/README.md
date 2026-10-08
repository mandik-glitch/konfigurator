# „Vložit do Scény“ – protokol v2 (bot10, 2026-10-08)

Robert 2026-10-08: „klikl jsem na vložit do scény, nic se nevložilo, a napsala se divná věta“. Příčina z nginx logu: víc karet Scény v prohlížeči, původní protokol poslal stůl DO VŠECH a první odpověď do 1,5 s vyhlásil za úspěch bez informace, kam
se stůl vložil (nově otevřená Scéna byla prázdná). Řešení a popis protokolu: `docs/KONTRAKT_KONFIGURATOR_UI.md` (sekce „Vložit do Scény – protokol v2“), kód `webapp/js/stul-do-sceny.js` + `webapp/js/scene/stul-konfigurator.js`.

**v3 (Robert téhož dne: „nemusím mít otevřenou scénu, prostě se otevře scéna s tím modelem“):** tlačítko VŽDY otevře novou kartu `/scene.html?stul=<dotaz>`; protokol v2 (ping / pong, vložení do JEDNÉ otevřené Scény) je jen malý odkaz pod hlášením. Test: sekce A = tlačítko (nová karta, stará Scéna nedotčená, blokátor oken, SSE bez odkazu), sekce 1–7 = odkaz „vložit do už otevřené Scény“.

**Test** `test_vlozit_do_sceny.js` (skutečná Scéna i skutečný generátor `stul-konfigurator.html` v Chromiu přes most `scripts/2026-10-06_nabidka_vykresy_testy/_most_scena.py`, příkaz v hlavičce souboru; ~3–6 minut,
Scény se pod zátěží VPS načítají 10–20 s): piny; žádná Scéna; jedna viditelná (vložení > 1,5 s se nehlásí jako „není otevřená“) a výměna; dvě karty (stůl jen do viditelné, skrytá nedotčená); jen skrytá karta („jiná karta“ + ● v názvu, zmizí po zobrazení);
původní protokol (Scéna ze starší verze stránky, i pozdní odpověď opraví hlášení); Scéna odpoví chybou / pomalu; skutečná chyba API; prohlížeč bez BroadcastChannel; bez chyb v konzoli. Viditelnost karty se v headless Chromiu nedělí, řídí ji `window.__vis`.
