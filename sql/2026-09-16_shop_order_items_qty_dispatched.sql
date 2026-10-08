-- bot5, 2026-09-16 - Robert primo: "potrebujeme resit dodaci listy, to
-- bude prvni zalozka, tzn polozky ktere se vydali a ktere jeste ne,
-- navazano na vydejky ze skladu."
--
-- `qty_dispatched` je CISTE VIZUALNI/PROCESNI pokrok "kolik z teto
-- polozky uz fyzicky odeslo ze skladu", NEZAVISLE na existujicim
-- STOCK_DEDUCTED_STATUSES mechanismu (api/orders.py) - ten uz jednou
-- naraz strhne CELE mnozstvi VSECH polozek ze skladove zasoby
-- (shop_products.stock_qty) pri prechodu objednavky do stavu
-- potvrzena/pripravit/expedovana/fakturovana. Tenhle sloupec ho
-- NENAHRAZUJE ani se do nej neplete (nemeni stock_qty) - resi jinou
-- otazku: u vicepolozkove objednavky, ktera se fyzicky expeduje na
-- vicekrat/po castech, kolik z KAZDE KONKRETNI polozky uz je fakticky
-- vydano zakaznikovi/prepravci, kolik jeste zbyva.
ALTER TABLE shop_order_items
  ADD COLUMN qty_dispatched INT NOT NULL DEFAULT 0 AFTER qty;
