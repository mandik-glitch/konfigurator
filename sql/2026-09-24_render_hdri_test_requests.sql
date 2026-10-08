-- Fronta jednorazovych testovacich renderu HDRI map (bot3/Robert,
-- 2026-09-24, po incidentu s primym zapisem do app_settings.render_hdri_*
-- - viz WORKFLOW.md pravidlo 50). Admin klikne "otestovat render" u
-- KTEREHOKOLI .hdr/.exr souboru na Sdilenem disku -> zaradi se JEDEN
-- rychly nahled (--test, jednosnimkovy rezim) na testovaci Vandr karte
-- s TOUHLE konkretni mapou jako PER-JOB override (--hdri) - `app_settings`
-- se vubec nedotyka, presne jak pravidlo 50 vyzaduje.
--
-- Backend endpoint (api/render_hdri.py) bezi jako www-data a NEMA pristup
-- k renderovacimu klici (/root/.konfigurator_render_klic je scvalne
-- root-only, pravidlo 31) - proto jen VLOZI radek sem, skutecne zarazeni
-- do fronty dela samostatny root-owned automat
-- (scripts/2026-09-24_render_hdri_test_dispatch.py), stejny princip jako
-- cela rodina *_auto_dispatch.py automatu.
CREATE TABLE render_hdri_test_requests (
  id INT AUTO_INCREMENT PRIMARY KEY,
  hdri_file_id INT NOT NULL,
  hdri_filename VARCHAR(255) NOT NULL,
  shop_product_id INT NOT NULL,
  status ENUM('pending','dispatched','done','error') NOT NULL DEFAULT 'pending',
  job_id VARCHAR(64) NULL,
  frame_url VARCHAR(500) NULL,
  error_text TEXT NULL,
  requested_by INT NULL,
  requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
