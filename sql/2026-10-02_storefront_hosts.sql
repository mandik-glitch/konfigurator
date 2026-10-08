-- Aliasy hostu mini-shopu (bot5, 2026-10-02; zadani bot3/Robert: dealer dostane subdomenu na nasi domene daneho jazyka, vlastni domenu dealera udelame jen na jeho zadost,
-- takze JEDEN storefront muze mit VIC hostu a objednavky ani prirazeni dealera se tim nemeni).
-- car_storefronts.primary_domain zustava hlavni host (unikatni, pouziva ho zbytek kodu), dalsi hosty jsou v storefront_hosts. Rozpoznani storefrontu: nejdriv primary_domain, pak alias
-- (car_storefronts.resolve_storefront). shop_orders.order_host nese skutecny host objednavky (alias nebo hlavni), storefront_id je v obou pripadech tentyz.
-- Unikatnost hostu napric obema tabulkami hlida aplikace (add_storefront_host a admin API storefrontu), v samotne tabulce je host unikatni.
-- Migrace JEN PRIDAVA novou tabulku. Aplikace: python api/db_migrate.py sql/2026-10-02_storefront_hosts.sql (opakovatelne). POZOR: db_migrate deli prikazy podle strednikuv, v COMMENT zadne.

CREATE TABLE IF NOT EXISTS storefront_hosts (
  id INT NOT NULL AUTO_INCREMENT,
  storefront_id INT NOT NULL,
  host VARCHAR(255) NOT NULL COMMENT 'dalsi host (alias) mini-shopu, normalizovany (male pismena, bez portu a www), napr. vlastni domena dealera na jeho zadost',
  note VARCHAR(255) DEFAULT NULL,
  created_by INT DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_storefront_hosts_host (host),
  KEY idx_storefront_hosts_storefront (storefront_id),
  CONSTRAINT fk_storefront_hosts_storefront FOREIGN KEY (storefront_id) REFERENCES car_storefronts (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
