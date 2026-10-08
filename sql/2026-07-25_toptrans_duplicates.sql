-- Toptrans doprava (realny cenik podle vzdalenosti + hmotnosti/objemu) +
-- evidence PSC + hlidani duplicit zakazniku - bot3, 2026-07-25, v8.
--
-- Kontext: Robert - "na dopravu pouzivame hlavne Toptrans, chci nastavit
-- tuto dopravu jako vychozi volbu, vedle osobnich odberu, cena nech se
-- odviji podle aktualnich ceniku Toptrans a PSC objednavajiciho klienta"
-- + "ta vyse dopravy zavisi take na objemu tzn rozmeru baliku ci palet,
-- cenik si najdi na toptrans.cz" + "dale je potreba hlidat duplicity kdyz
-- klient uz nakoupil v minulosti".
--
-- CENIK: stazen PRIMO z https://www.toptrans.cz/preprava/cs/ke-stazeni/
-- ("Cenik prepravy CZ - CZ", platnost od 1.9.2025, verejne dostupny PDF).
-- Je to REALNY oficialni cenik (BEZ DPH sloupec pouzit - system uklada
-- vsechny ceny bez DPH, viz v6 dokumenty), tarifikace: hmotnostni/
-- objemove pasmo (,,do X kg / Y m3'' - bere se vyssi z obou, ale nas
-- system NEMA rozmery produktu, jen hmotnost - viz omezeni nize) x
-- vzdalenostni pasmo (do 100/200/300/400/500/600/700 km). Nad 3000 kg je
-- v cenikuTopttrans "Individualni naceneni" - nelze dopocitat automaticky.
--
-- PSC -> vzdalenostni pasmo: Toptrans cenik je vzdalenostni (km OD
-- depa), NE primo podle PSC zony. NEMAM pristup k presnemu routovacimu
-- API, takze shop_zip_distance_bands NIZE je MUJ ODHAD vzdalenosti od
-- prazskeho depa LOGIMANu (Husinecka 903/10) podle kraje/regionu, ke
-- kteremu PSC prefix patri - NENI TO PRESNE ZMERENO. Admin si ho muze
-- kdykoli opravit pres /api/admin/shipping-zip-bands, bez redeploy.
--
-- Rozhodnuti Roberta k predchozim otazkam (AskUserQuestion):
--   - zdroj cisel: "bez preference" -> pouzit realny stazeny cenik (viz vyse).
--   - cena zavisi na PSC i hmotnosti - ANO (potvrzeno), objem/rozmery
--     bohuzel NEMAME v datech (shop_products nema rozmery, jen weight_g) -
--     znamy limit v1, viz api/orders.py docstring.
--   - duplicity: podle e-mailu A ICO, AUTOMATICKY NABIDNOUT propojeni.
--
-- Pouziti: mysql -h 80.211.73.226 -u <db_user> -p xebyhtfeaj < 2026-07-25_toptrans_duplicates.sql

