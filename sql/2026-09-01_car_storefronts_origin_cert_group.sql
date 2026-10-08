-- Robert (pres toscanaccio-0b, 2026-09-01): 3 nove standalone storefront
-- domeny per model auta (fiat-ducato-vestavby.top / fiat-doblo-vestavby.top
-- / fiat-scudo-vestavby.top), vedle existujicich subdomen pod
-- fiat-autovestavby.top - jina Cloudflare zona/Origin CA cert per domena
-- (bezpecnostni izolace, nechceme sahat na uz zivy sdileny cert
-- fiat-autovestavby.top). scripts/gen_storefront_vhosts.py potrebuje
-- vedet, ktery cert-soubor pro kterou domenu pouzit.
ALTER TABLE car_storefronts
    ADD COLUMN origin_cert_group VARCHAR(60) NOT NULL DEFAULT 'fiat-autovestavby' AFTER template_id;
