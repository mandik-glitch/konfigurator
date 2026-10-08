-- 3D model (view_3d_model) online nabidky zrcadleny na Sdileny disk
-- (Robert pres bot3, 2026-09-14: "geometrie sestav z online nabidek
-- potrebuje jit na Sdileny disk s vazbou na nabidku, aby prezila i
-- archivaci nabidky") - stejny vzor jako drive_file_id (PDF, viz
-- 2026-08-04_scene_offer_online.sql), ale NAROZDIL od nej (viz
-- admin_scene_offers_bulk_delete v api/scene_offers.py) se soubor na
-- Sdilenem disku PRI SMAZANI NABIDKY NEMAZE - na rozdil od PDF/
-- renderu neni GLB export bez puvodni zive sceny rekonstruovatelny,
-- takze zustava trvale dohledatelny ve slozce "Modely nabidek/<cislo
-- nabidky>" i po zaniku nabidky samotne.
ALTER TABLE scene_offers
  ADD COLUMN drive_model_file_id INT NULL,
  ADD CONSTRAINT fk_scene_offers_drive_model_file
    FOREIGN KEY (drive_model_file_id) REFERENCES shared_drive_files(id) ON DELETE SET NULL;
