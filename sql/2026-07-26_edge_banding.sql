-- Olepeni hran (ABS listy) - bot4, "optimizer", 2026-07-26.
-- Robert potvrdil: pouziva se jen JEDEN typ - ABS 2mm (barva materialu,
-- viz shop_cutting_stock.label). Sloupec `edge_banding_type` je proto
-- zatim vzdy 'ABS_2MM', ale je to sloupec (ne hardcoded konstanta v
-- kodu), aby slo pozdeji pridat dalsi typ bez dalsi migrace schematu.
--
-- Ctyri hrany jsou pojmenovane vzhledem k VLASTNI (deklarovane) orientaci
-- kusu v objednavce (width_mm x height_mm), NE podle finalni polohy na
-- rozrezane desce (tu muze algoritmus pro lepsi vyuziti otocit o 90 -
-- viz "rotated" priznak v odpovedi API/cutting_algo.py):
--   edge_band_top/bottom - hrany o delce width_mm (horni/dolni)
--   edge_band_left/right - hrany o delce height_mm (leva/prava)
--
-- Pouziti (na DB instance "Configurator", xebyhtfeaj @ 80.211.73.226):
--   mysql -h 80.211.73.226 -u <user> -p xebyhtfeaj < 2026-07-26_edge_banding.sql

ALTER TABLE shop_order_items
  ADD COLUMN edge_band_top    TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN edge_band_bottom TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN edge_band_left   TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN edge_band_right  TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN edge_banding_type VARCHAR(20) NULL DEFAULT 'ABS_2MM';
