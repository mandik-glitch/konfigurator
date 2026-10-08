-- Geo prehled: casovy filtr + mesto + zarizeni + straveny cas (bot9,
-- 2026-08-22, navazuje na sql/2026-08-22_geo_tracking.sql - vlastni
-- puvodni migrace). Adaptace vzoru, ktery bot10 postavil na
-- /opt/toscanaccio (commit 990b0db) - stejna architektura, jen
-- produkty/kategorie misto receptu/mapovych vrstev.
--
-- Robert pres bot3: "totez na obou projektech?" -> ano.
--
-- Architektonicky problem (stejny jako na toscanacciu): stavajici
-- tabulky drzi JEDEN RADEK NA UNIKATNIHO NAVSTEVNIKA (UNIQUE KEY
-- entity+ip_hash) s kumulativnim view_count/first_viewed_at/
-- last_viewed_at - "kolik zobrazeni bylo za poslednich N dni" se z
-- toho presne nespocita. Reseni: nove DENNI tabulky vedle stavajicich
-- (vzor poll_views - proste denni pocty, ZADNY per-navstevnik dedup
-- uvnitr dne), navysovane SOUCASNE se stavajicimi zapisy. Stavajici
-- tabulky/endpoint zustavaji beze zmeny pro vychozi "celkem" pohled -
-- jen doplneny o device_type/dwell.
--
-- DULEZITE: country/city/device_type v DENNICH tabulkach jsou NOT NULL
-- DEFAULT '' (ne NULL) - MySQL UNIQUE KEY povazuje kazdy NULL za
-- odlisny od jineho NULL, takze by se s NULL hodnotami misto agregace
-- zakladaly porad nove radky.

-- 1) page_views: device_type (chybelo uplne) + total_dwell_ms (dwell
-- site-wide vubec neexistoval).
ALTER TABLE page_views
  ADD COLUMN device_type VARCHAR(10) NULL AFTER city,
  ADD COLUMN total_dwell_ms BIGINT NOT NULL DEFAULT 0 AFTER device_type;

-- 2) product_views / category_views: jen device_type. Dwell VEDOME
-- VYNECHAN - page_views.path obsahuje "?id=", takze dwell na
-- /product.html?id=X uz je FAKTICKY per-produktovy rozpad, i bez
-- zvlastniho sloupce tady (viz TASKS.md pro cely duvod).
ALTER TABLE product_views
  ADD COLUMN device_type VARCHAR(10) NULL AFTER city;

ALTER TABLE category_views
  ADD COLUMN device_type VARCHAR(10) NULL AFTER city;

-- 3) Denni bucket tabulky - jedna radka = jeden (den, dimenze) soucet,
-- zadny per-navstevnik dedup (opakovana navsteva stejneho cloveka ve
-- stejny den se PROSTE PRICTE - presny pocet "zobrazeni za den" ma
-- zahrnovat i opakovane navstevy).

CREATE TABLE page_views_daily (
  id INT NOT NULL AUTO_INCREMENT,
  path VARCHAR(255) NOT NULL,
  page_type VARCHAR(30) NOT NULL,
  den DATE NOT NULL,
  country VARCHAR(2) NOT NULL DEFAULT '',
  city VARCHAR(100) NOT NULL DEFAULT '',
  device_type VARCHAR(10) NOT NULL DEFAULT '',
  view_count INT NOT NULL DEFAULT 0,
  dwell_ms_total BIGINT NOT NULL DEFAULT 0,
  dwell_count INT NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uq_page_views_daily (path, den, country, city, device_type),
  KEY idx_pvd_page_type_den (page_type, den),
  KEY idx_pvd_den (den)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE product_views_daily (
  id INT NOT NULL AUTO_INCREMENT,
  product_id INT NOT NULL,
  den DATE NOT NULL,
  country VARCHAR(2) NOT NULL DEFAULT '',
  city VARCHAR(100) NOT NULL DEFAULT '',
  device_type VARCHAR(10) NOT NULL DEFAULT '',
  view_count INT NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uq_product_views_daily (product_id, den, country, city, device_type),
  KEY idx_pvd2_den (den),
  CONSTRAINT fk_pvd_product FOREIGN KEY (product_id) REFERENCES shop_products(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE category_views_daily (
  id INT NOT NULL AUTO_INCREMENT,
  category_id INT NOT NULL,
  den DATE NOT NULL,
  country VARCHAR(2) NOT NULL DEFAULT '',
  city VARCHAR(100) NOT NULL DEFAULT '',
  device_type VARCHAR(10) NOT NULL DEFAULT '',
  view_count INT NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uq_category_views_daily (category_id, den, country, city, device_type),
  KEY idx_cvd_den (den),
  CONSTRAINT fk_cvd_category FOREIGN KEY (category_id) REFERENCES content_categories(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
