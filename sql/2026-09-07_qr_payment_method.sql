-- QR platba nahrazuje "Kartou online" (Robert 2026-09-07, pres bot3):
-- zadna platebni brana v projektu neexistuje, "Kartou online" byl
-- nefunkcni popisek bez navaznosti na skutecne zpracovani platby.
-- Cesky standard "QR Platba" (bankovni prevod zakodovany do QR kodu,
-- SPAYD/IBAN) funguje bez brany - uz pouzivany u verejnych nabidek ze
-- sceny (api/scene_offers.py).
--
-- requires_advance_invoice=1 stejne jako "Platba předem" - zajisti
-- automaticke vystaveni zalohove faktury s vlastnim variable_symbol
-- hned pri vytvoreni objednavky (api/documents.py::
-- create_proforma_invoice_if_needed), ktery uz existujici
-- api/bank_statements.py::match_bank_payments_to_orders automaticky
-- sparuje s prichozi bankovni platbou a oznaci bank_paid=1 - zadna nova
-- platebni logika, jen znovupouziti uz funkcniho mechanismu (viz
-- api/orders.py::orders_payment_qr, ktery pro tuhle fakturu generuje
-- QR kod).
--
-- name je jen SNAPSHOT text na uz existujicich objednavkach
-- (shop_orders.payment_method_name se kopiruje pri vytvoreni objednavky,
-- neni to zive FK) - prejmenovani tohoto radku historicke objednavky
-- se stary popiskem "Kartou online" nijak nezmeni.
UPDATE shop_payment_methods
SET name = 'QR platba', requires_advance_invoice = 1
WHERE name = 'Kartou online';
