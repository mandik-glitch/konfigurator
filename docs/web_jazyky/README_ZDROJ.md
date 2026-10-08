# Sešity překladů obsahu hlavního webu (EN `vandrawee.eu`, IT `vandrawee.it`) – soubory a pravidla bot7

Architektura (host → jazyk, `web_sites`, resolver, brána indexace) je v `README.md` (bot16). Tenhle soubor popisuje **moje sešity `01_…07_*.json`, glosář a nástroje překladu**.
Zadání: Robert 2026-10-08. Autor textu a překladu: bot7.

## Sešity (`docs/web_jazyky/*.json`, v jednom souboru obě jazyky)
Položka `{id, typ (text|html), cs, en, it, h, [zmena]}`; `id` = `<kód>:<pk>:<pole>`:
| kód | tabulka | pk |
|---|---|---|
| `kat` | `content_categories` (name, nav_label, menu_group_label, meta_title, meta_description, focus_keyword) | id |
| `str` | `content_pages` (title, intro_html, body_html, bottom_body_html) | category_id |
| `kar` | `shop_products` (name, short_description, description, meta_title, meta_description, availability_text) | id |
| `dom` | `homepage_blocks` (`blokN`), `homepage_carousel_slides` (`slideN`), `sidebar_blocks` (`bocniN`) | N |
| `typ` / `var` | `content_typologie` (nazev, popis_html) / `typologie_varianty` (nazev, popis_zakaznicky) | id |
| `gal` | `content_gallery_items` (caption, jen `is_public=1`) | id |
| `obch` | `shop_shipping_methods` (`dopravaN`), `shop_payment_methods` (`platbaN`), jednotky `unit:ks` … | N |
`h` = hash `cs` v okamžiku překladu; změní-li se `cs`, překlad zůstane a položka dostane `zmena: true` (znovu zkontrolovat, import ji bere jako zastaralou).
Odkazy v HTML jsou `href="@cat:<id kategorie>"` (id je stabilní, resolver doplní přeloženou cestu). Slugy (`slug` kategorií, karet, bloků) dělám zvlášť sešitem `08_slugy.json`
po dokončení překladu názvů (položky `kat:ID:slug`, `kar:ID:slug`, `dom:blokN:slug`; `cs` = dnešní slug) – bez diakritiky, jedinečné v rámci tabulky a jazyka.

## Nástroje (z kořene repa)
1. `systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/web_jazyk_zdroj.py` – znovu natáhne `cs` z DB (jen SELECT, rerun bezpečný: překlady zůstanou).
2. `python3 scripts/web_jazyk_davky.py --vystup <složka>` – nepřeložené texty (stejný text ve stejném poli jednou) do dávek `davka_NNN.json` `[{k, pole, typ, cs}]`.
3. Překlad dávky → `davka_NNN.out.json` `[{k, en, it}]`.
4. `python3 scripts/web_jazyk_slij.py --davky <složka|soubor>` kontrola, `--apply` zapíše bezchybné; `--stav` přehled sešitů.

## Pravidla překladu (kontroluje `scripts/_web_jazyk.py::zkontroluj`)
- **EN = britský pravopis** (aluminium). Robert: EN drážka = **slot**, nikdy groove. IT drážka = scanalatura (Robert 2026-10-08). Termíny jednotně podle `glosar.json`.
- **HTML**: stejné značky ve stejném pořadí i s atributy (`class`, `href="@cat:…"`), mění se jen viditelný text. Žádné nové značky, žádný markdown.
- **Čísla, kódy, SKU, rozměry, jednotky** (30x30, Ø50, M6, K-075, mm, kg) beze změny. EN: desetinná tečka, tisíce `1,000`; IT: desetinná čárka, tisíce `1.000`.
- **Zakázáno**: dogus, vandr*, unity, konfigurátor/configurator/configuratore (piš generator / 3D design), ponk, jména konkurentů a původního dodavatele knihovny karoserií. Nic nevymýšlet (nosnosti, ceny, normy, certifikace), nepřidávat věty.
- **Vestavby do aut**: nikdy „bez vrtání do karoserie“ ani „kotveno bez zásahu“; vestavba na míru = podle zákazníkova nářadí/kufrů.
- **Meta**: `meta_title` ≤ 60 znaků (hlavní fráze na začátku), `meta_description` 140–160 znaků (přirozeně, ne doslovně), `focus_keyword` = fráze, kterou by v dané zemi napsal kupující.
- **Styl**: B2B, věcný. EN „you“. IT neosobné věty nebo formální Lei, nikdy „tu“. Ve výstupu žádná česká diakritika.
- Názvy karet: přeložit popisná slova, kódy a rozměry nechat. `availability_text` „3 - 5 týdnů“ → „3–5 weeks“ / „3–5 settimane“.
