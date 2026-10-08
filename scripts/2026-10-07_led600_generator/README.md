# LED 600 v generátorech stolu (bot8, 2026-10-07)

Robert: „LED 600 doplnit do generátoru“ (po „přidal jsem nové LED 600, do karty, udělej mu 3D model zkrácením LED 1200“ – model hotový a commitnutý: `scripts/2026-10-07_led600/`, `webapp/katalog/product_5359.glb`, commit 79110369).
Vzor: délky perforovaného panelu (commit b612347e) – parametr + slot + veřejná nabídka podle aktivní karty + 3D menu + token + testy.

## Co je navržené (a proč)
* **Parametr generátoru `led_delka` (1200 | 600, výchozí 1200)**, všechna svítidla stolu stejně dlouhá, řadí se vedle sebe (rozteč = délka tělesa z GLB: 1247 / 647 mm), počet `max(1, floor((šířka + 47) / těleso))`, skupina vycentrovaná jako dosud (šablonový člen LED se klonuje se stejnou polohou a otočením, jen s dílem `product_5359` – model má stejný střed bboxu jako `product_4929`). **Výchozí 1200 = všechno stávající BITOVĚ stejné** (hash, díly, problémy, odebrané přepínače: zlatý otisk 465 konfigurací = 0 rozdílů; klíč se do hashe/tokenu/odkazu promítne jen u 600 a jen když je svítidlo na stole).
* **Nevejde-li se zvolená délka, LED se odebere jako dosud** (1200 od šířky 1200, 600 od šířky 600); délka se NEsnižuje sama (to by změnilo chování stolů užších než 1200 mm bez volby). Místo toho veřejné API u zakázaného přepínače LED nabídne **„Zapnout kratší LED 600 mm“** (`options.led.on.suggest = {ledlen: "600"}`; modul voleb to umí beze změny kódu).
* **Veřejné API:** slot `ledlen` (select 600 | 1200 mm za `ledlight`, `depends_on [posts, led, ledlight]`), `options.ledlen` (nevejde se = zakázáno s důvodem a nejmenší šířkou, v nabídce jen 1200 = `hidden`), token `K`, shrnutí voleb jen u 600, cache `resolve` nese délku a nabízené délky. **Veřejnost dostane 600 jen s AKTIVNÍ kartou #5359** (neaktivní/archivovaná/bez GLB/mimo scénu = jen 1200; zaměstnanec vidí obě) – jako u panelů, pravidlo 54.
* **3D menu** „Zvolit LED N mm“ (nevejde se = zakázáno s důvodem), EN/SK překlady; svítidla jedou s ramenem při živém tažení.
* **Počítadlo luxů:** server posílá `typ led_600` (svítící čára 600 mm vystředěná v tělese 647 mm); klient (**statický JS, zapisuje se živě**): `TYP_SKU`, záznam `LED600` v `lux-data.js` (**jen výkon 16 W a tok 1 920 lm z karty, ostatní neznámé = `null`, optika = HYPOTÉZA jako u LED1200 → výsledky „Orientační odhad“**), tlačítka stupňů výkonu se řídí typem svítidla (LED 1200: 33 W / 21 W; LED 600: jediný stupeň, volba se schová; při změně typu se tlačítka postaví znovu a nepodporovaný stupeň se vrátí na výchozí).

## Soubory (pathspec pro commity)
**API + testy + docs (jeden commit, zámek):**
`api/stul_konfigurator.py`, `api/stul_glb.py`, `api/stul_sse.py`, `api/stul_osvetleni.py`, `api/stul_shop.py`, `api/stul_ovladani_verejne.py`, `scripts/2026-10-02_stul_testy/test_stul_shop.py` (jen nový select `ledlen`), `docs/KONTRAKT_KONFIGURATOR_UI.md`, `MAPA_3D_A_GENERATORU.md`, `scripts/2026-10-07_led600_generator/` (celá složka, vč. `golden_head.json`).
**Statické JS (samostatný commit; zapisuje se ŽIVĚ → dřív než API reload, je zpětně kompatibilní):** `webapp/js/stul-luxy.js`, `webapp/js/lux/lux-data.js` + piny `?v=` (`apply_js.sh` spustí `scripts/stul_verze.py` a `scripts/miniweb_verze.py`: stránky generátorů 01–05, `webapp/embed/stul.html`, případně miniweb) – **pozor: piny v `webapp/stul-konfigurator*.html` / `stul-host.js` může zrovna měnit bot10 (zámek)**.

