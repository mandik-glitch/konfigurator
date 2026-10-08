-- Robert 2026-08-05: import obrazku noh z externiho systemu vandrawee.eu
-- ("nic tam neupravuj, jen nacti ty obrazky s nazvem, dej to k nam do DB").
-- FAZE 1: jen ulozit obrazek+nazev+zdroj, zadny vypocet geometrie/custom_shapes
-- zaznam - to az v dalsi fazi, az Robert rekne, ktere z nich nasadit do
-- panelu "Vlastni tvary" (viz VLASTNOSTI_PROFILU.md sekce 2an - postup na
-- rucni vytvoreni tvaru z vykresu, az na to dojde).
CREATE TABLE leg_reference_drawings (
  id INT AUTO_INCREMENT PRIMARY KEY,
  source_id INT NOT NULL,            -- id polozky na vandrawee.eu (work-single-leg/<id>)
  name VARCHAR(255) NOT NULL,        -- presny nazev (z nazvu souboru obrazku, netruncovany)
  image_path VARCHAR(500) NOT NULL,  -- relativni cesta v private-files/leg-reference-drawings/
  source_url VARCHAR(500) NOT NULL,  -- puvodni URL obrazku na vandrawee.eu
  cross_section VARCHAR(20) NULL,    -- napr. "40x40" - pokud bylo v seznamu uvedeno
  imported_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  processed TINYINT(1) NOT NULL DEFAULT 0,  -- 1 = uz z toho vznikl custom_shapes zaznam
  UNIQUE KEY uniq_source_id (source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
