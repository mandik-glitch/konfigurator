-- Zrcadleni produktovych sestav na Sdileny disk (Robert 2026-09-09:
-- "chci zrcadlit produktové sestavy, které nebudou nezařazené").
--
-- Stejny vzor jako custom_shapes.drive_file_id - jedna sestava = jeden
-- JSON soubor na disku, drzeny v sync pri zalozeni/prejmenovani/smazani.
-- ON DELETE SET NULL: smazani souboru na disku nesmi vzit sestavu s sebou.
ALTER TABLE product_assemblies
  ADD COLUMN drive_file_id INT DEFAULT NULL,
  ADD KEY idx_pa_drive_file (drive_file_id),
  ADD CONSTRAINT fk_pa_drive_file FOREIGN KEY (drive_file_id)
      REFERENCES shared_drive_files (id) ON DELETE SET NULL;
