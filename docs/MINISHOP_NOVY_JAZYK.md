# Mini-shop: jak přidat další jazykovou verzi (domény, nginx, spuštění)

Robert 2026-10-02: „ve všech EU jazycích každá svou doménu, .top“; 2026-10-07: dokončit EN 1:1 se SK + kopie v němčině a maďarštině.
Kód je jazykově obecný (API bere jakýkoli jazyk, cesty URL jsou v `PATHS`, texty v souborech) – nový jazyk = **data + infrastruktura**, ne programování.
Texty serverové části konfigurátoru (štítky voleb, hlášky) = postup v `docs/jazyky/README.md`.

## Kdo co dělá
| Krok | Kdo |
|---|---|
| Návrh domény (.top), kontrola dostupnosti, název shopu, SEO šablony, všechny zákaznické texty (`i18n/<jazyk>.json`, katalog, dokumenty, serverové texty) | **bot7** |
| Registrace domény (OpenProvider) | **Robert** |
| Cesty URL jazyka (`PATHS` v `api/miniweb_seo.py`), Cloudflare zóna + NS + certifikát, nginx vhost, testy, kontrola úplnosti | **bot16** |
| Řádek shopu v DB, import katalogu a dokumentů (drafty), zapnutí objednávek | **bot5** |
| Schválení textů (`/miniweb-schvaleni.html`) a root příkazy | **Robert** (koordinuje bot9) |

## Postup (pořadí)
1. **Jazyk a země**: kód ISO 639-1 (`de`, `hu`), země dodání (DE → `DE,AT`; HU → `HU`; EN → `CZ,SK,DE,AT,PL`), měna EUR, B2B (jen firmám, ceny bez DPH).
2. **Texty (bot7)**: `webapp/miniweb/i18n/<jazyk>.json` (stejné klíče jako `sk.json` včetně `.multi`/`.multi3`, stejné `{placeholdery}`), sekce `<jazyk>` v `api/miniweb_seo_sablony.json` (celá struktura jako `sk`: host, brand, locale, lang, home … order_done), katalog a dokumenty jako import JSON (`docs/miniweb_*_<jazyk>_*.json`, `url_slug` ASCII), serverová sada `api/jazyky/<jazyk>.json` (postup a nástroje `docs/jazyky/README.md`; commit sady spustí plánované nasazení), případně `webapp/pripni-cokoli/texty.json` (jazyk do `_aktivni` až po ověření; do té doby tile mluví anglicky).
3. **Cesty URL**: `PATHS["<jazyk>"]` v `api/miniweb_seo.py` (6 cest, ASCII bez diakritiky; nginx vhost je bere odtud, test `scripts/2026-10-07_miniweb_jazyky_testy/test_cesty_jazyky.py`). Hotové pro `sk en cs de hu`.
4. **Shop (bot5)**: `scripts/miniweb_shop.py --slug packstations-<jazyk> --host <doména> --lang <jazyk> --family packstations --currency EUR --locale <jazyk>-<ZEMĚ> --countries <ZEMĚ,…> --accent "#2dd4bf" --contact-from-company on --apply` (storefront vzniká jako `draft`, vidí ho jen staff).
5. **Import (bot5) a schválení (Robert)**: `scripts/miniweb_import.py <soubor>.json --apply` (jen drafty) → klik na `/miniweb-schvaleni.html`.
6. **Doména (bot16)**, každý příkaz nejdřív bez `--apply` (náhled):
   ```
   R="systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 scripts/miniweb_domena.py"
   $R plan <doména>
   $R zona <doména> --apply        # Cloudflare zóna + A záznamy (proxied)
   $R ns <doména> --apply          # nameservery u OpenProvidera na Cloudflare (+ vypne DNSSEC, jinak SERVFAIL)
   $R aktivace <doména>            # čekat na "active" (minuty až hodiny)
   $R cert <doména> --apply        # SDÍLENÝ Origin CA certifikát se přegeneruje jako kombinovaný (všechny domény + nová, stejný klíč) + AOP leaf do zóny
   ```
   Do aktivace zóny a do instalace vhostu vrací server pro novou doménu `401` (výchozí vhost) – nic se neukáže.
