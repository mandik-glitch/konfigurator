-- Robert 2026-09-13: u sestav s euroboxy volba "bez boxů" VEDLE montáže
-- (zatržení odečte cenu boxů, info se propíše do objednávky; "bez boxů"
-- = klient má vlastní boxy). Montáž (TEXT_FILTR.md pravidlo 14a) byla
-- dosud jen INFORMATIVNI zobrazení ceny na detailu - tímto se z ní stává
-- skutečně VOLITELNÁ položka, kterou lze zaškrtnout při vložení do košíku.
--
-- shop_cart_items dosud NEMĚLA žádnou vazbu na konkrétní variantu sestavy
-- (product_assemblies.id) - jedna karta = jedna cena (price_czk_placeholder),
-- bez ohledu na to, kterou variantu si zákazník na detailu prohlížel. Nová
-- vazba `assembly_id` tohle řeší zároveň i pro cenu samotné varianty (dosud
-- se do košíku vždy propsala cena zástupce, ne prohlížené varianty).
--
-- Cena se u assembly_id řádků NEUKLÁDÁ (stejný princip jako u_effective
-- ceny za řez/dealerská sleva výše v cart.py - dopočítává se VŽDY ŽIVĚ
-- z aktuálního product_assemblies.data.price_summary), proto tu není
-- žádný cenový sloupec - jen volba (co si zákazník zvolil). Na
-- shop_order_items (nemenná historie objednávky) je to naopak - tam se
-- cena v okamžiku objednání ZAMRZNE (snapshot), stejně jako
-- unit_price_czk/product_name_snapshot dnes.

-- POZOR pri uprave: COMMENT retezce NESMI obsahovat ';' - naivni
-- rozdeleni skriptu na prikazy pri prvnim behu podle ';' se rozbilo
-- prave na strednik uvnitr COMMENT textu (viz AGENTS_LOG.md).
ALTER TABLE shop_cart_items
  ADD COLUMN assembly_id INT NULL COMMENT 'vybrana varianta sestavy (product_assemblies.id)',
  ADD COLUMN montaz_zvolena TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'zakaznik si pripocetl montaz jako sluzbu',
  ADD COLUMN bez_boxu TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'zakaznik odmitl euroboxy, odecte se jejich cena';

-- Puvodni UNIQUE (user_id, product_id) by pri ruznych variantach TEHOZ
-- produktu "ON DUPLICATE KEY UPDATE" jen navysilo qty na existujicim
-- radku (tise ZAMENILO vybranou variantu/volby na spatny radek) - misto
-- NULL (kde by MySQL brala kazdy radek jako "jiny", takze by se plain
-- produkty bez varianty prestaly deduplikovat) je assembly_id NOT NULL
-- DEFAULT 0 (0 nikdy neni platne product_assemblies.id, auto_increment
-- zacina od 1) - shop_cart_items bylo v okamziku teto migrace PRAZDNE,
-- zadny prevod dat neni potreba. Nejdriv ADD noveho klice, pak DROP
-- stareho - obracene poradi MySQL odmitne (1553: stary index je potreba
-- pro FK fk_shop_cart_items_user, dokud neexistuje jiny index s
-- user_id na prvnim miste).
ALTER TABLE shop_cart_items MODIFY assembly_id INT NOT NULL DEFAULT 0 COMMENT 'vybrana varianta sestavy (product_assemblies.id); 0 = produkt bez variant/sestav';
ALTER TABLE shop_cart_items ADD UNIQUE KEY uq_shop_cart_user_product_assembly (user_id, product_id, assembly_id);
ALTER TABLE shop_cart_items DROP INDEX uq_shop_cart_user_product;

ALTER TABLE shop_order_items
  ADD COLUMN assembly_id INT NULL COMMENT 'vybrana varianta sestavy v okamziku objednani',
  ADD COLUMN assembly_kod_snapshot VARCHAR(32) NULL COMMENT 'kod_sestavy v okamziku objednani',
  ADD COLUMN montaz_zvolena TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN montaz_czk_snapshot DECIMAL(12,2) NULL COMMENT 'cena montaze v okamziku objednani',
  ADD COLUMN bez_boxu TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN boxy_czk_snapshot DECIMAL(12,2) NULL COMMENT 'odectena cena euroboxu v okamziku objednani';