-- PSC dodaci adresy jako STRUKTUROVANE pole (ne jen soucast volneho textu
-- delivery_address) - cena Toptrans se podle nej musi dopocitat DRIV, nez
-- zakaznik dokonci objednavku ("dodací adresu zadává dřív než je výběr
-- dopravy" - Robert).
ALTER TABLE shop_customers
    ADD COLUMN delivery_zip VARCHAR(6) NULL AFTER delivery_address;

ALTER TABLE shop_orders
    ADD COLUMN delivery_zip VARCHAR(6) NULL AFTER delivery_address;

-- "pricing_mode": 'fixed' (soucasne chovani - jedna cena_czk) nebo
-- 'zip_weight' (cena se dopocita z shop_shipping_price_rules podle
-- vzdalenostniho pasma z PSC + celkove hmotnosti objednavky).
-- "is_default" - kterou dopravu predvyplnit jako vychozi volbu ve
-- checkoutu (Robert: Toptrans vedle Osobniho odberu).
ALTER TABLE shop_shipping_methods
    ADD COLUMN pricing_mode VARCHAR(20) NOT NULL DEFAULT 'fixed',
    ADD COLUMN is_default TINYINT(1) NOT NULL DEFAULT 0;

INSERT INTO shop_shipping_methods (name, price_czk, active, sort_order, pricing_mode, is_default) VALUES
    ('Toptrans', 0, 1, 0, 'zip_weight', 1);

-- Toptrans uz je vychozi (is_default=1) - jen 1 vychozi soucasne.
UPDATE shop_shipping_methods SET is_default = 0 WHERE name != 'Toptrans';

-- Realny cenik Toptrans: hmotnostni pasmo (,,do X kg'') x vzdalenostni
-- pasmo (km_band = do kolika km) -> cena bez DPH. Admin CRUD:
-- /api/admin/shipping-price-rules.
CREATE TABLE IF NOT EXISTS shop_shipping_price_rules (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    shipping_method_id  INT NOT NULL,
    weight_to_kg        DECIMAL(8,2) NOT NULL,
    km_band             INT NOT NULL,
    price_czk           DECIMAL(10,2) NOT NULL,
    sort_order          INT NOT NULL DEFAULT 0,
    CONSTRAINT fk_shop_shipping_rules_method
        FOREIGN KEY (shipping_method_id) REFERENCES shop_shipping_methods(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- PSC prefix (prvni 2 cislice) -> vzdalenostni pasmo (km_band, musi
-- odpovidat hodnotam pouzitym v shop_shipping_price_rules: 100-700).
-- ODHAD (viz poznamka na zacatku souboru) - admin CRUD:
-- /api/admin/shipping-zip-bands.
CREATE TABLE IF NOT EXISTS shop_zip_distance_bands (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    zip_prefix   VARCHAR(3) NOT NULL UNIQUE,
    km_band      INT NOT NULL,
    note         VARCHAR(255) NULL,
    sort_order   INT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- === Cenik (119 radku = 17 hmotnostnich pasem x 7 vzdalenostnich pasem) ===
-- Zdroj: Cenik I. CZ-CZ, TOPTRANS EU a.s., platnost od 1.9.2025, sloupec
-- "BEZ DPH". Nad 3000 kg cenik uvadi "Individualni naceneni" - takove
-- objednavky nejdou automaticky ocenit (viz _resolve_toptrans_price).
INSERT INTO shop_shipping_price_rules (shipping_method_id, weight_to_kg, km_band, price_czk, sort_order)
SELECT id, 5, 100, 168, 1 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 5, 200, 191, 2 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 5, 300, 237, 3 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 5, 400, 257, 4 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 5, 500, 270, 5 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 5, 600, 293, 6 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 5, 700, 310, 7 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 15, 100, 249, 8 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 15, 200, 291, 9 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 15, 300, 317, 10 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 15, 400, 356, 11 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 15, 500, 396, 12 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 15, 600, 419, 13 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 15, 700, 442, 14 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 30, 100, 390, 15 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 30, 200, 458, 16 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 30, 300, 512, 17 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 30, 400, 557, 18 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 30, 500, 593, 19 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 30, 600, 625, 20 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 30, 700, 656, 21 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 50, 100, 526, 22 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 50, 200, 630, 23 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 50, 300, 712, 24 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 50, 400, 772, 25 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 50, 500, 830, 26 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 50, 600, 877, 27 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 50, 700, 920, 28 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 75, 100, 669, 29 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 75, 200, 813, 30 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 75, 300, 920, 31 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 75, 400, 1006, 32 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 75, 500, 1078, 33 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 75, 600, 1145, 34 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 75, 700, 1202, 35 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 100, 100, 794, 36 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 100, 200, 971, 37 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 100, 300, 1108, 38 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 100, 400, 1216, 39 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 100, 500, 1305, 40 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 100, 600, 1387, 41 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 100, 700, 1460, 42 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 150, 100, 1071, 43 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 150, 200, 1317, 44 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 150, 300, 1507, 45 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 150, 400, 1662, 46 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 150, 500, 1789, 47 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 150, 600, 1909, 48 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 150, 700, 2012, 49 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 200, 100, 1265, 50 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 200, 200, 1580, 51 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 200, 300, 1812, 52 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 200, 400, 2008, 53 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 200, 500, 2166, 54 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 200, 600, 2313, 55 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 200, 700, 2435, 56 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 300, 100, 1608, 57 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 300, 200, 2028, 58 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 300, 300, 2351, 59 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 300, 400, 2609, 60 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 300, 500, 2826, 61 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 300, 600, 3020, 62 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 300, 700, 3194, 63 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 400, 100, 1897, 64 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 400, 200, 2424, 65 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 400, 300, 2815, 66 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 400, 400, 3138, 67 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 400, 500, 3410, 68 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 400, 600, 3653, 69 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 400, 700, 3865, 70 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 500, 100, 2153, 71 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 500, 200, 2775, 72 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 500, 300, 3239, 73 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 500, 400, 3619, 74 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 500, 500, 3939, 75 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 500, 600, 4224, 76 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 500, 700, 4475, 77 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 700, 100, 2594, 78 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 700, 200, 3389, 79 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 700, 300, 3990, 80 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 700, 400, 4475, 81 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 700, 500, 4897, 82 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 700, 600, 5261, 83 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 700, 700, 5587, 84 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 1000, 100, 3134, 85 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 1000, 200, 4177, 86 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 1000, 300, 4960, 87 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 1000, 400, 5598, 88 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 1000, 500, 6144, 89 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 1000, 600, 6620, 90 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 1000, 700, 7049, 91 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 1500, 100, 3843, 92 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 1500, 200, 5255, 93 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 1500, 300, 6322, 94 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 1500, 400, 7187, 95 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 1500, 500, 7925, 96 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 1500, 600, 8573, 97 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 1500, 700, 9149, 98 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 2000, 100, 4402, 99 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 2000, 200, 6156, 100 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 2000, 300, 7477, 101 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 2000, 400, 8552, 102 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 2000, 500, 9465, 103 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 2000, 600, 10267, 104 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 2000, 700, 10984, 105 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 2500, 100, 4860, 106 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 2500, 200, 6953, 107 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 2500, 300, 7726, 108 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 2500, 400, 9763, 109 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 2500, 500, 10842, 110 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 2500, 600, 11790, 111 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 2500, 700, 12642, 112 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 3000, 100, 5242, 113 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 3000, 200, 7622, 114 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 3000, 300, 9407, 115 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 3000, 400, 10863, 116 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 3000, 500, 12105, 117 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 3000, 600, 13192, 118 FROM shop_shipping_methods WHERE name='Toptrans'
UNION ALL
SELECT id, 3000, 700, 14158, 119 FROM shop_shipping_methods WHERE name='Toptrans';

-- === PSC prefix -> vzdalenostni pasmo (ODHAD, viz poznamka nahore) ===
INSERT INTO shop_zip_distance_bands (zip_prefix, km_band, note, sort_order) VALUES
('10', 100, 'Praha a nejblizsi okoli', 1),
('11', 100, 'Praha a nejblizsi okoli', 2),
('12', 100, 'Praha a nejblizsi okoli', 3),
('13', 100, 'Praha a nejblizsi okoli', 4),
('14', 100, 'Praha a nejblizsi okoli', 5),
('15', 100, 'Praha a nejblizsi okoli', 6),
('16', 100, 'Praha a nejblizsi okoli', 7),
('17', 100, 'Praha a nejblizsi okoli', 8),
('18', 100, 'Praha a nejblizsi okoli', 9),
('19', 100, 'Praha a nejblizsi okoli', 10),
('20', 100, 'Stredocesky kraj (blizko Praze)', 11),
('21', 100, 'Stredocesky kraj (blizko Praze)', 12),
('25', 100, 'Stredocesky kraj (blizko Praze)', 13),
('26', 100, 'Stredocesky kraj (blizko Praze)', 14),
('27', 100, 'Stredocesky kraj (blizko Praze)', 15),
('28', 100, 'Stredocesky kraj (blizko Praze)', 16),
('29', 100, 'Stredocesky kraj (blizko Praze)', 17),
('30', 100, 'Plzen', 18),
('31', 100, 'Plzen', 19),
('32', 200, 'Plzensky kraj (Klatovy, Domazlice)', 20),
('33', 200, 'Plzensky kraj (Klatovy, Domazlice)', 21),
('34', 200, 'Plzensky kraj (Klatovy, Domazlice)', 22),
('35', 200, 'Karlovarsky kraj (Cheb, Karlovy Vary)', 23),
('36', 200, 'Karlovarsky kraj (Cheb, Karlovy Vary)', 24),
('37', 200, 'Jihocesky kraj (C. Budejovice, Tabor, Pisek, J. Hradec)', 25),
('38', 200, 'Jihocesky kraj (C. Budejovice, Tabor, Pisek, J. Hradec)', 26),
('39', 200, 'Jihocesky kraj (C. Budejovice, Tabor, Pisek, J. Hradec)', 27),
('40', 100, 'Ustecky kraj - blizsi cast (Usti n.L., Louny)', 28),
('41', 100, 'Ustecky kraj - blizsi cast (Usti n.L., Louny)', 29),
('44', 100, 'Ustecky kraj - blizsi cast (Usti n.L., Louny)', 30),
('42', 200, 'Ustecky kraj (Chomutov, Most)', 31),
('43', 200, 'Ustecky kraj (Chomutov, Most)', 32),
('45', 200, 'Liberecky kraj (Liberec, Jablonec, C. Lipa)', 33),
('46', 200, 'Liberecky kraj (Liberec, Jablonec, C. Lipa)', 34),
('47', 200, 'Liberecky kraj (Liberec, Jablonec, C. Lipa)', 35),
('50', 200, 'Kralovehradecky kraj (Hradec Kralove, Nachod)', 36),
('51', 200, 'Kralovehradecky kraj (Hradec Kralove, Nachod)', 37),
('53', 200, 'Pardubicky kraj (Pardubice, Chrudim)', 38),
('54', 200, 'Kralovehradecky kraj (Trutnov)', 39),
('55', 200, 'Pardubicky kraj (Rychnov, Usti n.O., Svitavy)', 40),
('56', 200, 'Pardubicky kraj (Rychnov, Usti n.O., Svitavy)', 41),
('57', 200, 'Vysocina (Havlickuv Brod, Jihlava, Zdar n.S.)', 42),
('58', 200, 'Vysocina (Havlickuv Brod, Jihlava, Zdar n.S.)', 43),
('59', 200, 'Vysocina/Jihomoravsky (Velke Mezirici, Bystrice)', 44),
('60', 300, 'Jihomoravsky kraj (Brno a okoli)', 45),
('61', 300, 'Jihomoravsky kraj (Brno a okoli)', 46),
('62', 300, 'Jihomoravsky kraj (Brno a okoli)', 47),
('63', 300, 'Jihomoravsky kraj (Brno a okoli)', 48),
('64', 300, 'Jihomoravsky kraj (Brno a okoli)', 49),
('65', 300, 'Jihomoravsky kraj (Brno a okoli)', 50),
('66', 300, 'Jihomoravsky kraj (Znojmo, Ivancice)', 51),
('67', 300, 'Jihomoravsky/Vysocina (Moravsky Krumlov, Znojmo)', 52),
('68', 300, 'Jihomoravsky/Zlinsky (Uh. Hradiste, Kyjov)', 53),
('69', 300, 'Jihomoravsky kraj (Hodonin, Breclav)', 54),
('70', 400, 'Moravskoslezsky/Olomoucky kraj (Ostrava)', 55),
('71', 400, 'Moravskoslezsky/Olomoucky kraj (Ostrava)', 56),
('72', 400, 'Moravskoslezsky/Olomoucky kraj (Ostrava)', 57),
('73', 400, 'Moravskoslezsky kraj (Karvina, Frydek-Mistek)', 58),
('74', 400, 'Moravskoslezsky kraj (Karvina, Frydek-Mistek)', 59),
('75', 300, 'Zlinsky kraj (Zlin, Vsetin, Kromeriz)', 60),
('76', 300, 'Zlinsky kraj (Zlin, Vsetin, Kromeriz)', 61),
('77', 300, 'Olomoucky kraj (Olomouc, Prerov, Sumperk, Jesenik)', 62),
('78', 300, 'Olomoucky kraj (Olomouc, Prerov, Sumperk, Jesenik)', 63),
('79', 300, 'Olomoucky kraj (Olomouc, Prerov, Sumperk, Jesenik)', 64);

-- ---------------------------------------------------------------------------
-- Hlidani duplicit zakazniku (Robert: "je potreba hlidat duplicity kdyz
-- klient uz nakoupil v minulosti") - podle e-mailu (app_users.email uz je
-- UNIQUE) a ICO (shop_customers.ico NENI unique - firma muze mit vic
-- kontaktnich osob/uctu). Index pro rychle vyhledavani duplicit podle ICO
-- pri rucnim zadavani objednavky adminem.
-- ---------------------------------------------------------------------------
CREATE INDEX idx_shop_customers_ico ON shop_customers (ico);
