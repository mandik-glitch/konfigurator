> **Pozn. 2026-10-07:** Robert změnil název webu (logo) na „Hliníkový konstrukční stavebnicový systém s drážkami“; všude níže, kde je starý název „… pro užitková vozidla“, platí nový (realizuje bot16).

# Hlavní web autovestavby.logiman.cz: GEO a SEO doplňky (bot7, 2026-10-05, NÁVRH, nic se nenasazuje)

Zdroj stavu: audit z 2026-10-05 (živé stránky + DB). Kód (`api/app.py`, `webapp/*`) je hlídaný, zapsat ho má bot16/bot9. Texty a data níže jsou připravená k vložení.

## 1. Organization JSON-LD na všech stránkách (dnes jen název-slogan a url)
Dnes `api/app.py` (~ř. 3111) posílá `"name": "Hliníkový stavebnicový systém pro užitková vozidla"` a `url`; podrobnější verze je jen na `/kontakt.html` (`api/company_info.py`). AI vyhledávače potřebují právní název a identitu na každé stránce. Navržený obsah (údaje z `company_info`, DB tabulka firmy; nic nového):
```json
{"@context":"https://schema.org","@type":"Organization",
 "name":"LOGIMAN s.r.o.",
 "legalName":"LOGIMAN s.r.o.",
 "alternateName":"Hliníkový stavebnicový systém pro užitková vozidla",
 "url":"https://autovestavby.logiman.cz",
 "telephone":"+420 603 230 059",
 "address":{"@type":"PostalAddress","streetAddress":"Husinecká 903/10","postalCode":"130 00","addressLocality":"Praha","addressCountry":"CZ"},
 "identifier":"IČO 28337638",
 "vatID":"CZ28337638"}
```
`logo` se doplní jen po rozhodnutí, který soubor je „ten pravý“ (nevymýšlím). `WebSite.name` nechat, doplnit `"inLanguage":"cs"`. Žádný e-mail (pravidlo: žádný živý e-mail na webu).

## 2. Domovská stránka – title, meta, H1 (potřebuje Robertovo schválení zaměření)
Dnes: title/H1/og:site_name = „Hliníkový stavebnicový systém pro užitková vozidla“, meta: „Navrhněte si konstrukci z hliníkových profilů ve 3D konfigurátoru Logiman.“ (74 znaků, jen vozidla, slovo „konfigurátor“).
Web ale nabízí i profily a spojovací prvky, balicí/montážní/ergonomické stoly a generátory stolů. Návrh:
- **title** (51 zn.): `Hliníkové profily, pracovní stoly a vestavby do aut`
- **meta description** (157 zn.): `Hliníkový stavebnicový systém: profily a spojovací prvky, balicí a montážní stoly na míru a vestavby do dodávek. Navrhněte si konstrukci ve 3D a poptejte ji.`
- **H1** (viditelný, ne jen logo): `Hliníkový stavebnicový systém: profily, stoly a vestavby na míru`
- og:site_name zůstává název značky; slogan „pro užitková vozidla“ zachovat jako podtitul (nechci rozbít pozice pro vozidla).
Důvod pro schválení: je to změna zaměření hlavní stránky, kterou zadal Robert (2026-08-09 zrušil hero sekci).

## 3. FAQ na hlavní stránce (GEO: otázka, přímá odpověď; jen ověřená fakta)
1. **Co Logiman vyrábí?** Hliníkový stavebnicový systém: profily a spojovací prvky, pracovní, balicí a montážní stoly na míru a vestavby do dodávek podle potřeb zákazníka.
2. **Mohu si stůl navrhnout sám?** Ano. Pro balicí stoly je na webu generátor: stůl z profilu 30×30 (system 30) nebo 40×40 (system 40), šířka 500 až 3000 mm, hloubka 400 až 1500 mm, náhled ve 3D.
3. **Je montáž povinná?** Ne. Montáž je volitelná služba a zákazník může konstrukci montovat svépomocí. Cena dopravy se mění podle toho, zda si montáž zvolíte; určí ji pracovník po objednávce a před vystavením zálohové faktury ji potvrdíte.
4. **Jak probíhá platba?** Platba je předem na základě zálohové faktury; objednávat lze jako host, bez účtu.
5. **Jak dlouho trvá výroba stolu?** Stůl se vyrábí na objednávku, u generátorových stolů je dodací lhůta 3–5 týdnů.
6. **Dělají se vestavby do dodávek na míru?** Ano, vestavba se vyrábí na míru podle toho, co zákazník vozí (nářadí, kufry, materiál); montáž zahrnuje vrtání do zpevněných částí karoserie v souladu s požadavky na homologaci.
Pozn.: věty 3–5 odpovídají textům schváleným Robertem 2026-10-04; věta 6 pravidlům 9/9a TEXT_FILTR. Doporučuji FAQ i jako JSON-LD `FAQPage` (texty musí být doslova stejné jako viditelné).

## 4. `llms.txt` (404 dnes)
Soubor `https://autovestavby.logiman.cz/llms.txt` (viz `docs/llms_txt_navrh.txt`): stručný popis webu a odkazy na hlavní kategorie, sitemapu a kontakt. Servírovat staticky (nginx `location = /llms.txt`, vhost `logiman-autovestavby`), `Content-Type: text/plain; charset=utf-8`. Nepovinný standard, nic nerozbije.

## 5. Další GEO mezery (stav)
- AI boti nejsou v `robots.txt` blokováni (v pořádku). `sitemap.xml` 901 URL (v pořádku).
- Produktové meta: 684 z 788 aktivních produktů nemá vlastní meta popis a dostávají šablonu „Název – kategorie. Cena: X Kč“. Funkční, ale generické; rozšíření je samostatný úkol (stovky produktů, texty z DB parametrů), neřeším teď.
- Google Search Console: sitemapa pravděpodobně neodeslána (v lozích žádný dotaz Googlebota na `/sitemap.xml`).
