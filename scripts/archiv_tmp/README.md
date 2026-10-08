# archiv_tmp — pět souborů se skutečným minulým použitím

Zbytek po úklidu mrtvého kódu 2026-09-11 (Robert/bot3: mazat, ne
odkládat — viz `AGENTS_LOG.md`, "Rozhodnutí: MAZAT, ne přesouvat do
archivu"). Tenhle adresář už NENÍ odkladiště pro nové jednorázové
skripty — nic sem nepřidávat.

Zůstává tu jen pět souborů, protože mají v `AGENTS_LOG.md` odkaz, který
je SKUTEČNÉ použití (ne jen zápis o třídění):

- `tmp_2026-09-01_bot16_configs.js`, `tmp_2026-09-01_bot16_driver.js`,
  `tmp_2026-09-01_bot16_render_all_2d.js`,
  `tmp_2026-09-01_bot16_insert_all.py` — popsány jako "Reusable
  pipeline" s funkčním určením každého (viz `AGENTS_LOG.md` řádek
  ~16314).
- `tmp_2026-09-01_bot16_rack_caddy_VW31.json` — data, kterými se
  skutečně dělal diff odhalující reálný bug (+1651,5mm offset u
  Caddy/Transit Connect PHEV, viz `AGENTS_LOG.md` řádek ~16428).

Relativní `require("./...")` mezi nimi nemusí fungovat, pokud
odkazovaly na soubory smazané v tomtéž úklidu.
