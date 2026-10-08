-- Zrcadleni Vlastnich tvaru do Sdileneho disku (Robert 2026-08-06:
-- "nech strom z tvaru ve scene zije zaroven ve sdilenym diskem" ->
-- upresneno: "kategorie tvaru = automaticky i slozka na disku").
-- Kazda custom_shape_categories kategorie ma parovou slozku v
-- shared_drive_folders (stejna hierarchie, stejny nazev) - umoznuje k
-- ni pripojit referencni soubory/fotky primo pres bezne rozhrani
-- Sdileneho disku. Jednosmerny sync (kategorie tvaru -> slozka disku,
-- ne obracene) - viz api/app.py.
ALTER TABLE custom_shape_categories
  ADD COLUMN drive_folder_id INT NULL,
  ADD CONSTRAINT fk_csc_drive_folder FOREIGN KEY (drive_folder_id) REFERENCES shared_drive_folders(id) ON DELETE SET NULL;
