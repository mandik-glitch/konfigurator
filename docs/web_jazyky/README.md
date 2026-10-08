# Webové jazyky: EN na `vandrawee.eu`, IT na `vandrawee.it` (stejný backend, DB a vzhled jako autovestavby.logiman.cz)

Zadání: Robert 2026-10-08 (TASKS.md, commit 58c915bc). Rozhodnutí Roberta: první vlna = kompletní e-shop, **prodej jen firmám** (jako mini-shopy: firma + VAT ID, žádné spotřebitelské texty), ceny v **EUR bez DPH** (kurz z Kč + marže).
Tenhle soubor je **architektura (bot16)**; **formát sešitů překladu, nástroje překladu a pravidla textu jsou v `README_ZDROJ.md` (bot7)**. Smlouva mezi bot7 (překlady, SEO), bot5 (DB, import, EUR/DPH, e-maily), bot16 (host → jazyk, zobrazení, resolver, brána indexace) a bot9 (koordinace, doména, certifikát).

## 1. Jak se pozná jazyk
* Tabulka **`web_sites`** (jeden řádek na host): `host`, `canonical_host` (alias `www.` → hlavní), `lang` (`en`/`it`), `locale` (`en-GB`/`it-IT`), `currency` (`EUR`), `price_mode` (`excl_vat`), `eur_rate` (Kč za 1 EUR; `NULL` = živý kurz Fio jako `miniweb_cena.py`), `margin_pct` (`NULL` = **žádná cena**; pravidlo 9: kurz ani marže nejsou v kódu), `status` (`draft`/`live`), `indexable` (0/1; smí být 1 jen po zelené bráně z bodu 5), `x_default` (`en` – konfigurovatelné).
* Host, který v `web_sites` není (autovestavby.logiman.cz, logiman.cz, storefronty, mini-shopy), se **nemění** – čeština, Kč, dnešní chování. Kód jen přidá jeden dotaz „je host v `web_sites`?“ (cache 60 s).
* Náhled bez DNS: přihlášený zaměstnanec může na kterémkoli hostu přidat `?jazyk=en|it` – vždy `noindex`, pro ostatní se parametr ignoruje. Robert schvaluje náhled (obrázky), teprve potom `status = live`; nic z toho se nenasazuje na ostrý jazykový host bez jeho schválení.
* `vandrawee.it` (dnes starý italský web) se **nepřepisuje**, dokud Robert nepřepne DNS; `vandrawee.eu` čeká na DNS a certifikát (bot9).

## 2. Co se překládá (tři vrstvy, jeden formát sešitů)
| Vrstva | Zdroj | Sešit překladu | Kdo |
|---|---|---|---|
| **Obsah z DB** (kategorie, stránky, karty, homepage, typologie, galerie, doprava/platba, vybrané `app_settings`) | `scripts/web_jazyk_zdroj.py` (bot7) | `01_…07_*.json`, `09_nastaveni.json` (`nast:<klíč>:<pole>`) | bot7 překládá, import → `web_i18n`, resolver čte (bot16) |
| **Texty stránek** (tlačítka, nadpisy, hlášky v `webapp/*.html` a `webapp/js/*.js`; čeština v kódu zůstává) | `api/venv/bin/python3 scripts/web_jazyk_ui_zdroj.py` (bot16) | `10_ui.json` (+ `10_ui_kontext.json` = kde se věta používá, mimo sešity) | bot7 překládá, import → `web_i18n` |
| **Generátory, e-maily, doklady** | `api/jazyky/<jazyk>.json` (postup `docs/jazyky/README.md`; EN je, IT hotové 8d10f928), šablony e-mailů/dokladů | – | bot7 + bot5 |

Položka sešitu (všechny vrstvy): `{id, typ (text|html), cs, en, it, h, [zmena]}`, `h` = `sha1(cs)[:10]` v okamžiku překladu, změněná čeština → překlad zůstane a položka má `zmena: true` (resolver ji NEpoužije).
**Texty stránek:** `id` = `ui:<sha1(cs)[:12]>:<kontext>`; `cs` je **normalizovaný zdroj = klíč slovníku v prohlížeči**: mezery složené, číselné skupiny → `{n}` (`Celkem 12 ks` → `Celkem {n} ks`), proměnné z JS šablon → `{0}` `{1}`, inline značky uvnitř věty (`<a>`, `<b>`, `<span>`) → číslované `<1>…</1>` (`<br>` → `<2/>`), atributy se nepřekládají. Překlad musí mít stejné `<N>` značky a stejné `{…}`.
Ceny a měna se do slovníku nedávají – server vrací částky v měně hostu a stránka je formátuje jednou funkcí (EUR, `Intl` podle `locale`); věty s pevnou částkou v Kč jsou v `10_ui_kontext.json` označené `mena` a řeší se v kódu, ne překladem.

