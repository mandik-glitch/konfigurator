-- Zive 3D sestavy NE do auta (bot5, 2026-10-02; zadani Robert pres bot3, TASKS.md "ZADANO 2026-10-02 ... zive 3D modely"): schema pro konfiguraci v
-- kosiku a v objednavce + prinak "zive 3D" u sestavy. Vsechno NULLable / s vychozi hodnotou, stary kod nove sloupce nezna a nevadi mu.
-- Aplikace: python api/db_migrate.py sql/2026-10-02_konfigurace_kosik_objednavka.sql (ALTER neni opakovatelny - pustit JEDNOU).
--
-- shop_cart_items: konfigurace (volby + verze pravidel) a jeji hash. Unikatni klic se rozsiruje o config_hash (NOT NULL DEFAULT '' = bezne radky
-- zustavaji slucovane jako dosud), jinak by se dve ruzne konfigurace stejne sestavy slily do jednoho radku. DROP + ADD v JEDNOM prikazu: cizi klic
-- fk_shop_cart_items_user potrebuje index na user_id, ktery stary unikatni klic dosud dela.
ALTER TABLE shop_cart_items
  ADD COLUMN configuration_json MEDIUMTEXT DEFAULT NULL COMMENT 'konfigurace sestavy: volby a verze pravidel (cena se pocita zive)',
  ADD COLUMN config_hash CHAR(16) NOT NULL DEFAULT '' COMMENT 'hash konfigurace, prazdny = bezny radek bez konfigurace',
  DROP INDEX uq_shop_cart_user_product_assembly,
  ADD UNIQUE KEY uq_shop_cart_user_product_assembly_cfg (user_id, product_id, assembly_id, config_hash);

-- shop_order_items: snimek konfigurace v okamziku objednani (volby s ceskymi nazvy, kusovnik, price_summary, verze pravidel, hash) a jeji kod pro doklady.
ALTER TABLE shop_order_items
  ADD COLUMN configuration_json MEDIUMTEXT DEFAULT NULL COMMENT 'snimek konfigurace: volby, kusovnik, price_summary, rules_version, hash',
  ADD COLUMN configuration_code VARCHAR(24) DEFAULT NULL COMMENT 'kod konfigurace z hashe, tiskne se na dokladech';

-- product_assemblies: Robertovo zaskrtnuti, ze sestava NE do auta se smi vystavit jako zivy 3D model (is_live_3d_assembly: typ sestavy <> AUTO + live_3d +
-- is_public + technicky_ok, fail-closed). Vychozi 0, nastavuje jen Robert.
ALTER TABLE product_assemblies
  ADD COLUMN live_3d TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'zive 3D: povoleno Robertem, jen sestavy typu mimo AUTO';
