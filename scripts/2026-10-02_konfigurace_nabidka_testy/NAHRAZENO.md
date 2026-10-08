# NAHRAZENO (bot5, 2026-10-06)

Tahle sada z 2. 10. (modul `konfigurace_nabidka.py`, `POST /api/admin/scene-offers/z-konfigurace`, sloupce `scene_offers.source` + `config_json` = DDL) se NENASAZUJE.
Nabídku z konfigurace stolu dělá nový modul **`api/nabidka_z_konfigurace.py`** (`POST /api/admin/konfigurace/nabidka`, snímek v `scene_offers.offer_options`, BEZ DDL), commity 9c422069 a b8549968,
kontrakt `docs/KONTRAKT_NABIDKA_Z_KONFIGURACE.md`, testy `scripts/2026-10-06_nabidka_z_konfigurace_testy/`.
Z téhle sady se převzala jen stránka nabídky (větev `offer.source === "configurator"`, V3D, souhrn voleb; JS test `test_nabidka_konfigurace_stranka.js`) a nápady (Toptrans 409 při neúplné hmotnosti, snímek na řádek objednávky).
