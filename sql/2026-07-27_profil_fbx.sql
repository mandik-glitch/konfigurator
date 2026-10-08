-- Podpora vazby FBX modelu na radek ceniku (cfg_dily) - bot1, 2026-07-27
-- Robert bude nahravat FBX soubory novych profilu pres admin (Ceny profilu),
-- potrebujeme si evidovat, ktery radek uz ma nahrany model a jaky puvodni
-- nazev souboru mel (pro jeho pozdejsi orientaci / pripadny GLB prevod).
ALTER TABLE cfg_dily
  ADD COLUMN fbx_original_name VARCHAR(255) NULL AFTER glb_file,
  ADD COLUMN fbx_uploaded_at DATETIME NULL AFTER fbx_original_name;
