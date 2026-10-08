-- Objednavky vznikle prijetim online nabidky (scene_offers) - bot5,
-- 2026-09-14. Dva navazujici pokyny od Robert:
-- 1) (pres bot16) "v pripade objednani se zadane udaje propisuji do
--    adresare zakazniku a do objednavek" - dosud public_offer_accept()
--    jen zapisoval do scene_offer_acceptances + poslal e-mail, zadny
--    zakaznik/objednavka nevznikaly.
-- 2) Primo: "je potreba u objednavky evidovat VS nabidky, resp VS
--    platby, podle ktere se to pak sparuje" - VS PLATBY uz existujici
--    mechanismus (shop_documents.variable_symbol, vznika az pri
--    vystaveni zalohove faktury pro objednavku, viz documents.py -
--    tenhle sloupec ho nijak nenahrazuje). VS NABIDKY zatim zadny
--    protejsek nemela - tenhle sloupec je trvala vazba objednavky
--    zpet na puvodni nabidku (scene_offers.offer_number pres JOIN),
--    dostupna hned pri zalozeni objednavky, driv nez pripadne vznikne
--    VS platby.
ALTER TABLE shop_orders
  ADD COLUMN source_scene_offer_id INT NULL,
  ADD KEY idx_shop_orders_source_scene_offer (source_scene_offer_id),
  ADD CONSTRAINT fk_shop_orders_source_scene_offer
    FOREIGN KEY (source_scene_offer_id) REFERENCES scene_offers (id) ON DELETE SET NULL;
