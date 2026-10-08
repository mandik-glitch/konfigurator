-- Hromadny rezny plan: prechod z vyberu "podle stavu objednavky" na
-- rucni zaskrtavani KONKRETNICH objednavek (Robert, 2026-08-06).
-- `statuses_filter` byl doposud povinny (NOT NULL) a vyplnoval se pri
-- kazdem generovani seznamem stavu ("nova,potvrzena,..."). Nove se
-- generuje z explicitniho seznamu order_id, proto:
--   - statuses_filter je ted NULL pro nove plany (historicke radky si
--     svou puvodni hodnotu zachovaji beze zmeny - jen auditni sloupec,
--     nikde se nezpetne necte)
--   - order_ids_filter (TEXT) drzi cisla vybranych objednavek pro audit
--
-- Pouziti (na DB instance "Configurator", xebyhtfeaj @ 80.211.73.226):
--   mysql -h 80.211.73.226 -u <user> -p xebyhtfeaj < 2026-08-06_cutting_plan_order_ids_filter.sql

ALTER TABLE shop_cutting_plans
    MODIFY COLUMN statuses_filter VARCHAR(100) NULL DEFAULT NULL,
    ADD COLUMN order_ids_filter TEXT NULL AFTER statuses_filter;
