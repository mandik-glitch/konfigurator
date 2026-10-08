-- Robert (pres toscanaccio-0b, 2026-08-29): "ruzne znacky/modely aut budou
-- mit vlastni web s kosikem, nizke desitky webu/minieshopu rizene z
-- konfiguratorskeho adminu" - "nemelo by to mit vlastni administraci, ta
-- by se ridila vice centralne". Architektura schvalena Robertem: 1 web =
-- 1 nazev vozu (nameplate, napr. "Fiat Ducato"), delkove/vyskove varianty
-- (car_models radky) uvnitr na jedne strance, sdileny Flask backend + DB,
-- zadny novy admin. Viz AGENTS_LOG.md pro plny navrh (Cloudflare vrstva
-- atd.) a diskuzi.

-- Jeden storefront = jeden verejny mini-eshop web (1 domena, 1 nameplate).
CREATE TABLE car_storefronts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    slug VARCHAR(150) NOT NULL,
    car_make_id INT NULL,
    primary_domain VARCHAR(255) NOT NULL,
    template_id VARCHAR(40) NOT NULL DEFAULT 'default',
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    hero_title VARCHAR(255) NULL,
    hero_text TEXT NULL,
    meta_title VARCHAR(255) NULL,
    meta_description VARCHAR(500) NULL,
    created_by INT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_car_storefronts_slug (slug),
    UNIQUE KEY uq_car_storefronts_domain (primary_domain),
    KEY idx_car_storefronts_make (car_make_id),
    CONSTRAINT fk_car_storefronts_make FOREIGN KEY (car_make_id) REFERENCES car_makes(id) ON DELETE SET NULL,
    CONSTRAINT fk_car_storefronts_created_by FOREIGN KEY (created_by) REFERENCES app_users(id) ON DELETE SET NULL
);

-- Ktere konkretni delkove/vyskove varianty (car_models radky) patri pod
-- ktery storefront - "nameplate" jako entita v DB jinak neexistuje, je jen
-- implicitni v textu car_models.name (viz navrh v AGENTS_LOG.md).
CREATE TABLE car_storefront_models (
    storefront_id INT NOT NULL,
    car_model_id INT NOT NULL,
    PRIMARY KEY (storefront_id, car_model_id),
    KEY idx_csm_model (car_model_id),
    CONSTRAINT fk_csm_storefront FOREIGN KEY (storefront_id) REFERENCES car_storefronts(id) ON DELETE CASCADE,
    CONSTRAINT fk_csm_model FOREIGN KEY (car_model_id) REFERENCES car_models(id) ON DELETE CASCADE
);

-- Robert (pres toscanaccio-0b, doplneni 2026-08-29): "kdo ma male auto
-- nepotrebuje videt vestavby do velkych aut" - sestava/produkt musi jit
-- filtrovat podle KONKRETNI zvolene varianty, ne jen podle nameplate jako
-- celku. NULL = sestava/prislusenstvi neni vazane na konkretni delku/
-- vysku, zobrazi se napric celym nameplate storefrontu.
ALTER TABLE product_assemblies
    ADD COLUMN car_model_id INT NULL AFTER category_id,
    ADD KEY idx_product_assemblies_car_model (car_model_id),
    ADD CONSTRAINT fk_product_assemblies_car_model FOREIGN KEY (car_model_id) REFERENCES car_models(id) ON DELETE SET NULL;

-- Ke kterym objednavkam dorazily z ktereho storefrontu (jen reporting/
-- filtr v adminu, kosik zustava sdileny napric weby - Robertovo
-- rozhodnuti, viz AGENTS_LOG.md). NULL = objednavka z hlavniho
-- konfiguratoru/e-shopu, ne z modeloveho mini-eshopu.
ALTER TABLE shop_orders
    ADD COLUMN storefront_id INT NULL AFTER user_id,
    ADD KEY idx_shop_orders_storefront (storefront_id),
    ADD CONSTRAINT fk_shop_orders_storefront FOREIGN KEY (storefront_id) REFERENCES car_storefronts(id) ON DELETE SET NULL;

-- Best-effort zpetne dopleneni car_model_id u uz existujicich sestav
-- pojmenovanych rucne s kodem vozu v zavorce (napr. "Nohy Jumpy
-- [CI15]") - parovani podle stejneho kodu v car_models.name.
-- COLLATE nutne: product_assemblies.name je utf8mb4_0900_ai_ci,
-- car_models.name je utf8mb4_unicode_ci (starsi nesrovnalost v DB,
-- neresi tato migrace jinde nez timhle jednim dotazem).
UPDATE product_assemblies pa
JOIN car_models cm
    ON cm.name LIKE CONCAT('%[', SUBSTRING(pa.name, LOCATE('[', pa.name) + 1, LOCATE(']', pa.name) - LOCATE('[', pa.name) - 1), ']%') COLLATE utf8mb4_unicode_ci
SET pa.car_model_id = cm.id
WHERE pa.name LIKE '%[%]%' AND pa.car_model_id IS NULL;
