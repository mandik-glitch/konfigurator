-- Mapovani deskoveho produktu na shop_cutting_stock.material_key
-- (bot4, 2026-08-08).
--
-- Robert: "nahraju ti testovací objednávku profily s přířezy a desky,
-- uchop to napoj reálně funkčně na řezné plány" - u desek na rozdil
-- od profilu neexistuje zadna dimenze (cfg_dily.dim_x/y/z), ze ktere
-- by slo material_key automaticky odvodit (cfg_dily radek 'pr10' ma
-- dim_x/y/z NULL - desky nejsou "extrudovany profil"), proto potreba
-- explicitni admin nastaveni per produkt.
ALTER TABLE shop_products ADD COLUMN cutting_material_key VARCHAR(40) NULL AFTER board_sheet_height_mm;

-- PR10 (jedina deska v katalogu, board_sheet_width_mm=1250/
-- height_mm=2500) presne odpovida existujicimu shop_cutting_stock
-- radku 'preklizka_10' (2500x1250, jen prohozena osa sirka/vyska) -
-- nastaveno jako soucast teto migrace, aby testovaci objednavka mela
-- co pouzit bez dalsiho rucniho kroku v adminu.
UPDATE shop_products SET cutting_material_key = 'preklizka_10' WHERE sku = 'PR10';
