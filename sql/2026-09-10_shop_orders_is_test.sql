-- Denni testovaci objednavky (WORKFLOW.md bod 27, Robert 2026-09-10:
-- "nech delat test, kazdy den 2 objednavky pro testovani stavu a
-- pruchodnosti systemem").
--
-- is_test        - priznak testovaci objednavky. Odfiltrovava se ze
--                  statistik/prehledu a spada pod automaticky uklid.
-- test_marked_at - OD KDY se pocita 14denni lhuta uklidu. Zamerne NENI
--                  odvozena od created_at: Robert 2026-09-10 na dotaz,
--                  jestli se 39 historickych objednavek ma smazat hned
--                  (vsechny jsou starsi 14 dnu), odpovedel doslova
--                  "pravidlo je po 14ti dnech, jako testovaci jsme je
--                  oznacili dnes" - lhuta tedy bezi od OZNACENI, ne od
--                  vzniku objednavky. Diky tomu se historie nesmaze pri
--                  prvnim behu uklidu, ale az 14 dni po oznaceni.
--                  U objednavek z generatoru je test_marked_at == vznik,
--                  takze pro ne plati totez pravidlo bez vyjimky.
ALTER TABLE shop_orders
  ADD COLUMN is_test TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN test_marked_at DATETIME NULL DEFAULT NULL;

CREATE INDEX idx_shop_orders_is_test ON shop_orders (is_test, test_marked_at);
