-- Mnozstvi kusu pri objednani online nabidky (Robert primo, 2026-09-14:
-- "jeste potreba pridat moznost objednat vice ks vyrobku") - zakaznik si
-- zvoli, kolik kusu cele sestavy chce, cena/platba (viz
-- api/scene_offers.py::public_offer_payment_qr) se timhle cislem
-- vynasobi. Kusovnik (items) zustava technicky rozpis pro JEDNU sestavu -
-- qty meni jen celkovou cenu/platbu, ne pocet radku kusovniku.
ALTER TABLE scene_offer_order_prefs
  ADD COLUMN qty SMALLINT NOT NULL DEFAULT 1 AFTER delivery_state;
