# Online nabídka: montáž zatržením + ruční položky (bot8, 2026-10-06)

Kontrakt ručních položek: `docs/KONTRAKT_NABIDKA_RUCNI_POLOZKY.md`. Nic z toho nezapisuje do ostrých dat (falešný server `page.route`, dočasné tabulky, dočasná složka obrázků).

| soubor | co hlídá | očekávání |
|---|---|---|
| `test_montaz.js` (+ `harness.js`) | stránka: montáž jako zatržítko u každé nabídky, místo, součet, QR | viz výpis |
| `test_montaz_backend.py` | AST: `_offer_montaz_net`, `_montaz_poznamka`, přijetí nabídky | |
| `test_rucni_polozky_db.py` | skutečné endpointy (Flask test client) nad dočasnými tabulkami: PUT, nahrání obrázku, veřejný obrázek a model | 79/79 |
| `test_rucni_polozky_objednavka.py` | přijetí nabídky → řádky objednávky (dočasné tabulky objednávek) | 7/7 |
| `test_rucni_polozky_stranka.js` | zákaznická stránka v Chromiu (V3D zastaven; `CDN=1 SNIMKY=/cesta` = skutečný 3D prohlížeč + snímek) | 19/19 (+ 1 s CDN) |
| `test_rucni_polozky_admin.js` | skutečný `admin.html` + `crm-nabidky.js`: editor, hledání, obrázky, PUT | 59/59 |
| `mutace_rucni_polozky.py` | 28 umělých chyb backendu, každá musí shodit `test_rucni_polozky_db.py` | „VŠECHNY CHYCENY“ |
| `mutace_rucni_polozky_ui.py` | 37 umělých chyb v adminu a na stránce, každá musí shodit příslušný test | „VŠECHNY CHYCENY“ |

DB testy: `systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator api/venv/bin/python3 <test>.py`
(kandidát před nasazením: `SCENE_OFFERS_PY=/cesta/scene_offers.py`). Prohlížečové: `node <test>.js` (kandidát: `NABIDKA_HTML=…`, `ADMIN_HTML=…`, `CRM_NABIDKY_JS=…`).
