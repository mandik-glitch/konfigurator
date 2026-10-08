-- bot16, 2026-09-24 (Robert pres bot3, WORKFLOW.md pravidlo 52 "nic se
-- neodklada") - Robert, doslovne: "naopak chci tam videt cenu profilu z
-- 1 m z original logiman.cz (samozrejme SKU je parovaci znak)". Zaznam
-- posledniho stazeneho cenoveho udaje z www.logiman.cz (verejny Shoptet
-- storefront) pro srovnavaci sloupec v adminu "Ceny profilu".
--
-- *** DULEZITE ROZLISENI (at si to nikdo nikdy nepreklada spatne) ***
-- Radek "Robert 2026-08-08: z logiman uz nic nebudeme tahat" v
-- api/admin_profily.py (viz refresh_price_for_row a okolni komentare)
-- se tyka NASI VLASTNI prodejni ceny/hmotnosti profilu - tu uz
-- POCITAME z Dogus (dogus_list_price_usd x kurz x koeficient, viz
-- WORKFLOW.md bod 9), ne z logiman.cz. TOHLE je neco jineho: cisty
-- READ-ONLY srovnavaci udaj ("kolik ma svuj profil se stejnym SKU
-- na webu ZA KOLIK ted Robert sam"), zobrazeny admin VEDLE nasi ceny,
-- nikdy nepouzity jako zdroj/vstup do naseho vlastniho cenoveho
-- vypoctu. Zadny kod nesmi tuhle tabulku cist jako zdroj pro
-- cfg_dily.price_czk_approx / shop_products cenotvorbu - je to jen
-- referencni/kontrolni hodnota pro admina.
--
-- Plni scripts/2026-09-24_logiman_price_reference_crawl.py (sekvencni
-- crawl s prodlevou mezi requesty, sitemap.xml -> produktove stranky
-- obsahujici "profil" v URL - viz hlavicka toho skriptu pro presny
-- rozsah a zduvodneni). SKU (shop_products.sku) je parovaci klic,
-- presne podle Robertova zadani.
CREATE TABLE IF NOT EXISTS logiman_cz_price_reference (
  id INT AUTO_INCREMENT PRIMARY KEY,
  sku VARCHAR(64) NOT NULL,
  price_per_m_czk DECIMAL(10,2) NULL,      -- "Měrná cena" z detailu produktu (Kč/1m) - NULL, kdyz produkt tuhle radku vubec nema (napr. kusove zbozi jako zaslepky)
  price_per_piece_czk DECIMAL(10,2) NULL,  -- cena "/ ks" ze stejne stranky - jen sanity-check (merna_cena * pocet_m_v_tyci by mel sedet), NEPOUZIVA se jako primarni hodnota
  product_url VARCHAR(500) NOT NULL,
  product_name VARCHAR(300) NULL,
  fetched_at DATETIME NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_logiman_price_ref_sku (sku)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
