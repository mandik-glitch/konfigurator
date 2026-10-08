# Mini-shop: montáž je volitelná, cena dopravy po objednávce (bot7, 2026-10-04, NÁVRH, nic se nenahrává)

Robert 2026-10-04: „montáž je vždy volitelná a podle toho se změní cena dopravy, kterou určí staff“. Platí i pro SK/EN mini-shop. Žádné číslo procenta, žádné tvrzení o smontovaném ani rozloženém stavu.

## Fáze 1 – hotové v souborech (bez slibu volby montáže, protože ji SK mini-shop zatím neumí)
Změněno v `miniweb_packstations_sk_navrh.json`, `miniweb_packstations_sk_navrh_s_url_slug.json`, `miniweb_packstations_en_navrh.json` (katalog: `delivery` a poslední část popisu), `miniweb_packstations_sk_home_navrh.json` (`home.usp4.d`, `faq.5.q/a`, `faq.8.a`, `pd.shipping_payment_text`) a v meta popisech kategorie (`miniweb_seo_sablony_navrh.json`).
Nový obsah: „Vyrába sa na objednávku. Dodacia lehota je 3–5 týždňov. Cenu dopravy určíme po objednávke a pred vystavením zálohovej faktúry ju potvrdíme.“ (EN: „Made to order. Delivery in 3–5 weeks. We set the shipping price after the order and confirm it before the proforma invoice is issued.“)
Import živého SK textu: změna schváleného textu jde jen přes schvalování; `--revise-approved` jen s Robertovým klikem.
Pozor na rozpor: `co.ship_note` v pokladně (bot16) říká, že se cena dopravy „počíta podľa PSČ“. Robert teď říká, že ji určí pracovník po objednávce. Sjednotit.

## Fáze 2 – zapnout až bude volba montáže v SK mini-shopu (backend + UI)
Přidat větu (SK / EN):
- katalog `delivery` + část „Dodanie a doprava“: „Montáž je voliteľná služba. Cena dopravy sa mení podľa toho, či si montáž zvolíte.“ / „Assembly is an optional service. The shipping price depends on whether you choose assembly.“
- FAQ (nová otázka 9): „Je montáž súčasťou dodávky?“ – „Nie, montáž je voliteľná služba. Cena dopravy sa mení podľa toho, či si ju zvolíte. Cenu určíme po objednávke a pred vystavením zálohovej faktúry ju potvrdíme.“
Cena montáže (procento z ceny stolu) se do textu nedává, ukazuje ji volba v generátoru.


## Aktualizace 2026-10-05 (Robert): S montáží je stůl dodán smontovaný, bez montáže demontovaný (rozložený)
Fáze 2 je rozepsaná v `docs/miniweb_montaz_faze2_texty_navrh.json` (katalog `delivery` a poslední část popisu, FAQ, `home.usp4.d`, `pd.shipping_payment_text`, SK a EN). Zapnout spolu s UI volby montáže. Klíče `pdc.montazLabel`, `pdc.montazOn`, `pdc.montazOff` jsou už v `webapp/miniweb/i18n/{cs,sk,en}.json`. CS text je zapsaný v kategoriích 206 a 311 a v popisu karty 4934.
