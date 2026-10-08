# Mini-shop (Packstations) – serverové API `/api/miniweb/*` (bot5, 2026-10-02)

**Stav: NENASAZENO.** Migrace jsou v DB (`sql/2026-10-02_miniweb.sql`, `_miniweb_inquiries.sql`, `_miniweb_family.sql`, tabulky prázdné), kód čeká v téhle sadě. Nasazení: `bash scripts/2026-10-02_miniweb_testy/nasazeni/deploy_miniweb.sh`
(zámek, patche `api/app.py` + `api/qa_checks.py`, nové `api/miniweb.py`, `api/miniweb_admin.py`, `webapp/miniweb-schvaleni.html`, testy nad živými soubory, commit; na ostro při plánovaném nasazení serveru 03:30/12:30).
**Skript spouštět jen s PŘÍMÝM povolením Roberta v session, která ho spouští** (první pokus zablokoval systém oprávnění jako produkční nasazení, zpráva od jiné session nestačí).
Rozsah schválil bot3: **fáze 1** (čtení), **fáze 2** (poptávka), **fáze 1b** (import textů jako draft a klikací schvalování Robertem). **Fáze 3** (objednávky: měna, DPH, doprava, doklady v cizí měně) je zavřená do rozhodnutí Roberta.

## Model
- **Mini-shop = storefront** (`car_storefronts`: host a jazyk podle DOMÉNY, aliasy hostu v `storefront_hosts`) **+ řádek v `miniweb_shops`** (rodina, měna, barva, země, kontakt, `price_mode`, `inquiry_enabled`).
  Jazykové verze téhož shopu = další storefront na jiné doméně se stejnou `family` (z toho `alternates` pro hreflang). Nový jazyk = nový storefront + řádek + texty, bez zásahu do kódu.
- **Katalog je jazykově neutrální** a patří **rodině** shopu (`miniweb_categories.family`, produkt ji dědí přes kategorii; shop jiné rodiny vidí jen svůj katalog; `miniweb_products`: slug, veřejný kód `public_sku`, konfigurátor `shop_product_id`), **texty po jazycích** (`miniweb_category_texts`, `miniweb_product_texts`)
  se stavem `draft`/`approved`. Veřejnosti se servíruje jen `approved`; staff v náhledu vidí i `draft` (u produktu `text_status: "draft"`).
- Poptávka: osobní údaje JEN v CRM (`crm_leads` + `crm_lead_messages`, `source='miniweb'`), tabulky `miniweb_inquiries` a `miniweb_inquiry_items` nesou jen nepersonální snímek (shop, host, jazyk, země, souhlas, položky s konfigurací).

## Kontrakt (JSON)
Brána: shop ve stavu `live` je veřejný, shop ve stavu `draft` vidí **jen staff** (přihlášený, role z `PERMISSION_ROLES`) – kontrola je NA SERVERU, ostatní dostanou `404 shop_not_found`. Shop se pozná podle hostu (hlavní doména nebo alias);
na společné doméně `?shop=<slug storefrontu>` a `?lang=<kód>` jen pro staff, `?drafts=1` přidá koncepty i na živém shopu. Všechny odpovědi nesou `X-Robots-Tag: noindex, nofollow`, živé veřejné GET `Cache-Control: public, max-age=60`, vše ostatní `no-store`.

| Endpoint | Odpověď |
|---|---|
| `GET /api/miniweb/config` | `{shop, lang, locale, currency, accent, countries[], contact{phone,hours}, price_mode, inquiry_only, inquiry_enabled, alternates[{lang,href}], preview}` (nahrazuje statický `config.json`, bez `vat` a `shipping` – to je fáze 3) |
| `GET /api/miniweb/categories` | `{categories:[{id, parent_id, slug, name, count}]}`; `count` = viditelné produkty **včetně podkategorií** |
| `GET /api/miniweb/products?category=<slug>&limit&offset` | `{products:[…], total}`; kategorie zahrnuje podkategorie, `limit` 1–200 (výchozí 100), řazeno `sort_order`, `id` |
| `GET /api/miniweb/products/<id>` | `{product}` nebo `404 {error:"not_found"}` (stejně pro všechny důvody skrytí) |
| `GET /api/miniweb/legal` | `{seller:{name,address,country_code,id,vat_id}, contact, documents:[]}` – **jediné místo s názvem společnosti** (zákonná identifikace prodejce, k ověření u účetní/právníka); texty podmínek dodá Robert |
| `POST /api/miniweb/inquiry` | viz níže |

