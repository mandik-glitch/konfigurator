-- Rozdeleni shop_orders.status na dve nezavisle osy (bot18, 2026-09-04,
-- Robert pres bot3 - schvalene doporuceni z hloubkoveho rozboru
-- Dolibarr/ERPNext, bod 2/5). PRIPRAVA - NESPOUSTET bez vyslovneho "jdi
-- na to" po review (viz TASKS.md/AGENTS_LOG.md pro presny stav
-- pripravenosti a duvod postupneho pristupu).
--
-- ADITIVNI migrace - NEODSTRANUJE ani nemeni existujici sloupec
-- `status` ani ALLOWED_TRANSITIONS/STOCK_DEDUCTED_STATUSES logiku v
-- api/orders.py. Cil teto faze: dve nove, spravne dopocitane osy vedle
-- sebe, nulova zmena chovani existujicich API/UI cest (vsechny dnes
-- ctou/pisi jen `status`, ten zustava jedinym zdrojem pravdy, dokud se
-- kod VYSLOVNE nepreorientuje na nove sloupce v samostatnem, dalsim
-- kole).
--
-- Duvod aditivniho pristupu (ne primeho nahrazeni `status`): soucasny
-- ALLOWED_TRANSITIONS graf ma bezpecnostni pravidlo zavedene 2026-09-03
-- (zruseni JIZ EXPEDOVANE objednavky neni povolene, aby se tise
-- nevratilo zbozi na sklad, ktere fyzicky vraceno nebylo) - prepsani na
-- dvouosy model najednou by muselo bezchybne reprodukovat tuhle a dalsi
-- jemne nuance v JEDNOM kroku nad zivymi objednavkami s historii.
-- Aditivni krok je plne reverzibilni (DROP COLUMN) a nemeni zadne
-- existujici chovani.
--
-- delivery_state: mirror 5 "delivery" hodnot dnesniho statusu beze
-- zmeny textu (viz backfill skript) - "fakturovana" i "zrusena" NEJSOU
-- delivery stavy, dopocitavaji se zvlast (viz backfill).
-- billing_state: nova nezavisla osa, jen 2 hodnoty.

ALTER TABLE shop_orders
    ADD COLUMN delivery_state ENUM('nova','ceka_na_zbozi','potvrzena','pripravit','expedovana') NULL DEFAULT NULL AFTER status,
    ADD COLUMN billing_state ENUM('nevyfakturovano','fakturovano') NOT NULL DEFAULT 'nevyfakturovano' AFTER delivery_state;

-- Backfill se VEDOME nedela primo v tomhle SQL (na rozdil od jednoduchych
-- migraci jinde v projektu) - viz scripts/2026-09-04_shop_orders_state_backfill.py
-- (dry-run vychozi, --apply pro skutecny zapis), ktery pred zapisem
-- vypise presny diff kazde objednavky a po zapisu overi invarianty
-- cerstvym SELECTem z NOVEHO spojeni.
