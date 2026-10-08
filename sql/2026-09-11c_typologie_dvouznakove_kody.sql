-- Dvouznakove kody zbylych tri typologii (bot9, 2026-09-11, Robert pres bot8).
--
-- Navazuje na sql/2026-09-11b_kod_sestavy_format_roberta.sql, kde se
-- `regal_typologie.kod` rozsiril na CHAR(2) a euroboxy dostaly `EB`.
-- Zbyle tri zustaly zamerne jednoznakove, dokud o nich Robert nerozhodne -
-- ted rozhodl (potvrdil navrh):
--     UN  universal
--     OS  ocelove supliky
--     EV  euroboxy na vysuvech
--
-- Bezpecne: zadna z techhle tri typologii nema jedinou sestavu
-- (product_assemblies.typologie_id ukazuje vyhradne na EB), takze se
-- nemeni zadny uz vygenerovany kod sestavy.
UPDATE regal_typologie SET kod='UN' WHERE klic='universal';
UPDATE regal_typologie SET kod='OS' WHERE klic='ocelove_supliky';
UPDATE regal_typologie SET kod='EV' WHERE klic='euroboxy_vysuvy';
