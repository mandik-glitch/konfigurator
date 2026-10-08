-- Robert: "na detailech produktů chybí dostupnost" - 537/538 aktivnich
-- produktu melo stock_qty=0 a prazdny availability_text, takze stranka
-- ukazovala vsude "NENI SKLADEM" (zavadejici pro katalog rezany/objednavany
-- na miru). Doplneno na "3 - 5 tydnu" (Robert), stejna hodnota nastavena
-- i jako sloupcovy default pro budouci produkty bez vlastni hodnoty.
UPDATE shop_products
    SET availability_text = '3 - 5 týdnů'
    WHERE stock_qty = 0 AND (availability_text IS NULL OR availability_text = '');

ALTER TABLE shop_products
    MODIFY availability_text VARCHAR(200) DEFAULT '3 - 5 týdnů';