Produkt (tvar z `demo-api.js`): `{id, slug, sku, category_id, name, summary, description, price_from, currency, delivery, configurator:{available, default_view, product_id}, specs:[{name,value}]}`.
- `price_from` je **vždy `null`** (ceny se nevydávají ani nepřijímají, dokud Robert nerozhodne o měně a DPH), `currency` z řádku shopu nebo `null`.
- `configurator.product_id` = karta sestavy pro endpointy bot10 (`/api/shop/products/<id>/configurator` …), jen když `available`, jinak `null`. Jiné interní id ani dodavatel neodchází.
- Všechny texty jsou **čistý text** (HTML pryč, entity rozbalené). `description` může obsahovat `\n` (odstavce) – ve stránce `white-space: pre-line` nebo rozdělit podle `\n`; vykreslovat přes `textContent`.

### `POST /api/miniweb/inquiry`
Tělo `application/json` (jiný typ = `400 invalid_json`, to je i bariéra proti cross-site formulářům), max 64 kB:
`{name, email, phone?, company?, country? (ISO 2 písmena), message?, consent: true, website: "" (honeypot – skrytý input, musí zůstat prázdný), items?: [{product_id, qty 1–99, kod?, configuration? {hash,…}, summary? [{label,value}]}]}`
- Povinné: `name`, platný ASCII `email`, `consent === true` a aspoň `message` nebo `items` (max 20). Položka musí být **viditelný produkt tohoto shopu**; název a kód bere server z databáze (klient o nich nerozhoduje), cenu (`unit_net` apod.) ignoruje.
  `configuration` je neprůhledná, neověřená (max 6 kB, hloubka 32) – **nikdy z ní nebrat cenu**; cenu určí nabídka.
- Úspěch `201 {status:"ok", inquiry_id}`. Chyby `{error, field?}`: `invalid_json`, `payload_too_large` (413), `name_required`, `email_invalid`, `country_invalid`, `consent_required`, `message_or_items_required`, `items_invalid` (`field: "items[1]"`),
  `inquiry_disabled` (403), `shop_not_found` (404), `rate_limited` (429, 5 poptávek/10 min na IP), `too_many_inquiries` (429, 3/den na e-mail), `internal_error` (500). Front-end si kódy přeloží do svých i18n textů.
- Honeypot vyplněný = tváří se jako úspěch (`inquiry_id: 0`), nic se neukládá. **Náhled** (shop není `live`, staff) poptávku jen zvaliduje a **neuloží** (`201 {inquiry_id:0, preview:true}`) – žádná testovací data v produkci.
- Vznikne CRM poptávka (zpráva pro zaměstnance česky: text zákazníka, firma, země, výčet položek s kódem a parametry konfigurace) a nepersonální snímek. **Potvrzení zákazníkovi e-mailem je ZATÍM VYPNUTÉ**
  (`CONFIRMATION_ENABLED = False`, rozhodnutí Roberta přes bot3: mini-shop nepotvrzuje, zaměstnanec odpoví osobně, protože společné SMTP odesílá jako "Logiman s.r.o." z Robertovy adresy). Šablona (`en`) je připravená a otestovaná:
  po zapnutí půjde jen do schvalovací fronty (`system_emails`, `kind='storefront_lead'`, `pending`, pravidlo 16); zapnout až s neutrálním odesílatelem (doména a schránka shopu) a s přepínačem v DB per shop.

## Fáze 1b: import textů a schvalování (jen admin)
Tok: bot7 dodá soubor JSON (formát v hlavičce `api/miniweb_admin.py`) → `scripts/miniweb_import.py SOUBOR.json` (výchozí je NÁHLED, nic nezapíše) → `--apply` zapíše jako **draft** (nikdy approved; před zápisem zazálohuje stávající řádky do `backups/`) →
Robert otevře `/miniweb-schvaleni.html` (přihlášen jako admin, stránka je pro mobil: velká tlačítka, „Schválit“ u každého textu a „Schválit všechny návrhy“ se dvoukrokovým potvrzením, „Náhled shopu“ s `?drafts=1`) → schválený text je veřejný až když je storefront shopu `live`
(spuštění shopu je záměrně zvlášť, schvalování ho nezveřejňuje).
- **Import je bezpečný:** celý soubor se nejdřív zvaliduje a při jediné chybě se nezapíše nic (neznámý klíč, značka/dodavatel, limity, duplicity, neexistující kategorie nebo karta sestavy, cyklus). Schválený text se importem **nepřepíše** (`--revise-approved` ho přepíše a vrátí do návrhu),
  katalogová data existující položky se jen ohlásí (`--update-catalog` je změní). Texty se ukládají už očištěné (HTML pryč), schvaluje se přesně to, co zákazník uvidí.