## 3. DB a čtení (resolver)
* **`web_i18n`**: `klic` (`kat:5:name`, `ui:ab12cd34ef56:tlacitko`, `nast:homepage_intro_html:html` …), `lang`, `text`, `h`, `zastarale`; PK (`klic`, `lang`). Import čte sešity `docs/web_jazyky/*.json` (bot5/bot16), nic jiného není zdroj.
* Resolver `prelozit(...)` doplní do odpovědí API a SSR překlady pro jazyk hostu; kde překlad chybí, je prázdný nebo zastaralý (`h` ≠ sha1 dnešní češtiny), vrátí **češtinu** a řádek označí `neprelozeno`. Odkazy `href="@cat:<id>"` v HTML poli resolver nahradí přeloženou cestou. Na českém hostu se nic nečte navíc.
* Pole `shop_products.manufacturer` ani jména dodavatelů se na jazykových hostech **nezobrazují** (TEXT_FILTR; ověří test).
* `webapp/js/i18n.js`: na českém hostu **prázdná operace**; na `en`/`it` vymění texty podle slovníku (přesná shoda normalizované věty, pak vzory `{0}`; atributy `placeholder|title|alt|aria-label`; `alert/confirm/prompt`), slovník dodá server ve stránce.

## 4. Adresy a hreflang
* Cesty (bot7): `/kosik` → `/basket` | `/carrello`, `/moje-objednavky` → `/my-orders` | `/i-miei-ordini`, `/kontakt` → `/contact` | `/contatti`, `/realizace` → `/projects` | `/realizzazioni`, `/kategorie/` → `/category/` | `/categoria/`, `/produkt/` → `/product/` | `/prodotto/`. Kategorie na kořeni (`/<slug>`) zůstávají na kořeni s přeloženým slugem (`08_slugy.json`). Česká adresa na jazykovém hostu = 301 na přeloženou.
* **301 ze starého italského webu** `vandrawee.it` (`/modeli-3d`, `/box-estraibili-dal-pianale`, `/cassetti-estraibili-dalle-porte`, `/estrattore-personalizzato-per-generatore`, `/scaffali-a-parete-per-furgoni`, `/contatti`) – mapa v `PATHS`, cíle doplní bot7 po slugech.
* **hreflang** z jednoho místa (`alternates(klic)`): živé řádky `web_sites` × přeložené slugy; stejná funkce plní `<link rel="alternate">` v hlavičce i `xhtml:link` v `sitemap.xml`; `x-default` = EN (sloupec `x_default`).

## 5. „Vše nebo nic“ před indexací
* Jazykový host je **indexovatelný jen když** (a) pro každou položku sešitů (a každý nový viditelný řádek ze zdroje) existuje překlad bez `zmena` a projde `scripts/_web_jazyk.py::zkontroluj` (jedna verze pravdy, bot7) a (b) E2E průchod hlavními stránkami v prohlížeči (EN i IT) nenajde viditelný český text. Jinak: `<meta name="robots" content="noindex, nofollow">`, `X-Robots-Tag`, `robots.txt` = `Disallow: /`, prázdná `sitemap.xml`.
* Nepřeložený řádek přidaný až po spuštění dostane `noindex` sám (jednotlivě), viditelně česky.

## 6. Fáze
0. Smlouva + zdroj UI vět (bot16) + sešity obsahu (bot7) – **teď**.
1. Kostra: `web_sites`, host → jazyk, resolver, `i18n.js`, EN náhled `index/category/product` na 1–2 kategoriích (bot16; tabulky + import bot5).
2. Celý katalog + texty stránek + generátory.
3. Košík, objednávky, účet, e-maily, doklady v EUR (bot5, UI bot16): **firmy + VAT ID**, DPH podle země/reverse charge (bot5).
4. Brána, hreflang, sitemap, náhled Robertovi → `live` → DNS/certifikát (bot9).

## 7. Otevřené
* Model měny v objednávkách a dokladech (bot5): `currency` na hlavičce a položkách, nebo Kč + převod?
* `nabidka-online.html` (online nabídky) a 3D konfigurátor – samostatná vlna po e-shopu.
