-- Presny tvar kodu sestavy podle Roberta (bot9, 2026-09-11, pres bot8).
--
-- Navazuje na sql/2026-09-11_kod_sestavy_ciselniky.sql (aplikovano tyz den).
-- Robert urcil doslovny tvar, ktery VYHRAVA nad tim, co jsme si odvodili
-- z drivejsiho zkraceneho navrhu (K-075-E30A72):
--
--     K-075-EB-30-A-0001-2-0
--     |     |  |  | |    | +-- dodatek     (posledni slozka)
--     |     |  |  | |    +---- horni blok  (0-6, 0 = bez bloku)
--     |     |  |  | +--------- rozpis boxu (CTYRI cislice)
--     |     |  |  +----------- VERZE       (samostatna slozka, A-E)
--     |     |  +-------------- profil      (30/40/45, urcuje admin)
--     |     +----------------- typologie   (DVA znaky)
--     +----------------------- karoserie
--
-- Slozky jsou oddelene POMLCKAMI, nezretezuji se.
--
-- Tri zmeny proti prvni verzi ciselniku:
--   1. typologie ma DVA znaky (EB pro euroboxy), ne jeden
--   2. VERZE je samostatna slozka - dosud vubec neexistovala jako pole
--      (pismeno "C" u Dobla C nebylo ulozene nikde, jen v textu nazvu)
--   3. rozpis boxu je ctyrmistny (0001-0097), ne base36 (1R)
--
-- Princip "kazda slozka vlastni sloupec, kod se generuje" Robert
-- nezpochybnil - zustava.

-- 1) Typologie na dva znaky ------------------------------------------
ALTER TABLE regal_typologie MODIFY COLUMN kod CHAR(2) NOT NULL;
UPDATE regal_typologie SET kod='EB' WHERE klic='euroboxy';
-- Zbyle tri typologie (universal / ocelove supliky / euroboxy na
-- vysuvech) zatim zustavaji jednoznakove ZAMERNE: jsou jen pojmenovane,
-- nemaji zadna data a dvouznakove kody pro ne urcuje Robert (navrh
-- UN / OS / EV mu jde pres bot8). Prepis se, az rozhodne.

-- 2) Rozpis boxu ctyrmistne -------------------------------------------
-- Precislovani 97 existujicich radku (base36 -> 0001..0097) dela
-- scripts/2026-09-11_kod_sestavy_format.py, ne tahle migrace - poradi
-- musi zustat totozne s prvnim seedem, aby se kody nezamichaly.
ALTER TABLE typologie_varianty MODIFY COLUMN kod CHAR(4) NOT NULL;

-- 3) Verze jako samostatna slozka -------------------------------------
-- A-E. Naplneni resi tyz skript: z nazvu sestavy (overeno dvema
-- nezavislymi vzory se shodnym vysledkem a NULOVYM poctem konfliktu),
-- u sesti variant vzoru dedenim od zakladni sestavy na tomtez produktu.
-- Kde to nejde, zustava NULL - nehada se.
ALTER TABLE product_assemblies
  ADD COLUMN verze CHAR(1) NULL AFTER profil_mm;
