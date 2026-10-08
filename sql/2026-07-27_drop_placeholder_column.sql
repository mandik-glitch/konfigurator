-- Odstraneni nepouzivaneho konceptu "placeholder produkt" (Robert:
-- "tak to vsude odstran" - po dotazu na tlacitko "Smazat vsechny
-- placeholder produkty"). Sloupec drzel priznak pro 293 uvodnich
-- ukazkovych produktu prevzatych ze skladapp (nahodne ceny, jen vzor
-- struktury), smazanych jiz drive pri uklidu pred Shoptet importem.
-- Overeno pred spustenim: 0 radku ma is_placeholder=1, zadny soucasny
-- kod uz ho nikdy nenastavuje na 1 (obe INSERT mista v api/app.py ho
-- vzdy vkladaly jako literal 0).

ALTER TABLE shop_products DROP COLUMN is_placeholder;
