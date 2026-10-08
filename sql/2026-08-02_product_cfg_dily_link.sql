-- Robert 2026-08-02: "udělejme to jako na logiman.cz... cena za metr,
-- ta cena za 1 ks je za délku 3m" - PUVODNI verze tohohle souboru pridavala
-- vlastni sloupec unit_length_m (delka tyce), ale Robert upozornil:
-- "něco už na skladových kartách máme tak to neduplikuj" - overeno
-- (na jeho pozadavek "zkontroluj to na par polozkach"): tabulka
-- cfg_dily (profily pouzivane primo v 3D scene) uz ma pro presne
-- tytez profily (identicka price_source_url, overeno u vsech 22
-- prekryvajicich se radku) autoritativni cenu/hmotnost ZA METR
-- (price_czk_approx/weight_kg_approx, dim_y_mm=1000), pravidelne
-- obnovovanou nocnim cronem (konfigurator-refresh-prices.timer).
--
-- Misto duplicitniho sloupce proto jen LEHKA VAZBA na existujici
-- radek cfg_dily - kdyz je vyplnena, "Merna cena" na strance produktu
-- se pocita z NI (autoritativni zdroj), ne z noveho pole.
ALTER TABLE shop_products
  ADD COLUMN cfg_dily_id VARCHAR(64) NULL
  COMMENT 'Vazba na cfg_dily.id (stejny profil v 3D konfiguratoru) - kdyz vyplneno, merna cena/hmotnost za metr se bere odtud (price_czk_approx/weight_kg_approx), ne z tohoto produktu'
  AFTER weight_g,
  ADD CONSTRAINT fk_shop_products_cfg_dily FOREIGN KEY (cfg_dily_id) REFERENCES cfg_dily(id) ON DELETE SET NULL;
