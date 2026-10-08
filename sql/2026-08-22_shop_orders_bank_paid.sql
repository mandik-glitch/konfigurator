-- Objednavky: parovani bankovnich plateb podle VS - bot10, 2026-08-22
-- (Robert: "u objednavek potrebujeme nove 2 sloupce, uhrazena/neuhrazena
-- a uhrazena kdy. parovaci znak je VS").
--
-- VYSLOVNE NOVE, samostatne sloupce - NEnavazuje na existujici
-- payment_received_at/payment_received_total_czk (ty zustavaji vazane
-- na vystaveni danoveho dokladu, jiny ucel/tok - Robert potvrdil pres
-- AskUserQuestion, nepretpisovat/nemichat).
ALTER TABLE shop_orders
  ADD COLUMN bank_paid TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN bank_paid_at DATETIME NULL;
