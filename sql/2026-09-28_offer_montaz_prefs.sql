-- Online nabidka: volba Montaze (+ Misto montaze) pro sestavy do auta -
-- bot5, 2026-09-28 (Robert primo: "stejne jako je volba montaze
-- (Praha/Slavicin) na eshopu v detailu sestav, tataz volba montaze
-- nech je v online nabidce... pokud je v nabidce sestava do auta").
--
-- Stejny vzor jako existujici sloupce (shipping_method/delivery_state/
-- qty) na tehle tabulce - jedna radka na (offer_id, guest_id), posledni
-- volba vyhrava (UPSERT, viz api/scene_offers.py::public_offer_order_
-- prefs). montaz_misto je volny retezec validovany proti zivemu
-- katalogu montaz_mista.klic (api/product_assemblies.py::_montaz_mista_map),
-- ne FK - stejny vzor jako montaz_misto na shop_order_items/shop_cart_items.
ALTER TABLE scene_offer_order_prefs
  ADD COLUMN montaz_zvolena TINYINT(1) NOT NULL DEFAULT 0 AFTER delivery_state,
  ADD COLUMN montaz_misto VARCHAR(40) NULL AFTER montaz_zvolena;
