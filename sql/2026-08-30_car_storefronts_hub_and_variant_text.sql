-- Robert (pres toscanaccio-0b, 2026-08-30, noc): "cely Fiat katalog, ne
-- jen Ducato" - Dobló/Ducato/Scudo kazdy jako vlastni "model" storefront
-- (variant subdomeny pod fiat-autovestavby.top, zadna dalsi Cloudflare
-- zona/OpenProvider zmena netreba - subdomeny jsou v ramci uz existujici
-- zony) + fiat-autovestavby.top samo jako "brand_hub" (prehled, odkazuje
-- na 3 nameplate weby). Viz AGENTS_LOG.md pro cely kontext.

ALTER TABLE car_storefronts
    ADD COLUMN kind VARCHAR(20) NOT NULL DEFAULT 'model' AFTER car_make_id;

-- Rucne psany text per varianta (Robert: "unikatni text per varianta,
-- zadna duplicita, ne obecne fraze") - render na SSR strance
-- /api/storefront-page/<variant_slug> MISTO obecne generovane vety.
ALTER TABLE car_storefront_models
    ADD COLUMN variant_description TEXT NULL,
    ADD COLUMN meta_title VARCHAR(255) NULL,
    ADD COLUMN meta_description VARCHAR(500) NULL,
    ADD COLUMN hero_image_url VARCHAR(500) NULL;
