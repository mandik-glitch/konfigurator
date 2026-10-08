-- Fotogalerie realizaci - bot2, 2026-07-25.
-- Robert: "udelej sekce fotogalerie, systemove at se pohodlne nahravaji
-- hromadne obrazky, at se jim z hlediska SEO davaji vhodne nazvy, cerpej
-- z fotogalerii logiman.cz rovnou tam nacucni ty obrazky"
--
-- category: 'vestavby_dodavek' | 'realizace_stolu' (viz api/gallery.py
-- GALLERY_CATEGORIES - drzeno jako VARCHAR bez FK/ENUM kvuli konzistenci
-- se zbytkem projektu, viz napr. shop_documents.document_type).
CREATE TABLE IF NOT EXISTS shop_gallery_images (
  id INT AUTO_INCREMENT PRIMARY KEY,
  category VARCHAR(30) NOT NULL,
  filename VARCHAR(255) NOT NULL,
  alt_text VARCHAR(300),
  title VARCHAR(300),
  sort_order INT NOT NULL DEFAULT 0,
  source_url VARCHAR(500),
  active TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_category_filename (category, filename),
  KEY idx_category_active (category, active, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
