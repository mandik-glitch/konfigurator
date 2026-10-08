# Standard: ideální texty kategorií (title, meta popis, obsah) pro SEO/GEO

Návod, jak psát `meta_title`, `meta_description`, `focus_keyword` a obsah
(`body_html`/`bottom_body_html`) u kategorií produktů — postavený na
reálném průzkumu konkurence, ne na obecných SEO poučkách. Zdroj dat:
`SEO_KONKURENCE_NASTENKA.md` (11+ sledovaných domén, jejich meta
keywords, a 5 reálných Google dotazů s pozicemi).

Založeno bot4, 2026-08-08 (Robert: "vytvoř nový soubor který popisuje
ideální texty titles, meta popisy, obsah kategorií vzhledem ke znalostem
o konkurenci a jejich výsledcích... vyplň podle toho náš eshop").

## Priorita č. 1: náš výrobní program a stávající texty, konkurence až potom

Robert (2026-08-08, doplnění k zadání): "samozřejmě především s ohledem
na náš výrobní program a stávající texty" + "a vzhledem k textům na
logiman.cz" — konkurence dává vzor JAK psát (formát title/popisu, kolik
variant, co funguje v Google), ale NIKDY není zdroj CO psát. Pořadí
priorit zdrojů pravdy o obsahu (od nejdůležitějšího):

1. **Náš vlastní výrobní program** — co Logiman skutečně vyrábí/nabízí,
   žádné vymyšlené tvrzení jen kvůli klíčovému slovu.
2. **Texty už živé na logiman.cz** (dnešní Shoptet web) — logiman.cz už
   pro spoustu těchhle frází reálně VEDE v Google (viz nástěnka, sekce
   "Skutečné pozice") — jeho stávající formulace jsou tedy prověřené,
   ne teoretické, a mají přednost před vymýšlením nové fráze od nuly.
   Kde se dá, přebírat/parafrázovat jejich už fungující znění, ne
   nahrazovat obecnou konkurenční šablonou.
3. **Stávající schválené texty v naší DB** (`body_html`/
   `meta_description` z předchozích session, `logiman_geo_obsah.docx`) —
   neruší se ani nepřepisují od nuly, jen se DOPLŇUJÍ o další variantu
   fráze, pokud v popisu ještě chybí.
4. **Vzor konkurence** (formát/technika, viz níže) — použít až na
   doladění formy, ne obsahu.

## Co jsme se z konkurence naučili

1. **`<meta name="keywords">` nepoužívat.** Google ho ignoruje od 2009,
   žádný ranking efekt. 3 z 11 sledovaných konkurentů ho pořád mají
   (topcentrum.cz, sortimo.cz, dvaptaci.cz), ale je to jen zvyk, ne
   výhoda — nekopírovat.
2. **Víc variant fráze patří do title a meta description, ne do
   samostatného pole.** do-dodavky.cz a bott.cz nemají keywords tag
   vůbec, ale nacpou 7-9 variant klíčové fráze přímo do title/popisu
   (`"Dílenské vestavby do aut | Pojízdné dílny do dodávek | Servisní
   vestavby do dodávek | ..."`). Google title/description skutečně čte a
   používá pro relevanci i úryvek ve výsledcích.
3. **Ale ne mechanicky nacpat — psát přirozeně.** Čistě pipe-separated
   seznam skoro identických frází (do-dodavky.cz styl) je z pohledu
   moderního SEO (Google "helpful content" hodnocení) i GEO (AI
   vyhledávače preferují přirozený jazyk, ne seznam klíčových slov)
   riskantní — může to vypadat jako keyword-stuffing. Cíl: 2-4 PŘÍBUZNÉ
   varianty přirozeně vetkané do jedné souvislé věty/dvou vět, ne seznam
   oddělený znaky.
