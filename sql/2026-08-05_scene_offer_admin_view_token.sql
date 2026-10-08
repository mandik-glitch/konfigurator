-- Tlacitko "Zobrazit online" v admin seznamu online nabidek (Robert
-- 2026-08-05, screenshot seznamu: "sem pridej tlacitko na kliknuti pro
-- shlednuti online"). Klientsky view_token se uklada JEN jako hash
-- (nejde zpetne dohledat) - admin proto dostava VLASTNI, oddeleny
-- token: kazde kliknuti ho vygeneruje znovu (hash sem), klientsky
-- odkaz/platnost zustavaji nedotcene. _resolve_offer_by_token pak
-- pousti oba.
ALTER TABLE scene_offers
  ADD COLUMN admin_view_token_hash CHAR(64) NULL AFTER view_token_hash,
  ADD KEY idx_so_admin_token (admin_view_token_hash);
