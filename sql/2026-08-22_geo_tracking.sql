-- Robert pres bot3, 2026-08-22: geograficky tracking podle IP polohy
-- ("totez nasadit na vandrawee.cz" - stejny princip jako na
-- toscanacciu, adaptovany na konfigurator). Poloha se pocita JEDNOU
-- na serveru z lokalni GeoIP databaze (api/geoip.py), nikdy se
-- neuklada syrova IP - jen jeji HMAC hash (ip_hash), poprve zavedeny
-- vzor v tomhle repu (viz api/tracking.py::_ip_hash).

-- 1) page_views: obecny page-view tracking pro CELY verejny web
-- (index/category/product/blok/nabidka-online/poptavka-stul/
-- realizace/remeslo*.html) - dedup-agregacni vzor (UNIQUE (path,
-- ip_hash)), NE log kazde jednotlive navstevy.
CREATE TABLE page_views (
  id INT NOT NULL AUTO_INCREMENT,
  path VARCHAR(255) NOT NULL,
  page_type VARCHAR(30) NOT NULL,
  ip_hash CHAR(64) NOT NULL,
  country VARCHAR(2) NULL,
  region VARCHAR(100) NULL,
  city VARCHAR(100) NULL,
  view_count INT NOT NULL DEFAULT 1,
  first_viewed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_viewed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_page_view (path, ip_hash),
  KEY idx_page_views_page_type (page_type),
  KEY idx_page_views_country (country)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2) product_views: geo-breakdown NAVIC k existujicimu produktu -
-- "odkud se divaji na TENHLE produkt" (analogie recipe_views na
-- toscanacciu). Zadna existujici tabulka pro tohle v konfiguratoru
-- nebyla (scene_offer_views je jiny, starsi ucel - viz komentar
-- v api/tracking.py).
CREATE TABLE product_views (
  product_id INT NOT NULL,
  ip_hash CHAR(64) NOT NULL,
  country VARCHAR(2) NULL,
  region VARCHAR(100) NULL,
  city VARCHAR(100) NULL,
  view_count INT NOT NULL DEFAULT 1,
  first_viewed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_viewed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (product_id, ip_hash),
  CONSTRAINT fk_pv_product FOREIGN KEY (product_id) REFERENCES shop_products(id) ON DELETE CASCADE,
  KEY idx_product_views_country (country)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3) category_views: totez pro kategorie.
CREATE TABLE category_views (
  category_id INT NOT NULL,
  ip_hash CHAR(64) NOT NULL,
  country VARCHAR(2) NULL,
  region VARCHAR(100) NULL,
  city VARCHAR(100) NULL,
  view_count INT NOT NULL DEFAULT 1,
  first_viewed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_viewed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (category_id, ip_hash),
  CONSTRAINT fk_cv_category FOREIGN KEY (category_id) REFERENCES content_categories(id) ON DELETE CASCADE,
  KEY idx_category_views_country (country)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
