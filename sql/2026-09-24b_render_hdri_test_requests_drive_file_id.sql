-- Robert, 2026-09-24, duraznze: "chci to prece pristupne na disku!!!
-- jako vsechno ostatni" - testovaci HDRI rendery se navic (NE MISTO)
-- kopiruji do Sdileneho disku (Rendering / HDRi / testy), aby si je
-- Robert mohl normalne prochazet vedle sebe jako cokoli jineho na
-- disku. Tenhle sloupec drzi id vysledneho radku v shared_drive_files,
-- at na nej jde v odpovedi endpointu odkazat primo.
ALTER TABLE render_hdri_test_requests
  ADD COLUMN drive_file_id INT NULL;
