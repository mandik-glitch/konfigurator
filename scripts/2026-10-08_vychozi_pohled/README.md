# Výchozí úhel pohledu 3D v generátorech stolů (bot10, 2026-10-08)

Robert 2026-10-08: „chci nastavit výchozí úhel pohledu 3D v generátorech“.

**Co to dělá:** jedno nastavení pro VŠECHNY generátory stolů (30 / 35 / 40 / 41 / 45, karty z konfigurace, mini-shopy, vložený generátor): úhel pohledu „3D“ (otočení od čela modelu `az`, náklon nad vodorovnou `el`,
ve stupních). Vzdálenost kamery se neukládá, dopočte ji viewer tak, aby byl vidět celý stůl. Bez uloženého nastavení platí původních 35° / 25°. Ukládá jen admin (právo `nastaveni` / `upravit`) v okně „Výchozí konfigurace“
na stránce generátoru: natočí model, jak se má otevírat, a klikne na **Uložit aktuální pohled jako výchozí** (dvoukrokové potvrzení – platí pro všechny návštěvníky); **Vrátit původní pohled** nastavení smaže.

**Kde co je**
- `webapp/js/v3d/viewer3d.js` **1.17.0**: `opts.isoAngles {az, el}`, `v.setIsoAngles({az, el} | null, fly)`, `v.currentAngles()`, `state().isoAngles`, `V3D.normalizeIsoAngles` (meze `el` −15…85); bez volby beze změny (`docs/VIEWER3D_SETMODEL.md`).
- `api/stul_pohled.py` (nový; v `api/stul_shop.py` jen import + řádek `out["view"]` ve veřejném schématu konfigurátoru): `app_settings.configurator_view_default` = `{az, el}`, `PUT` / `DELETE /api/shop/configurator/view`
  (jen admin; hodnoty se kontrolují znovu, mimo meze = chyba, nic se potichu neořezává; zápis + `audit_log` v JEDNÉ transakci).
- `webapp/js/product-configurator.js`: předá `schema.view` viewer jako `isoAngles` (sdílený kód všech míst); `webapp/js/stul-host.js`: blok „Výchozí pohled 3D“ v okně „Výchozí konfigurace“ (živý popisek aktuálního úhlu),
  ukáže se až když schéma nese klíč `view` (starý backend = skrytý). Piny `?v=` stránek přes `scripts/stul_verze.py` a `scripts/miniweb_verze.py`.
- Kontrakt a pravidla: `docs/KONTRAKT_KONFIGURATOR_UI.md` (odstavec Výchozí úhel pohledu 3D).

**Nasazení:** statika je živá po commitu; blok v okně a samotné ukládání se objeví po nasazení API (plánovaně 0:00 / 12:30, nebo Robertovo „nasadit hned“: `scripts/restart_konfigurator.sh --stav` a `--reload`).
Scéna (`scene.html`) a online nabídky mají vlastní výchozí pohled (beze změny).

**Testy**
- `test_pohled_api.py` (DB přes `systemd-run`, viz hlavička; zápisy do TEMPORARY tabulek, živé tabulky se kontrolují před a po; kandidát `POHLED_DIR=<kořen překryvu s api/>`): meze, RBAC, uložení / smazání, audit v téže transakci,
  poškozená uložená hodnota, schéma.
- `test_pohled_stranka.js` (skutečný viewer, stránka Generátor stolu a modul voleb přes most `scripts/2026-10-02_stul_testy/_most_stul.py`; uložení a mazání se v testu SIMULUJE přes `page.route`, nic se nezapisuje):
  A viewer API | B modul použije `schema.view` při mountu | C okno Výchozí konfigurace: blok (sonda, uložení, vrácení, chyby, živé hodnoty) | D statické kontroly (verze, piny). `ONLY=A,C`; snímky `SHOT=/cesta/predpona`.
  Dvoukroková tlačítka (potvrzení do 6 s) se v testu mačkají `force`, aby je pod zátěží VPS (SwiftShader) nezpomalilo čekání na ustálenou animaci.
- Regrese viewer3d.js 1.17.0 (kontrolní scéna, nabídka, vzhled): `scripts/2026-10-06_v3d_vzhled_testy`, `2026-10-07_v3d_aomat_testy`, `2026-10-07_v3d_lesk_testy`, `2026-10-06_v3d_rady_testy`, `2026-10-02_v3d_testy`, `vandr_system/test_kontrola_komponenta.js`.

**Nehoda při vývoji testu:** první verze zapsala do ŽIVÉHO `audit_log` 6 zkušebních řádků (`entity_type='configurator_view'`, id 6878–6883, 2026-10-08 09:15:21, user_id 1) – `log_audit()` jde jiným spojením než dočasné tabulky.
Opraveno (audit se píše uvnitř téže transakce, test ho zachytává v dočasné tabulce); řádky v logu zůstaly (smazání jsem nemohl provést) – nepatří k žádné skutečné změně, smí je smazat Robert.
