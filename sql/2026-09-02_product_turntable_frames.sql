-- Otocny (sfericky) nahled produktove sestavy pro e-shop (bot16, 2026-09-02).
-- Robert 2026-09-02: misto fotky produktove sestavy chce na e-shopu
-- otocny nahled generovany primo ze 3D sceny, "k nerozeznani svou
-- kvalitou, zadne rozmazani"; upresneni pres bot3 tentyz den: nahled je
-- SFERICKY - 5 prstencu elevace (0/20/40/60/80 stupnu, 80 ~ pudorys),
-- kazdy 36 snimku po 10 stupnich azimutu = 180 snimku na sestavu, kazdy
-- ve 2 tierech (master 2048x1536 + 1024x768) = 360 souboru.
--
-- ZAMERNE ODDELENE od bezne fotogalerie produktu (content_gallery_items) -
-- snimky otocneho nahledu nejsou "fotky do galerie", ale jedna technicka
-- sada, ktera se vzdy vymenuje CELA najednou (viz batch/is_active nize) a
-- kterou cte jen widget na strance produktu (GET /api/shop/products/<id>/
-- turntable, viz api/turntable.py).
--
-- batch = id jedne render davky (adresar na disku:
--   webapp/content-files/turntable/<shop_product_id>/<batch>/<tier>/e<elev>/a<azim>.jpg).
-- Nova davka se nahrava po castech s is_active=0; az commit endpoint overi
-- vsech 360 souboru, prepne is_active na novou davku a starou (soubory i
-- radky) smaze - stara sada tak zustava na e-shopu funkcni az do okamziku,
-- kdy je nova kompletni (atomicka vymena, zadne "napul nahrane" stavy).
-- batch v ceste souboru = URL se nikdy nemeni pod rukama, muze mit dlouhou
-- cache (nginx location /content-files/turntable/ - viz AGENTS_LOG.md).
--
-- assembly_id: sablona (product_assemblies), ze ktere se renderovalo - jen
-- informativne (ON DELETE SET NULL), snimky patri PRODUKTU, ne sablone.
CREATE TABLE product_turntable_frames (
    id INT AUTO_INCREMENT PRIMARY KEY,
    shop_product_id INT NOT NULL,
    assembly_id INT NULL,
    batch VARCHAR(32) NOT NULL,
    elevation_deg SMALLINT NOT NULL,
    azimuth_deg SMALLINT NOT NULL,
    tier_px SMALLINT NOT NULL,
    filename VARCHAR(255) NOT NULL,
    width_px SMALLINT NOT NULL,
    height_px SMALLINT NOT NULL,
    bytes INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active TINYINT(1) NOT NULL DEFAULT 0,
    UNIQUE KEY uq_ptf_frame (shop_product_id, batch, elevation_deg, azimuth_deg, tier_px),
    INDEX idx_ptf_product_active (shop_product_id, is_active),
    CONSTRAINT fk_ptf_product FOREIGN KEY (shop_product_id) REFERENCES shop_products(id) ON DELETE CASCADE,
    CONSTRAINT fk_ptf_assembly FOREIGN KEY (assembly_id) REFERENCES product_assemblies(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
