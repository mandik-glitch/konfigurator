# Hilti kufr 2-tools (S) SF/SI prázdný (2329229) – poznámky k modelu

Model: `kufr_2329229.mjs` (+ `p2329229_zaklad.mjs` loft/polygony, `p2329229_skorepina.mjs` skořepina z dat, `p2329229_data.mjs` data z fotografie c01), sestavení `node kufry_hilti/vytvor.mjs 2329229` → `modely/2329229.glb` (32 dílů, ~4 500 trojúhelníků, obálka 395 × 495 × 149 mm, odchylka 0/0/0 mm). Náhled `nahled/2329229.html`, srovnání `kufriky_cloud/srovnani/2329229/`.
Souřadnice: X = hloubka 395 (čelo s madlem a západkami do +X), Y = délka 495, Z = výška 149 (víko nahoře), počátek ve středu obálky. Katalog hilti.cz: 495 × 395 × 149 (D × Š × V), vnitřní rozměry a hmotnost hilti.cz neuvádí.
Zadání (Robert): hlavní je ZAVŘENÁ verze a vnější pohled; **vnitřek zjednodušen, nedokončeno**. Víko = skupina `vicko`, pivot na pantové hraně (x = −190, z' = 88), `extras.osa = [0,−1,0]`, `max_uhel = 135`; `--pose vicko=135.7` odpovídá fotografiím c02–c04.

## Fotografie (jen čteny ze scratchpadu, v repu nejsou; URL v `../fotky_url_vlna2.tsv`)
| soubor | pohled | použití |
|---|---|---|
| c01 (L128480, 1200×974) | **pohled shora** na zavřený kufr, čelo (madlo, západky) nahoře | půdorys (silueta), reliéf víka, logo; porovnání `celo` |
| c02 (L128481, 902×1200) | shora, otevřený, víko ~136° | kamera z 4 bodů (okno madla) + obrys, porovnání `otevreny-c02` |
| c03 (L128481_compartments) | totéž s číslovanými kroužky přihrádek | `otevreny-c03` |
| c04 (L128482, 899×1200) | totéž s vloženým nářadím (SID 6-22, SF 6H-22, nabíječka C 6-22) | `otevreny-c04` |
Žádná fotografie nemá kóty ani boční/zadní/spodní pohled.

## Změřeno (z c01; px → mm: 495/1199 vodorovně, 395/973 svisle, silueta normalizována na obálku katalogu; ±1,5 mm)
- Půdorys (silueta zavřeného kufru) včetně zkosených předních rohů, širšího pásu uprostřed (±2,6 mm v délce cca 117 mm hloubky) a zkosených zadních rohů. Silueta fotografie je 1200 × 974 px = poměr 1,232 proti katalogu 495/395 = 1,253 (−1,7 %); normalizováno na katalog.
- Okno madla (průchozí výřez u čela): obrys výřezu a okna v c01 px (okno 417–783 px nahoře, 477–723 dole, výška 56 px), černá příčka madla (px 352–848 × 4–83), šedý límec a černý vnitřní lem.
- Západky: černé bloky px 113–279 × 12–89 (vlevo, vpravo zrcadlově), kapsy 900..1100 px.
- Plató a drážka s logem: hrany jasových přechodů v c01 (přední plató od py ~160/205, drážka py ~310–598, zadní plató od py ~650, zadní svahy py ~815–935).
- Nopy (stohovací výstupky) px 55–215 × 223–287 a 750–812; logo HILTI: písmena H I L T I jako obdélníkové obrysy z masky bílé barvy (px 141–1057 × 414–541, tj. 378 × 51 mm).
- Okno madla vidět skrz kufr i v c02–c04 (oba půlky mají výřez); kontrola: šířky hran okna v c02 odpovídají c01 (151 / 101 mm vs. 144 / 108 mm z fotografie, rozdíl dán perspektivou).

## Výsledky porovnání (IoU obrysu; `nastroje/srovnej_vse_2329229.sh`)
| pohled | IoU | poznámka |
|---|---:|---|
| `celo` (c01, pohled shora, téměř ortografický, render oříznut na obrys a roztažen na rozměr fotografie jako u PKC 35) | **0,985** | rozdíl obrysu jen v okolí rohů a madla |
| `otevreny-c02` | 0,954 | kamera z ručních bodů + obrys (`nastroje/fit_lm.mjs --pose-fix`), víko 135,7° |
| `otevreny-c03` | 0,955 | totéž (stejný záběr s kroužky; maska bez rozlišení barev, kroužky leží uvnitř) |
| `otevreny-c04` | 0,954 | totéž (s nářadím; nářadí leží uvnitř obrysu) |
Dvojice fotografie | model | překryv byly prohlédnuty (čelo: madlo, okno, západky, nopy, logo, plató; otevřený: víko, pant, rám madla). Kamera otevřených pohledů je odhad (ohnisko se vyladilo, ne změřilo; fov ≈ 29°, elevace ≈ 82°), IoU zahrnuje i chybu kamery a úhlu víka (úhel a elevace jsou částečně zaměnitelné; použit společný úhel 135,7° pro všechny tři fotografie). Okno madla se v maskách fotografií c02–c04 vyplňuje (je obklopeno rámem), model má skutečný otvor – to drží IoU o ~1 % níž.

## Odhad (z fotografie nezjistitelné, odhadnuto)
- **Všechny svislé míry:** poloha dělicí spáry (z' = 88, spodní díl 88 mm / víko 61 mm), výška desky víka (z' = 140), plató (146) a nopů (149, tj. obálka 149 z katalogu), hloubka drážky s logem (6 mm), sklon svahů plató, zaoblení horních hran víka (7 mm × 8–11 mm) – boční pohled neexistuje. Odstín světlých/tmavých pásů v c01 jsem vyložil jako svahy (světlý = svah dolů k čelu/po boku, tmavý = svah dolů k zádi); tvar „drážka mezi dvěma plató" z toho plyne, ale je to **výklad stínování**, ne měření.
- Výška černé příčky madla (z' 80–120), výška a tvar západek (bloky z' 88–138 s úkosem 3 mm), líc límce okna (z' 83–87 ve spodním dílu, 128–132 ve víku), tloušťka stěn (3 mm), dno (3 mm).
- Pant: 7 úseků po ~69 mm, válec r = 5,2 mm, osa x = −190, černý kolík; podle c02 (viditelné články na hraně) – počet a rozměr článků z c02 odečten jen přibližně.
- Přesná dvojice „horní madlo ve víku + dolní madlo ve spodním dílu": pohled shora ukazuje jen horní příčku; spodní příčka (grip, c02 dole) je modelována jako samostatná černá příčka pod ní.

## Neověřeno / zjednodušeno
- **Vnitřek:** dutina je hladká (stěna 3 mm); v základně je místo tvarované vložky **hladká černá deska bez kapes** (z' 3–82, `vlozka_zjednodusena`), kapsy podle c02/c03 (5 přihrádek, číslované 1–3) **nejsou**. Vnitřek víka je hladký (chybí žebra, příčky, výřezy kolem západek viditelné v c02). Zaoblení uvnitř neověřeno.
- **Spodek, zadní strana, boky:** na fotografiích nejsou. Chybí nožky, spodní žebrování, odlitkové detaily boků; zadní hrana a pant jen přibližně.
- **Západky jsou v modelu součástí víka** (skupina `vicko`, aby se při otevření neprotínaly s kapsou); ve skutečnosti patří spodnímu dílu a zaklapávají na víko. Pohyb západek ani drátů nemodelován.
- Drobné detaily nemodelovány: texturování povrchu (zrno), nápisy na západkách („HILTI"), vyražený text na dně, malé oko v rámu okna, jemné žebrování víka kolem západek a kapes (vidět v c02).
- Materiály: červená `cervena` (shoduje se s lineární hodnotou ze světlých míst c01 ≈ 0,55–0,66), černá `cerna`/`cerna_mat`, šedý límec `seda_svetla`, logo `logo_bila` (doplněno za běhu v `p2329229_skorepina.mjs`, `glb.js` beze změny). Hodnoty ze vzorků fotografie (červená ~ sRGB 190–210/32/44), bez kalibrace osvětlení.

## Poměr k modelu 2294834
Oba kufry mají podle hilti.cz stejné vnější rozměry, ale reliéf víka na fotografiích **není shodný** (viz `2294834_poznamky.md`) – proto jsou dva datové soubory nad společným kódem skořepiny.