## Nasazení (pořadí)
1. Zámek bot8. `scripts/2026-10-07_led600_generator/apply.sh` (API + test + docs atomicky přes dočasný adresář) → `py_compile`, testy (viz níže) → commit.
2. `scripts/2026-10-07_led600_generator/apply_js.sh` (statika živě + piny) → commit (nejlépe PŘED reloadem API, aby nový `typ led_600` našel klient připravený; starý klient s novým serverem u LED 600 jen tiše nezapne lux).
3. API: plánovaný reload 0:00 / 12:30, nebo na Robertův pokyn (`scripts/restart_konfigurator.sh --reload`). Hned po reloadu se **veřejnosti** objeví volba „Délka LED svítidla“ (karta #5359 je aktivní; vypnout ji může jen Robert – pravidlo 54).
4. Po nasazení: `api/venv/bin/python3 scripts/miniweb_jazyk_zdroj.py --lang de` / `--lang hu` (nové řetězce `ledlen*`, `LEDLEN_NEVEJDE`, `LED_NENI_V_NABIDCE`, `led_kratsi`, položky 3D menu pro bot7; do té doby anglická záloha + varování v logu).
Zaplaty jsou kotvené malé hunky (assert `count == 1`), slučitelné s `scripts/2026-10-07_police_bez_desky/` v OBOU pořadích (ověřeno na dvou čistých kopiích: výsledné API soubory byte-shodné; liší se jen pořadí dvou sekcí v `KONTRAKT_KONFIGURATOR_UI.md`).

## Testy (příkazy z kořene repa; kandidát = `STUL_API_OVERRIDE=<api>`, DB testy přes `systemd-run`, viz hlavičky souborů; výsledky nad kandidátem 2026-10-08: generátor 3 288, živé tažení 21, veřejné API 163, lux 10, regrese 4 853, Chromium 20, mutace 60/60, zlatý otisk 465/465)
* `test_led_delka.py` – generátor, GLB, lux data (bez DB): model v katalogu, konstanty a vstup, **zlatý otisk 465 konfigurací** (`golden_head.json` = stav PŘED změnou, `golden_head.py` ho znovu vyrobí nad starým kódem), geometrie nezávisle z vrcholů meshe (počet, rozteč, vystředění, přesah ≤ 48, žádné zanoření; 4 systémy × 24 šířek × 3 ramena), hash, `led_info.typy` proti skutečnému chování, 3D menu, GLB (materiál led, délka), payload luxu, degradace při chybějícím GLB, SSE, krajní šířky 500 / 3000.
* `test_led_delka_zive.py` – živé tažení ramene LED se svítidly 600 (nezávisle proti modelu ze serveru ≤ 0,05 mm).
* `test_led_delka_shop.py` – veřejné API (DB jen čte; cena = cena karty × počet, kusovník, zakázané délky, nabídka kratšího svítidla, gating karty, token, shrnutí, cache, 3D menu cs/en/sk, lux payload, staff API).
* `test_led_delka_stranka.js` – stránka Generátor stolu v Chromiu + počítadlo luxů (HUD = nezávislý výpočet LuxCore, stupně podle typu, mobil); spouští se z kandidátního kořene `prepare_cand_web.sh` přes most `_most_stul.py` (viz hlavička).
* `mutace.py` – 60 mutací (`MUT_ZDROJ_API=<api s nasazenými záplatami>`, rychlý režim `TEST_STOP_PRVNI=1`), každá musí shodit příslušný test.
* `test_led_delka_lux.py` – katalog LED600 + LuxCore v Node (po nasazení JS; před ním z kandidátního kořene), `test_regrese_bez_led.py` – `test_s45_regrese.py` proti revizi v gitu s odfiltrovaným přírůstkem LED (4 853 / 4 853 = nic jiného se nezměnilo).
* Existující sady (27 sad nad kandidátem): vše beze změny kromě `test_stul_shop.py` (nový select `ledlen`; záplata `patches_test/`). `scripts/2026-10-07_system45/test_s45_regrese.py` porovnává odpověď s revizí v gitu a nová pole (`led_delka` v `parametry`, `led_info`, položky 3D menu) hlásí jako rozdíl (376 z 4 853) – po commitu (HEAD už je nese) projde; že jiný rozdíl není, dokazuje `test_regrese_bez_led.py`.

## Otevřené body pro Roberta
1. Karta #5359 je aktivní → veřejnost uvidí „Délka LED svítidla“ hned po reloadu API (a po nasazení JS i počítadlo luxů s LED 600).
2. Počítadlo luxů: LED 600 má jen výkon a tok z karty; optika (120°, kosinová) je předpoklad. Potřebuje štítek / datový list LED 600 (výrobce, model, úhel, ev. druhý výkonový stupeň).
3. Na stolech užších než 1200 mm se LED bez volby dál odebere (beze změny); místo toho se nabízí „Zapnout kratší LED 600 mm“. Chce Robert, aby se na úzkém stole 600 zvolila sama? A směs 1200 + 600 na jednom stole (dnes všechna svítidla stejně dlouhá)?
