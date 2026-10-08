# Mini-shop: právní dokumenty, kontakt ze společnosti, poptávka JEN FIRMÁM, skript shopu (bot5, 2026-10-02/03)

**Stav: KÓD A TESTY HOTOVÉ, NENASAZENO** (čeká na přímé povolení Roberta). Nasazení: `bash scripts/nasad_cekajici_bot5.sh pravni` (nebo `konfigurace pravni` obě sady po sobě). Skript patchuje `api/miniweb.py`,
`api/miniweb_admin.py` a `webapp/miniweb-schvaleni.html`, nakopíruje nové testy, pustí všechny testy mini-shopu nad živými soubory a commitne. API jde na ostro při nasazení serveru, stránka schvalování hned.
Tabulka `miniweb_documents` už v DB je (`sql/2026-10-02_miniweb_documents.sql`). Skripty `scripts/miniweb_shop.py` a `scripts/miniweb_import.py` fungují už teď (nepotřebují nasazení).

Zadání: Robert přes bot3 2026-10-02 – slovenský mini-shop se spouští ŽIVĚ (baliace-stoly.top), prodává se **vždy jen firmám**, kontakt = Robertovy údaje z jednoho zdroje, e-mail nikde, žádný automatický e-mail zákazníkovi.

## 1. Poptávka jen od firem – `POST /api/miniweb/inquiry`
Tělo: `{name, email, phone?, company, company_id, vat_id?, b2b_confirm: true, country?, message?, consent: true, website: "" (honeypot), items?}`.
| pole | pravidlo | chyba (HTTP 400, tělo `{error, field}`) |
|---|---|---|
| `company` | povinné (název firmy, po vyčištění neprázdný) | `company_required` |
| `company_id` (IČO) | povinné; CZ a SK 6 až 8 číslic (doplní se nulami na 8, mezery a pomlčky se odstraní), jinde 4 až 20 znaků | `company_id_required`, `company_id_invalid` |
| `vat_id` (DIČ / IČ DPH) | **nepovinné** (pro dodání bez DPH v rámci EU); když je, kontroluje se syntaxe: SK 10 číslic nebo `SK` + 10 číslic, CZ 8 až 10 číslic s `CZ` nebo bez, jinde prefix země (GR = `EL`) + 2 až 12 znaků | `vat_id_invalid` |
| `b2b_confirm` | povinné `true` (zákazník potvrzuje, že dopyt odesílá jménem podnikatele) | `b2b_confirm_required` |
| `country` | dvoupísmenný kód; u shopu s JEDINOU zemí dodání (SK) se doplní sama, jinak povinná | `country_invalid`, `country_required` |
| `consent` | povinné `true` (zpracování údajů) | `consent_required` (jako dosud) |
Totéž platí pro kontaktní formulář (poptávka jen se zprávou, bez položek): i ten vyžaduje firmu a IČO (rozhodnutí Roberta „vždy jen firmám“). **Ověření ve VIES a v registrech je OTEVŘENÝ BOD** (zatím jen syntaxe).
Do CRM (zpráva pro zaměstnance) jde řádek `Firma: … | IČO: 00123456 | DIČ/IČ DPH: SK2020202020 | Země: SK` (CRM umí IČO vyčíst při převodu na zákazníka); firma je i ve sloupci `crm_leads.company_name`. Do nepersonálního snímku
`miniweb_inquiries` IČO ani DIČ nejdou. Zaměstnanec vidí poptávku jako novou nepřečtenou (odznak „Poptávky“ v administraci), žádný e-mail zákazníkovi ani zaměstnanci (pravidlo 16).

## 2. Právní dokumenty (podmínky, soukromí, vrácení)
- Tabulka `miniweb_documents` (rodina, druh `terms|privacy|returns|shipping|cookies`, jazyk, nadpis, text, draft/approved).
- **Import**: v JSON souboru klíč `documents: [{kind, title, body}]` (stejný soubor jako katalog nebo jen `{version, family, lang, documents}`), import jako DRAFT, schválený se nepřepíše (jen `--revise-approved`). Neznámé klíče v souboru
  (např. `status`, `poznamka`) jsou CHYBA, do souboru pro import patří jen `version, family, lang, categories, products, documents`.
- **Značka**: dokument se značkou se neimportuje; povolený je JEN zákonný název prodejce (jako `legal.seller`, bez ohledu na velikost písmen a mezery). Samotné „Logiman“, „konfigurátor“, dodavatelé = chyba.
- **Zástupné značky** `[DOPLNIŤ: …]`, `[OVERIŤ: …]` a označení „NÁVRH k právnej kontrole“: dokument se nahraje jako draft s varováním, ale **nejde schválit a nikdy se veřejně nevydá**, dokud ho nenahradí finální verze po kontrole právníkem.
- **Schválení**: Robert na `/miniweb-schvaleni.html` (karta „Dokument“, dlouhý text s náhledem a „Zobrazit celé znění“, schválení s otiskem obsahu jako u ostatních textů).
- **Výdej**: `GET /api/miniweb/legal` → `{seller, contact, documents: [{kind, title, body, updated}]}`: jen schválené, v jazyce shopu (en-ie spadne na en), v pořadí `terms, privacy, returns, shipping, cookies`; staff v náhledu (`?drafts=1`) vidí i koncepty. `updated` = datum schválení.
  Prodejce a jeho údaje zůstávají v `seller` (zákonná identifikace, název firmy je jen tam a v dokumentech).

