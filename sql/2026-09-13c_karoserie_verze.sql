-- Registr AUTO x VERZE -> ROZPIS BOXU (bot9, 2026-09-13, Robert primo v chatu).
--
-- Segment 5+6 kod_sestavy (`verze` + `typologie_varianta_id`) nemely
-- zadnou formalni vazbu - `verze` (A/B/C/D/E) je nezavisly text na
-- product_assemblies, ktery se dnes cte regexem z NAZVU sestavy
-- (scripts/2026-09-11_kod_sestavy_format.py, overeno bot8 2026-09-13).
-- Robert: "a,b,c,d... budou nezavislym oznacenim pro nas pro kupujiciho,
-- aby se nejak rozlisovalo v komunikaci" - NENI to geometricky odvozene
-- poradi, je to jen stabilni komunikacni stitek PRO KONKRETNI AUTO.
--
-- Kontrola pred zapisem (bot9): vsech 236 existujicich dvojic
-- (karoserie_kod, verze) v product_assemblies dnes ukazuje na PRAVE
-- JEDEN typologie_varianta_id - 0 kolizi. Tabulka tedy jen FORMALIZUJE,
-- co uz je v datech nahodou konzistentni, misto aby to dal zaviselo na
-- textu nazvu.
CREATE TABLE karoserie_verze (
  id INT AUTO_INCREMENT PRIMARY KEY,
  karoserie_kod VARCHAR(8) NOT NULL,
  verze CHAR(1) NOT NULL,
  typologie_varianta_id INT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_karoserie_verze (karoserie_kod, verze),
  FOREIGN KEY (typologie_varianta_id) REFERENCES typologie_varianty(id)
);

-- Zpetne naplneni ze stavajicich, jiz konzistentnich dat.
INSERT INTO karoserie_verze (karoserie_kod, verze, typologie_varianta_id)
SELECT DISTINCT karoserie_kod, verze, typologie_varianta_id
FROM product_assemblies
WHERE karoserie_kod IS NOT NULL AND verze IS NOT NULL AND typologie_varianta_id IS NOT NULL;
