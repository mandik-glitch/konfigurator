-- Robert, 2026-09-13, doslova: "u montáže nevidim v adminu ty dve volby
-- kde se muze montovat." Puvodni reseni (dnesni commit 757e2617) mela
-- dve PEVNE hodnoty zapecene v Python konstante MONTAZ_MISTA - zadna
-- viditelnost/editace v adminu. Robert pri dotazu ("jen zobrazit, nebo
-- editovat?") zvolil PLNOU editaci - novy maly katalog, stejny vzor
-- jako regal_umisteni (klic/nazev/aktivni/sort_order).
--
-- `klic` DRZI STEJNE HODNOTY jako dosavadni retezce v
-- shop_cart_items.montaz_misto / shop_order_items.montaz_misto_snapshot
-- ('praha'/'slavicin') - zadna migrace existujicich dat potreba.

CREATE TABLE montaz_mista (
  id INT NOT NULL AUTO_INCREMENT,
  klic VARCHAR(20) NOT NULL,
  nazev VARCHAR(60) NOT NULL,
  aktivni TINYINT(1) NOT NULL DEFAULT 1,
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY klic (klic)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO montaz_mista (klic, nazev, sort_order) VALUES
  ('praha', 'Praha', 0),
  ('slavicin', 'Slavičín', 1);
