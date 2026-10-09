# Zadání pro cloudového bota: čelní strana organizérů PACKOUT (první cloudový test)

Zadal Robert (majitel), 2026-10-09, doslova: *„Čelní stranu organizérů John nezvládá, ať to dotáhne cloudový bot jako první test.“*

## Co je hotovo (od bota John, OpenAI)
Pět organizérů Milwaukee PACKOUT (SKU 4932471064, 4932464082, 4932471065, 4932478625, 4932498323) jako 3D modely 1:1 (GLB, mm). Poslední verze je **v6** (`nahled-modely-v6/`, generátor `vytvor_doladene_tvary_v6.js` + `geometrie_organizery_v6.js`, popis `README_doladeni_v6.md`, měření `mereni-tvar-v6/`, fotografie jen jako odkazy v `zdroje/fotografie.csv|json`).

## Co je špatně (Robertovými slovy, v chronologickém pořadí)
- „Vyřiď mu, že chceme reálný tvar, ne jen obálku.“
- „John nech znovu doladí modely 3D kufrů, jsou tam ještě slabé místa, trčící prvky, potřebuje asi více fotografií najít na netu.“
- „Některý typ tam má divné trčící plochy z čela kufru“ (screenshot `podklady_robert/robert_kufr_trcici_plochy_2026-10-07.png`).
- „To podstavné plošky jsou posunuté mimo kufry jakoby.“ — „první 3 organizéry“.
- „Pořád mu tam něco vykukuje, ať si najde další fotky, další úhly pohledu a ty organizéry spraví.“
- „Zatím nech se věnovat zpátky kufříkům, organizérům, které nejsou pořád podle skutečnosti.“
- 2026-10-09: čelní strana organizérů pořád nesedí na skutečnost, John ji nezvládá.

## Úkol
1. Pro KAŽDÝ z pěti organizérů zkontroluj **čelní stranu** (čelo víka i spodního dílu, zámek/západka tvaru C a červené pouzdro úchopu, držadlo, čelní vybrání, rohy, hrany, vnější žebra a prolisy, přechod víko–dno) proti fotografiím z odkazů v `zdroje/fotografie.csv` (jen čtení z internetu; fotky se stahují jen pro vlastní měření a NEukládají se do repozitáře).
2. Najdi další fotografie a úhly čela (zepředu, šikmo zepředu, zblízka zámek a držadlo, otevřený/zavřený stav), zapiš odkazy do `zdroje/` (jen URL, ne soubory).
3. Oprav geometrii čela v generátoru (nová verze **v7**, v6 nech beze změny) tak, aby tvar sedal na fotografie (rozdíl > 2 mm nebo viditelný tvarový rozdíl = chyba); nic nevykukuje mimo obrys než to, co fotografie ukazují; rozměry proti zdroji beze změny.
4. Vyrenderuj pro každý organizér dvojice „fotografie (odkaz) vs. náš model“ ze stejného úhlu (čelo, šikmo čelo, bok) a ulož je do `srovnani-v7/` (vlastní rendery, ne cizí fotografie).
5. Napiš `README_v7.md`: co neodpovídalo, jak opraveno, co zůstává neověřeno (poctivě).
6. Vše na novou větev `cloud/kufriky-v7`, žádný push do `main`, žádné nasazení.

## Úsilí (Robert: „Nastav maximální úsilí“)
Pracuj s MAXIMÁLNÍM úsilím a důkladností: pro každý organizér udělej úplné srovnání se všemi dostupnými fotografiemi, opakuj render–porovnání–oprava, dokud rozdíl nezmizí, nespokojuj se s prvním přijatelným výsledkem, a před odevzdáním znovu zkontroluj všech pět typů ze všech pohledů. Nic nehádej; co nelze ověřit z fotografií, poctivě označ „neověřeno“.

## Pravidla (povinná)
- Návrh pro Roberta: nic se nenasazuje a nepředává dál, dokud to Robert neschválí.
- Žádné účty, formuláře ani zprávy; internet jen ke čtení. Žádná hesla ani přístupy.
- Do výstupů nesmí jít jméno dodavatele původní knihovny karoserií.
- České texty, stručně.
