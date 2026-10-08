-- Firemni udaje u potvrzeni objednavky online nabidky (bot4,
-- 2026-08-06). Robert: "Na posledni strance u tlacitka objednat dej
-- tabulku se vsemi inicialy firemnimi s tim ze nejdrive se za ico se
-- doplni automaticky napriklad z justice.cz" - doplnovani resi ARES
-- REST API (stejna data jako justice.cz), viz
-- GET /api/public/ares/<ico> v api/scene_offers.py.
ALTER TABLE scene_offer_acceptances
  ADD COLUMN company_ico VARCHAR(20) NULL AFTER name,
  ADD COLUMN company_name VARCHAR(255) NULL AFTER company_ico,
  ADD COLUMN company_dic VARCHAR(20) NULL AFTER company_name,
  ADD COLUMN company_address VARCHAR(500) NULL AFTER company_dic,
  ADD COLUMN contact_email VARCHAR(255) NULL AFTER company_address,
  ADD COLUMN contact_phone VARCHAR(50) NULL AFTER contact_email;
