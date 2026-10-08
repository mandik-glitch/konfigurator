# Audit SEO / AI viditelnosti (Google AI Overviews, AI Mode) — 2026-08-28

Zadání: Robert přes bot3, cíl "aby si AI model vybíral konfigurátor
jako zdroj/doporučení" + klasické SEO pro relevantní klíčová slova.
**Audit only — žádné změny na produkci** (kromě jednoho vedlejšího
akutního fixu mimo SEO scope, viz sekce na konci). Provádí bot10.

Souběžně stejný audit na sesterském projektu
`/opt/vybaveni-uzitkovych-vozidel` (`AUDIT_SEO_AI_VISIBILITY_2026-08-28.md`
tam) — část 1 níže z něj cituje jako referenční příklad.

---

## 1. Strukturovaná data (schema.org / JSON-LD)

**Co už funguje:**

| Typ stránky | Schema | Umístění v kódu |
|---|---|---|
| Detail produktu | `Product` (name/sku/description/image/url) + `Offer` (price/priceCurrency/availability) | `api/app.py:4900-4923` |
| Kategorie | `BreadcrumbList` + `CollectionPage` (hasPart → Product odkazy) | `api/app.py:4982-5015` |
| Homepage | `ItemList` (obsahové bloky) | `api/app.py:5233-5245` |

Dostupnost (`availability`) je řešená chytře — `stock_qty>0 NEBO
availability_text` (ne holé `stock_qty>0`), protože **99,8 % katalogu
je řezané/objednávané na míru** (`stock_qty=0` u skoro všeho by jinak
appka nesprávně hlásila jako `OutOfStock` a Google by ceny degradoval/
neukazoval) — vidět v komentáři u `api/app.py:4914-4921`, dobré řešení.

**Chybí zcela (na CELÉM webu, ne jen na jedné stránce):**

1. **`Organization` / `WebSite` JSON-LD** — nikde, ani na homepage.
   Tohle je základní "kdo jste" signál, který Google/AI Overviews
   potřebují k identifikaci firmy za webem (napojení na Knowledge
   Graph, brand recognition). Sesterský projekt
   `vybaveni-uzitkovych-vozidel` (`api/app.py:927-934`) tohle už MÁ
   hotové a funguje jako přímo použitelný vzor:
   ```python
   + _ld_json_script({
       "@context": "https://schema.org", "@type": "Organization",
       "name": SITE_NAME, "url": request.host_url.rstrip("/"),
   })
   + _ld_json_script({
       "@context": "https://schema.org", "@type": "WebSite",
       "name": SITE_NAME, "url": request.host_url.rstrip("/"),
   })
   ```
   U konfigurátoru by šlo navíc obohatit o `LocalBusiness` (má fyzickou
   provozovnu/montáž) místo holého `Organization` — `api/documents.py:121`
   (`SUPPLIER` dict) už má VŠECHNA potřebná data (název, adresa, IČO,
   DIČ, telefon, e-mail) centrálně, jen se nikdy nepoužila pro schema.
   `remeslo.py:3855` má navíc už FUNKČNÍ `LocalBusiness` JSON-LD (na
   veřejných vizitkách řemeslníků) — třetí referenční vzor přímo v
   tomhle repu, jen pro jiný modul.
2. **`FAQPage` JSON-LD** — nikde, i když **27 z 59 stránek s obsahem
   (46 %) už má hotový vizuální FAQ blok** (`<div class="seo-faq">`,
   viz sekce 2) — content existuje, jen není označkovaný jako
   strukturovaná FAQ data. Nejlevnější "quick win" celého auditu:
   parsovat existující `<div class="seo-faq">` blok z `body_html`/
   `bottom_body_html` (má konzistentní `<p><strong>Otázka?</strong><br>
   Odpověď.</p>` vzor) a generovat `FAQPage` JSON-LD automaticky —
   ŽÁDNÝ nový text, jen strukturování už napsaného obsahu.
3. **`AggregateRating`/`Review`** — chybí, ale e-shop nemá recenzní
   systém vůbec, takže momentálně nedává smysl doplňovat (bylo by to
   prázdné/fabrikované). Zmiňuji jen pro úplnost, NE jako doporučení k
   akci.

---

## 2. Existující textový obsah — inventura (na výslovnou žádost, ať se
## nenavrhuje přepisovat, co už je hotové)

**Celkový stav**: 119 kategorií v `content_categories`, z toho **59 má
vlastní `content_pages` řádek** (50 %) — zbylých 60 kategorií je
prázdných (fallback text "Zatím bez obsahu" z `category.html:1629`).
Z těch 59 vyplněných má **27 (46 %) hotový FAQ blok** (`class="seo-faq"`,
nadpis "Časté dotazy", 2-4 otázky/odpovědi ve formátu `<strong>Otázka?
</strong><br>Odpověď.`), typicky doplněný sekcí "Související stránky"
s prolinky na sesterské kategorie.

