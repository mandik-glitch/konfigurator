-- SEO audit kategorickeho stromu (bot6, 2026-08-03).
-- Robert: "predevsim zabojovat v oblasti: pracovni vestavby do dodavek"
-- (konkurent s dobrymi vysledky: www.do-dodavky.cz) - vyplneni meta_title/
-- meta_description pro celou vetev "Vestavby do dodavek, aut" (id 184 +
-- 11 podkategorii), ktere byly v DB dosud NULL (viz vsech 117 kategorii
-- bez meta - zbytek stromu dostava jen genericky fallback popis pri
-- vykreslovani, viz _category_page_response v api/app.py).

UPDATE content_categories SET
  meta_title = 'Pracovní vestavby do dodávek a aut | Logiman',
  meta_description = 'Pracovní vestavby do dodávek a užitkových aut na míru z hliníkových profilů. Šuplíky, výsuvy, police i úložné prostory – navrhněte si v 3D konfigurátoru.'
WHERE id = 184;

UPDATE content_categories SET
  meta_title = 'Šuplíkové vestavby TECNO do dodávek a aut',
  meta_description = 'Robustní šuplíkové vestavby TECNO pro dodávky a užitková vozidla. Modulární hliníkový systém, přesné výsuvy, nosnost pro nářadí i materiál.'
WHERE id = 210;

UPDATE content_categories SET
  meta_title = 'Výsuvy z dodávky na míru | pracovní vestavby',
  meta_description = 'Výsuvné plošiny a šuplíky z dodávky na míru. Usnadní nakládku i práci v terénu, hliníková konstrukce, vysoká nosnost, 3D konfigurátor zdarma.'
WHERE id = 220;

UPDATE content_categories SET
  meta_title = 'Vestavby pro Fiat Ducato, Citroën Jumper, Peugeot Boxer',
  meta_description = 'Pracovní vestavby na míru pro Fiat Ducato, Citroën Jumper a Peugeot Boxer. Regály, šuplíky a úložné systémy z hliníkových profilů.'
WHERE id = 233;

UPDATE content_categories SET
  meta_title = 'Výsuvy na kola z dodávky na míru',
  meta_description = 'Individuální výsuvné nosiče a plošiny na kola do dodávky. Bezpečné uložení kol i další techniky, hliníková konstrukce na míru vozidlu.'
WHERE id = 245;

UPDATE content_categories SET
  meta_title = 'Vyjímatelná ložná plocha do dodávky',
  meta_description = 'Přídavná vyjímatelná ložná plocha pro dodávky – rychlá montáž i demontáž, více prostoru pro náklad, robustní hliníková konstrukce na míru.'
WHERE id = 246;

UPDATE content_categories SET
  meta_title = 'Úložný prostor v podlaze dodávky na míru',
  meta_description = 'Skrytý úložný prostor v podlaze dodávky pro nářadí a drobný materiál. Využijte každý centimetr vozidla, hliníková konstrukce na míru.'
WHERE id = 249;

UPDATE content_categories SET
  meta_title = 'Vestavba dodávky Ford Transit Custom na míru',
  meta_description = 'Pracovní vestavba na míru do Ford Transit Custom. Regály, šuplíky a organizéry z hliníkových profilů, navrženo v 3D konfigurátoru.'
WHERE id = 250;

UPDATE content_categories SET
  meta_title = 'Vestavba dodávky Toyota ProAce na míru',
  meta_description = 'Pracovní vestavba na míru do Toyota ProAce. Praktické uspořádání regálů, šuplíků a úložných boxů z hliníkových profilů.'
WHERE id = 251;

UPDATE content_categories SET
  meta_title = 'Vestavba dodávky pro elektrikáře na míru',
  meta_description = 'Pracovní vestavba dodávky pro elektrikáře – přehledné uložení nářadí, kabelů a materiálu. Hliníková konstrukce, navrhněte si v 3D konfigurátoru.'
WHERE id = 252;

UPDATE content_categories SET
  meta_title = 'Vestavba dodávky pro instalatéra na míru',
  meta_description = 'Pracovní vestavba dodávky pro instalatéry – uložení nářadí, trubek a spojovacího materiálu. Hliníková konstrukce na míru, 3D konfigurátor.'
WHERE id = 253;

UPDATE content_categories SET
  meta_title = 'Výsuvné podlahy do dodávek na míru',
  meta_description = 'Výsuvná podlaha do dodávky usnadní nakládku těžkého nákladu. Hliníková konstrukce s vysokou nosností, řešení na míru vašemu vozidlu.'
WHERE id = 254;
