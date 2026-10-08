-- "Zakreslena pripominka" na strance produktu (bot14, 2026-09-02).
-- Robert (pres bot3/toscanaccio-0b): zakaznik si prohlizi obrazek
-- produktu/sestavy a chce do nej zakrouzkovat/dokreslit/skrtnout, co
-- chce jinak, pridat text a odeslat jako dotaz. Kreslici modul
-- webapp/js/image-markup.js (bot5) produkuje composite JPEG/PNG +
-- strukturovana marks_json data, tenhle radek je zaznam jedne takove
-- pripominky - vede vedle sebe jak surova data pro pripadnou pozdejsi
-- editaci (marks_json), tak hotovy obrazek pro rychly prehled v adminu
-- (composite_filename).
CREATE TABLE product_markups (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    gallery_item_id INT NULL,
    image_url VARCHAR(500) NOT NULL,
    view_json JSON NULL,
    marks_json LONGTEXT NOT NULL,
    composite_filename VARCHAR(255) NOT NULL,
    note TEXT NOT NULL,
    contact_email VARCHAR(255) NOT NULL,
    contact_phone VARCHAR(50) NULL,
    lead_id INT NULL,
    status ENUM('new', 'in_progress', 'done') NOT NULL DEFAULT 'new',
    client_ip VARCHAR(64) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_product_markups_product FOREIGN KEY (product_id) REFERENCES shop_products(id) ON DELETE CASCADE,
    CONSTRAINT fk_product_markups_lead FOREIGN KEY (lead_id) REFERENCES crm_leads(id) ON DELETE SET NULL,
    INDEX idx_product_markups_product (product_id),
    INDEX idx_product_markups_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
