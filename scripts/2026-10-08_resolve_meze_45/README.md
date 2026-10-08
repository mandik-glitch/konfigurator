# Meze posuvníků v `options` odpovědi resolve() podle systému (bot10, 2026-10-08)

Nález bot16: v embedu / na kartě / v mini-shopu nešla u systému 45 („Robustní“) nastavit hloubka nad 1500 mm. `POST /api/shop/configurator/resolve` pro kartu #5353 vracel `options.d = {min: 400, max: 1500}` (globální `S.ROZSAH`),
zatímco schéma karty (`GET /api/shop/products/5353/configurator`) má `slider.max = 2500`; klient se řídí `options`, takže hodnotu oříznul a nápověda ukazovala „Povoleno od 400 do 1500 mm“. Server hloubku 2000–2500 přijímal (jen strop v `options`).

**Oprava:** `api/stul_shop.py` `_spocti()`: `lo, hi = S._rozsahy(p["system"])[par]` (meze podle systému; ostatní místa už `_rozsahy(system)` používala – `normalizuj`, schéma, výřezy).

**Test** `test_resolve_meze_45.py` (14 kontrol; před opravou 3 padaly přesně na systému 45): funkce `resolve()` pro systémy 30 / 35 / 40 / 45 a SKUTEČNÁ trasa `POST /api/shop/configurator/resolve` pro karty #5353 (45), #4954 (40), #4934 (30);
`options.d` = meze posuvníku ve schématu karty; w / h / ov beze změny. Spuštění viz hlavička (DB přes `systemd-run`, jen čtení).
