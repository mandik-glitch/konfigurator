# SEO/GEO audit — strom kategorií a produktů (vandrawee.cz)

Založeno bot12, 2026-08-18 na zadání Roberta (přes bot3): projít celý
strom kategorií konfigurátoru (`content_categories`, `shop_products`)
a udělat SEO (klasické vyhledávače) + GEO (Generative Engine
Optimization — jak si stránku "přečte" AI asistent/vyhledávač, ne jen
Google) audit. Metoda: systematicky, kde možné přes DB dotaz/skript,
ne namátkovým klikáním — přesně podle zadání. `webapp/scene.html`
a vše kolem 3D scény vědomě nedotčeno.

**Rozsah dat**: 119 kategorií (9 top-level), 730 produktů (651
aktivních). Zdroj: přímý dotaz do produkční DB + živé ověření
vykreslené HTML odpovědi (`curl` přes unix socket, bez JS) u reálných
stránek.

**Tohle je ČISTĚ ANALÝZA — nic z toho není opraveno.** Čeká na
schválení bot3/Robertem.

---

## Jak číst tenhle dokument

Nálezy podle **kategorie**, uvnitř podle **závažnosti** (vysoká →
nízká), `soubor:řádek` kde relevantní. Než čtete nálezy, důležitý
kontext: **existující infrastruktura je na tomhle projektu překvapivě
už docela vyspělá** — SSR meta tagy, canonical, JSON-LD, sitemap.xml i
robots.txt jsou promyšlené a fungující (viz sekce "Co už funguje
dobře" na konci). Nálezy níže jsou mezery/regrese v rámci tohohle
už existujícího systému, ne "od nuly nic není".

---

## 1. SEO — VYSOKÁ závažnost

### 1.1 `api/app.py` (`_product_page_response`) — H1, breadcrumb a popis produktu se NIKDY nerenderují serverově — na všech 730 produktových stránkách

**Živě ověřeno** (`curl` na `/produkt/uhelnikova-spojka-30x30` bez
JS): syrová HTML odpověď obsahuje `<h1 class="pd-title"
id="pdTitle">Načítám…</h1>` (`webapp/product.html:872`) — doslova
"Načítám…", ne název produktu. Stejně tak breadcrumb
(`webapp/product.html:871`) a popis produktu (`#pdDesc`,
`webapp/product.html:923`) zůstávají prázdné/placeholder v prvotní
HTML odpovědi — vyplní je až klientský JS po `fetch("/api/products/
<id>")`.

**Přitom identická technika u kategorií už existuje a funguje** —
`_category_page_response` (`api/app.py:4480-4482`) má přesně tenhle
SSR fix explicitně "kvůli robotům, kteří JS nevykonávají" (komentář
tamtéž), ale u produktové stránky (`_product_page_response`,
`api/app.py:4279-4387`) žádný `body_replacements` pro H1/breadcrumb/
popis vůbec neexistuje — jen `<head>` (title/meta/canonical/JSON-LD)
je serverově vyplněný, tělo stránky ne.

**Dopad**: `<title>` a JSON-LD `Product` v hlavičce SICE obsahují
správný název/cenu (viz sekce "Co funguje"), ale **hlavní obsah
stránky (H1, popis, breadcrumb) je pro každého robota/AI asistenta,
co nevykoná JS, prázdný nebo "Načítám…"** — to je přesně ten GEO
scénář ze zadání ("jasnost faktického obsahu... vyjádřené strojově
čitelně, ne jen v obrázku/JS"). Google to částečně zachraňuje
"druhou vlnou" indexace (spustí JS dodatečně), ale řada GEO/AI
crawlerů (a rychlé LLM-based scrapery) druhou vlnu nedělá vůbec.

**Oprava** je přímočará — stejný vzor jako category.html, jen
aplikovaný na `product.html`: `body_replacements['<h1 class="pd-title"
id="pdTitle">Načítám…</h1>']`, breadcrumb div, `#pdDesc` — všechna
data (`row["name"]`, `chain`, `desc`) v `_product_page_response` už
jsou dostupná, jen se nepoužívají na tělo stránky.

### 1.2 `shop_products.meta_title`/`meta_description` — mrtvé sloupce, admin UI klame uživatele

DB dotaz: **0 ze 730 produktů** má tyhle sloupce vyplněné. Napřed to
vypadalo jako "730 chybějících popisků", ale skutečný problém je
horší: **`_product_page_response` (`api/app.py:4279-4387`) tyhle
sloupce vůbec nikdy nečte** — `og["title"]`/`og["description"]` se
VŽDY generují dynamicky z `name`+cena (řádek 4297, 4326), bez ohledu
na to, co je v DB.

Přitom `webapp/admin.html:12466-12467` má u skladové karty pole
popsaná přesně "SEO titulek (title)" / "SEO popis (meta description)"
(`api/app.py:3703-3704`, `api/products.py:248,885-887,1566` write
cestu), která se ukládají do DB (`api/products.py`), ale **nemají
ŽÁDNÝ efekt na skutečnou stránku**. Kdokoli v adminu vyplní tohle pole
v domnění, že řídí SEO titulek produktu, dostane naprosto stejný
auto-generovaný text jako předtím — tichý, nikde nehlášený rozpor
mezi tím, co admin nastaví, a tím, co se reálně vyrenderuje.

**Buď** propojit `_product_page_response` s těmito sloupci (fallback
na auto-generaci, když prázdné — stejný vzor jako u kategorií, viz
`api/app.py:4411,4415`), **nebo** pole z admin UI odstranit, ať
nikoho neklame. První varianta je hodnotnější (umožní ruční doladění
SEO textu u klíčových produktů).

## 2. SEO — STŘEDNÍ závažnost

### 2.1 `webapp/index.html` — homepage nemá ŽÁDNÝ `<h1>`

Grep na `<h1` v celém souboru — nic. Jediný nadpis na homepage je
`<h2 class="sidebar-title">Kategorie</h2>` (řádek 741) u bočního menu,
což sémanticky patří k navigaci, ne k hlavnímu obsahu. Homepage je
nejčastěji nejsilnější stránka webu z pohledu autority/klíčových
slov — chybějící H1 je základní, snadno opravitelná chyba.

### 2.2 Chybí `Organization`/`WebSite` schema.org — nikde na webu

`grep -rn "Organization\|WebSite" api/*.py` — nic. Existuje JSON-LD
`Product`, `BreadcrumbList`, `CollectionPage` (viz "Co funguje"), ale
žádné schema, které by AI asistentovi/vyhledávači řeklo "kdo je tenhle
web/firma" (název firmy, logo, kontakt, sídlo — ideálně na homepage
nebo site-wide). Relevantní hlavně pro GEO ("koho doporučit" dotazy)
i klasické SEO (Knowledge Panel).

### 2.3 Chybí laterální prolinkování mezi příbuznými kategoriemi

Prošel jsem `category.html`/`api/app.py` render logiku — kategorie
odkazují jen na přímé rodiče/děti (breadcrumb + `#subcatsList`), žádné
"související kategorie" mezi sourozeneckými/vzdálenějšími uzly stromu
(např. kategorie "Trubky" by mohla odkazovat na "Kolena a tvarovky",
i když nejsou v přímé rodič-dítě vazbě). Snižuje to prostupnost
crawleru napříč stromem mimo hierarchii a omezuje interní PageRank
tok mezi tematicky blízkými, ale stromově vzdálenými kategoriemi.

## 3. SEO — NÍZKÁ závažnost

### 3.1 96 % aktivních produktů (623/651) nemá `short_description`

Meta popis pak padá na auto-generovaný fallback `"{název} –
{kategorie}. Cena: X Kč."` (`api/app.py:4312-4326`) — funkční
(nikdy prázdný, viz "Co funguje"), ale generický/formulaický u drtivé
většiny katalogu, ne skutečně popisný text. Nejde o chybu, spíš
o objem ruční práce, kterou by stálo za to postupně doplňovat
u nejnavštěvovanějších produktů.

### 3.2 CSS 100 % inline na každé stránce (~30 % velikosti odpovědi)

Živě změřeno na `/produkt/uhelnikova-spojka-30x30`: odpověď 190 441
bytů, z toho `<style>` blok 57 487 bytů (30 %). Stejný vzor je
i u `category.html`/`index.html` (identický `<style>` blok kopírovaný
do KAŽDÉ HTML odpovědi). Protože styl není v externím `.css` souboru,
prohlížeč ho nemůže cachovat napříč navigací — každá stránka znovu
stahuje totožných ~55-60 KB. Ovlivňuje rychlost načtení (Core Web
Vitals → nepřímo i SEO ranking), víc na mobilu/pomalejším připojení.
Přesun do externího cachovaného `.css` by byl čistě technická úprava
bez rizika pro UX.

### 3.3 1 aktivní produkt bez slugu → spadá na `?id=` URL v sitemapě

Zanedbatelné množství (1 z 651), ale `_product_rel_url()`
(`api/app.py:4243-4244`) padá na `/product.html?id=X` pro produkty
bez slugu, což se pak dostane i do `sitemap.xml` — query-string URL
v sitemapě je obecně slabší signál než čistý slug. Snadná oprava
(doplnit slug u 1 produktu).

## 4. GEO — STŘEDNÍ závažnost

### 4.1 Product JSON-LD neobsahuje fyzické rozměry

`product_ld` (`api/app.py:4350-4358`) má `name`/`sku`/`description`/
`image`/`url`/`offers` (cena+dostupnost), ale **ne rozměry** — přitom
`shop_products.length_mm`/`width_mm`/`height_mm` v DB existují a jsou
u profilového/deskového sortimentu klíčové nákupní kritérium.
Schema.org `Product` podporuje `width`/`height`/`depth` jako
`QuantitativeValue` právě pro tenhle účel. Bez toho musí AI asistent
odpovídající na dotaz "jaké má rozměry produkt X" spoléhat na to, že
se mu podaří přečíst číslo z JS-vykresleného textu (viz 1.1) — ne
z jasně strukturovaných dat.

### 4.2 (Průnik s 1.1) Chybějící SSR těla produktové stránky je i GEO problém

Zmíněno v sekci 1, ale stojí za zdůraznění zvlášť z GEO úhlu: AI
asistent odpovídající v reálném čase na dotaz o konkrétním produktu
typicky NEspouští plný headless prohlížeč s JS (na rozdíl od Google
"druhé vlny") — pro něj je `<h1>Načítám…</h1>` a prázdný popis
doslova to, co "produkt je". JSON-LD v hlavičce částečně mitiguje
(cena/dostupnost jsou tam), ale ne kompletně (chybí rozměry, viz 4.1,
a delší popisný text je jen v `<meta description>`, ne v těle).

## 5. Co už funguje dobře (kontext, ať nálezy nepůsobí jednostranně)

Existující SEO/GEO infrastruktura je promyšlenější, než by se čekalo
— stojí za vyzdvižení, aby oprava navázala na existující vzory, ne je
znovu vynalézala:

- **Kategorie mají kompletní SSR**: H1, breadcrumb, podkategorie,
  úvodní/spodní text, celá mřížka produktů — vše vyplněné přímo
  v prvotní HTML odpovědi, s explicitním odůvodněním v komentářích
  ("kvůli robotům... GEO/AI enginy berou první odstavec jako
  shrnutí" — `api/app.py:4472-4479,4518-4523`). 118/119 kategorií má
  vyplněný `meta_title`/`meta_description` (99 %) a existuje i
  automatická QA kontrola na chybějící popis (`api/qa_checks.py:467`,
  aktivní od 2026-08-10).
- **Canonical tagy**: správně nastavené na "čistou" URL i při přístupu
  přes `?id=`/`?slug=` variantu (žádný duplicate-content konflikt).
- **JSON-LD**: `Product`+`Offer` (cena, dostupnost s promyšleným
  fallbackem na `availability_text`, ne naivní `stock_qty>0`),
  `BreadcrumbList`, `CollectionPage` u kategorií — všechno přítomné a
  validní.
- **`robots.txt`/`sitemap.xml`**: promyšlené (např. vědomé rozhodnutí
  NEBLOKOVAT `?id=` varianty, ať canonical tag může dělat svou práci
  — `api/app.py:4803-4810`), sitemap pokrývá kategorie i aktivní
  produkty s `lastmod`/`priority`.
- **Obrázky v mřížce kategorie**: mají `alt` s názvem produktu/
  kategorie, `loading="lazy"`.
- **Odpovědi jsou rychlé**: kategorie ~340 ms, produkt ~390 ms přímo
  ze serveru (bez CDN) — není to důvod ke starosti, spíš CSS
  duplicita (3.2) je jediný reálný váhový problém.

---

## Doporučené pořadí řešení

1. **1.1** SSR H1/breadcrumb/popis na produktové stránce — nejvyšší
   dopad (730 stránek), technika už existuje, jen se přenese.
2. **1.2** Propojit `shop_products.meta_title/meta_description` se
   skutečným renderem (nebo pole odstranit) — zavádějící admin UI.
3. **2.1** Doplnit `<h1>` na homepage.
4. **4.1** Přidat rozměry do `Product` JSON-LD — malá změna, přímý
   GEO přínos u katalogu, kde rozměr je klíčové kritérium.
5. **2.2** Přidat `Organization`/`WebSite` schema (site-wide, stačí
   jednou na homepage nebo globálně).
6. **2.3** Zvážit laterální prolinkování příbuzných kategorií.
7. **3.2** Přesunout inline CSS do externího cachovaného souboru —
   větší technická práce, nižší naléhavost.
8. **3.1, 3.3** Průběžné doplňování obsahu (short_description,
   1 chybějící slug) — nízké riziko, nízká naléhavost, spíš úkol na
   pozadí než jednorázová oprava.
