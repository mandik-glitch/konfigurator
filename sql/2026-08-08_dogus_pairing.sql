-- Parovani naseho katalogu s dodavatelem doguskalip.com.tr (bot4, 2026-08-08).
--
-- Robert: "vymeníme vazby z logiman na doguskalip" + "nachystej strukturu
-- pro parovani z dogus vsech produktu, ano SKU jsou stejne protoze
-- nakjupujeme v doguskalip". logiman.cz je nas soucasny ostry e-shop
-- (bude nahrazen timhle projektem), doguskalip.com.tr je skutecny
-- dodavatel - nakupujeme pod jeho kody, shop_products.sku uz DNES
-- odpovida jeho "Stock Code".
--
-- NEPRIPOJUJEME se timhle k cene - doguskalip cenu verejne nezobrazuje
-- (potreba prihlaseni, Robert dodá login/heslo pozdeji) - price_source_url
-- (pouzivany pro tydenni auto-refresh z logiman.cz, viz
-- scrape_logiman_product_price v api/app.py) ZUSTAVA BEZE ZMENY, dokud
-- nebude hotovy autentizovany scraper pro doguskalip.
--
-- Tato migrace jen PRIPRAVUJE strukturu (sloupce pro ulozeni parovani),
-- NEAPLIKOVANA dokud Robert neschvali - viz
-- scripts/2026-08-08_dogus_pairing_crawl.py pro READ-ONLY crawl+match
-- report pred jakymkoli zapisem do techto sloupcu.
--
-- Robert upresnil rozsah (2026-08-08, druhe kolo): "natahovat budeme
-- pouze 2 hlavni obrazky, render(foto) a schema z hlavni zalozky...
-- dulezite jsou u produktu ty tabulky ve spodni casti jejich detailu
-- produktu" - proto dogus_image_render_url/dogus_image_schema_url (NE
-- plna fotogalerie - "pozdeji vymyslíme nějake sdilene fotogalerie
-- mezi produkty pro vice obrazků", zatim mimo rozsah) a
-- dogus_specs_json (JSON sloupec, protoze pocet/nazvy sloupcu tabulky
-- se lisi podle typu produktu - profily maji External Dimensions/
-- Material/L/Ix/Iy/Wx/Wy/Area/Mass, spojovaci prvky jen Material/
-- Weight - viz SpecTableParser ve scripts/2026-08-08_dogus_pairing_crawl.py).
ALTER TABLE shop_products ADD COLUMN dogus_url VARCHAR(500) NULL AFTER price_source_url;
ALTER TABLE shop_products ADD COLUMN dogus_stock_code VARCHAR(64) NULL AFTER dogus_url;
ALTER TABLE shop_products ADD COLUMN dogus_image_render_url VARCHAR(500) NULL AFTER dogus_stock_code;
ALTER TABLE shop_products ADD COLUMN dogus_image_schema_url VARCHAR(500) NULL AFTER dogus_image_render_url;
ALTER TABLE shop_products ADD COLUMN dogus_specs_json JSON NULL AFTER dogus_image_schema_url;
ALTER TABLE shop_products ADD COLUMN dogus_matched_at DATETIME NULL AFTER dogus_specs_json;

-- Kalkulace prodejni ceny (Robert: "pro kalkulaci cen bude pro admina v
-- sekci nastaveni zvolitelny koeficient k vypoctu ceny Kc (cena Dogus x
-- kurz dolaru x koeficient) a to separatne pro kazdou kategorii").
-- Koeficient patri ke KATEGORII (ne k jednotlivemu produktu), proto
-- primo na content_categories - stejny vzor jako existujici
-- is_visible/menu_expanded sloupce tamtez. NULL = koeficient jeste
-- nenastaven (kategorie nema jeste dogus-based cenotvorbu zapnutou).
ALTER TABLE content_categories ADD COLUMN dogus_price_coefficient DECIMAL(6,3) NULL;

-- Kurz USD/CZK - RESIT PRES existujici app_settings (klic-hodnota,
-- viz get_setting()/set_setting() v api/app.py), NE novy sloupec/tabulka -
-- jde o jednu globalni hodnotu, ne o zaznam navazany na konkretni radek.
-- Navrzeny klic: "dogus_usd_czk_rate" (+ "dogus_usd_czk_rate_updated_at"
-- pro zobrazeni stari kurzu v adminu). Zdroj kurzu (CNB denni kurzovni
-- listek vs. rucni zadani) - k rozhodnuti, zatim nic needeployovano.
