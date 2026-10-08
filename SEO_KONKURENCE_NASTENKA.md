# Nástěnka: SEO/GEO průzkum konkurence

Živý přehled konkurenčních webů (vestavby do dodávek, stavebnice do aut,
regály do vozidel) — co používají za klíčová slova, jak stavějí title/meta
description, co si z toho vzít pro `logiman.cz`/konfigurátor.

Založeno bot4, 2026-08-08 na žádost Roberta ("založit nástěnku, zapsat na
nastenku konkurenci skrze zkoumání SEO/GEO"). Navazuje na dřívější SEO audit
2026-08-03 (5 konkurentů zmíněných v TASKS.md - bott.cz/regaz.cz/
do-dodavky.cz/alfavaria.cz/topcentrum.cz - viz HTTPS redirect úkol), teď
rozšířeno na 11 domén.

## Metodika

Zjišťováno přímým stažením HTML (`curl` s desktop User-Agentem) a přes
`WebFetch`/`WebSearch` u webů blokujících přímý přístup (Cloudflare apod.).
Kontrolováno: `<title>`, `<meta name="description">`, `<meta
name="keywords">` (kde existuje), a to jak na homepage, tak (kde šlo
dohledat) na konkrétní kategorii "vestavby/regály do aut".

**Důležitá poznámka k `<meta name="keywords">`:** Google tento tag oficiálně
ignoruje jako ranking signál od roku 2009 - jeho přítomnost/absence u
konkurence NENÍ signál kvality jejich SEO, jen zvyk. Skutečně důležité je,
kolik variant klíčových frází pokrývají v title/description/nadpisech/textu
- to Google i AI vyhledávače reálně čtou.

## Přehled nálezů

| # | Doména | URL zkoumané stránky | `meta keywords` | Počet frází | Poznámka |
|---|---|---|---|---|---|
| 1 | **reca.cz** | https://www.reca.cz/cz/ | ne | 0 | Velký B2B distributor nářadí/spojovacího materiálu, homepage obecná firemní prezentace, žádná specifická "vestavby" kategorie na první pohled - nejspíš jen okrajový sortiment, ne přímý konkurent v této nice. |
| 2 | **rebuild-car.cz** | https://www.rebuild-car.cz/ | ne | 0 | Jiná nika - **obytné/kempinkové** vestavby (přestavba osobního auta na kemp), ne pracovní/servisní vestavby do dodávek. Částečně příbuzné, ne přímý konkurent kategorie "Vestavby do dodávek". |
| 3 | **topcentrum.cz** (homepage) | https://www.topcentrum.cz/ | **ano** | 12 | `nářadí, topcentrum, top centrum, stavební mechanizace, aku nářadí, elektrické nářadí, profesional, kvalita, vestavby, vestavby do vozidel, sortimo, milwaukee, knipex` - mix obecných+brand termínů, homepage není kategorie-specifická. |
| 3b | **topcentrum.cz** (kategorie) | https://www.topcentrum.cz/vestavby-do-vozidel | **ano** | 8 | `vestavba do vozidla, vestavba do auta, vestavby do vozidel, vestavby do aut, vestavba do dodávky, vestavby do dodávek, sortimo, regál do auta` - přesně cílené skloňované varianty stejného tématu (jsou prodejce Sortimo systémů, ne vlastní výrobce). |
| 4 | **regaz.cz** | https://www.regaz.cz/eshop-kategorie-vestavby-do-aut-3268.html | **nezjištěno** | - | Cloudflare bot-ochrana blokuje přímý přístup i běžný scraping; přes WebFetch zjištěn jen title "Vestavby do aut - 5 let záruka - Regaz.cz" a H1 stejného znění, meta tagy se nepodařilo přečíst. |
| 5 | **sortimo.cz** | https://www.sortimo.cz/ (= "Vestavby do dodávky" homepage) | **ano** | 12 | `vestavba, vestavby do dodávky, vestavba do auta, vestavba do vozidla, regál do auta, regálové systémy, regál, l-boxx, t-boxx, kufr na nářadí, boxy na nářadí, box, kufr` - nejbohatší nalezený seznam, kombinuje obecné + vlastní brand produkty (L-BOXX, T-BOXX). |
| 6 | **bott.cz** | https://www.bott.cz/nas-produkt/vestavby-do-dodavek/vestavby-do-dodavek | ne | 0 | Žádný keywords tag (homepage i kategorie), zato bohatý title+description s brand názvy: "vario3", spolupráce Festool/TANOS/Systainer³. |
| 7 | **do-dodavky.cz** | https://www.do-dodavky.cz/dilenske-vestavby-do-dodavek | ne | 0 | Nejagresivnější **title-stuffing** ze všech: title homepage má ~9 různých frází ("Pojízdné dílny, servisní a montážní vestavby do aut, police, regály a šuplíky do dodávek, podlahy a výdřevy pro užitkové vozidla, střešní nosiče a příčníky, zajištění nákladu"), meta description má 7+ frází oddělených „\|" (i ta je uříznutá "..."). |
| 8 | **univestcz.cz** | https://www.univestcz.cz/ | ne | 0 | Čistý, stručný title+description bez keyword-stuffingu ani keywords tagu. |
| 9 | **wuerth.cz** | https://eshop.wuerth.cz/cs/CZ/CZK | **nedostupné** | - | HTTP 403 i přes WebFetch (Access Denied) - velký B2B e-shop s agresivní anti-bot ochranou, nešlo přečíst vůbec nic. |
| 10 | **dvaptaci.cz** (kategorie) | https://www.dvaptaci.cz/vestavba-auto-dodavka-podlaha-pojizdna-dilna/vestavby-do-aut-vozu-dodavek/k45 | **ano** | 9 | `vestavba, vestavby, vozu, vozidel, auta, servis, pojízdná, dílna, výdřeva` - firma je primárně prodejce manipulační techniky (vysokozdvižné vozíky), vestavby do aut jsou vedlejší sortiment, ale keywords tag mají cíleně nastavený i pro tuhle kategorii. |
| 11 | **volkswagenprestavby.cz** | https://www.volkswagenprestavby.cz/ | ne | 0 | Žádný keywords tag, žádný meta description ani - nejslabší SEO základ ze všech zkoumaných, úzká nika (jen VW užitkové vozy). |

## Souhrn

- **Meta keywords tag používají 3 z 11** (topcentrum.cz, sortimo.cz,
  dvaptaci.cz) - v rozsahu 8-12 frází. Zbylých 6 s ověřeným výsledkem ho
  nemá vůbec (2 weby - regaz.cz, wuerth.cz - se nepodařilo prověřit kvůli
  bot-ochraně).
- I weby BEZ keywords tagu (do-dodavky.cz, bott.cz) běžně pokrývají
  **7-9 variant klíčové fráze přímo v title/meta description** - to je
  skutečně účinná technika (Google title/description čte a používá pro
  hodnocení relevance i pro úryvek ve výsledcích).
- **Nejagresivnější/nejucelenější SEO struktura:** do-dodavky.cz (title) a
  sortimo.cz (keywords + zjevně i obsah stránek, jsou přímý výrobce/
  distributor systému Sortimo).
- **Nejslabší SEO:** volkswagenprestavby.cz (nic - ani description, ani
  keywords), reca.cz a univestcz.cz (žádný keyword-stuffing, ale aspoň mají
  slušný title+description).

## Doporučení pro logiman.cz/konfigurátor

1. Nepřidávat `<meta name="keywords">` jen proto, že to dělá menšina
   konkurence - je to mrtvý signál pro Google, jen kosmetika.
2. Místo toho rozšířit `meta_description` u kategorií o 2-4 příbuzné
   varianty fráze (po vzoru do-dodavky.cz/bott.cz), a totéž vetkat
   přirozeně do textu/nadpisů - **tohle skutečně čtou algoritmy i AI
   vyhledávače (GEO)**.
3. `focus_keyword` (1 hlavní fráze na kategorii) necháváme jako je -
   odpovídá to standardní praxi (Yoast/Rank Math styl - 1 hlavní +
   podpůrné varianty v obsahu, ne v jednom poli).

*(Otevřený bod k rozhodnutí: chce Robert i formálně rozšířit datový model
o pole pro víc "podpůrných" klíčových frází na kategorii, nebo stačí je jen
vetkat do textu/description bez zvláštního pole?)*

## Skutečné pozice v Google Search (5 reálných dotazů, 2026-08-08)

Na žádost Roberta ("nejdřive analyzuj jaké mají kdo výsledky v google
search") - ne jen JAK mají konkurenti nastavené keywords, ale KDE se
skutečně umisťují ve výsledcích vyhledávání. Testováno přes `WebSearch`
(Google) na 5 dotazech odpovídajících našim vlastním kategoriím.

| Dotaz | Kdo se umístil (přibližná pozice) |
|---|---|
| **"vestavby do dodávek"** (obecný) | Žádný z 11 sledovaných konkurentů se NEUMÍSTIL v top 8! Dominují **obytné/kempinkové vestavby** (CZCAMPER #3, Vansafe, JVM Camper, Resl group, WoodVANs, Newagenomads) + Bazoš bazar. rebuild-car.cz #2 (ale to je taky kempinková nika). |
| **"regály do auta hliníková stavebnice"** | **logiman.cz #1, #2, #3, #5** (4 různé stránky logiman.cz na první stránce!) - kaiserkraft.cz #4, alfavaria.cz #8. Žádný jiný sledovaný konkurent. |
| **"pracovní vestavba do dodávky na míru"** | **logiman.cz #1, #2** - autovestavba.cz #3, #9 (nový konkurent, viz níže) - bott.cz #4 - pojizdna-dilna.cz/Storevan #5 - do-dodavky.cz #6, #7 - regaz.cz #10. |
| **"stavebnice do aut hliníkový profil šuplíky"** | **logiman.cz #1, #2, #3, #8** (opět 4 stránky!) - ostatní výsledky jsou obecní dodavatelé hliníkových profilových systémů (kaiserkraft.cz, askmt.com, marek.eu, eprofily.cz, sharplayers.cz, hlinikoveprofilybosch.cz) - žádný z 11 sledovaných "vestavbových" konkurentů. |
| **"vestavba Ford Transit Custom na míru"** | logiman.cz #6 (ale stránka `/ford/` - značková, ne konkrétní model Custom) - autovestavba.cz #7, #9 - zbytek dominují kempinkové/obytné vestavby (JVM Camper, autocaravansport.cz, nomadem.cz) + Bazoš. |

### Zásadní zjištění

1. **logiman.cz (náš vlastní současný web na Shoptetu) už teď silně
   vede** ve výsledcích pro specifické, dlouhé fráze blízké našemu
   vlastnímu obsahu (regály+stavebnice+hliník+šuplíky) - běžně 3-4 různé
   stránky logiman.cz na první stránce výsledků. To je cenné aktivum pro
   plánovaný přechod domény na konfigurátor - nesmí se ztratit (proto
   302/301 přesměrování při migraci, viz TASKS.md).
2. **Obecná fráze "vestavby do dodávek" je z 90 % obsazená kempinkovými/
   obytnými přestavbami**, ne pracovními/servisními vestavbami jako je náš
   byznys. Cílit primárně na tuhle obecnou frázi je neefektivní - lepší
   cílit specifičtější "pracovní/servisní vestavba do dodávky", kde už
   logiman.cz i reální konkurenti (bott.cz, do-dodavky.cz) skutečně
   soupeří o pozice.
3. **Z původních 11 sledovaných domén se ve výsledcích objevily jen 3**:
   bott.cz, do-dodavky.cz, regaz.cz. Zbylých 8 (reca.cz, sortimo.cz,
   topcentrum.cz, univestcz.cz, wuerth.cz, dvaptaci.cz,
   volkswagenprestavby.cz, rebuild-car.cz - poslední jen pro kempinkovou
   frázi) se v těchto 5 dotazech vůbec neobjevily v top 10 - buď necílí na
   tahle přesná slova, nebo jsou v Google pro ně slabší.
4. **Nový, opakovaně se objevující konkurent MIMO původní seznam:
   autovestavba.cz** (3× ve výsledcích, silná přítomnost pro "pracovní
   vestavba"/"Ford Transit" dotazy) - stojí za přidání do sledovaného
   seznamu. Další nové jméno: **pojizdna-dilna.cz / Storevan**.
5. Vedlejší, mimo hlavní obor: **kaiserkraft.cz** (velký průmyslový
   distributor, konkuruje jen v obecné "hliníkový profilový systém" rovině,
   ne přímo vestavbám do aut).

### Doplnění doporučení

- Při migraci na doménu logiman.cz **zachovat/přesměrovat existující URL
  struktura** (aspoň pro stránky, které dnes vedou v žebříčku - `/regaly-
  do-auta/`, `/stavebnice-do-aut/`, `/vestavby-do-dodavek-aut/` a
  podstránky) - jinak riskujeme ztrátu už vybojovaných pozic.
- Přidat **autovestavba.cz** a **pojizdna-dilna.cz** do sledovaného
  seznamu konkurentů.
- Zvážit cílení na specifičtější fráze ("pracovní vestavba do dodávky",
  "servisní vestavba do auta") místo obecného "vestavby do dodávek", kde
  soutěžíme s úplně jinou zákaznickou skupinou (kempink/karavaning).
