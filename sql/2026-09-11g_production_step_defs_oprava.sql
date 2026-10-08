-- Oprava ciselniku rucnich kroku (bot3 koordinace, po Robertove opravnem
-- hlaseni 2026-09-11: "urcite nebudu klikat v tech vnitrnich tabulkach a
-- neco hledat, pokud jsem ve scene udelal zatrzitko nebudu to prece
-- potvrzovat znova").
--
-- 1. `robert_confirmed_placement` byl zbytecny - Robertovo potvrzeni JE
--    zatrzitko `technicky_ok` ve scene, uz dopocitane jako faze "2
--    Schvaleno". Deaktivovano (NE smazano - kdyby se ukazalo, ze Robert
--    potvrzuje neco, co technicky_ok nepokryva, radek tu zustava).
-- 2. `texts_done` (popis produktu) patri ke KARTE, ne k jednotlive
--    sestave - popis pise clovek jednou za produkt, ne za kazdou
--    variantu zvlast.
UPDATE production_step_defs SET active=0 WHERE step_key='robert_confirmed_placement';
UPDATE production_step_defs SET scope='karta' WHERE step_key='texts_done';
