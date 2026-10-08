-- Robert (pres toscanaccio-0b, 2026-08-29): "lide zadavaji i 'vestavba do
-- Ducato L2H2' apod." - kazda delkova/vyskova varianta potrebuje VLASTNI
-- indexovatelnou URL (napr. ducato-domena.top/l2h2), ne jen JS prepinac v
-- ramci jedne stranky (Google by ji nikdy nenasel/nezaindexoval). Slug je
-- vlastnost VAZBY storefront<->model (ne car_models samotneho - stejna
-- delkova varianta muze mit jiny "hezky" slug na ruznych strankach, a
-- car_models je sdileny i s 3D scenou/karoseriemi, nechceme tam pridavat
-- neco specifickeho jen pro storefronty).

ALTER TABLE car_storefront_models
    ADD COLUMN variant_slug VARCHAR(60) NOT NULL DEFAULT '';

ALTER TABLE car_storefront_models
    ADD UNIQUE KEY uq_csm_storefront_slug (storefront_id, variant_slug);
