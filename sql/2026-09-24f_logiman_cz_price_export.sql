-- bot16, 2026-09-24 (Robert pres bot3, WORKFLOW.md pravidlo 52 "nic se
-- neodklada") - Robert sam exportoval kompletni cenik z logiman.cz
-- (administrace Shoptetu) do xlsx a dal ho do repa:
-- backups/2026-09-24_logiman_cenik_export.xlsx (616 radku, sloupec
-- A=kod produktu/SKU, C=nazev, D=guid, E=cena Kc; SKU je parovaci
-- klic, stejne jako u logiman_cz_price_reference nize).
--
-- *** DULEZITE ROZLISENI OD `logiman_cz_price_reference` (sql/2026-09-24c) ***
-- Ta tabulka je PRUBEZNY CRAWL (scripts/2026-09-24_logiman_price_
-- reference_crawl.py, opakovane spustitelny, ziva data z webu, pouziva
-- se v zalozce "Ceny profilu"). TOHLE je JEDNORAZOVY IMPORT konkretniho
-- Robertova xlsx souboru (scripts/2026-09-24f_logiman_price_export_
-- import.py, pouziva se v zalozce "Dogus: cena vs. vzorec") - jina
-- zalozka, jiny ucel (historicke porovnani nasi ceny vs. cena, kterou
-- mel produkt na logiman.cz v okamziku exportu), jiny zdroj dat (Robert
-- rucne exportoval z administrace, ne nas crawler). `source_label` +
-- `imported_at` u kazdeho radku exponuji tenhle rozdil primo v datech,
-- aby si to nikdo v budoucnu nespletl/nezamenil tabulky. Cisty
-- READ-ONLY srovnavaci udaj - zadny kod nesmi tuhle tabulku pouzit jako
-- vstup do naseho vlastniho cenoveho vypoctu (stejne omezeni jako u
-- logiman_cz_price_reference).
CREATE TABLE IF NOT EXISTS logiman_cz_price_export (
  id INT AUTO_INCREMENT PRIMARY KEY,
  sku VARCHAR(64) NOT NULL,
  product_name VARCHAR(300) NULL,          -- sloupec C xlsx ("name")
  guid VARCHAR(64) NULL,                   -- sloupec D xlsx ("guid") - Shoptet interni ID, jen pro dohledani, nikde jinde v appce nepouzite
  price_czk DECIMAL(10,2) NULL,            -- sloupec E xlsx ("price") - cena v okamziku Robertova exportu, bez DPH (includingVat='0' u vsech radku)
  source_label VARCHAR(100) NOT NULL DEFAULT 'robert_xlsx_export_2026-09-24',  -- explicitni odliseni od zive crawlovanych dat, viz komentar vyse
  source_file VARCHAR(255) NOT NULL DEFAULT 'backups/2026-09-24_logiman_cenik_export.xlsx',
  imported_at DATETIME NOT NULL,           -- kdy skript import spustil (NENI datum, kdy Robert soubor exportoval z Shoptetu - to nevime, jen kdy jsme ho nacetli k nam)
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_logiman_price_export_sku (sku)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