7. **Nginx (Robert, root, jediný příkaz)**: `cd /opt/konfigurator && bash scripts/miniweb_nginx_install.sh <doména> --index <jazyk>` (zkopíruje kombinovaný certifikát pro všechny vhosty, `nginx -t` s rollbackem, reload). Potom `$R overit <doména> --origin`.
8. **Objednávky (bot5)**: `--orders on` až po schválení dokumentů „Operator and orders“ + ochrana údajů v daném jazyce.
9. **Spuštění**: `scripts/miniweb_shop.py --slug packstations-<jazyk> --go-live` (náhled) → `--apply`. Vedle původních podmínek vypisuje a vyžaduje řádky `jazyk ANO/NE`: překlady frontendu úplné, SEO šablony úplné, cesty URL, serverová jazyková sada. Vrácení: `--take-offline --apply`.
10. **Po spuštění**: hreflang odkazy mezi všemi živými shopy rodiny se doplní samy (`alternates`); při změně JS/CSS mini-shopu vždy `api/venv/bin/python3 scripts/miniweb_verze.py` (Cloudflare drží statiku 4 h).

## Kontroly
- `node scripts/2026-10-07_miniweb_jazyky_testy/test_jazyk_stranky.js` – jazyková úplnost frontendu (klíče jako `sk`, placeholdery, abeceda jazyka, žádné holé klíče, HUD 3D, názvy zemí). `JAZYKY=de,hu` pro vybrané.
- `python3 scripts/2026-10-07_miniweb_jazyky_testy/test_cesty_jazyky.py` – `PATHS` a vhost pro každý jazyk s překladovým souborem.
- `systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-07_miniweb_jazyky_testy/test_seo_jazyky.py` – server-side SEO pro `en,de,hu` (`JAZYKY=…`): adresy jazyka, canonical, hreflang, 301 ze starého slugu, sitemap, robots, 404 pro cizí cesty; chybějící soubory jazyka nahradí syntetickými, takže kód ověří dřív než přijdou texty.
- `python3 scripts/2026-10-07_miniweb_jazyky_testy/test_podminky_jazyka.py` – podmínky úplnosti při `--go-live`.
- `scripts/miniweb_jazyk_parita.py --lang <jazyk>` (jazykové sady, i18n, SEO šablony, DB) – viz `docs/jazyky/README.md`.
- `node scripts/2026-10-07_miniweb_jazyky_testy/test_dlazdice_jazyk.js` – jazyk dlaždice „Připni cokoli“ se bere z `_aktivni` v `webapp/pripni-cokoli/texty.json` (skutečný `pdc-layout.js`, 38 kontrol); nový jazyk dlaždice = jen přidat jazyk do `_aktivni` po ověření textů (bot7), kód se nemění.
- `api/venv/bin/python3 scripts/2026-10-07_miniweb_jazyky_testy/test_nasazeni_jazyky.py` – plánované nasazení (0:00 / 12:30) a panel Nasazení serveru sledují i `api/jazyky/*.json` (commit samotné sady jazyka nasazení spustí).

## Pasti
- Chybějící `i18n/<jazyk>.json`, šablony SEO nebo `PATHS` se **mlčky nahradí angličtinou** (`MW` načte `en.json`, SEO bere šablony `en`, cesty `/category/`) – proto kontrola úplnosti v `--go-live`.
- Název země bez překladového klíče (`country.<ISO>`) bere stránka z prohlížeče (`Intl.DisplayNames`) v jazyce shopu; existující klíče mají přednost.
- Dlouhá slova (německé složeniny, maďarština): CSS má zalamování `overflow-wrap` + `hyphens` jen pro `:lang(de)` a `:lang(hu)` (nadpisy, tlačítka, karty); po dodání skutečných překladů znovu zátěžový pohled na 390/768/1280 px (pseudo-německý test přetečení stránek už prošel).
- Sdílený Origin CA certifikát je jeden soubor pro všechny domény: nová doména ho přegeneruje (`cert --apply`) a root instalátor ho rozešle do nginx; starý zůstává jako `miniweb-origin-ca.pem.bak-<datum>`.
- Doprava: odhad Toptrans (košík) počítá jen s 5místným PSČ (CZ, SK, DE, PL); rakouské a maďarské 4místné PSČ odhad nedostane a cenu dopravy zadá zaměstnanec při schválení objednávky; DPH podle země zákazníka a ověření IČ DPH přes VIES je obecné pro všechny členské státy (`api/miniweb_objednavky.py::_dph`).
- Právní stránky: DE/HU dokumenty a identifikace firem (DE: Handelsregisternummer/USt-IdNr, HU: cégjegyzékszám/adószám) – ověření IČ DPH přes VIES řeší backend obecně (prefix země + 2–12 znaků), IČO/registrační číslo mimo CZ/SK je pole 4–20 znaků bez ověření v rejstříku.