**Kvalita ukázky** (kategorie 184, "Vestavby do dodávek, aut" — kořen
stromu, na který se ptal bot3 explicitně): obsah je věcný, konkrétní,
obsahuje ověřitelná fakta (konkrétní modely dodávek — Sprinter/Transit/
Ducato/…, číslo homologace HP-0579, místa montáže), NE generický
marketingový text. FAQ blok má 3 dobře formulované otázky včetně
rozlišení "vestavba vs. stavebnice" (typický zákaznický dotaz).

**Vestavby strom konkrétně** (7 kategorií, 184+6 potomků) — VŠECH 7 má
vyplněný obsah, ale objem je skromný (18-260 slov na stránku napříč
intro+body+bottom). Jen kořenová kategorie (184) má FAQ blok — 6
potomků (Ford Custom, Toyota ProAce, TECNO, Ducato/Jumper/Boxer,
elektrikáři, instalatéři) FAQ blok NEMÁ, i když by u konkrétních
modelů/profesí dávaly smysl stejně dobře jako u kořene (např. "Kolik
váží vestavba pro Ford Custom?", "Jak dlouho montáž trvá?").

**Závěr k obsahu**: content gap NENÍ "chybí text" — je to (a)
nedokončené pokrytí FAQ vzoru napříč už existujícím obsahem (27/59, ne
59/59) a (b) 60 kategorií zcela bez `content_pages` řádku (mohou být
záměrně technické/číselníkové kategorie bez potřeby popisu — nekontroloval
jsem každou zvlášť, jen celkový poměr). Doporučuji NEpsat nový obsah
plošně, ale (1) doplnit FAQ blok tam, kde už je nějaký text, ale FAQ
chybí, a (2) u zbylých 60 prázdných kategorií nechat na Robertovi/bot3
rozhodnutí, které z nich reálně obsah potřebují.

---

## 3. NAP konzistence (název/adresa/telefon)

**Zdroj pravdy existuje** — `api/documents.py:121`, `SUPPLIER` dict:
LOGIMAN s.r.o., Husinecká 903/10, 13000 Praha, IČO 28337638,
+420 603 230 059, mandik@logiman.cz.

**Problém: tahle data se NIKDE na veřejném webu nezobrazují.**

- **Patička je prázdná** na všech 3 hlavních šablonách
  (`index.html:772`, `category.html:1088`, `product.html:978`) —
  obsahuje jen jednořádkový tagline "Hliníkový stavebnicový systém pro
  užitková vozidla", žádný název firmy, adresa, telefon, IČO, odkaz na
  kontakt.
- **Neexistuje žádná dedikovaná kontakt/o-nás stránka** (`ls webapp/`
  neobsahuje nic jako `kontakt.html`/`o-nas.html`).
- Firemní údaje se objevují JEN v adminovi (fakturační doklady) a
  interně v kódu — návštěvník webu ani robot/AI crawler je nikde
  nenajde.

Tohle je zásadní mezera pro obojí — klasické SEO (NAP konzistence je
základní E-E-A-T/lokální SEO signál) i AEO (AI model potřebuje umět
identifikovat, KDO za webem stojí, aby ho doporučil jako důvěryhodný
zdroj). Návrh: patička s NAP + odkazem na kontakt, + jednoduchá
kontakt/o-nás stránka (i krátká stačí na začátek) s `LocalBusiness`
schema (viz bod 1).

---

## 4. Obecná technická SEO kvalita

**Silné stránky** (potvrzuje "SEO infrastruktura už vyladěná" z
CLAUDE.md sesterského projektu — NENÍ to prázdné tvrzení):

- `meta description`, `robots` (s pokročilými direktivami
  `max-snippet:-1, max-image-preview:large, max-video-preview:-1`),
  `canonical`, kompletní OG tagy (type/site_name/title/description/
  image/url), Twitter card — vše generováno centrálně
  (`_render_og_page`, `api/app.py:4751`).
- Čisté, klíčovým slovem popsané URL (`/kategorie/<slug>`,
  `/produkt/<slug>`) s 301 redirecty pro staré slugy
  (`shop_product_redirects`) — SEO audit z 2026-08-03, zmíněný
  opakovaně v komentářích kódu.
- **SSR (server-side render) obsahu** pro roboty/AI crawlery, které
  JS nevykonávají nebo ho vykonají opožděně — kategorie i produkty mají
  serverem vyplněný HTML obsah (ne jen "Načítám…" placeholder), klient
  ho pak identicky/aktuálně přepíše. Existují i QA kontroly hlídající
  drift mezi SSR a klientským renderem (`check_ssr_client_render_drift`,
  `check_ssr_sidebar_tree_missing` v `api/qa_checks.py`).
- `lang="cs"`, `viewport` meta — v pořádku na všech kontrolovaných
  šablonách.
- `sitemap.xml` existuje, 742 URL (kategorie+produkty), `lastmod`+
  `priority` vyplněné. Drobnost: `lastmod` u prohlédnutých položek má
  fixní datum "2026-08-10" napříč vzorkem — stojí za ověření, jestli
  se skutečně aktualizuje podle reálné poslední změny obsahu, nebo je
  to zamrzlé datum jednorázového generování.
- Existující QA kontrola `check_mobile_layout_zero_width` (historicky
  vzniklá z reálného incidentu — viz git `26a938f` "KRITICKY: obsah
  stránky neviditelný na mobilu") hlídá mobilní layout regrese
  automaticky.

**Zásadní blokující problém (objeven při kontrole domény/canonical):**

Web momentálně běží JEN na holé IP adrese (`80.211.210.103`) a
`sslip.io` wildcard doméně, BEZ HTTPS, BEZ vlastní domény — potvrzeno
`nginx` konfigurací (`server_name 80.211.210.103;` a
`80-211-210-103.sslip.io`) i živě (`canonical`/`og:url`/`sitemap.xml`
Sitemap řádek všechny ukazují na `http://80.211.210.103/...`).
`robots.txt` přitom aktivně říká `index, follow` — appka TEĎ ZVE
crawlery, ať tuhle holou-IP verzi indexují.

Tohle není překvapení (projekt je vědomě v pre-launch/testovací fázi,
produkční cutover odhadem za 1-2 měsíce), ale je to **zásadní blokátor
pro cokoli z zadání "AI si vybere konfigurátor jako zdroj"** — Google
Rich Results i AI Overviews prakticky nikdy necitují holé IP adresy bez
HTTPS jako důvěryhodný zdroj, a jakékoli SEO/schema vylepšení udělané
TEĎ na aktuální IP se bude muset po přechodu na reálnou doménu částečně
zopakovat/přesměrovat (301 z staré na novou strukturu, případně úplně
zahodit indexovaná URL). Doporučuji s Robertem probrat, jestli:
(a) `robots.txt` má prozatím radši `Disallow: /` (zabránit
předčasnému indexování holé IP, dokud doména není jistá), nebo
(b) je reálná doména/HTTPS blíž, než se zdá, a tenhle bod odpadá.

**Vedlejší nález (mimo SEO, ale objevený při kontrole domény,
OPRAVENO stejný den, viz zápis v AGENTS_LOG.md 2026-08-28)**:
`api/.env` `APP_BASE_URL` ukazoval na `vandrawee.cz` (Robertova jiná
značka, ne konfigurátor) — odkazy v e-mailech s resetem hesla/ověřením
registrace tak vedly na cizí web. Opraveno na správnou IP appky, dopad
na reálné zákazníky ověřen jako nulový (jen Robertovo vlastní
testování, žádná reálná registrace zákazníka zatím neproběhla).

---

## Souhrn — TOP doporučení (pořadí podle poměru dopad/náročnost)

1. **Doplnit `Organization`/`WebSite` (případně `LocalBusiness`) JSON-LD
   na všechny stránky** — nejrychlejší, nejjistější zásah, přímo
   okopírovatelný vzor ze sesterského projektu i z vlastního
   `remeslo.py`. Data (`SUPPLIER` dict) už existují.
2. **Automaticky generovat `FAQPage` JSON-LD z existujících `seo-faq`
   bloků** (27 stránek už má hotový obsah, jen chybí strukturování) —
   žádný nový text, čistě technická práce.
3. **Patička s NAP + kontakt/o-nás stránka** — uzavírá NAP-konzistenci
   i chybějící E-E-A-T signál, znovupoužije `SUPPLIER` data.
4. **Rozšířit FAQ blok na zbylých 32 stránek s obsahem, co ho ještě
   nemají** (začít 6 potomky "Vestavby do dodávek" — konkrétní
   modely/profese, přirozeně vhodné pro Q&A formát) — navazuje na
   existující vzor, ne nový koncept.
5. **Rozhodnout osud `robots.txt`/indexace před reálným launchem
   domény** — strategické rozhodnutí pro Roberta, ne technický úkol.
6. U zbylých 60 kategorií bez obsahu — projít s Robertem/bot3, které z
   nich reálně obsah potřebují (ne plošně doplňovat).

Žádný z těchto bodů nebyl implementován — čeká na společné schválení
Robertem/bot3.