4. **Cílit na specifické, ne obecné fráze.** Reálný Google test ukázal,
   že obecná fráze "vestavby do dodávek" je z 90 % obsazená kempinkovými/
   obytnými přestavbami (jiná zákaznická skupina) — v top 8 se
   NEUMÍSTIL žádný z 11 sledovaných "pracovních" konkurentů. Naopak pro
   specifické fráze jako "regály do auta hliníková stavebnice" nebo
   "stavebnice do aut hliníkový profil šuplíky" **logiman.cz už teď
   silně vede** (3-4 stránky na 1. straně). → Vždy zahrnout specifikující
   slovo (materiál, typ, značka, systém), ne jen obecné "vestavba do
   dodávky".
5. **Chránit existující pozice.** logiman.cz má vybojované pozice pro
   dlouhé fráze blízké dnešnímu obsahu — texty NEMĚNIT tak razantně, aby
   zmizela klíčová slova, kvůli kterým dnes vede (hliník, stavebnice,
   šuplíky, regály, systém, konkrétní modely vozidel).
6. **FAQ a interní prolinkování = GEO zlato.** Strukturovaný FAQ formát
   (otázka → přímá odpověď) je přesně to, co AI vyhledávače/odpovědní
   enginy nejsnáz extrahují a citují. Žádný ze sledovaných konkurentů
   FAQ nemá (aspoň ne strukturovaně) — je to naše odlišení, ne kopie
   konkurence.

## Formule pro `meta_title`

```
{Hlavní fráze (focus_keyword rozepsaný)} — {1 specifikující detail}
```

- Do ~60 znaků (delší se v SERP ořízne).
- Hlavní klíčové slovo na začátku (přednost při skenování).
- Specifikující detail = materiál/systém/rozměr/značka vozidla — ne
  obecné slovo navíc.
- Bez značky "| Logiman" jako povinné přípony — jen tam, kde title bez
  ní zní příliš obecně (u vlajkových/rodičovských kategorií).

Příklad (už použito, potvrzeno funkční): *"Systém 30 — šuplíky do auta
s nosností 20–25 kg"* — hlavní fráze "Systém 30" + specifikace "šuplíky
do auta s nosností 20-25 kg" (číslo = konkrétní, důvěryhodné, odlišuje
od konkurence).

## Formule pro `meta_description`

```
{1 věta: co to je, s hlavní frází a 1. specifikující variantou}.
{1 věta: 2-3 další přirozeně našroubované varianty/kontext (materiál,
kompatibilní vozidla, systém) — NE seznam oddělený „|“}.
```

- 140-160 znaků (Google ořízne kolem 155-160).
- Aspoň 2, ideálně 3 odlišné formulace stejného tématu v přirozené
  větě (např. "regály do auta" + "hliníková stavebnice" + "vestavba na
  míru" v jedné popisce, ne 3× to samé slovo).
- Konkrétní čísla/fakta (nosnost, rozměr, rok, homologace HP-0579) —
  zvyšují důvěryhodnost i CTR, konkurence (bott.cz, do-dodavky.cz) to
  dělá důsledně.

## `focus_keyword`

Zůstává **1 hlavní fráze** (standardní praxe SEO nástrojů typu Yoast/
Rank Math — jedno primární + podpůrné varianty v obsahu, ne v
samostatném poli). Podpůrné varianty se nezapisují do žádného
speciálního pole — žijí v `meta_description` a v textu/nadpisech.

## Struktura obsahu kategorie (`body_html` / `bottom_body_html`)

Nemění se vzor zavedený 2026-08-08 (viz commit `94cb670`):

1. **`body_html`** — 1-3 odstavce: co produkt/kategorie je, pro koho,
   jaké modely/systémy podporuje, konkrétní čísla. Zachovat existující
   fotogalerie (`plus-gallery-wrap` bloky), jen před ně vložit text.
2. **`bottom_body_html`** — FAQ (otázka tučně, odpověď pod ní) + odstavec
   "Související stránky" s interními odkazy na `/kategorie/...`.

## Co konkrétně změnit u dnešních 25 kategorií

Meta popisy dnes typicky obsahují jen 1 hlavní frázi. Rozšířit každý o
1-2 další přirozené varianty (viz aplikační skript, který tenhle
dokument doprovází) — beze změny `body_html`/`bottom_body_html`/
`focus_keyword`, protože ty už odpovídají bodu 6 výše.
