-- Toptrans doprava podle objemu - bot3, 2026-08-08.
--
-- Kontext: Robert - "Toptrans chceme řešit nikoli ručně dohledávanou
-- cenou, ale poloautomaticky... Systém porovná ceny podle: váhy a PSČ vs
-- objem a PSČ. Toptrans vždy fakturuje tu vyšší cenu."
--
-- ZJIŠTĚNÍ (bot3): existující shop_shipping_price_rules (viz
-- 2026-07-25_toptrans_duplicates.sql) uz obsahuje realny cenik z
-- www.toptrans.cz ("Cenik I. CZ-CZ", platnost od 1.9.2025), ale jen
-- hmotnostni pasma - tehdy byl znamy limit "objem/rozmery bohuzel
-- NEMAME v datech". Po stazeni a rozparsovani (pdftotext) skutecneho
-- PDF (https://www.toptrans.cz/preprava/data/2025-09-01-08-35-38-Cenik-CZ-CZ-s-DPH-na-web.pdf)
-- se ukazalo, ze Toptrans NEMA dve oddelene tabulky pro vahu a objem -
-- kazdy radek cenika je PAR "do X kg / do Y m3" se stejnou cenou
-- (tarifikuje se podle toho, co je prekroceno driv). 17 hmotnostne-
-- objemovych pasem (presne odpovidajicich 17 distinct weight_to_kg uz
-- v DB) x 7 vzdalenostnich pasem = 119 radku, presne pocet, co uz mame.
--
-- Reseni tedy NENI druha tabulka, jen doplneni parovaneho sloupce
-- volume_to_m3 k existujicim radkum - stejny km_band/cena, jen se prida
-- odpovidajici objemova hranice z PDF. Vypocet ceny (viz
-- _resolve_toptrans_price v api/orders.py) pak spocita cenu podle vahy
-- I podle objemu (stejny km_band) a vezme tu vyssi - presne "vezme se
-- vyssi z obou", jak pise Toptrans cenik i Robert.

ALTER TABLE shop_shipping_price_rules
    ADD COLUMN volume_to_m3 DECIMAL(6,3) NULL AFTER weight_to_kg;

UPDATE shop_shipping_price_rules SET volume_to_m3 = 0.12 WHERE weight_to_kg = 5.00;
UPDATE shop_shipping_price_rules SET volume_to_m3 = 0.20 WHERE weight_to_kg = 15.00;
UPDATE shop_shipping_price_rules SET volume_to_m3 = 0.30 WHERE weight_to_kg = 30.00;
UPDATE shop_shipping_price_rules SET volume_to_m3 = 0.40 WHERE weight_to_kg = 50.00;
UPDATE shop_shipping_price_rules SET volume_to_m3 = 0.60 WHERE weight_to_kg = 75.00;
UPDATE shop_shipping_price_rules SET volume_to_m3 = 0.80 WHERE weight_to_kg = 100.00;
UPDATE shop_shipping_price_rules SET volume_to_m3 = 1.20 WHERE weight_to_kg = 150.00;
UPDATE shop_shipping_price_rules SET volume_to_m3 = 1.60 WHERE weight_to_kg = 200.00;
UPDATE shop_shipping_price_rules SET volume_to_m3 = 2.00 WHERE weight_to_kg = 300.00;
UPDATE shop_shipping_price_rules SET volume_to_m3 = 2.80 WHERE weight_to_kg = 400.00;
UPDATE shop_shipping_price_rules SET volume_to_m3 = 4.00 WHERE weight_to_kg = 500.00;
UPDATE shop_shipping_price_rules SET volume_to_m3 = 6.00 WHERE weight_to_kg = 700.00;
UPDATE shop_shipping_price_rules SET volume_to_m3 = 8.00 WHERE weight_to_kg = 1000.00;
UPDATE shop_shipping_price_rules SET volume_to_m3 = 10.00 WHERE weight_to_kg = 1500.00;
UPDATE shop_shipping_price_rules SET volume_to_m3 = 12.00 WHERE weight_to_kg = 2000.00;
UPDATE shop_shipping_price_rules SET volume_to_m3 = 14.00 WHERE weight_to_kg = 2500.00;
UPDATE shop_shipping_price_rules SET volume_to_m3 = 16.00 WHERE weight_to_kg = 3000.00;

-- Rozmery pro dopravu na produktove karte (Robert: "tak založ v kartách
-- produktů také rozměry") - pro produkty BEZ cfg_dily_id (prislusenstvi,
-- katalog ve scene), kde prurez/delka profilu neni k dispozici z
-- cfg_dily. U profilu (cfg_dily_id NOT NULL) se objem pocita z
-- cfg_dily.dim_x_mm/dim_y_mm (prurez) x skutecna delka - tahle pole
-- tam netreba. Nepovinne (NULL = chybi, degraduje na vypocet jen podle
-- vahy pro danou polozku, doplni se postupne pozdeji).
ALTER TABLE shop_products
    ADD COLUMN length_mm INT NULL AFTER weight_g,
    ADD COLUMN width_mm INT NULL AFTER length_mm,
    ADD COLUMN height_mm INT NULL AFTER width_mm;
