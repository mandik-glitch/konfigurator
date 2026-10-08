# Nástěnka: SEO textové vzory italské konkurence (pro budoucí italskou verzi miniwebů)

Krátký zdroj FORMY (ne obsahu) pro texty/metatagy budoucí italské jazykové
verze Fiat/miniwebů. Tři domény vybral přímo Robert (2026-09-17) — mají
dobré výsledky ve vyhledávání, jiné se zatím nezkoumaly (širší automatický
průzkum italské konkurence byl na jeho pokyn zastaven).

**Stejné pravidlo jako u české `SEO_STANDARD_TEXTY_KATEGORII.md`:**
konkurence je vzor FORMY (jak psát title/description, jaké fráze fungují),
NIKDY zdroj OBSAHU — nekopírovat/nepřekládat cizí text 1:1 (riziko
duplicitního obsahu i cizího duševního vlastnictví). Italský text se
skládá podle stejné priority zdrojů jako český: 1) náš výrobní program,
2) co už funguje na logiman.cz/konfigurátoru, 3) schválené texty v DB,
4) forma odkoukaná odsud.

## Přehled (ověřeno přímo z HTML, `curl`, 2026-09-17)

| Doména | `<title>` | `<meta description>` | Poznámka |
|---|---|---|---|
| syncro-system.com/allestimenti-x-furgoni | *Allestimenti per furgoni Syncro System \| Syncro System* | *Con gli allestimenti interni per furgoni e i rivestimenti interni Syncro System puoi trasformare qualsiasi veicolo commerciale in una vera officina mobile.* | Italský výrobce/síť (13 center allestimento v Itálii). Nejbohatší H2 struktura ze tří (rivestimenti interni, allestimenti interni per veicoli commerciali, esempi...). Žádné meta keywords, žádné FAQ. |
| fimesrl.it/allestimento-furgoni | *Allestimento Furgoni* | — (žádný meta description tag; OG: *„Allestimento furgoni su misura"* / *„Progetto su misura in base alle tue esigenze ed al tuo veicolo"*) | Menší/lokální dodavatel, silně staví na frázi „su misura" (na míru) — stejná core myšlenka jako naše `TEXT_FILTR.md` pravidlo 10. |
| wuerth.it/orsymobil | *Allestimento furgoni e veicoli commerciali \| Orsy Mobil* | *Scopri le soluzioni Orsy Mobil per l'allestimento furgoni di tutte le marche. Entra nel sito!* | Značka Würth (velký B2B hráč). CTA styl v description ("Entra nel sito!"), vlastní produktová řada „ORSY®_mobil_" jako brand přímo v title. |

## Klíčové italské fráze (napříč všemi třemi, podle frekvence)

1. **„allestimento furgoni"** — hlavní/nosná fráze u všech tří (obdoba české „vestavby do dodávek" / „regály do auta").
2. **„veicoli commerciali"** (užitková vozidla) — 2 ze 3.
3. **„su misura"** (na míru) — 2 ze 3, přímo odpovídá povinné myšlence z `TEXT_FILTR.md` pravidla 10 ("na míru na milimetr").
4. **„officina mobile"** (mobilní dílna) — 2 ze 3.
5. Produktové termíny: *cassettiere* (šuplíkové skříně), *scaffalature/scaffali* (regály/police), *ripiani* (přihrádky/police), *banchi da lavoro* (pracovní stoly), *rivestimenti interni* (vnitřní obložení), *pianali/pianale rialzato* (zvýšená podlaha).
6. Žádný ze tří nemá `<meta name="keywords">` ani strukturované FAQ — stejný vzorec jako u české konkurence (`SEO_KONKURENCE_NASTENKA.md`: jen 3 z 11 keywords mají, žádný FAQ). → FAQ zůstává naše odlišení i na italském trhu, ne jen na českém.

## Doporučení pro italský title/meta popis (forma, ne obsah)

- Stejná formule jako česká (`SEO_STANDARD_TEXTY_KATEGORII.md`): hlavní fráze na začátku title + 1 specifikující detail; description 1–2 přirozené věty s 2–3 variantami fráze; žádný keyword-stuffing.
- Základní italská fráze: „allestimento furgoni" / „allestimenti per furgoni".
- Náš diferenciátor (hliníkový modulární profilový systém, ne hotový ocelový regál) se v žádném ze tří textů neobjevuje — možná mezera/příležitost, ale ze vzorku 3 domén to nejde tvrdit jistě.
- „Su misura" patří do italské verze stejně závazně jako české „na míru, na milimetr" — konkurence ji používá taky, je to tedy i ověřená zavedená fráze na italském trhu, ne jen náš vlastní vynález.

---
Zdroj: přímé stažení HTML (`curl`, desktop User-Agent), bot7, 2026-09-17,
na výslovné zadání Roberta ("tyto tři weby, jiné nás zatím nezajímají").
