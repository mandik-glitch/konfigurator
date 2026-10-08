-- Vandr FBX fronta - druhy zdroj (bot5, 2026-09-22, navrh bot3, overeno
-- zive): Robert se ptal, jestli mechanismus umi stahovat FBX primo z
-- vandrawee adminu, misto rucniho stazeni+nahrani na Sdileny disk.
-- Overeno: /opt/konfigurator i /opt/vandrawee bezi jako STEJNY OS
-- uzivatel www-data na stejne VPS, takze nas skript muze cist
-- /opt/vandrawee/web/storage/app/exported_models/<uuid>/<uuid>.fbx
-- primo, jakmile `vandrawee_work.stored_models.fbx_exported_at`
-- neni NULL (Robert klikl na export v designeru).
--
-- shared_drive_file_id byl puvodne jediny idempotencni klic (1 radek =
-- 1 zpracovany soubor na Sdilenem disku) - ted uz existuje DRUHY zdroj
-- bez zadneho shared_drive_files radku, klic se proto presouva na
-- vandrawee_uuid (UNIQUE - 1 radek = 1 zpracovane UUID, bez ohledu na
-- to, kterou cestou bylo nalezeno). shared_drive_file_id zustava,
-- jen uz neni NOT NULL/jediny unique - vyplnuje se jen kdyz UUID prislo
-- z disk-skenu.
ALTER TABLE vandr_fbx_queue
  MODIFY shared_drive_file_id INT NULL,
  DROP FOREIGN KEY fk_vfq_file,
  ADD CONSTRAINT fk_vfq_file2 FOREIGN KEY (shared_drive_file_id) REFERENCES shared_drive_files(id) ON DELETE SET NULL,
  DROP INDEX uq_vfq_file,
  ADD UNIQUE KEY uq_vfq_uuid (vandrawee_uuid),
  ADD KEY idx_vfq_file (shared_drive_file_id);
