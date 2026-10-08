# Mini-shop Packstations – kontrakt front-end ↔ server (bot16, 2026-10-02)

Rozdělení: **bot5** serverové `/api/miniweb/*` (katalog, texty po jazycích, poptávka), **bot10** konfigurátor (`/api/shop/products/<id>/configurator`, `resolve`, `model/<hash>`,
viz `docs/KONTRAKT_KONFIGURATOR_UI.md`), **bot16** front-end `webapp/miniweb/*` + modul `webapp/js/product-configurator.js`.
**Zdroj pravdy pro tvary fáze 1+2** je `scripts/2026-10-02_miniweb_testy/nasazeni/README.md` (bot5). Tady jen to, co front-end z něj používá, a to, co je navíc.

## Co front-end dělá
| Věc | Chování |
|---|---|
| Konfigurace | `GET /api/miniweb/config` (host určuje shop a jazyk; na společné/IP doméně `?shop=<slug>&lang=<kód>[&drafts=1]` jen pro staff – front-end je přidává do každého dotazu, drží je v `sessionStorage`). Statický `config.json` se používá JEN v demu (`?demo=1`). |
| Brána | Koncept shopu = jen staff, **brána na serveru** (404 `shop_not_found`). JS při 404 nabídne přihlášení (nepřihlášený) nebo ‚not public‘ (zákazník). `config.preview:true` → pruh ‚Staff preview‘ a vyžaduje staff i v JS. Živý shop (`preview:false`) je veřejný, bez brány. |
| Jazyk | z `config.lang` → `miniweb/i18n/<lang>.json` (fallback `en`). **Žádný text není v HTML ani v JS napevno**; chybějící klíč je vidět jako klíč. Nový jazyk = nový `i18n/<lang>.json` + storefront na jiné doméně (stejná `family`), `alternates` → `<link rel=alternate hreflang>`. |
| Ceny | `config.price_mode:"hidden"` → karta ‚Price on request‘, skrytý řádek ceny konfigurátoru. `price_from:null` v seznamu = totéž. Klient **nikdy neposílá cenu**; `unit_net` apod. neexistuje. |
| Košík | `config.inquiry_only:true` (nebo `checkout_mode:"inquiry"`) → poptávkový košík: bez cen/DPH/dopravy, odeslání `POST /api/miniweb/inquiry`. Jinak objednávkový košík (fáze 3, níže). Do `localStorage` se ukládá jen výběr voleb (`product_id, qty, kod, configuration{selection,hash,rules_version}, summary`). |
| Poptávka | tělo přesně podle bot5 README (`name, email, phone?, company?, country, message?, consent:true, website:"", items[]`); položka = `{product_id, qty, kod, configuration, summary}`. Kódy chyb → `err.<kód>` v i18n. `201 {preview:true}` (koncept) → hláška ‚nic se neuložilo‘, košík zůstává. Kontaktní formulář = stejná poptávka bez `items` (+ souhlas). |
| Konfigurátor | karta volá modul s `{id: configurator.product_id, configurator}`; `product_id` je karta sestavy pro endpointy bot10. 3D model přichází jen jako krátce platný odkaz z `resolve`/`model` (ne `katalog/*.glb`). |
| Zobrazení textů | jen `textContent` (žádné `innerHTML`); `description` s `\n` → `white-space: pre-line`. |
| E-mail | **nikde se nezobrazuje** (Robertovo pravidlo 2026-09-06): `config.contact.email` i `legal.seller.email` front-end ignoruje; kontakt = formulář. |
| Právní údaje | `GET /api/miniweb/legal` → `seller{name,address,id,vat_id}` – jediné místo s názvem společnosti; ve statickém HTML není. |

## Fáze 3 (objednávka) – NÁVRH, na serveru zatím neexistuje
Front-end ji volá jen když `inquiry_only !== true`; v demu ji simuluje `demo-api.js` (tvar tedy otestován, serverová strana ne).
- `POST /api/miniweb/quote` `{country, items:[{product_id, qty, kod, configuration, summary}]}` → `{currency, lines:[{net_unit, qty, net_total}], subtotal, shipping, vat_rate, vat, total}` (vše ze serveru: ceník z `resolve`, doprava podle země/velikosti, DPH podle země dodání + VAT ID).
- `POST /api/miniweb/orders` `{country, company, vat_id?, name, email, phone, street, city, zip, pay:"transfer", website:"", items[]}` → `201 {status:"created", reference}`; vznikne naše objednávka (`dealer_id` NULL, host + jazyk), proforma + QR/párování plateb stávajícím mechanismem, e-mail zákazníkovi jen přes schvalovací frontu (pravidlo 16).
- Čeká na Robertovo rozhodnutí: **zdroj cen v EUR** (jeho volba: EUR bez DPH, DPH podle země dodání CZ 21 / SK 23 / DE 19 / AT 20 / PL 23, bankovní převod, fixní doprava podle země/velikosti – ale DB má ceny v Kč) a výše dopravy.

## Odpovědi na (a)–(f) od bot5
(a) ano, texty a kategorie jako JSON → `draft`; počáteční anglické klíče `demo.*` v `i18n/en.json` jsou jen DEMO, ne zdroj pro produkci. (b) ano, `sku` v odpovědi = `public_sku`. (c) ano, `specs` po jazycích (name i value jako text). (d) `alternates` jen na úrovni shopu. (e) ano, `count` včetně podkategorií. (f) ano; na doméně shopu se staff přihlásí přes `/login.html`, na společné doméně stačí `?shop=`.
Navíc: `config.contact.email` a `seller.email` nevydávat k zobrazení (pravidlo e-mailu); `inquiry_id` klientovi nic neříká (zobrazuje se jen poděkování).
