# Karta z konfigurace generátoru stolu – testy a nástroje (bot10, 2026-10-07)

Funkce: tlačítko „Vytvořit kartu“ v generátorech stolů 01–05 založí z aktuální konfigurace AKTIVNÍ kartu `STUL-S<systém>-<hash8>` (Robert 2026-10-07). Kontrakt, rozhodnutí, endpoint, pasti: `docs/KONTRAKT_KARTA_Z_KONFIGURACE.md`.
Kód: `api/stul_karta.py`, `webapp/js/stul-karta.js` (+ mount v `webapp/js/stul-host.js`), `scripts/stul_karta_glb.py` (CLI pro automat otoček bot4).

Všechny testy se dají pustit nad kandidátem před nasazením (`KARTA_DIR=<adresář s kandidátním stul_karta.py / products.py>`, má přednost před živými moduly). DB přes systemd:
`systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-07_stul_karta/<test>.py`

| soubor | co hlídá |
|---|---|
| `test_karta_db.py` [`--rychle`] | jádro (`plan()` / `vytvor()`) nad DOČASNÝMI tabulkami (`_docasne.py`): SKU = kontrakt bot4, hash8 nezávisle, texty, kategorie, chyby, vznik karty + registr + výchozí výběr + záznam + audit, idempotence a souběh, neaktivní bez práva, rollback a úklid GLB, skutečné modely všech 5 systémů (bajty = veřejný generátor, `front` v GLB) |
| `test_karta_route.py` | endpoint přes Flask test client (vč. načtení uložených pravidel před trasou karty a nabídky, 1.5): RBAC (anonym 401, zákazník 403), náhled bez zápisu, vznik, idempotence, chyby, limit, neaktivní bez práva, veřejný detail produktu vrací `glb_file: null`, schéma nové karty se otevírá s uloženou konfigurací |
| `test_karta_cli.py` | CLI `stul_karta_glb.py`: uložený GLB karty = model S razítky (`--razitka`), bez přepínače model bez razítek, načítání uložených pravidel stolu (sekce 1b: práh šířky střední nohy), kódy 2 / 3 / 4, atomický zápis |
| `test_karta_tlacitko.js` | prohlížeč přes most `scripts/2026-10-02_stul_testy/_most_stul.py` (endpoint simulovaný `page.route`): sonda, dialog, požadavky, chyby serveru, XSS, klávesnice, všech 5 systémů, statika / piny. Hlavička souboru má příkaz; `SHOT=<předpona>` uloží snímek dialogu |

Zápisy testů jdou VÝHRADNĚ do TEMPORARY tabulek (`shop_products`, `app_settings`, `audit_log`, `content_categories`) a do dočasného adresáře; ostré tabulky a `webapp/katalog/stul/` se kontrolují před a po. Úspěšná cesta proti ostré DB
se netestuje (zakládá skutečnou kartu). Past: MySQL nepustí dočasnou tabulku do dotazu, který ji čte dvakrát (1137) – `content_categories` se před kontrolou detailu produktu zahazuje.
