-- Robert 2026-08-11: "tato barva se priradi natrvalo k danemu ID objektu
-- i po zavreni browseru" - profily (cfg_dily) dosud zadnou vychozi barvu
-- pro scenu nemely (mely ji jen produkty, shop_products.color_hex).
ALTER TABLE cfg_dily ADD COLUMN color_hex VARCHAR(9) DEFAULT NULL