## 3. Kontakt shopu z nastavení společnosti
Řádek shopu s `contact_json = {"use_company": true, "hours": "…"}` vydá v `config.contact` a `legal.contact` navíc **`name`, `address` a `phone` z nastavení společnosti** (`app_settings.company_info`, editovatelné v adminu, z něj se plní i `kontakt.html`),
telefon ze společnosti má přednost před telefonem z řádku; doba (`hours`) zůstává z řádku. **Nikdy e-mail ani web.** Bez `use_company` (nebo s hodnotou jinou než přesně `true`) zůstává kontakt jen `{phone, hours}` z řádku shopu jako dosud.
Zapíná se `scripts/miniweb_shop.py --contact-from-company on`.

## 4. Skript shopu – `scripts/miniweb_shop.py`
Zakládá storefront (VŽDY jako koncept, `kind='miniweb'`) a řádek `miniweb_shops`, bez ručního SQL; bez `--apply` je to jen náhled. Příklad slovenského shopu:
`scripts/miniweb_shop.py --slug packstations-sk --host baliace-stoly.top --lang sk --family packstations --currency EUR --locale sk-SK --countries SK --accent "#2dd4bf" --contact-from-company on --name "Baliace stoly (SK)" --apply`
(spouští se přes `systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 …`).
**Spuštění**: `--slug packstations-sk --go-live [--apply]` přepne na live JEN když: je nainstalovaný nginx vhost domény (`/etc/nginx/sites-enabled/miniweb-<doména>`, `scripts/miniweb_nginx_install.sh`), shop má země dodání a přijímá poptávky,
je aspoň jedna veřejná kategorie a produkt (schválené texty), identifikace prodejce (`legal.seller`: název, adresa, IČO, DIČ) je úplná, je schválená informace o ochraně osobních údajů (`privacy`) v jazyce shopu, a (u `use_company`) je ve společnosti vyplněný telefon.
Podmínky, reklamace a vrácení se k spuštění NEvyžadují (Robert 2026-10-03: „jen běžné zákonné prvky“); jiné druhy jdou volitelně vyžádat `--require-docs terms,privacy,returns`. Jinak vypíše, co chybí, a nic nezmění. DNS (Cloudflare) neověří, jen připomene
(`scripts/miniweb_domena.py overit`). `--take-offline [--apply]` vrátí do konceptu bez podmínek.

## 5. Postup spuštění slovenského shopu (pořadí)
1. Nasadit tuhle sadu (`bash scripts/nasad_cekajici_bot5.sh pravni`), API naživo při nasazení serveru.
2. `scripts/miniweb_shop.py … --apply` (viz výše) – storefront a řádek shopu jako koncept (nezávisí na nasazení sady).
3. Import katalogu: `scripts/miniweb_import.py docs/miniweb_packstations_sk_navrh.json` (náhled) a `--apply` (draft), potom zredukované právní dokumenty od bot7 (`docs/miniweb_packstations_sk_pravne_navrh.json`, jen `terms` = „Prevádzkovateľ a dopyt“ a `privacy`) stejným příkazem. Soubor smí mít jen klíče `version, family, lang, categories, products, documents`.
4. Robert schválí texty a oba dokumenty na `/miniweb-schvaleni.html` (z mobilu; schválit musí kategorii, produkt a `privacy`).
5. Doména: `scripts/miniweb_domena.py` (zóna, NS, cert) a `bash scripts/miniweb_nginx_install.sh baliace-stoly.top` (bot16, root krok pro Roberta).
6. `scripts/miniweb_shop.py --slug packstations-sk --go-live` (náhled podmínek), pak `--apply`. Ověřit: `config.preview` je `false`, `legal.documents` obsahuje tři dokumenty.

## Testy (kandidáti přes `MINIWEB_PY`, `MINIWEB_ADMIN_PY`, `SCHVALENI_HTML`)
Čtení `test_miniweb.py` 63 (sekce K slovenština, L dokumenty, N kontakt), poptávka `test_miniweb_poptavka.py` 62 (G B2B), import a schvalování `test_miniweb_admin.py` 59 (E dokumenty), stránka schvalování `test_miniweb_schvaleni.js` 30
(Chromium, F dokumenty a mutace stránky), skript `test_miniweb_shop.py` 28. Po nasazení jsou testy ve `scripts/2026-10-02_miniweb_testy/` a v `run_all.sh`.
Poznámka k testům: `app.py` už importuje nasazený `miniweb`, kandidát se musí dát do `sys.path` PŘED `import app` (jinak by test potichu zkoušel nasazenou kopii; opraveno v nových testech).

## Otevřené
VIES a registry (jen syntaxe), právní dokumenty po právníkovi (zatím blokované zástupnými značkami), potvrzení zákazníkovi e-mailem zůstává VYPNUTÉ (rozhodnutí Roberta, žádná šablona ani pro sk), kontakt na stránce = údaje ze společnosti (e-mail nikdy),
`miniweb_documents` není v `product_duplicate.SKIPPED_TABLES` ani nemá sloupec product_id, takže se duplikace produktů ho netýká.
