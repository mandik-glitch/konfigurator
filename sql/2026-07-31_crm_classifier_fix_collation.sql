-- Oprava dvou zjištěných chyb v CRM klasifikátoru (bot6, 2026-07-31,
-- po testu s 20 testovacími e-maily od Roberta).
--
-- 1) KOLACE BEZ DIAKRITIKY: sloupec `word` mel kolaci utf8mb4_unicode_ci,
--    ktera pro porovnavani BERE AKCENTOVANE A NEAKCENTOVANE ZNAKY JAKO
--    STEJNE (overeno primo: `SELECT 'máte' = 'mate' COLLATE
--    utf8mb4_unicode_ci` vraci 1/TRUE). Nekolik slov bez diakritiky
--    (mate, dobry, den, dotaz...) se do tabulky dostalo drive (rucni
--    korekce administratora psane rychle bez hacku/carek) - kazdy dalsi
--    e-mail se spravnou diakritikou pak OMYLEM matchoval tahle slova a
--    dostaval nespravne kladne skore. Zmena na utf8mb4_bin (presne
--    bajtove porovnani) tohle opravuje - "máte" a "mate" uz budou
--    dve ruzna slova, jak se ceka.
--
-- 2) SLOVO "nabídka" (zakladni/1. pad) je prilis nejednoznacne - stejne
--    slovo se pouziva jak pri ZADOSTI o cenovou nabidku (zakaznik chce
--    koupit), tak kdyz NEKDO JINY nabizi neco NAM (napr. "Nabízíme
--    reklamní prostor..." - realny test prypad, chybne se zaradil jako
--    poptavka). Robert: "napis poradne ze nabidka nemuze spadnout do
--    poptavky" - vaha slova "nabídka" (jen tenhle zakladni tvar, NE
--    "nabídku"/"nabídky"/"nabízíme" - ty zustavaji, jsou specifictejsi
--    a mnohem casteji se objevuji pri skutecne zadosti o nabidku, ne
--    nabizeni) snizena na 0 (neutralni) - samo o sobe uz nemuze
--    prevazit skore do poptavky, potrebuje k tomu i jine kladne slovo.

ALTER TABLE crm_classifier_words MODIFY word VARCHAR(64) COLLATE utf8mb4_bin NOT NULL;

UPDATE crm_classifier_words SET poptavka_count = 0 WHERE word = 'nabídka';