- **Schvalování nelze obejít:** `POST /api/admin/miniweb/approve` bere položky `{kind, id, lang, rev}`; `rev` je otisk obsahu, který admin viděl, a když se text mezitím změnil (import), **neschválí se** (`skipped: changed`). Text se značkou nebo bez názvu nejde schválit (`blocked`).
  `GET /api/admin/miniweb/overview` vrací texty tak, jak je uvidí zákazník, s příznaky (`blocking`, `info`), `public` (ukázalo by je teď veřejné API) a počty; `POST .../unapprove` vrací schválené do návrhu. Každá změna jde do `audit_log`.
- Ukázkový soubor: `{"version":1,"family":"packstations","lang":"en","categories":[{"slug":"tables","parent":null,"sort":1,"name":"Tables"}],"products":[{"slug":"packing-station-ps120","sku":"PS-120","category":"tables","sort":1,"configurator":{"available":true,"shop_product_id":1234},"name":"…","summary":"…","description":"…","delivery":"…","specs":[{"name":"Width","value":"1200 mm"}]}]}`.

## Pravidla (neměnit bez Roberta/bot3)
- **Žádný živý e-mail na webu** (Robert 2026-09-06): API nevydává žádnou e-mailovou adresu (`contact` = telefon a doba, jinak formulář `/inquiry`), ani když je v `contact_json`.
- **Bez značky**: každý vydávaný text (názvy, popisy, parametry, kontakt, adresy jazykových verzí, e-mail) projde `dealers._BRAND_RE`, **fail closed** – pole se značkou se nevydá, produkt/kategorie se značkou (i s podkategoriemi) se skryje.
  Výjimka jen `legal.seller`. QA kontrola `miniweb_text_brand_leak` ukáže, který text je třeba opravit u zdroje.
- Texty `approved` schvaluje Robert (dodává bot7); právní texty (podmínky, soukromí, vrácení) dodá Robert, do té doby placeholder a stránka draft/noindex.
- Objednávky z mini-shopu bez dealera jsou naše (`dealer_id` NULL, snímek host + jazyk) – až ve fázi 3.

## Založení shopu (po nasazení)
1. Storefront (admin): doména (jedna na jazyk), `lang` (en, de…), stav `draft` (po schválení `live`), `kind` jiný než `model` (hub stránka vypisuje jen `model`); nginx vhost/TLS a aliasy řeší Robert/bot14.
2. `INSERT INTO miniweb_shops (storefront_id, family, price_mode, currency, locale, accent, countries, contact_json) VALUES (…)` – `price_mode` zůstává `hidden`, `currency` NULL do rozhodnutí.
3. Kategorie, produkty a texty (status `draft`); k `approved` je přepíná jen Robert. Správa přes admin zatím **není** (návrh fáze 1b k odsouhlasení bot3: import textů jako draft + admin schválení).

## Po nasazení ověřit (jen nemutující sondy)
`GET /api/miniweb/config` na cizím hostu = `404 {"error":"shop_not_found"}` (route žije), `GET /api/admin/miniweb/overview` bez přihlášení = `401`, `GET /miniweb-schvaleni.html` = `200`, `POST /api/miniweb/inquiry` bez těla = `400 invalid_json` (nic se neuloží),
hlavní routy a běžná objednávka beze změny, QA panel bez nových nálezů.

## K potvrzení s bot16 (návrh)
(a) texty a kategorie dodá bot7 jako JSON, vloží se jako `draft`; (b) veřejný kód produktu je `public_sku` (ne interní SKU); (c) parametry (`specs`) jsou po jazycích, ne překlad klíčů; (d) `alternates` jen na úrovni shopu, ne produktu;
(e) `count` v kategoriích zahrnuje podkategorie; (f) koncept shopu vidí jen přihlášený staff (na jeho vlastní doméně je třeba se přihlásit, jinak `?shop=` na hlavní doméně).
